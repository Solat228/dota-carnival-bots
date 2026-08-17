# -*- coding: utf-8 -*-
"""Разведка геометрии поля арканоида по снятому кадру.

Печатает найденную панель, границы игрового поля и цвета в опорных точках,
сохраняет визуализацию в Debug/.
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import panel as panelmod  # noqa: E402


def main(path):
    full = cv2.imread(path)
    if full is None:
        print('нет кадра', path)
        return 1
    print('кадр:', full.shape)
    found = panelmod.detect_panel(full)
    print('панель:', found)
    if not found:
        return 1
    px, py, pw, ph = found
    img = full[py:py + ph, px:px + pw]

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    #тёмно-синий фон поля
    back = cv2.inRange(hsv, (100, 80, 20), (135, 255, 130))
    cols = back.sum(axis=0) / 255.0
    rows = back.sum(axis=1) / 255.0
    thr_c = 0.25 * cols.max()
    thr_r = 0.25 * rows.max()
    xs = np.where(cols > thr_c)[0]
    ys = np.where(rows > thr_r)[0]
    print('поле по синему фону: x', (int(xs[0]), int(xs[-1])) if len(xs) else None,
          ' y', (int(ys[0]), int(ys[-1])) if len(ys) else None)

    #блоки — насыщенный оранжевый
    bricks = cv2.inRange(hsv, (10, 120, 120), (30, 255, 255))
    bxs = np.where(bricks.sum(axis=0) > 0)[0]
    bys = np.where(bricks.sum(axis=1) > 0)[0]
    print('оранжевые блоки: x', (int(bxs[0]), int(bxs[-1])) if len(bxs) else None,
          ' y', (int(bys[0]), int(bys[-1])) if len(bys) else None)

    vis = img.copy()
    if len(xs) and len(ys):
        cv2.rectangle(vis, (int(xs[0]), int(ys[0])), (int(xs[-1]), int(ys[-1])),
                      (0, 255, 0), 2)
    os.makedirs(os.path.join(ROOT, 'Debug'), exist_ok=True)
    cv2.imwrite(os.path.join(ROOT, 'Debug', 'field_probe.png'), vis)
    cv2.imwrite(os.path.join(ROOT, 'Debug', 'field_back.png'), back)
    cv2.imwrite(os.path.join(ROOT, 'Debug', 'field_bricks.png'), bricks)
    print('сохранено: Debug/field_probe.png, field_back.png, field_bricks.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
