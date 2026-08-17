# -*- coding: utf-8 -*-
"""Почему не проходит пробел: проверяем фокус и два способа нажатия."""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import capture      # noqa: E402
import sendkeys     # noqa: E402

user32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x0002


def vk_press(vk, hold=0.08):
    """Старый добрый keybd_event по виртуальному коду (не скан-коду)."""
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(hold)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def shot(name):
    img = capture.grab_region(None)
    if img is not None:
        import cv2
        cv2.imwrite(os.path.join('Debug', name), img)


if __name__ == '__main__':
    os.makedirs('Debug', exist_ok=True)
    print('фокус:', repr(capture.foreground_title()))
    hwnd, title = capture.find_window('Dota 2')
    print('окно доты:', hwnd, repr(title))
    if hwnd:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        print('фокус после подъёма:', repr(capture.foreground_title()))

    scan = sendkeys.scan_for_vk(0x20)
    sendkeys.send_scan(scan, up=False)
    time.sleep(0.08)
    sendkeys.send_scan(scan, up=True)
    time.sleep(1.0)
    shot('space_scan.png')
    print('скан-код отправлен, снимок space_scan.png')

    vk_press(0x20)
    time.sleep(1.0)
    shot('space_vk.png')
    print('vk отправлен, снимок space_vk.png')
