# -*- coding: utf-8 -*-
"""Метрики кадра по состояниям экрана — чтобы пороги брать из чисел, а не наугад."""
import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import panel as panelmod          # noqa: E402
from arkanoid import vision       # noqa: E402


def metrics(path):
    full = cv2.imread(path)
    if full is None:
        return f'{os.path.basename(path)}: нет файла'
    region = panelmod.detect_panel(full)
    if not region:
        return f'{os.path.basename(path)}: панель не найдена'
    x, y, w, h = region
    img = full[y:y + h, x:x + w]
    field = vision.field_bounds(img)
    left, top, right, bottom = field
    back = vision._mask(img[top:bottom, left:right], vision.BACK_LO, vision.BACK_HI)
    area = max(1, (bottom - top) * (right - left))
    bricks, _low = vision.brick_stats(img, field)
    return (f'{os.path.basename(path):32s} поле={field} '
            f'синий={float(back.sum() // 255) / area:.3f} '
            f'блоки={bricks:6d} ({bricks / area:.3f}) '
            f'яркость={vision.field_brightness(img, field):5.1f} '
            f'насыщ={vision.field_colorfulness(img, field):5.1f}')


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        print(metrics(arg))
