# -*- coding: utf-8 -*-
"""Клик мышью по абсолютным координатам экрана (для отладки/меню мини-игр).

    python tools/click_at.py 958 820
"""
import ctypes
import sys
import time

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def click(x, y, hold=0.05):
    """Ставит курсор и кликает левой кнопкой."""
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.03)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(hold)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


if __name__ == '__main__':
    cx, cy = int(sys.argv[1]), int(sys.argv[2])
    click(cx, cy)
    print(f'клик по ({cx}, {cy})')
