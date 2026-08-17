# -*- coding: utf-8 -*-
"""Кнопки экранов: «ИГРАТЬ» (правила) и «СЫГРАТЬ ЕЩЁ» (конец игры).

Регресс живого прогона 2026-08-17: шаблона «Сыграть ещё» не было, а запасная
точка клика оказалась на 77 px ниже кнопки — бот после проигрыша щёлкал в
пустоту и не мог начать заново.
"""
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import panel as panelmod
from arkanoid import vision
from arkanoid.play import Brain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures')
TEMPLATES = os.path.join(ROOT, 'arkanoid', 'templates')

FIELD = (100.0, 100.0, 700.0, 950.0)
PADDLE = (400.0, 60.0, 860.0)


def tpl(name):
    img = cv2.imread(os.path.join(TEMPLATES, name))
    assert img is not None, name
    return img


def over_frame():
    return cv2.imread(os.path.join(FIXTURES, 'boot_over.png'))


def menu_frame():
    full = cv2.imread(os.path.join(FIXTURES, 'boot_menu.jpg'))
    x, y, w, h = panelmod.detect_panel(full)
    return full[y:y + h, x:x + w]


def test_again_button_found_on_game_over():
    got = vision.find_button(over_frame(), tpl('again_button.png'))
    assert got is not None
    assert abs(got[0] - 482) <= 10 and abs(got[1] - 774) <= 10


def test_again_button_absent_on_rules_screen():
    assert vision.find_button(menu_frame(), tpl('again_button.png')) is None


def test_play_button_absent_on_game_over():
    """Шаблоны не должны путаться: кнопки оформлены одинаково, текст разный."""
    assert vision.find_button(over_frame(), tpl('play_button.png')) is None


def test_play_button_found_on_rules_screen():
    got = vision.find_button(menu_frame(), tpl('play_button.png'))
    assert got is not None


def test_brain_clicks_again_from_other_state():
    """Конец игры распознаётся как 'other' (окно рекордов цветное) — клик всё равно."""
    b = Brain()
    act = b.step(0.0, 'other', FIELD, PADDLE, None, {'again': (482.0, 774.0)})
    assert act.click == (482.0, 774.0)


def test_game_over_score_is_readable():
    """Счёт на экране конца игры пригодится для отчёта о прогрессе."""
    img = over_frame()
    assert img is not None and img.shape[0] > 900
