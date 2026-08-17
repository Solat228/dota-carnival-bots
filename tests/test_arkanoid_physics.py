# -*- coding: utf-8 -*-
"""Предсказание точки падения сапога и решение о движении платформы."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arkanoid import physics

LEFT, RIGHT = 100.0, 500.0          # поле шириной 400
PADDLE_Y = 900.0


# --- отражение координаты от стен ------------------------------------------

def test_fold_inside_field_unchanged():
    assert physics.fold(300.0, LEFT, RIGHT) == 300.0


def test_fold_one_bounce_right():
    #перелёт на 50 за правую стену -> 50 обратно внутрь
    assert physics.fold(550.0, LEFT, RIGHT) == 450.0


def test_fold_one_bounce_left():
    assert physics.fold(50.0, LEFT, RIGHT) == 150.0


def test_fold_two_bounces():
    #от левой стены пролетел 850 при ширине 400: 400 вправо, 400 влево, 50 вправо
    assert physics.fold(950.0, LEFT, RIGHT) == 150.0


def test_fold_exactly_on_walls():
    assert physics.fold(LEFT, LEFT, RIGHT) == LEFT
    assert physics.fold(RIGHT, LEFT, RIGHT) == RIGHT


def test_fold_degenerate_field():
    assert physics.fold(300.0, 200.0, 200.0) == 200.0


# --- предсказание -----------------------------------------------------------

def test_predict_straight_down():
    got = physics.predict_x(300.0, 100.0, 0.0, 400.0, LEFT, RIGHT, PADDLE_Y)
    assert got == 300.0


def test_predict_diagonal_no_bounce():
    #летит вниз-вправо: 800 px вниз за 2 с, вправо 100 px/с -> +200
    got = physics.predict_x(200.0, 100.0, 100.0, 400.0, LEFT, RIGHT, PADDLE_Y)
    assert abs(got - 400.0) < 1e-6


def test_predict_with_wall_bounce():
    #без стен получилось бы 600 -> отражение даёт 400
    got = physics.predict_x(200.0, 100.0, 200.0, 400.0, LEFT, RIGHT, PADDLE_Y)
    assert abs(got - 400.0) < 1e-6


def test_predict_ball_going_up_is_unknown():
    assert physics.predict_x(300.0, 500.0, 50.0, -300.0, LEFT, RIGHT, PADDLE_Y) is None


def test_predict_ball_below_line_is_unknown():
    assert physics.predict_x(300.0, 950.0, 0.0, 300.0, LEFT, RIGHT, PADDLE_Y) is None


def test_predict_without_velocity():
    assert physics.predict_x(300.0, 100.0, 0.0, None, LEFT, RIGHT, PADDLE_Y) is None


def test_time_to_line():
    assert physics.time_to_line(100.0, 400.0, PADDLE_Y) == 2.0
    assert physics.time_to_line(100.0, -400.0, PADDLE_Y) is None


# --- платформа --------------------------------------------------------------

def test_clamp_paddle_keeps_it_inside():
    assert physics.clamp_paddle(LEFT, 40.0, LEFT, RIGHT) == LEFT + 40.0
    assert physics.clamp_paddle(RIGHT, 40.0, LEFT, RIGHT) == RIGHT - 40.0
    assert physics.clamp_paddle(300.0, 40.0, LEFT, RIGHT) == 300.0


def test_clamp_paddle_wider_than_field():
    assert physics.clamp_paddle(300.0, 500.0, LEFT, RIGHT) == 300.0


def test_aim_center_none_when_unknown():
    assert physics.aim_center(None, 40.0, LEFT, RIGHT) is None


def test_aim_with_offset_shifts_paddle():
    #принять мяч ЛЕВЫМ краем: центр платформы правее точки падения
    got = physics.aim_with_offset(300.0, 40.0, LEFT, RIGHT, 1.0)
    assert got == 340.0
    got = physics.aim_with_offset(300.0, 40.0, LEFT, RIGHT, -1.0)
    assert got == 260.0


def test_aim_offset_is_clamped_to_field():
    #у правой стены смещение вправо упирается в край поля
    got = physics.aim_with_offset(RIGHT - 10.0, 40.0, LEFT, RIGHT, 1.0)
    assert got == RIGHT - 40.0
    #а смещение влево там же клампа не требует
    assert physics.aim_with_offset(RIGHT - 10.0, 40.0, LEFT, RIGHT, -1.0) == 450.0


def test_move_decision():
    assert physics.move_decision(100.0, 300.0) == 1
    assert physics.move_decision(300.0, 100.0) == -1
    assert physics.move_decision(300.0, 302.0) == 0        #мёртвая зона
    assert physics.move_decision(300.0, None) == 0
    assert physics.move_decision(None, 300.0) == 0


def test_press_time_scales_with_distance():
    fast = physics.press_time(20.0, 200.0)
    slow = physics.press_time(200.0, 200.0)
    assert slow > fast
    assert physics.press_time(10000.0, 200.0) <= 0.35      #ограничен сверху
    assert physics.press_time(1.0, 0.0) == 0.02            #скорость неизвестна


# --- трекер мяча ------------------------------------------------------------

def test_tracker_velocity():
    trk = physics.BallTracker()
    trk.update(0.0, 100.0, 100.0)
    trk.update(0.1, 120.0, 140.0)
    vx, vy = trk.velocity()
    assert abs(vx - 200.0) < 1e-6
    assert abs(vy - 400.0) < 1e-6


def test_tracker_needs_two_samples():
    trk = physics.BallTracker()
    assert not trk.ready()
    trk.update(0.0, 100.0, 100.0)
    assert not trk.ready()
    trk.update(0.05, 105.0, 110.0)
    assert trk.ready()


def test_tracker_rejects_teleport():
    """Мяч «прыгнул» через полполя — это новый трек, а не скорость 5000 px/с."""
    trk = physics.BallTracker(jump_limit=100.0)
    trk.update(0.0, 100.0, 100.0)
    assert not trk.update(0.05, 400.0, 100.0)
    assert not trk.ready()


def test_tracker_restarts_after_pause():
    trk = physics.BallTracker(stale_sec=0.2)
    trk.update(0.0, 100.0, 100.0)
    assert not trk.update(1.0, 105.0, 110.0)     #слишком давно — трек заново


def test_tracker_position_and_reset():
    trk = physics.BallTracker()
    trk.update(0.0, 100.0, 200.0)
    assert trk.position() == (100.0, 200.0)
    trk.reset()
    assert trk.position() == (None, None)


def test_tracker_ignores_none():
    trk = physics.BallTracker()
    assert not trk.update(0.0, None, None)


def test_tracker_keeps_short_history():
    trk = physics.BallTracker()
    for i in range(10):
        trk.update(i * 0.05, 100.0 + i, 100.0 + i)
    assert len(trk.samples) <= 4
