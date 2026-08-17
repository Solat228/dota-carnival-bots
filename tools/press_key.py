# -*- coding: utf-8 -*-
"""Синтетическое нажатие клавиши — проверка горячих клавиш бота.

    python tools/press_key.py 0x79      — нажать F10
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sendkeys  # noqa: E402


def press(vk, hold=0.06):
    scan = sendkeys.scan_for_vk(vk)
    sendkeys.send_scan(scan, up=False)
    time.sleep(hold)
    sendkeys.send_scan(scan, up=True)
    return scan


if __name__ == '__main__':
    code = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x79
    print(f'нажимаю {sendkeys.key_name(code)} (vk=0x{code:02X}, scan={press(code)})')
