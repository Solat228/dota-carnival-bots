# -*- coding: utf-8 -*-
"""Бот мини-игры «Сапожный снос» (арканоид) в Dota 2.

    python boot.py --dry      — ничего не нажимает, только показывает решения
    python boot.py            — игра; F10 старт/стоп, F12 выход
    python boot.py --once     — один разбор кадра (отладка)

ВАЖНО (выяснено живым прогоном 2026-08-17): мини-игра не получает клавиши,
пока по её панели не кликнули мышью — Panorama до этого не отдаёт панели
клавиатурный фокус. Поэтому бот при старте кликает в пустое место поля.
"""

import argparse
import os
import threading
import time

import cv2

import capture
import config
import panel as panelmod
import sendkeys
from arkanoid import hud, play, vision

VK_A, VK_D, VK_SPACE, VK_F9 = 0x41, 0x44, 0x20, 0x78

DEFAULTS = {
    #Кадры приходят из фонового потока каждые ~17 мс (60 Гц монитора), а
    #разбор занимает ~7 мс. Опрашиваем чаще, чем приходят кадры, иначе цикл
    #их проспит: с 45 Гц бот терял каждый третий кадр.
    'loop_fps': 120,
    'paddle_speed': 200.0,      # замер: 182 px за 0.9 с
    'dead_zone': 10.0,
    'aim_offset': 0.0,
    'focus_click': [0.5, 0.72],  # доля поля: пустое место под блоками
    'hotkey_toggle': 0x79,
    'hotkey_quit': 0x7B,
}


class FrameSource(threading.Thread):
    """Снимает кадры в фоне.

    Замер: BitBlt с экрана стоит 16.7 мс независимо от размера области — это
    ожидание кадра монитора (60 Гц), а не копирование пикселей. Ждать его в
    главном цикле — значит дарить это время впустую; в фоне оно совмещается
    с разбором кадра.
    """

    daemon = True

    def __init__(self, region=None):
        super().__init__(daemon=True)
        self._lock = threading.Lock()
        self._region = list(region) if region else None
        self._frame = None
        self._stamp = 0.0
        #ВАЖНО: не звать поле `_stop` — так называется внутренний метод
        #threading.Thread, и `join()` падает с «Event object is not callable».
        self._stopping = threading.Event()
        self._grabber = capture.Grabber()

    def set_region(self, region):
        with self._lock:
            self._region = list(region) if region else None
            self._frame = None

    def latest(self):
        """(кадр, время съёмки) — последний снятый кадр."""
        with self._lock:
            return self._frame, self._stamp

    def stop(self):
        self._stopping.set()

    def run(self):
        while not self._stopping.is_set():
            with self._lock:
                region = list(self._region) if self._region else None
            if not region:
                time.sleep(0.05)
                continue
            img = self._grabber.grab(*[int(v) for v in region])
            if img is None:
                time.sleep(0.05)
                continue
            with self._lock:
                self._frame = img
                self._stamp = time.time()
        self._grabber.close()


class HudWorker(threading.Thread):
    """OCR уровня и счёта в фоне.

    Один проход Tesseract по двум полоскам HUD стоит ~340 мс: в главном цикле
    бот на треть секунды слепнет и пропускает мяч. Здесь он просто отдаёт
    копию кадра и забирает результат, когда тот готов.
    """

    daemon = True

    def __init__(self, period=1.5):
        super().__init__(daemon=True)
        self.period = float(period)
        self._lock = threading.Lock()
        self._pending = None
        self._status = (None, None)
        #ВАЖНО: не звать поле `_stop` — так называется внутренний метод
        #threading.Thread, и `join()` падает с «Event object is not callable».
        self._stopping = threading.Event()

    def submit(self, panel_bgr):
        with self._lock:
            if self._pending is None:
                self._pending = panel_bgr.copy()

    def status(self):
        with self._lock:
            return self._status

    def stop(self):
        self._stopping.set()

    def run(self):
        while not self._stopping.is_set():
            with self._lock:
                job, self._pending = self._pending, None
            if job is None:
                time.sleep(0.05)
                continue
            try:
                got = hud.read_status(job)
            except Exception:
                got = (None, None)
            with self._lock:
                self._status = got
            time.sleep(self.period)


class Mouse:
    """Клик по координатам панели (для кнопок меню и фокуса)."""

    def __init__(self, origin=(0, 0), dry=False):
        self.origin = origin
        self.dry = dry

    def click(self, x, y):
        import ctypes
        sx, sy = int(self.origin[0] + x), int(self.origin[1] + y)
        if self.dry:
            print(f'[dry] клик ({sx}, {sy})')
            return
        user32 = ctypes.windll.user32
        user32.SetCursorPos(sx, sy)
        time.sleep(0.03)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)


