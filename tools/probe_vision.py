# -*- coding: utf-8 -*-
"""Прогон зрения арканоида по снятым кадрам: метрики и визуализация."""
import glob
import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import panel as panelmod          # noqa: E402
from arkanoid import vision       # noqa: E402


def main(pattern, limit=0, dump=3):
    files = sorted(glob.glob(pattern))
    if limit:
        files = files[:limit]
    os.makedirs(os.path.join(ROOT, 'Debug'), exist_ok=True)
    prev_panel = None
    region = None
    dumped = 0
    for path in files:
        full = cv2.imread(path)
        if full is None:
            continue
        if region is None:
            region = panelmod.detect_panel(full)
            if not region:
                continue
        x, y, w, h = region
        img = full[y:y + h, x:x + w]
        field = vision.field_bounds(img)
        state = vision.screen_state(img, field)
        paddle = vision.find_paddle(img, field)
        bricks, brick_low = vision.brick_stats(img, field)
        ball = vision.find_ball(prev_panel, img, field,
                                paddle[2] if paddle else None)
        print(f'{os.path.basename(path):32s} {state:5s} '
              f'поле={field} платформа='
              f'{None if not paddle else (round(paddle[0]), round(paddle[1]))} '
              f'блоков={bricks:6d} мяч={None if not ball else (round(ball[0]), round(ball[1]))}')
        if dumped < dump and paddle:
            vis = img.copy()
            fl, ft, fr, fb = field
            cv2.rectangle(vis, (fl, ft), (fr, fb), (0, 255, 0), 2)
            cv2.circle(vis, (int(paddle[0]), int(paddle[2])), 8, (0, 0, 255), 2)
            if ball:
                cv2.circle(vis, (int(ball[0]), int(ball[1])), 12, (255, 0, 255), 2)
            cv2.imwrite(os.path.join(ROOT, 'Debug',
                                     f'vis_{os.path.basename(path)}.png'), vis)
            dumped += 1
        prev_panel = img
    return 0


if __name__ == '__main__':
    pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'ScreensBoot', '*.jpg')
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    raise SystemExit(main(pat, lim))
