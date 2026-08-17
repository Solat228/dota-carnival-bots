# -*- coding: utf-8 -*-
"""Реагирует ли игра на удержание A/D (синтетический ввод).

Снимает полосу с платформой до и после удержания клавиши и печатает,
насколько сместился центр яркой платформы.
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import capture      # noqa: E402
import sendkeys     # noqa: E402

#Полоса, где ездит тележка с сапогом (координаты экрана 1920x1080)
CART_BAND = (650, 860, 640, 130)     # x, y, w, h


def cart_x(img):
    """Центр самой яркой (красно-жёлтой) массы в полосе платформы."""
    x, y, w, h = CART_BAND
    sub = img[y:y + h, x:x + w]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    #тележка — насыщенная красно-жёлтая, фон полосы тёмно-синий
    mask = cv2.inRange(hsv, (0, 90, 90), (35, 255, 255))
    total = mask.sum()
    if total < 255 * 50:
        return None, mask
    cols = mask.sum(axis=0).astype(np.float64)
    return float((cols * np.arange(len(cols))).sum() / cols.sum()) + x, mask


def hold(vk, secs):
    scan = sendkeys.scan_for_vk(vk)
    sendkeys.send_scan(scan, up=False)
    time.sleep(secs)
    sendkeys.send_scan(scan, up=True)


if __name__ == '__main__':
    os.makedirs('Debug', exist_ok=True)
    before = capture.grab_region(None)
    bx, bmask = cart_x(before)
    cv2.imwrite(os.path.join('Debug', 'cart_mask.png'), bmask)
    print('центр платформы до:', bx)

    key = sys.argv[1].upper() if len(sys.argv) > 1 else 'A'
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
    hold(ord(key), secs)
    time.sleep(0.3)

    after = capture.grab_region(None)
    ax, _ = cart_x(after)
    print(f'центр платформы после {key} ({secs}с):', ax)
    if bx is not None and ax is not None:
        print(f'сдвиг: {ax - bx:+.1f} px')
    cv2.imwrite(os.path.join('Debug', 'cart_after.png'), after)