class Keys:
    """Удержание A/D и короткие нажатия. Держим клавишу, а не долбим её."""

    def __init__(self, dry=False):
        self.dry = dry
        self.held = 0               # -1 A, +1 D, 0 ничего

    def hold(self, direction):
        if direction == self.held:
            return
        for vk, want in ((VK_A, -1), (VK_D, 1)):
            scan = sendkeys.scan_for_vk(vk)
            if self.held == want and direction != want:
                if not self.dry:
                    sendkeys.send_scan(scan, up=True)
            if direction == want and self.held != want:
                if not self.dry:
                    sendkeys.send_scan(scan, up=False)
        self.held = direction

    def tap(self, vk, hold=0.05):
        if self.dry:
            return
        scan = sendkeys.scan_for_vk(vk)
        sendkeys.send_scan(scan, up=False)
        time.sleep(hold)
        sendkeys.send_scan(scan, up=True)

    def release_all(self):
        self.hold(0)


class Bot:
    def __init__(self, cfg, dry=False):
        self.cfg = cfg
        self.dry = dry
        self.region = None
        self.field = None
        self.keys = Keys(dry)
        self.mouse = Mouse((0, 0), dry)
        self.brain = play.Brain(paddle_speed=cfg.get('paddle_speed', 200.0),
                                dead_zone=cfg.get('dead_zone', 10.0),
                                aim_offset=cfg.get('aim_offset', 0.0))
        #Запасные точки кликов (доли панели) — замерены живыми кликами:
        #«Играть» экрана правил и «Сыграть ещё» экрана конца игры.
        self.fallback_frac = {'play': tuple(cfg.get('play_click', [0.49, 0.87])),
                              'again': tuple(cfg.get('again_click', [0.49, 0.79]))}
        self.prev_panel = None
        self.prev_ball = None
        self.frames = FrameSource()
        self.hud_worker = HudWorker(period=cfg.get('hud_period', 1.5))
        self.last_stamp = 0.0
        self.templates = self._load_templates()
        self.best_level = 0
        self.best_score = 0
        self.last_hud = 0.0
        self.last_panel_try = 0.0
        self.last_field = 0.0
        self.last_hint_check = 0.0
        self.last_hint = False
        self.last_bricks = 0.0
        self.brick_x = None
        self.hwnd = 0
        self.last_no_panel = 0.0
        self.no_panel_tries = 0
        self.misses = 0
        self.ball_areas = []
        self.last_ball_seen_pos = None
        self.last_ball_time = 0.0
        self.seen_ball = 0          # кадров с найденным мячом
        self.seen_frames = 0        # кадров в игре (для процента видимости)
        self.dim_since = 0.0
        self.times = []

    # --- подготовка ---------------------------------------------------------
    def _load_templates(self):
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'arkanoid', 'templates')
        out = {}
        for key, name in (('play', 'play_button.png'), ('again', 'again_button.png'),
                          ('hint', 'space_hint.png')):
            img = cv2.imread(os.path.join(here, name))
            if img is not None:
                out[key] = img
        return out

    def find_panel(self):
        full = capture.grab_region(None)
        if full is None:
            print('[бот] не смог снять экран')
            return False
        found = panelmod.detect_panel(full)
        if not found:
            #Сообщение раз в 10 с: спам заполнял консоль, а она ещё и лежала
            #поверх игры — бот сам себе закрывал панель.
            if (time.time() - self.last_no_panel) > 10.0:
                self.last_no_panel = time.time()
                print('[бот] панель мини-игры не найдена — открой «Сапожный снос»')
            self.no_panel_tries += 1
            if self.no_panel_tries % 3 == 0:
                self.ensure_foreground()        #дота могла уйти за другое окно
            self.region = None
            return False
        self.no_panel_tries = 0
        self.region = list(found)
        place_console(self.region)          #консоль не должна закрывать панель
        self.mouse.origin = (self.region[0], self.region[1])
        self.frames.set_region(self.region)
        if not self.frames.is_alive():
            self.frames.start()
        if not self.hud_worker.is_alive():
            self.hud_worker.start()
        img = None
        for _ in range(40):                 #дождёмся первого кадра из потока
            img = self._grab()
            if img is not None:
                break
            time.sleep(0.02)
        self.field = vision.field_bounds(img) if img is not None else None
        pw, ph = self.region[2], self.region[3]
        self.brain.fallbacks = {key: (pw * fx, ph * fy)
                                for key, (fx, fy) in self.fallback_frac.items()}
        print(f'[бот] панель {self.region}, поле {self.field}')
        return True

    def _grab(self):
        """Свежий кадр панели: из фонового потока, если он запущен."""
        if self.frames.is_alive():
            img, stamp = self.frames.latest()
            if img is not None and stamp > self.last_stamp:
                self.last_stamp = stamp
                return img
            return None                     #нового кадра ещё нет — не считаем дважды
        return capture.grab_region(self.region) if self.region else None

    def ensure_foreground(self):
        """Поднимает окно доты, если оно ушло из фокуса.

        Мини-игра САМА встаёт на паузу, когда дота теряет фокус (замечено при
        работе без человека). Клавиши в этот момент до неё не доходят, поэтому
        сначала окно, потом клик по полю — и только затем F9.
        """
        title = self.cfg.get('window_title', 'Dota 2')
        if title.lower() in capture.foreground_title().lower():
            return False
        if not self.hwnd:
            self.hwnd, _t = capture.find_window(title)
        if not self.hwnd:
            return False
        try:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(self.hwnd)
            time.sleep(0.2)
        except Exception:
            pass
        print('[бот] окно доты потеряло фокус — поднимаю')
        #Кликать вслепую НЕЛЬЗЯ: пока панель не найдена, поверх игры может
        #висеть диалог доты (ловил приглашение в группу — точка фокуса легла
        #ровно между «Принять» и «Отклонить»). Клик только по видимой панели.
        if self.region and self.field:
            self.focus_click()
        return True

    def focus_click(self):
        """Клик в пустое место поля: без него игра не слышит клавиши."""
        if not self.field:
            return
        left, top, right, bottom = self.field
        fx, fy = self.cfg.get('focus_click', [0.5, 0.72])
        x = left + (right - left) * float(fx)
        y = top + (bottom - top) * float(fy)
        print(f'[бот] клик по полю для фокуса ({x:.0f}, {y:.0f})')
        self.mouse.click(x, y)
        time.sleep(0.15)

    # --- один кадр ----------------------------------------------------------
    def tick(self, t):
        img = self._grab()
        if img is None:
            return None
        #Границы поля НЕЛЬЗЯ считать один раз: на экране правил синяя маска
        #даёт другую рамку, и с ней полоса поиска не достаёт до тележки
        #(живой прогон: поле 153..851 вместо 171..950, платформа «застыла»).
        if self.field is None or (t - self.last_field) > 1.0:
            self.last_field = t
            got = vision.field_bounds(img)
            if got:
                self.field = got
        state = vision.screen_state(img, self.field)
        paddle = vision.find_paddle(img, self.field) if state == 'play' else None
        ball = None
        hint = False
        if state == 'play':
            #Подсказку ищем, только когда мяч не в полёте: 2.5 мс на кадр
            #впустую, пока трек живой.
            if not self.brain.tracker.ready() or (t - self.last_hint_check) > 0.5:
                self.last_hint_check = t
                hint = vision.find_hint(img, self.templates.get('hint'),
                                        self.field) is not None
                self.last_hint = hint
            else:
                hint = False
            if (t - self.last_bricks) > 0.5:
                self.last_bricks = t
                spot = vision.brick_centroid(img, self.field)
                self.brick_x = None if spot is None else spot[0]
            ball = vision.find_ball(self.prev_panel, img, self.field,
                                    paddle[2] if paddle else None,
                                    self.brain.expected_ball(t))
            self.prev_ball = ball or self.prev_ball
            if not hint:
                self.seen_frames += 1
                self.seen_ball += 1 if ball else 0
            self._note_miss(ball, paddle, hint, t)
            if ball:
                self.ball_areas.append(vision.LAST_BALL_AREA)
                if len(self.ball_areas) > 400:
                    self.ball_areas = self.ball_areas[-400:]
        if state == 'dim':
            #Затемнение держится дольше секунды — возможно, дота вообще не в
            #фокусе и F9 до неё не долетит.
            if not self.dim_since:
                self.dim_since = t
            elif (t - self.dim_since) > 1.0:
                self.dim_since = t
                self.ensure_foreground()
        else:
            self.dim_since = 0.0
        buttons = {}
        if state != 'play':
            for key, tpl in self.templates.items():
                got = vision.find_button(img, tpl)
                if got:
                    buttons[key] = got
        act = self.brain.step(t, state, self.field, paddle, ball, buttons, hint,
                              self.brick_x)
        self.apply(act)
        self.prev_panel = img
        if t - self.last_hud > 1.0:
            self.last_hud = t
            self._read_hud(img, state, act, paddle, ball)
        return act

    def _note_miss(self, ball, paddle, hint, t):
        """Разбор НАСТОЯЩЕЙ потери мяча.

        Первая версия считала голом любое исчезновение мяча внизу — и почти
        все «промахи» оказались ложными: у самой платформы мяч сливается с
        тележкой и пропадает на кадр-другой, хотя отбит. Надёжный признак
        потери — игра снова просит бросок (появилась подсказка), а мяч перед
        этим летал.
        """
        if ball is not None:
            self.last_ball_seen_pos = ball
            self.last_ball_time = t
        if not hint:
            return
        if (t - self.last_ball_time) > 1.5 or not self.last_ball_seen_pos:
            return                              #мяча давно нет — уже отчитались
        last, self.last_ball_seen_pos = self.last_ball_seen_pos, None
        self.misses += 1
        if not paddle:
            print(f'[бот] ПОТЕРЯ #{self.misses}: мяч ушёл на x={last[0]:.0f}')
            return
        paddle_x, half, _top = paddle
        edge = 'внутри платформы' if abs(last[0] - paddle_x) <= half else \
               f'мимо на {abs(last[0] - paddle_x) - half:.0f} px'
        print(f'[бот] ПОТЕРЯ #{self.misses}: мяч x={last[0]:.0f}, '
              f'платформа {paddle_x:.0f}±{half:.0f} -> {edge}, '
              f'цель {self.brain.target if self.brain.target is None else round(self.brain.target)}')

    def _read_hud(self, img, state, act, paddle, ball):
        self.hud_worker.submit(img)
        level, score = self.hud_worker.status()
        if level:
            self.best_level = max(self.best_level, level)
        if score:
            self.best_score = max(self.best_score, score)
        pos = None if not paddle else round(paddle[0])
        bpos = None if not ball else (round(ball[0]), round(ball[1]))
        ms = (sum(self.times[-40:]) / max(1, len(self.times[-40:]))) if self.times else 0
        rate = 100.0 * self.seen_ball / self.seen_frames if self.seen_frames else 0
        #Строка короткая: консоль стоит в узкой боковой полосе, чтобы не
        #закрывать панель мини-игры.
        area = ''
        if self.ball_areas:
            srt = sorted(self.ball_areas)
            area = (f' пл{srt[len(srt) // 2]}/'
                    f'{srt[int(len(srt) * 0.9)]}')       #медиана/90-й перцентиль
        print(f'{state[:4]} ур{level} сч{score} мяч{"+" if bpos else "-"} '
              f'вид{rate:.0f}%{area} {ms:.0f}мс {act.note}')

    def apply(self, act):
        self.keys.hold(act.move)
        if act.space:
            self.keys.tap(VK_SPACE)
        if act.f9:
            self.keys.tap(VK_F9)
        if act.click:
            self.mouse.click(*act.click)
            time.sleep(0.2)
            self.focus_click()          #после кнопки фокус снова нужен полю

    # --- цикл ---------------------------------------------------------------
    def run(self, active=False):
        period = 1.0 / max(1.0, float(self.cfg.get('loop_fps', 45)))
        toggle = int(self.cfg.get('hotkey_toggle', 0x79))
        quit_key = int(self.cfg.get('hotkey_quit', 0x7B))
        keys = sendkeys.Hotkeys()
        print(f'[бот] готов. {sendkeys.key_name(toggle)} — старт/стоп '
              f'(сейчас {"РАБОТАЕТ" if active else "стоп"}), '
              f'{sendkeys.key_name(quit_key)} — выход'
              f'{" (СУХОЙ РЕЖИМ)" if self.dry else ""}')
        if active:
            self.focus_click()
        started = time.time()
        while True:
            t0 = time.time()
            if keys.pressed(toggle):
                active = not active
                print(f'[бот] {"ПОЕХАЛИ" if active else "пауза"}')
                if active:
                    self.find_panel()
                    self.focus_click()
                else:
                    self.keys.release_all()
            if keys.pressed(quit_key):
                print('[бот] выход')
                break
            #Панель могла не найтись (шёл переход экрана) — ждём и пробуем
            #снова, а не выходим: бот должен переживать смену экранов сам.
            if active and not self.region and (t0 - self.last_panel_try) > 2.0:
                self.last_panel_try = t0
                if self.find_panel():
                    self.focus_click()
            if active and self.region:
                try:
                    self.tick(time.time())
                except Exception as err:
                    print(f'[бот] сбой тика: {err}')
                    self.keys.release_all()
            self.times.append((time.time() - t0) * 1000)
            if len(self.times) > 400:
                self.times = self.times[-400:]
            time.sleep(max(0.0, period - (time.time() - t0)))
        self.keys.release_all()
        self.frames.stop()
        self.hud_worker.stop()
        avg = sum(self.times) / len(self.times) if self.times else 0
        print(f'[бот] итог: лучший уровень {self.best_level}, '
              f'счёт {self.best_score}, кадр {avg:.0f} мс, '
              f'время {time.time() - started:.0f} с')


