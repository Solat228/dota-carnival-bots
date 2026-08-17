# -*- coding: utf-8 -*-
"""Зрение арканоида на настоящих кадрах игры (сняты 2026-08-17)."""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import panel as panelmod
from arkanoid import vision

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def panel_of(name):
    full = cv2.imread(os.path.join(FIXTURES, name))
    assert full is not None, name
    region = panelmod.detect_panel(full)
    assert region, f'панель не найдена на {name}'
    x, y, w, h = region
    return full[y:y + h, x:x + w]


# --- геометрия поля ---------------------------------------------------------

def test_field_bounds_on_play_frame():
    img = panel_of('boot_play.jpg')
    left, top, right, bottom = vision.field_bounds(img)
    #замер по живому кадру: (171, 111, 792, 950)
    assert abs(left - 171) <= 8 and abs(top - 111) <= 8
    assert abs(right - 792) <= 8 and abs(bottom - 950) <= 8


def test_field_bounds_degenerate():
    assert vision.field_bounds(None) is None
    assert vision.field_bounds(np.zeros((0, 0, 3), np.uint8)) is None


def test_field_bounds_fallback_on_blank_frame():
    """Синего фона нет -> долевая заглушка, а не падение."""
    blank = np.zeros((976, 976, 3), np.uint8)
    got = vision.field_bounds(blank)
    assert got is not None and got[2] > got[0] and got[3] > got[1]


# --- платформа --------------------------------------------------------------

def test_find_paddle_on_play_frame():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    got = vision.find_paddle(img, field)
    assert got is not None
    cx, half, top_y = got
    assert abs(cx - 482) <= 12          #тележка стояла по центру
    assert 40 <= half <= 90             #ширина ~128 px
    assert top_y > field[1]


def test_paddle_moved_left_on_throw_frame():
    """На кадре после удержания A тележка уехала к левой стене."""
    img = panel_of('boot_throw.png')
    field = vision.field_bounds(img)
    got = vision.find_paddle(img, field)
    assert got is not None
    assert got[0] < 350


def test_find_paddle_degenerate():
    assert vision.find_paddle(None, (0, 0, 10, 10)) is None
    assert vision.find_paddle(np.zeros((10, 10, 3), np.uint8), None) is None


# --- блоки и состояние ------------------------------------------------------

def test_brick_fraction_play_vs_menu():
    play = panel_of('boot_play.jpg')
    menu = panel_of('boot_menu.jpg')
    assert vision.brick_fraction(play, vision.field_bounds(play)) > 0.05
    assert vision.brick_fraction(menu, vision.field_bounds(menu)) < 0.01


def test_brick_stats_returns_lowest_row():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    count, low = vision.brick_stats(img, field)
    assert count > 10000
    assert field[1] < low < field[3]


def test_screen_state_play():
    img = panel_of('boot_play.jpg')
    assert vision.screen_state(img, vision.field_bounds(img)) == 'play'


def test_screen_state_menu_is_not_play():
    img = panel_of('boot_menu.jpg')
    assert vision.screen_state(img, vision.field_bounds(img)) == 'other'


def test_screen_state_dim_on_greyed_frame():
    """Пауза/конец игры гасят цвет — состояние 'dim'."""
    img = panel_of('boot_play.jpg')
    grey = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    assert vision.screen_state(grey, vision.field_bounds(img)) == 'dim'


def test_screen_state_degenerate():
    assert vision.screen_state(None, None) == 'other'


# --- кнопки -----------------------------------------------------------------

def test_find_play_button_on_menu():
    tpl = cv2.imread(os.path.join(os.path.dirname(FIXTURES), '..', 'arkanoid',
                                  'templates', 'play_button.png'))
    if tpl is None:
        tpl = cv2.imread(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'arkanoid', 'templates', 'play_button.png'))
    assert tpl is not None
    menu = panel_of('boot_menu.jpg')
    got = vision.find_button(menu, tpl)
    assert got is not None
    assert abs(got[0] - 480) <= 15 and abs(got[1] - 850) <= 15


def test_find_button_absent_on_play_frame():
    tpl = cv2.imread(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'arkanoid', 'templates', 'play_button.png'))
    play = panel_of('boot_play.jpg')
    assert vision.find_button(play, tpl) is None


def test_find_button_degenerate():
    assert vision.find_button(None, None) is None
    big = np.zeros((5, 5, 3), np.uint8)
    assert vision.find_button(big, np.zeros((50, 50, 3), np.uint8)) is None


# --- мяч --------------------------------------------------------------------

def test_ball_not_found_on_identical_frames():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    assert vision.find_ball(img, img, field) is None


def test_ball_found_when_blob_moves():
    """Рисуем светлое пятно размером с сапог и двигаем его."""
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    a = img.copy()
    b = img.copy()
    cv2.circle(a, (400, 700), 14, (240, 240, 240), -1)
    cv2.circle(b, (440, 730), 14, (240, 240, 240), -1)
    got = vision.find_ball(a, b, field, paddle_top=820)
    assert got is not None
    #ближе к новой позиции, чем к старой
    assert abs(got[0] - 440) < 45


def test_ball_prefers_blob_near_expected_point():
    """Из двух пятен берём то, что ближе к ПРОГНОЗУ полёта."""
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    a = img.copy()
    b = img.copy()
    cv2.circle(b, (300, 400), 14, (240, 240, 240), -1)   #ложное пятно
    cv2.circle(b, (600, 700), 14, (240, 240, 240), -1)   #наш мяч
    got = vision.find_ball(a, b, field, paddle_top=820, expect_pos=(590, 690))
    assert got is not None and abs(got[0] - 600) < 40


def test_ball_ignores_expectation_when_far_off():
    """Прогноз далеко от всех пятен -> берём по яркости, а не ближайшее."""
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    a = img.copy()
    b = img.copy()
    cv2.circle(b, (600, 700), 14, (240, 240, 240), -1)
    got = vision.find_ball(a, b, field, paddle_top=820, expect_pos=(200, 150))
    assert got is not None and abs(got[0] - 600) < 40


def test_ball_ignores_huge_change():
    """Смена всего кадра (уровень сменился) не должна давать «мяч»."""
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    other = np.zeros_like(img)
    assert vision.find_ball(img, other, field, paddle_top=820) is None


def test_ball_degenerate_inputs():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    assert vision.find_ball(None, img, field) is None
    assert vision.find_ball(img, None, field) is None
    assert vision.find_ball(img, img, None) is None
    assert vision.find_ball(img, np.zeros((10, 10, 3), np.uint8), field) is None
