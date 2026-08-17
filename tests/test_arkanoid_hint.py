# -*- coding: utf-8 -*-
"""Подсказка «␣ ВЫБРАТЬ ПОЗИЦИЮ / БРОСИТЬ САПОГ» — признак «сапог не брошен».

Регресс живого прогона 2026-08-17: бот определял это по отсутствию мяча, а
мерцание декора у стен давало ложные «мячи». Бот считал, что игра идёт, не жал
пробел и простоял на выборе позиции, пока не кончились сапоги.
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arkanoid import vision
from arkanoid.play import Brain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures')
TEMPLATE = os.path.join(ROOT, 'arkanoid', 'templates', 'space_hint.png')

FIELD = (100.0, 100.0, 700.0, 950.0)
PADDLE = (400.0, 60.0, 860.0)


def frame():
    return cv2.imread(os.path.join(FIXTURES, 'boot_hint.png'))


def test_hint_found_on_real_frame():
    img = frame()
    tpl = cv2.imread(TEMPLATE)
    field = vision.field_bounds(img)
    got = vision.find_hint(img, tpl, field)
    assert got is not None
    assert abs(got[0] - 374) <= 10 and abs(got[1] - 624) <= 10


def test_hint_absent_when_band_cleared():
    img = frame()
    tpl = cv2.imread(TEMPLATE)
    field = vision.field_bounds(img)
    left, top, right, bottom = field
    h = bottom - top
    img[top + int(h * 0.55):top + int(h * 0.70), left:right] = 0
    assert vision.find_hint(img, tpl, field) is None


def test_hint_degenerate():
    assert vision.find_hint(None, None, None) is None
    tiny = np.zeros((10, 10, 3), np.uint8)
    tpl = cv2.imread(TEMPLATE)
    assert vision.find_hint(tiny, tpl, (0, 0, 9, 9)) is None


def test_brain_presses_space_on_hint():
    b = Brain()
    act = b.step(0.0, 'play', FIELD, PADDLE, None, hint=True)
    assert act.space is True
    assert 'подсказка' in act.note


def test_brain_ignores_false_ball_while_hint_visible():
    """Даже если «мяч» найден, при видимой подсказке игра ещё не началась."""
    b = Brain()
    act = b.step(0.0, 'play', FIELD, PADDLE, (174.0, 742.0), hint=True)
    assert act.space is True
    assert not b.tracker.ready()


def test_brain_plays_when_hint_gone():
    b = Brain()
    b.step(0.0, 'play', FIELD, PADDLE, None, hint=True)
    b.step(0.5, 'play', FIELD, PADDLE, (300.0, 300.0))
    act = b.step(0.55, 'play', FIELD, PADDLE, (320.0, 340.0))
    assert not act.space
    assert 'цель' in act.note


def test_ball_near_wall_is_rejected():
    """Центр сапога не может стоять в 2 px от стены — это мерцание декора."""
    img = frame()
    field = vision.field_bounds(img)
    left = field[0]
    a = img.copy()
    b = img.copy()
    cv2.circle(b, (left + 2, 742), 10, (240, 240, 240), -1)
    assert vision.find_ball(a, b, field, paddle_top=860) is None