def place_console(panel_rect=None, margin=45):
    """Убирает СВОЮ консоль с панели мини-игры и держит её поверх окон.

    Наступил на это лично: окно с логом легло ровно на панель, бот перестал её
    видеть и заполнил консоль сообщениями «панель не найдена».
    """
    import ctypes
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    #Типы обязательны: HWND — указатель. Передача -1 (HWND_TOPMOST) обычным
    #int'ом на 64 битах молча ломала вызов, и окно не двигалось.
    k32.GetConsoleWindow.restype = ctypes.c_void_p
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint]
    hwnd = k32.GetConsoleWindow()
    if not hwnd:
        return False
    try:
        k32.SetConsoleTitleW('БОТ АРКАНОИД')
    except Exception:
        pass
    screen_w = u32.GetSystemMetrics(0)
    screen_h = u32.GetSystemMetrics(1)
    if panel_rect:
        px, _py, pw, _ph = panel_rect
        left_room = px - margin
        right_room = screen_w - (px + pw) - margin
        if right_room >= left_room:
            x, w = px + pw + margin, max(320, right_room)
        else:
            x, w = 0, max(320, left_room)
    else:
        #Зазор обязателен: консоль вплотную к панели СЛИВАЕТСЯ с ней в одно
        #светлое пятно, и панель перестаёт находиться (проверено на себе —
        #бот ослеп на 18 px зазора).
        x, w = 0, max(300, min(400, screen_w // 5))
    ok = u32.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(-1),
                          int(x), 0, int(w), int(screen_h - 40), 0x0040)
    return bool(ok)


class Tee:
    """Печать одновременно в консоль и в файл (чтобы и видеть, и разбирать)."""

    def __init__(self, stream, path):
        self.stream = stream
        self.file = open(path, 'w', encoding='utf-8', buffering=1)

    def write(self, text):
        self.stream.write(text)
        try:
            self.file.write(text)
        except Exception:
            pass
        return len(text)

    def flush(self):
        self.stream.flush()
        try:
            self.file.flush()
        except Exception:
            pass


def load_cfg():
    cfg = dict(DEFAULTS)
    cfg.update(config.load().get('arkanoid', {}) if hasattr(config, 'load') else {})
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='ничего не нажимать')
    ap.add_argument('--once', action='store_true', help='один кадр и выход')
    ap.add_argument('--start', action='store_true', help='начать сразу')
    ap.add_argument('--log', default='', help='дублировать вывод в файл')
    args = ap.parse_args(argv)

    if args.log:
        import sys
        sys.stdout = Tee(sys.stdout, args.log)
    place_console()                         #сразу уводим консоль с центра экрана

    cfg = load_cfg()
    bot = Bot(cfg, dry=args.dry)
    #Версия кода в шапке лога: однажды тестировали ЗАВИСШИЙ старый процесс и
    #считали, что правки не помогли. По этой строке видно, какой код в логе.
    here = os.path.abspath(__file__)
    stamp = time.strftime('%d.%m %H:%M', time.localtime(os.path.getmtime(here)))
    print(f'[бот] код от {stamp}, pid {os.getpid()}')
    hwnd, title = capture.find_window('Dota 2')
    print(f'[бот] окно игры: {title or "НЕ НАЙДЕНО"}')
    found = bot.find_panel()
    if args.once and not found:
        return 1
    if args.once:
        img = bot._grab()
        field = vision.field_bounds(img)
        state = vision.screen_state(img, field)
        paddle = vision.find_paddle(img, field)
        level, score = hud.read_status(img)
        print(f'состояние={state} поле={field} платформа={paddle} '
              f'уровень={level} счёт={score}')
        return 0
    bot.run(active=args.start)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

