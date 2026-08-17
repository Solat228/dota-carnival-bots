# -*- coding: utf-8 -*-
"""Быстрый захват прямоугольника экрана (BitBlt) + поиск окна игры.

GDI-объекты освобождаются в finally — иначе при любой ошибке протекает память
(на ARK-боте это выливалось в ~8 МБ за тик и падение игры).
"""

import ctypes

import numpy as np
import win32con
import win32gui
import win32ui


def screen_size():
    """Размер основного экрана (без учёта DPI-масштаба)."""
    u32 = ctypes.windll.user32
    return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)


def find_window(title_part):
    """HWND первого видимого окна, в заголовке которого есть подстрока."""
    found = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if title and title_part.lower() in title.lower():
            found.append((hwnd, title))
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else (0, '')


def foreground_title():
    """Заголовок активного окна (чтобы не печатать мимо игры)."""
    try:
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    except Exception:
        return ''


class Grabber:
    """Снимки экрана с ПЕРЕИСПОЛЬЗОВАНИЕМ GDI-объектов.

    Замер (арканоид, 2026-08-17): создание DC+bitmap на каждый снимок стоило
    16.6 мс и не зависело от размера области — то есть весь цикл упирался в
    накладные расходы, а не в пиксели. Держим DC и bitmap между кадрами и
    пересоздаём только при смене размера.

    Утечки, из-за которых на ARK-боте падала игра, тут не возникает: объекты
    ровно одни на экземпляр, освобождаются в `close()` и при смене размера.
    """

    def __init__(self):
        self._size = None
        self._src_dc = None
        self._dc = None
        self._mem_dc = None
        self._bitmap = None

    def _free(self):
        try:
            if self._bitmap is not None:
                win32gui.DeleteObject(self._bitmap.GetHandle())
        except Exception:
            pass
        try:
            if self._mem_dc is not None:
                self._mem_dc.DeleteDC()
        except Exception:
            pass
        try:
            if self._dc is not None:
                self._dc.DeleteDC()
        except Exception:
            pass
        try:
            if self._src_dc is not None:
                win32gui.ReleaseDC(win32gui.GetDesktopWindow(), self._src_dc)
        except Exception:
            pass
        self._size = None
        self._src_dc = self._dc = self._mem_dc = self._bitmap = None

    close = _free

    def _ensure(self, w, h):
        if self._size == (w, h) and self._bitmap is not None:
            return True
        self._free()
        try:
            self._src_dc = win32gui.GetWindowDC(win32gui.GetDesktopWindow())
            self._dc = win32ui.CreateDCFromHandle(self._src_dc)
            self._mem_dc = self._dc.CreateCompatibleDC()
            self._bitmap = win32ui.CreateBitmap()
            self._bitmap.CreateCompatibleBitmap(self._dc, w, h)
            self._mem_dc.SelectObject(self._bitmap)
            self._size = (w, h)
            return True
        except Exception:
            self._free()
            return False

    def grab(self, x, y, w, h):
        """Снимок области экрана -> BGR numpy. None при сбое."""
        if w <= 0 or h <= 0:
            return None
        if not self._ensure(w, h):
            return None
        try:
            self._mem_dc.BitBlt((0, 0), (w, h), self._dc, (x, y), win32con.SRCCOPY)
            buf = self._bitmap.GetBitmapBits(True)
            if len(buf) != w * h * 4:
                return None
            img = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
            return np.ascontiguousarray(img[:, :, :3])   # BGRA -> BGR
        except Exception:
            #Экран мог смениться (разрешение, блокировка) — соберём заново
            self._free()
            return None


_DEFAULT = Grabber()


def grab(x, y, w, h):
    """Снимок области экрана -> BGR numpy (как у cv2). None при сбое."""
    return _DEFAULT.grab(x, y, w, h)


def grab_region(region):
    """Снимок по [x, y, w, h]; None/пусто -> весь экран."""
    if not region:
        sw, sh = screen_size()
        return grab(0, 0, sw, sh)
    x, y, w, h = region
    return grab(int(x), int(y), int(w), int(h))
