# -*- coding: utf-8 -*-
"""Прицеливание краем платформы: посылать мяч туда, где остались блоки."""
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import panel as panelmod
from arkanoid import physics, vision
from arkanoid.play import Brain

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
LEFT, RIGHT = 100.0, 700.0
FIELD = (LEFT, 100.0, RIGHT, 950.0)
PADDLE = (400.0, 60.0, 860.0)


# --- чистая формула ---------------------------------------------------------

def test_offset_sends_ball_toward_bricks_on_left():
    """Блоки слева -> принимаем ЛЕВЫМ краем (положительное смещение)."""
    got = physics.aim_offset_for(hit_x=400.0, brick_x=200.0, left=LEFT, right=RIGHT)
    assert got > 0


def test_offset_sends_ball_toward_bricks_on_right():
    got = physics.aim_offset_for(hit_x=300.0, brick_x=600.0, left=LEFT, right=RIGHT)
    assert got < 0


def test_offset_zero_when_bricks_overhead():
    assert physics.aim_offset_for(400.0, 400.0, LEFT, RIGHT) == 0.0


def test_offset_is_capped():
    got = physics.aim_offset_for(699.0, 101.0, LEFT, RIGHT, strength=0.7)
    assert abs(got) <= 0.7


def test_offset_without_data():
    assert physics.aim_offset_for(None, 300.0, LEFT, RIGHT) == 0.0
    assert physics.aim_offset_for(300.0, None, LEFT, RIGHT) == 0.0


# --- решение мозга ----------------------------------------------------------

def feed(b, ball_a, ball_b, brick_x=None, dt=0.05):
    b.step(0.0, 'play', FIELD, PADDLE, ball_a, brick_x=brick_x)
    return b.step(dt, 'play', FIELD, PADDLE, ball_b, brick_x=brick_x)


def test_aims_with_edge_when_there_is_time():
    """Мяч падает медленно и близко — есть запас, целимся краем."""
    b = Brain(paddle_speed=400.0)
    feed(b, (410.0, 300.0), (410.0, 320.0), brick_x=150.0)
    centre = Brain(paddle_speed=400.0)
    feed(centre, (410.0, 300.0), (410.0, 320.0))
    assert b.target is not None and centre.target is not None
    #с блоками слева платформа встаёт ПРАВЕЕ, чтобы принять мяч левым краем
    assert b.target > centre.target


def test_keeps_centre_when_barely_reachable():
    """Мяч валится быстро и далеко — не до красоты, принимаем центром."""
    b = Brain(paddle_speed=60.0)
    feed(b, (650.0, 700.0), (660.0, 800.0), brick_x=120.0)
    centre = Brain(paddle_speed=60.0)
    feed(centre, (650.0, 700.0), (660.0, 800.0))
    assert b.target == centre.target


def test_no_bricks_means_centre():
    b = Brain(paddle_speed=400.0)
    feed(b, (410.0, 300.0), (410.0, 320.0), brick_x=None)
    centre = Brain(paddle_speed=400.0)
    feed(centre, (410.0, 300.0), (410.0, 320.0))
    assert b.target == centre.target


# --- центр масс блоков на настоящем кадре -----------------------------------

def test_brick_centroid_on_real_frame():
    full = cv2.imread(os.path.join(FIXTURES, 'boot_play.jpg'))
    x, y, w, h = panelmod.detect_panel(full)
    img = full[y:y + h, x:x + w]
    field = vision.field_bounds(img)
    got = vision.brick_centroid(img, field)
    assert got is not None
    cx, cy = got
    #на первом уровне кладка симметрична: центр масс близок к середине поля
    assert abs(cx - (field[0] + field[2]) / 2.0) < 60
    assert field[1] < cy < field[3]


def test_brick_centroid_none_when_no_bricks():
    full = cv2.imread(os.path.join(FIXTURES, 'boot_menu.jpg'))
    x, y, w, h = panelmod.detect_panel(full)
    img = full[y:y + h, x:x + w]
    assert vision.brick_centroid(img, vision.field_bounds(img)) is None


def test_brick_centroid_degenerate():
    assert vision.brick_centroid(None, FIELD) is None
