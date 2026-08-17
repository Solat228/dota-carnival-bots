# -*- coding: utf-8 -*-
"""Офлайн-прогон распознавания по снятым кадрам (Screens/*.png).

Запуск:
    python tools/offline_test.py               — прогон по всем кадрам, сводка
    python tools/offline_test.py --dump 25      — плюс картинки-разборы в Debug/
    python tools/offline_test.py --one FILE     — один кадр подробно
"""

import argparse
import glob
import os
import sys
import time

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import ocr          # noqa: E402
import panel as panelmod   # noqa: E402
import wordfind     # noqa: E402
import words as wordsmod   # noqa: E402

SCREENS = os.path.join(ROOT, 'Screens')
DEBUG = os.path.join(ROOT, 'Debug')

#Зоны HUD (счёт/время/рекорд) — заполним после калибровки; пока пусто
ZONES = []


def analyze(img, zones=ZONES):
    """Один кадр -> (что печатать, откуда взято, bbox, время_мс)."""
    t0 = time.time()
    box, letters = wordfind.find_progress_line(img, zones=zones)
    if box is not None:
        text = ocr.read_text(wordfind.prepare_for_ocr(wordfind.crop_mask(letters, box)))
        return text, 'progress', box, (time.time() - t0) * 1000
    boxes, gm = wordfind.find_label_lines(img, zones=zones)
    if boxes:
        box = boxes[0]
        text = ocr.read_text(wordfind.prepare_for_ocr(wordfind.crop_mask(gm, box)))
        return text, 'label', box, (time.time() - t0) * 1000
    return '', 'none', None, (time.time() - t0) * 1000


def replay_tracker(files):
    """Прогон кадров ПО ПОРЯДКУ через якорную починку: видно, что бот напечатал бы."""
    trk = wordsmod.WordTracker(wordsmod.Vocabulary())
    region = None
    typed = last = ''
    changed = 0
    for path in files:
        full = cv2.imread(path)
        if full is None:
            continue
        if region is None:
            region = panelmod.detect_panel(full)
        img = full
        zones = []
        if region is not None:
            x, y, w, h = region
            img = full[y:y + h, x:x + w]
            zones = panelmod.hud_zones((x, y, w, h))
        box, letters = wordfind.find_progress_line(img, zones=zones)
        if box is None:
            continue
        raw = ocr.read_text(wordfind.prepare_for_ocr(wordfind.crop_mask(letters, box)))
        out, _conf, note = trk.feed(raw)
        if not out or out == last:
            continue
        last = out
        typed += out
        mark = f'   <- {raw!r} [{note}]' if out != wordsmod.normalize(raw) else ''
        if mark:
            changed += 1
        print(f'{os.path.basename(path):28s} {out}{mark}')
    print(f'\nпочинено остатков: {changed}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--track', action='store_true',
                    help='прогон по порядку через якорную починку (что бот напечатал бы)')
    ap.add_argument('--dump', type=int, default=0, help='сколько разборов сохранить в Debug/')
    ap.add_argument('--one', default='')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args(argv)

    ocr.setup()
    files = [args.one] if args.one else sorted(glob.glob(os.path.join(SCREENS, '*.png')))
    if args.limit:
        files = files[:args.limit]
    os.makedirs(DEBUG, exist_ok=True)
    if args.track:
        return replay_tracker(files)

    kinds ={'progress': 0, 'label': 0, 'none': 0}
    words = {}
    times = []
    dumped = 0
    for path in files:
        img = cv2.imread(path)
        if img is None:
            continue
        text, kind, box, ms = analyze(img)
        kinds[kind] += 1
        times.append(ms)
        if text:
            words[text] = words.get(text, 0) + 1
        if args.one or (dumped < args.dump and kind != 'none'):
            vis = img.copy()
            if box is not None:
                x, y, w, h = box[:4]
                cv2.rectangle(vis, (x - 3, y - 3), (x + w + 3, y + h + 3), (0, 0, 255), 2)
                cv2.putText(vis, f'{kind}:{text}', (x, max(20, y - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            name = os.path.splitext(os.path.basename(path))[0]
            cv2.imwrite(os.path.join(DEBUG, f'{name}_vis.png'), vis)
            if box is not None:
                x, y, w, h = box[:4]
                sub = img[max(0, y - 12):y + h + 12, max(0, x - 12):x + w + 12]
                cv2.imwrite(os.path.join(DEBUG, f'{name}_crop.png'),
                            cv2.resize(sub, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
            dumped += 1
        if args.one:
            print(f'{os.path.basename(path)}: kind={kind} text={text!r} box={box} {ms:.0f}ms')

    if not args.one:
        n = max(1, len(times))
        print(f'кадров: {len(files)}  время: сред {sum(times)/n:.0f} мс, макс {max(times):.0f} мс')
        print('источник:', kinds)
        print('распознанные слова (по частоте):')
        for w, c in sorted(words.items(), key=lambda kv: -kv[1]):
            print(f'   {c:4d}  {w}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
