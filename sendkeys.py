# -*- coding: utf-8 -*-
"""Ввод текста в игру через SendInput (скан-коды) + переключение раскладки на EN.

Почему скан-коды, а не WM_CHAR/PostMessage: Dota 2 (Source 2 / Panorama) читает
системный ввод, а не сообщения окна — фоновые PostMessage игра игнорирует.
Из-за скан-кодов буква зависит от раскладки, поэтому перед вводом окну игры
принудительно ставится EN-US (как в ARK-боте: WM_INPUTLANGCHANGEREQUEST).
"""

import ctypes
import string
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
WM_INPUTLANGCHANGEREQUEST = 0x0050

#Символы, которые вообще умеем печатать (в игре знаки препинания можно не вводить)
ALLOWED = set(string.ascii_uppercase + string.digits)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD),
                ('wParamH', wintypes.WORD)]


class _INPUTunion(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', _INPUTunion)]


def vk_for_char(ch):
    """VK-код для символа (только латиница/цифры). None — если печатать нечем."""
    ch = ch.upper()
    if ch in ALLOWED:
        return ord(ch)
    return None


def scan_for_vk(vk):
    """Скан-код клавиши по VK (раскладка тут не важна — берём физическую клавишу)."""
    return user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC


def _key_input(scan, up):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.u.ki = KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0), 0, 0)
    return inp


def send_scan(scan, up=False):
    """Одно нажатие/отпускание по скан-коду."""
    inp = _key_input(scan, up)
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def clean_text(text):
    """Оставляет только то, что умеем печатать: A-Z и цифры, в верхнем регистре.

    Пробелы и знаки препинания по правилам игры можно не вводить — выкидываем.
    """
    return ''.join(ch for ch in (text or '').upper() if ch in ALLOWED)


def type_text(text, delay_ms=6, clean=True):
    """Печатает строку. Возвращает, сколько символов реально отправлено."""
    payload = clean_text(text) if clean else (text or '').upper()
    sent = 0
    delay = max(0.0, delay_ms / 1000.0)
    for ch in payload:
        vk = vk_for_char(ch)
        if vk is None:
            continue
        scan = scan_for_vk(vk)
        if not scan:
            continue
        send_scan(scan, up=False)
        send_scan(scan, up=True)
        sent += 1
        if delay:
            time.sleep(delay)
    return sent


def type_text_burst(text, clean=True):
    """Печатает строку ОДНИМ вызовом SendInput (максимально быстро, без пауз)."""
    payload = clean_text(text) if clean else (text or '').upper()
    events = []
    for ch in payload:
        vk = vk_for_char(ch)
        if vk is None:
            continue
        scan = scan_for_vk(vk)
        if not scan:
            continue
        events.append(_key_input(scan, False))
        events.append(_key_input(scan, True))
    if not events:
        return 0
    arr = (INPUT * len(events))(*events)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    return len(events) // 2


def force_en_layout(hwnd):
    """Ставит окну игры раскладку EN-US (иначе скан-коды напечатают кириллицу)."""
    if not hwnd:
        return False
    try:
        hkl = user32.LoadKeyboardLayoutW('00000409', 1)
        user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        return True
    except Exception:
        return False


def key_down(vk):
    """Зажата ли клавиша сейчас (для горячих клавиш без глобального хука)."""
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


#Имена клавиш для сообщений (клавиши настраиваются, поэтому не хардкодим «F10»)
VK_NAMES = {0x1B: 'Esc', 0x20: 'Space', 0x2D: 'Insert', 0x2E: 'Delete',
            0x21: 'PgUp', 0x22: 'PgDn', 0x23: 'End', 0x24: 'Home',
            0xC0: '`/Ё', 0x09: 'Tab', 0x14: 'CapsLock'}
VK_NAMES.update({0x70 + i: f'F{i + 1}' for i in range(24)})


def key_name(vk):
    """Код клавиши -> читаемое имя ('F10'); неизвестный код -> 'VK 0x..'."""
    vk = int(vk)
    if vk in VK_NAMES:
        return VK_NAMES[vk]
    if 0x30 <= vk <= 0x5A:          #цифры и буквы совпадают с ASCII
        return chr(vk)
    return f'VK 0x{vk:02X}'


class Hotkeys:
    """Ловит НАЖАТИЕ (фронт) клавиши: удержание не должно срабатывать повторно.

    Читалка вынесена параметром — так логику можно проверить тестами без железа.
    """

    def __init__(self, reader=None):
        self.reader = reader or key_down
        self._prev = {}

    def pressed(self, vk):
        """True ровно один раз на каждое нажатие."""
        down = bool(self.reader(vk))
        was = self._prev.get(vk, False)
        self._prev[vk] = down
        return down and not was

    def forget(self, vk=None):
        """Сбрасывает память о зажатых клавишах (после смены режима)."""
        if vk is None:
            self._prev.clear()
        else:
            self._prev.pop(vk, None)
