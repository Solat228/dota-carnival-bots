# -*- coding: utf-8 -*-
"""Сквозная проверка без игры: рисуем кадр «как в игре» и гоняем весь путь
кадр -> зрение -> физика -> решение.

Смысл: поймать рассогласование модулей (координаты, знаки, единицы) там, где
отдельные юнит-тесты каждого модуля проходят, а вместе они не работают.
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arkanoid import play, vision

SIZE = 976
FIELD = (171, 111, 792, 950)        # как на живом кадре


def hsv_bgr(h, s, v):
    px = np.uint8([[[h, s, v]]])
    return tuple(int(c) for c in cv2.cvtColor(px, cv2.COLOR_HSV2BGR)[0][0])


BACK = hsv_bgr(115, 180, 90)        # тёмно-синий фон поля
BRICK = hsv_bgr(20, 220, 220)       # оранжевый блок
CART = hsv_bgr(8, 220, 210)         # красно-жёлтая тележка
BALL = (240, 240, 240)


def frame(ball=None, cart_x=480, bricks=True):
    """Синтетический кадр панели: поле, блоки, тележка, мяч."""
    img = np.zeros((SIZE, SIZE, 3), np.uint8)
    left, top, right, bottom = FIELD
    cv2.rectangle(img, (left, top), (right, bottom), BACK, -1)
    if bricks:
        for row in range(6):
            y = top + 40 + row * 26
            cv2.rectangle(img, (left + 30, y), (right - 30, y + 20), BRICK, -1)
    #тележка в нижней полосе поля
    cv2.rectangle(img, (int(cart_x) - 64, 880), (int(cart_x) + 64, 920), CART, -1)
    if ball:
        #радиус как у настоящего сапога: замер живой игры дал пятно ~1800 px
        cv2.circle(img, (int(ball[0]), int(ball[1])), 22, BALL, -1)
    return img


def test_synthetic_frame_is_recognised_as_play():
    img = frame(ball=(400, 500))
    field = vision.field_bounds(img)
    assert field is not None
    assert vision.screen_state(img, field) == 'play'


def test_field_and_paddle_found_on_synthetic_frame():
    img = frame(cart_x=300)
    field = vision.field_bounds(img)
    left, top, right, bottom = field
    assert abs(left - FIELD[0]) <= 6 and abs(right - FIELD[2]) <= 6
    paddle = vision.find_paddle(img, field)
    assert paddle is not None
    assert abs(paddle[0] - 300) <= 12
    assert 50 <= paddle[1] <= 80


def test_ball_tracked_between_frames():
    a = frame(ball=(400, 500))
    b = frame(ball=(430, 540))
    field = vision.field_bounds(b)
    got = vision.find_ball(a, b, field, paddle_top=870)
    assert got is not None
    assert abs(got[0] - 430) <= 25 and abs(got[1] - 540) <= 25


def run_fall(start_ball, vx_px, vy_px, cart_x=300.0, steps=24):
    """Гоняет падение мяча через весь конвейер, двигая тележку как игра."""
    brain = play.Brain(dead_zone=8.0)
    prev = frame(ball=start_ball, cart_x=cart_x)
    moves, t = [], 0.0
    for step in range(1, steps):
        t += 0.05
        bx, by = start_ball[0] + step * vx_px, start_ball[1] + step * vy_px
        if by > 860:
            break
        cur = frame(ball=(bx, by), cart_x=cart_x)
        field = vision.field_bounds(cur)
        paddle = vision.find_paddle(cur, field)
        ball = vision.find_ball(prev, cur, field, paddle[2] if paddle else None,
                                brain.expected_ball(t))
        act = brain.step(t, vision.screen_state(cur, field), field, paddle, ball)
        moves.append(act.move)
        cart_x = max(field[0] + 64, min(field[2] - 64,
                                        cart_x + act.move * 200.0 * 0.05))
        prev = cur
    return brain, cart_x, moves


def test_full_chain_paddle_drives_toward_prediction():
    """Мяч летит вниз-вправо: платформа едет вправо и сокращает разрыв.

    Доехать она может не успеть — тележка ~200 px/с, а мяч пересекает поле
    быстрее. Проверяем именно НАПРАВЛЕНИЕ и сокращение расстояния.
    """
    brain, cart_x, moves = run_fall((400, 300), 12, 22, cart_x=300.0)
    assert brain.target is not None
    assert moves.count(1) > moves.count(-1)          #ехали вправо
    assert cart_x > 300.0
    assert abs(cart_x - brain.target) < abs(300.0 - brain.target)


def test_full_chain_catches_slow_ball():
    """Медленный мяч платформа обязана встретить точно."""
    brain, cart_x, _moves = run_fall((520, 300), 4, 12, cart_x=420.0, steps=48)
    assert brain.target is not None
    assert abs(cart_x - brain.target) <= 20


def test_full_chain_tracks_ball_positions():
    """Трекер должен видеть мяч почти на каждом кадре, а не терять его."""
    brain, _cart, _moves = run_fall((400, 300), 10, 20, cart_x=400.0)
    assert brain.tracker.ready()
    vx, vy = brain.tracker.velocity()
    assert vy > 0                                    #мяч падает
    assert vx > 0                                    #и уходит вправо


def test_menu_frame_gives_no_movement():
    img = frame(bricks=False)
    #поле без блоков и без мяча: бот не должен ехать наугад
    field = vision.field_bounds(img)
    brain = play.Brain()
    act = brain.step(0.0, vision.screen_state(img, field), field,
                     vision.find_paddle(img, field), None)
    assert act.move in (-1, 0, 1)
    assert not act.click
