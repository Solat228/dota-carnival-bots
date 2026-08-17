# -*- coding: utf-8 -*-
"""Бот мини-игры «Атака автоматонов» (Dota 2 / Dark Carnival).

Что делает: находит панель мини-игры, читает у текущей цели ОСТАТОК слова
(жёлтая буква + белые) и печатает его. Серые (уже набранные) буквы в маску не
попадают, поэтому повторов нет.

Запуск:
    python main.py            — работа (F10 старт/стоп, F12 выход)
    python main.py --dry      — то же, но БЕЗ нажатий: только печать в консоль
    python main.py --once     — один разбор текущего экрана и выход
    python main.py --start    — начать сразу, не дожидаясь F10
"""

import argparse
import os
import sys
import time

import cv2

import capture
import config
import ocr
import panel as panelmod
import sendkeys
import wordfind
import words

HERE = os.path.dirname(os.path.abspath(__file__))


class Bot:
    def __init__(self, cfg, dry=False):
        self.cfg = cfg
        self.dry = dry
        self.voc = words.Vocabulary()
        self.tracker = words.WordTracker(
            self.voc,
            min_ratio=float(self.cfg.get('dict_min_ratio', 0.80)),
            snap_ratio=float(self.cfg.get('snap_min_ratio', 0.62)))
        self.region = None          #[x, y, w, h] панели мини-игры на экране
        self.zones = []             #зоны HUD внутри панели
        self.hwnd = 0
        self.last_typed = ''        #что напечатали последним
        self.last_typed_at = 0.0
        self.stat_words = 0
        self.stat_chars = 0
        self.stat_fixed = 0
        self.times = []
        self.no_hud_since = 0.0     #когда последний раз видели HUD мини-игры
        self.stall = 0              #сколько раз подряд слово не менялось после ввода

    # --- подготовка ---------------------------------------------------------
    def setup(self):
        exe = ocr.setup(self.cfg.get('tesseract', ''))
        print(f'[bot] tesseract: {exe}')
        self.hwnd, title = capture.find_window(self.cfg.get('window_title', 'Dota 2'))
        print(f'[bot] окно игры: {title or "НЕ НАЙДЕНО"}')
        if self.hwnd and self.cfg.get('force_en_layout', True):
            sendkeys.force_en_layout(self.hwnd)
        return self.find_panel()

    def find_panel(self):
        """Ищет панель мини-игры (или берёт region из конфига)."""
        fixed = self.cfg.get('region')
        if fixed:
            self.region = list(fixed)
        else:
            full = capture.grab_region(None)
            if full is None:
                print('[bot] не смог снять экран')
                return False
            found = panelmod.detect_panel(full)
            if not found:
                print('[bot] панель мини-игры не найдена — открой мини-игру и нажми F10')
                self.region = None
                self.zones = []
                return False
            self.region = list(found)
        self.zones = panelmod.hud_zones(self.region)
        print(f'[bot] область игры: {self.region}')
        return True

    # --- разбор кадра -------------------------------------------------------
    def read_frame(self, img):
        """Кадр панели -> (что печатать, источник, уверенность, bbox)."""
        box, letters = wordfind.find_progress_line(img, zones=self.zones)
        if box is not None:
            #Слово «зависло» (напечатали, а остаток не изменился) — значит остаток
            #прочитан неверно. Берём зелёную надпись и печатаем слово ЦЕЛИКОМ:
            #лишние буквы игра игнорирует, зато слово точно закроется.
            if self.stall >= self.cfg.get('stall_limit', 2):
                lbox, gmask = wordfind.find_label_above(img, box)
                if lbox is not None:
                    raw = ocr.read_text(wordfind.prepare_for_ocr(
                        wordfind.crop_mask(gmask, lbox), self.cfg.get('ocr_upscale', 3.0)))
                    text, conf = self.polish(raw)
                    if text:
                        self.voc.observe_full_word(text)
                        self.tracker.note_label(text)
                        return text, 'полное слово', conf, lbox, raw
            raw = ocr.read_text(wordfind.prepare_for_ocr(
                wordfind.crop_mask(letters, box), self.cfg.get('ocr_upscale', 3.0)))
            if not self.cfg.get('dict_correct', True):
                return words.normalize(raw), 'progress', 0.0, box, raw
            text, conf, note = self.tracker.feed(raw)
            if text != words.normalize(raw):
                self.stat_fixed += 1
            return text, ('progress ' + note).strip(), conf, box, raw
        boxes, gmask = wordfind.find_label_lines(img, zones=self.zones)
        if boxes:
            box = boxes[0]
            raw = ocr.read_text(wordfind.prepare_for_ocr(
                wordfind.crop_mask(gmask, box), self.cfg.get('ocr_upscale', 3.0)))
            text, conf = self.polish(raw)
            if text:
                self.voc.observe_full_word(text)
                self.tracker.note_label(text)
            return text, 'label', conf, box, raw
        return '', 'none', 0.0, None, ''

    def polish(self, raw):
        """Чинит СЛОВО ЦЕЛИКОМ по словарю (для зелёных надписей)."""
        text = words.normalize(raw)
        if len(text) < self.cfg.get('min_word_len', 3):
            #одна-две буквы бывают в конце слова — их не чиним, но и не отбрасываем
            return text, (1.0 if text else 0.0)
        if not self.cfg.get('dict_correct', True):
            return text, 0.0
        fixed, conf = self.voc.fix_full(text, self.cfg.get('dict_min_ratio', 0.80))
        if fixed != text:
            self.stat_fixed += 1
        return fixed, conf

    # --- ввод ---------------------------------------------------------------
    def should_type(self, text):
        """Нужно ли печатать: новое слово или прошлое «застряло»."""
        if not text:
            return False
        if text != self.last_typed:
            self.stall = 0
            return True
        if (time.time() - self.last_typed_at) > self.cfg.get('retype_after_sec', 0.8):
            self.stall += 1
            return True
        return False

    def type_word(self, text, source, conf, raw):
        marks = '' if conf >= 1.0 else (f' (чинил из {raw!r})' if raw != text else ' (?)')
        if self.dry:
            print(f'[dry] {source}: {text}{marks}')
        else:
            sendkeys.type_text(text, self.cfg.get('key_delay_ms', 6))
            print(f'[бот] {source}: {text}{marks}')
        self.last_typed = text
        self.last_typed_at = time.time()
        if source == 'полное слово':
            self.stall = 0          #страховка сработала — счётчик обнуляем
        self.stat_words += 1
        self.stat_chars += len(text)
        delay = self.cfg.get('post_word_delay_ms', 30) / 1000.0
        if delay > 0:
            time.sleep(delay)

    # --- главный цикл -------------------------------------------------------
    def game_focused(self):
        want = (self.cfg.get('window_title', 'Dota 2') or '').lower()
        return want in capture.foreground_title().lower()

    def tick(self):
        """Один проход: снять кадр, прочитать, напечатать. True — что-то сделал."""
        img = capture.grab_region(self.region)
        if img is None:
            return False
        #Мини-игру могли закрыть, а бот ещё активен — тогда жать клавиши нельзя
        if self.cfg.get('require_hud', True) and not panelmod.hud_present(img, self.zones):
            now = time.time()
            if now - self.no_hud_since > 5.0:
                self.no_hud_since = now
                print('[bot] мини-игра не видна — жду (панель ищу заново)')
                self.find_panel()
            return False
        self.no_hud_since = time.time()

        t0 = time.time()
        text, source, conf, _box, raw = self.read_frame(img)
        self.times.append((time.time() - t0) * 1000)
        if len(self.times) > 200:
            self.times = self.times[-200:]
        if source == 'label':
            #Зелёная надпись — запасной путь; печатаем ТОЛЬКО известные слова,
            #иначе можно вбить мусор из интерфейса доты
            if not self.cfg.get('type_labels', True) or conf < 0.9:
                return False
        if self.should_type(text):
            self.type_word(text, source, conf, raw)
            return True
        return False

    def run(self, active=False):
        period = 1.0 / max(1.0, float(self.cfg.get('loop_fps', 25)))
        toggle = int(self.cfg.get('hotkey_toggle', 0x79))
        quit_key = int(self.cfg.get('hotkey_quit', 0x7B))
        keys = sendkeys.Hotkeys()
        started = time.time()
        print(f'[bot] готов. {sendkeys.key_name(toggle)} — старт/стоп '
              f'(сейчас {"РАБОТАЕТ" if active else "стоп"}), '
              f'{sendkeys.key_name(quit_key)} — выход'
              f'{" (СУХОЙ РЕЖИМ: без нажатий)" if self.dry else ""}')
        while True:
            t0 = time.time()
            if keys.pressed(toggle):
                active = not active
                print(f'[bot] {"ПОЕХАЛИ" if active else "пауза"}')
                if active:
                    self.find_panel()
                    self.tracker.reset()
                    if self.hwnd and self.cfg.get('force_en_layout', True):
                        sendkeys.force_en_layout(self.hwnd)
            if keys.pressed(quit_key):
                print('[bot] выход')
                break

            if active and self.region and (self.dry or self.game_focused()):
                try:
                    self.tick()
                except Exception as err:
                    print(f'[bot] сбой тика: {err}')
            time.sleep(max(0.0, period - (time.time() - t0)))

        avg = sum(self.times) / len(self.times) if self.times else 0
        print(f'[bot] итог: слов {self.stat_words}, букв {self.stat_chars}, '
              f'починок {self.stat_fixed}, разбор {avg:.0f} мс, '
              f'время {time.time() - started:.0f} с')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='ничего не нажимать, только печатать')
    ap.add_argument('--once', action='store_true', help='один разбор экрана и выход')
    ap.add_argument('--start', action='store_true', help='начать сразу, без F10')
    ap.add_argument('--save', default='', help='сохранить кадр разбора в файл (с --once)')
    ap.add_argument('--region', default='', help='область игры вручную: x,y,w,h')
    args = ap.parse_args(argv)

    cfg = config.load()
    if args.region:
        try:
            cfg['region'] = [int(v) for v in args.region.split(',')]
        except ValueError:
            print('[bot] --region ожидает x,y,w,h')
            return 1
    bot = Bot(cfg, dry=args.dry)
    ok = bot.setup()

    if args.once:
        if not ok:
            return 1
        img = capture.grab_region(bot.region)
        text, source, conf, box, raw = bot.read_frame(img)
        print(f'источник={source} raw={raw!r} -> {text!r} уверенность={conf:.2f} box={box}')
        if args.save and img is not None:
            if box is not None:
                x, y, w, h = box[:4]
                cv2.rectangle(img, (x - 3, y - 3), (x + w + 3, y + h + 3), (0, 0, 255), 2)
            cv2.imwrite(args.save, img)
            print(f'кадр сохранён: {args.save}')
        return 0

    bot.run(active=args.start)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
