# -*- coding: utf-8 -*-
"""Сколько миллисекунд стоит каждый шаг разбора кадра арканоида."""
import os
import sys
import time

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import capture                      # noqa: E402
import panel as panelmod            # noqa: E402
from arkanoid import hud, vision    # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures')


def timeit(name, fn, times=30):
    fn()
    t0 = time.time()
    for _ in range(times):
        fn()
    ms = (time.time() - t0) / times * 1000
    print(f'{name:34s} {ms:6.2f} мс')
    return ms


def main():
    full = cv2.imread(os.path.join(FIX, 'boot_play.jpg'))
    region = panelmod.detect_panel(full)
    x, y, w, h = region
    img = full[y:y + h, x:x + w]
    prev = img.copy()
    field = vision.field_bounds(img)
    tpl_hint = cv2.imread(os.path.join(ROOT, 'arkanoid', 'templates', 'space_hint.png'))
    tpl_play = cv2.imread(os.path.join(ROOT, 'arkanoid', 'templates', 'play_button.png'))

    total = 0.0
    total += timeit('снимок панели (BitBlt)',
                    lambda: capture.grab_region(list(region)), 20)
    total += timeit('field_bounds (границы поля)', lambda: vision.field_bounds(img))
    total += timeit('screen_state (состояние)', lambda: vision.screen_state(img, field))
    total += timeit('find_paddle (тележка)', lambda: vision.find_paddle(img, field))
    total += timeit('find_ball (мяч)',
                    lambda: vision.find_ball(prev, img, field, 860))
    total += timeit('find_hint (подсказка)',
                    lambda: vision.find_hint(img, tpl_hint, field))
    timeit('find_button (кнопка, вся панель)',
           lambda: vision.find_button(img, tpl_play), 10)
    timeit('hud.read_status (OCR, раз в сек)',
           lambda: hud.read_status(img), 5)
    print(f'{"ИТОГО за кадр (без OCR/кнопок)":34s} {total:6.2f} мс')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
