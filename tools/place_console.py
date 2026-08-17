# -*- coding: utf-8 -*-
"""Ставит окно консоли бота в боковую полосу и делает поверх всех окон.

Иначе консоль ложится ровно на панель мини-игры, бот перестаёт её видеть и
заполняет экран сообщениями «панель не найдена» (проверено на себе).

    python tools/place_console.py "БОТ АРКАНОИД" 0 0 470 1040
"""
import ctypes
import sys

user32 = ctypes.windll.user32
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x0040


def find_window(title_part):
    found = []

    def cb(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_part.lower() in buf.value.lower():
                found.append((hwnd, buf.value))
        return True

    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(proto(cb), 0)
    return found


def place(title_part, x, y, w, h, topmost=True):
    wins = find_window(title_part)
    if not wins:
        return 0
    for hwnd, title in wins:
        user32.SetWindowPos(hwnd, HWND_TOPMOST if topmost else 0,
                            int(x), int(y), int(w), int(h), SWP_SHOWWINDOW)
        print(f'окно {title!r} -> ({x}, {y}) {w}x{h}, поверх={topmost}')
    return len(wins)


if __name__ == '__main__':
    args = sys.argv[1:]
    name = args[0] if args else 'БОТ АРКАНОИД'
    box = [int(v) for v in args[1:5]] if len(args) >= 5 else [0, 0, 470, 1040]
    if not place(name, *box):
        print(f'окно {name!r} не найдено')
