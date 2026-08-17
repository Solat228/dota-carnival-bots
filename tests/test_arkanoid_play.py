# -*- coding: utf-8 -*-
"""Автомат арканоида: решения на каждом кадре (без игры)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arkanoid.play import Brain

FIELD = (100.0, 100.0, 700.0, 950.0)
PADDLE = (400.0, 60.0, 860.0)       # центр, полуширина, верх тележки


def brain(**kw):
    return Brain(**kw)


# --- игра -------------------------------------------------------------------

def test_moves_right_to_predicted_point():
    b = brain()
    #мяч идёт вниз-вправо: две точки задают скорость
    b.step(0.00, 'play', FIELD, PADDLE, (300.0, 300.0))
    act = b.step(0.05, 'play', FIELD, PADDLE, (320.0, 340.0))
    assert act.move == 1                       #цель правее платформы
    assert 'цель' in act.note


def test_moves_left_when_ball_falls_left():
    b = brain()
    b.step(0.00, 'play', FIELD, PADDLE, (500.0, 300.0))
    act = b.step(0.05, 'play', FIELD, PADDLE, (480.0, 340.0))
    assert act.move == -1


def test_stands_still_inside_dead_zone():
    b = brain(dead_zone=30.0)
    b.step(0.00, 'play', FIELD, PADDLE, (400.0, 300.0))
    act = b.step(0.05, 'play', FIELD, PADDLE, (400.0, 340.0))
    assert act.move == 0


def test_follows_ball_when_it_goes_up():
    """Мяч летит вверх — предсказывать нечего, держимся под ним."""
    b = brain()
    b.step(0.00, 'play', FIELD, PADDLE, (600.0, 500.0))
    act = b.step(0.05, 'play', FIELD, PADDLE, (610.0, 460.0))
    assert act.move == 1                       #мяч правее платформы


def test_prediction_accounts_for_wall_bounce():
    """Летит вправо-вниз у самой стены: цель должна быть ЛЕВЕЕ точки отскока."""
    b = brain()
    b.step(0.00, 'play', FIELD, PADDLE, (640.0, 700.0))
    act = b.step(0.05, 'play', FIELD, PADDLE, (660.0, 720.0))
    assert act.move in (-1, 0, 1)
    assert b.target is not None
    assert b.target <= FIELD[2] - PADDLE[1]    #в поле, с учётом ширины


def test_space_pressed_when_ball_missing():
    b = brain(lost_ball_sec=0.5)
    b.step(0.0, 'play', FIELD, PADDLE, None)
    act = b.step(1.0, 'play', FIELD, PADDLE, None)
    assert act.space is True
    assert 'бросок' in act.note


def test_no_space_spam():
    """Пробел жмётся сразу, потом молчит до истечения интервала."""
    b = brain(lost_ball_sec=0.2, press_gap=1.0)
    first = b.step(0.0, 'play', FIELD, PADDLE, None)
    second = b.step(0.5, 'play', FIELD, PADDLE, None)
    assert first.space and not second.space
    assert b.step(1.2, 'play', FIELD, PADDLE, None).space is True


def test_goes_to_centre_while_waiting():
    b = brain(lost_ball_sec=0.2, press_gap=99.0)
    b.step(0.0, 'play', FIELD, PADDLE, None)
    act = b.step(0.5, 'play', FIELD, PADDLE, None)
    assert act.move == 0                       #платформа уже в центре (400)
    far = (150.0, 60.0, 860.0)
    act2 = b.step(0.6, 'play', FIELD, far, None)
    assert act2.move == 1                      #из левого края едем к центру


def test_no_field_no_action():
    b = brain()
    act = b.step(0.0, 'play', None, None, None)
    assert act.move == 0 and not act.space


# --- пауза и конец игры -----------------------------------------------------

def test_dim_presses_f9_first():
    b = brain()
    act = b.step(0.0, 'dim', FIELD, PADDLE, None)
    assert act.f9 is True


def test_dim_clicks_again_button_when_found():
    b = brain()
    act = b.step(0.0, 'dim', FIELD, PADDLE, None, {'again': (480.0, 820.0)})
    assert act.click == (480.0, 820.0)
    assert 'сыграть' in act.note


def test_dim_falls_back_to_space():
    b = brain(press_gap=0.0)
    b.step(0.0, 'dim', FIELD, PADDLE, None)
    act = b.step(2.0, 'dim', FIELD, PADDLE, None)
    assert act.space is True


# --- меню -------------------------------------------------------------------

def test_menu_clicks_play_button():
    b = brain()
    act = b.step(0.0, 'other', FIELD, PADDLE, None, {'play': (480.0, 850.0)})
    assert act.click == (480.0, 850.0)


def test_menu_without_buttons_waits_then_presses_space():
    b = brain(press_gap=0.0)
    first = b.step(0.0, 'other', FIELD, PADDLE, None)
    assert not first.space and not first.click
    later = b.step(3.0, 'other', FIELD, PADDLE, None)
    assert later.space is True


def test_state_change_resets_timer():
    b = brain(press_gap=0.0)
    b.step(0.0, 'other', FIELD, PADDLE, None)
    b.step(5.0, 'play', FIELD, PADDLE, (400.0, 300.0))
    act = b.step(5.1, 'other', FIELD, PADDLE, None)
    assert not act.space                       #таймер экрана пошёл заново


def test_dim_falls_back_to_click_when_stuck():
    """Шаблона кнопки нет, F9 и пробел не помогли -> клик по известной точке."""
    b = brain(press_gap=0.0, fallbacks={'again': (480.0, 774.0)},
              fallback_after=3.0)
    b.step(0.0, 'dim', FIELD, PADDLE, None)
    assert b.step(2.0, 'dim', FIELD, PADDLE, None).click is None
    act = b.step(4.0, 'dim', FIELD, PADDLE, None)
    assert act.click == (480.0, 774.0)


def test_menu_falls_back_to_click_when_stuck():
    b = brain(press_gap=0.0, fallbacks={'play': (480.0, 850.0)},
              fallback_after=3.0)
    b.step(0.0, 'other', FIELD, PADDLE, None)
    act = b.step(4.0, 'other', FIELD, PADDLE, None)
    assert act.click == (480.0, 850.0)


def test_template_button_wins_over_fallback():
    b = brain(fallbacks={'play': (1.0, 1.0)})
    act = b.step(0.0, 'other', FIELD, PADDLE, None, {'play': (480.0, 850.0)})
    assert act.click == (480.0, 850.0)


def test_expected_ball_extrapolates():
    b = brain()
    b.step(0.0, 'play', FIELD, PADDLE, (300.0, 300.0))
    b.step(0.1, 'play', FIELD, PADDLE, (320.0, 340.0))
    got = b.expected_ball(0.2)
    assert got is not None
    assert abs(got[0] - 340.0) < 1.0 and abs(got[1] - 380.0) < 1.0


def test_expected_ball_without_track():
    assert brain().expected_ball(0.0) is None


def test_reach_time():
    b = brain(paddle_speed=200.0)
    assert b.reach_time(100.0, 300.0) == 1.0
    assert b.reach_time(100.0, None) is None
