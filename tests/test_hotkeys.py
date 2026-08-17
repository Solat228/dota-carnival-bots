# -*- coding: utf-8 -*-
"""Горячие клавиши: фронт нажатия, имена клавиш, коды из конфига."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import sendkeys


class FakeKeys:
    """Подставная читалка клавиатуры: держим набор «зажатых» кодов."""

    def __init__(self):
        self.down = set()

    def __call__(self, vk):
        return vk in self.down


def test_press_fires_once_per_press():
    fake = FakeKeys()
    keys = sendkeys.Hotkeys(fake)
    assert not keys.pressed(0x79)          #не нажата
    fake.down.add(0x79)
    assert keys.pressed(0x79)              #нажали — сработало
    assert not keys.pressed(0x79)          #держим — больше не срабатывает
    assert not keys.pressed(0x79)
    fake.down.discard(0x79)
    assert not keys.pressed(0x79)          #отпустили
    fake.down.add(0x79)
    assert keys.pressed(0x79)              #нажали снова — снова сработало


def test_keys_are_independent():
    fake = FakeKeys()
    keys = sendkeys.Hotkeys(fake)
    fake.down.add(0x79)
    assert keys.pressed(0x79)
    assert not keys.pressed(0x7B)
    fake.down.add(0x7B)
    assert keys.pressed(0x7B)
    assert not keys.pressed(0x79)


def test_forget_allows_refire():
    fake = FakeKeys()
    keys = sendkeys.Hotkeys(fake)
    fake.down.add(0x79)
    assert keys.pressed(0x79)
    keys.forget()
    assert keys.pressed(0x79)              #после сброса зажатая считается новой


def test_toggle_sequence():
    """Старт -> стоп -> старт по одной клавише."""
    fake = FakeKeys()
    keys = sendkeys.Hotkeys(fake)
    active = False
    for _ in range(3):
        fake.down.add(0x79)
        if keys.pressed(0x79):
            active = not active
        fake.down.discard(0x79)
        keys.pressed(0x79)
    assert active is True                  #нечётное число нажатий


def test_key_names():
    assert sendkeys.key_name(0x79) == 'F10'
    assert sendkeys.key_name(0x7B) == 'F12'
    assert sendkeys.key_name(0x70) == 'F1'
    assert sendkeys.key_name(0xC0) == '`/Ё'
    assert sendkeys.key_name(ord('A')) == 'A'
    assert sendkeys.key_name(0x05).startswith('VK 0x')


def test_config_hotkeys_are_f10_f12():
    """Дефолты конфига должны совпадать с тем, что бот пишет пользователю."""
    cfg = config.DEFAULTS
    assert sendkeys.key_name(cfg['hotkey_toggle']) == 'F10'
    assert sendkeys.key_name(cfg['hotkey_quit']) == 'F12'


def test_real_reader_returns_bool():
    """Живой GetAsyncKeyState не должен падать и обязан вернуть bool."""
    assert sendkeys.key_down(0x79) in (True, False)
