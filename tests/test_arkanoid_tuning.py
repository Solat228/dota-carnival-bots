# -*- coding: utf-8 -*-
"""Доводка после живых прогонов: сглаживание скорости и мягкий добор мяча."""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import panel as panelmod
from arkanoid import physics, vision

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def panel_of(name):
    full = cv2.imread(os.path.join(FIXTURES, name))
    x, y, w, h = panelmod.detect_panel(full)
    return full[y:y + h, x:x + w]


# --- каменные уровни --------------------------------------------------------

def test_stone_level_is_recognised_as_play():
    """С 4-го уровня кладка каменная: оранжевого почти нет, но игра идёт.

    Регресс живого прогона: бот принял 4-й уровень за меню (счёт 3085 замер)
    и вместо игры щёлкал по экрану, пока я не посмотрел скриншот.
    """
    img = cv2.imread(os.path.join(FIXTURES, 'boot_stone.png'))
    assert img is not None
    field = vision.field_bounds(img)
    assert vision.brick_fraction(img, field) < 0.02      #оранжевого мало
    assert vision.find_paddle(img, field) is not None    #а тележка на месте
    assert vision.screen_state(img, field) == 'play'


def test_menu_still_not_play_with_cart_rule():
    """Правило про тележку не должно записывать меню в игру."""
    img = panel_of('boot_menu.jpg')
    assert vision.screen_state(img, vision.field_bounds(img)) == 'other'


def test_game_over_still_not_play():
    img = cv2.imread(os.path.join(FIXTURES, 'boot_over.png'))
    field = vision.field_bounds(img)
    assert vision.screen_state(img, field) != 'play'


# --- размер мяча ------------------------------------------------------------

def test_spark_near_prediction_does_not_steal_track():
    """Искра от сбитого блока рядом с прогнозом не должна становиться мячом.

    Замер живой игры: пятно сапога 1700..2300 px. Мелкие вспышки отсекаются
    по площади — иначе трек перехватывался и платформа ехала не туда.
    """
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    a = img.copy()
    b = img.copy()
    cv2.circle(b, (500, 600), 4, (250, 250, 250), -1)     #искра ~50 px
    got = vision.find_ball(a, b, field, paddle_top=860, expect_pos=(505, 605))
    assert got is None


def test_real_size_ball_is_taken():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    a = img.copy()
    b = img.copy()
    cv2.circle(b, (500, 600), 22, (250, 250, 250), -1)    #пятно ~1500 px
    got = vision.find_ball(a, b, field, paddle_top=860, expect_pos=(505, 605))
    assert got is not None and abs(got[0] - 500) < 30


def test_huge_blob_is_rejected():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    a = img.copy()
    b = img.copy()
    cv2.rectangle(b, (300, 500), (420, 620), (250, 250, 250), -1)
    assert vision.find_ball(a, b, field, paddle_top=860) is None


# --- скорость ---------------------------------------------------------------

def test_velocity_smooths_noise():
    """Дрожание детекта на пиксель не должно скакать в скорости."""
    trk = physics.BallTracker()
    trk.update(0.00, 100.0, 100.0)
    trk.update(0.02, 104.0, 108.0)
    trk.update(0.04, 107.0, 116.0)          #на 1 px меньше «идеала»
    vx, vy = trk.velocity()
    rough_x, _ = trk._pair_speed(trk.samples[-2], trk.samples[-1])
    assert abs(vx - 175.0) < 30.0           #среднее по двум парам
    assert abs(vx - rough_x) > 1.0          #и это НЕ голая последняя пара
    assert vy > 0


def test_velocity_does_not_smooth_across_bounce():
    """После отскока от стены усреднять нельзя — направление сменилось."""
    trk = physics.BallTracker()
    trk.update(0.00, 300.0, 100.0)
    trk.update(0.02, 320.0, 120.0)          #летел вправо
    trk.update(0.04, 300.0, 140.0)          #отскочил влево
    vx, _vy = trk.velocity()
    assert vx < 0
    assert abs(vx - (-1000.0)) < 1.0        #ровно последняя пара, без среднего


def test_velocity_ignores_big_jump_in_speed():
    trk = physics.BallTracker()
    trk.update(0.00, 100.0, 100.0)
    trk.update(0.02, 102.0, 104.0)          #медленно
    trk.update(0.04, 130.0, 150.0)          #резко быстрее (сбил блок)
    vx, _vy = trk.velocity()
    assert vx > 1000.0                      #берём свежую пару, не среднее


def test_velocity_two_points_still_works():
    trk = physics.BallTracker()
    trk.update(0.0, 100.0, 100.0)
    trk.update(0.1, 120.0, 140.0)
    vx, vy = trk.velocity()
    assert abs(vx - 200.0) < 1e-6 and abs(vy - 400.0) < 1e-6


def test_velocity_smoothing_can_be_disabled():
    trk = physics.BallTracker()
    trk.update(0.00, 100.0, 100.0)
    trk.update(0.02, 104.0, 108.0)
    trk.update(0.04, 107.0, 116.0)
    raw = trk.velocity(smooth=False)
    assert abs(raw[0] - 150.0) < 1e-6


# --- мягкий добор мяча ------------------------------------------------------

def faint_pair(delta=20):
    """Пара кадров, где мяч еле-еле отличается от фона."""
    img = panel_of('boot_play.jpg')
    a = img.copy()
    b = img.copy()
    patch = b[600:626, 400:426].astype(np.int16) + delta
    b[600:626, 400:426] = np.clip(patch, 0, 255).astype(np.uint8)
    return a, b, vision.field_bounds(img)


def test_faint_ball_found_by_expectation():
    """Слабый контраст: по прогнозу мяч должен находиться."""
    a, b, field = faint_pair(delta=20)
    got = vision.find_ball(a, b, field, paddle_top=860, expect_pos=(413, 613))
    assert got is not None
    assert abs(got[0] - 413) < 60 and abs(got[1] - 613) < 60


def test_faint_ball_not_invented_far_from_expectation():
    """Мягкий добор работает только вокруг прогноза, а не по всему полю."""
    a, b, field = faint_pair(delta=20)
    got = vision.find_ball(a, b, field, paddle_top=860, expect_pos=(250, 250))
    assert got is None


def test_strong_ball_still_found_without_expectation():
    img = panel_of('boot_play.jpg')
    a = img.copy()
    b = img.copy()
    cv2.circle(b, (500, 700), 13, (245, 245, 245), -1)
    got = vision.find_ball(a, b, field=vision.field_bounds(img), paddle_top=860)
    assert got is not None and abs(got[0] - 500) < 30


def test_identical_frames_still_give_nothing():
    img = panel_of('boot_play.jpg')
    field = vision.field_bounds(img)
    assert vision.find_ball(img, img, field, 860, expect_pos=(400, 600)) is None
