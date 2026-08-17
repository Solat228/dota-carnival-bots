# -*- coding: utf-8 -*-
"""Устойчивость арканоида: находки независимого ревью 2026-08-17.

Каждый тест закрывает конкретный сценарий залипания или опасного поведения,
который ревьюер воспроизвёл симуляцией.
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boot
from arkanoid import physics, vision
from arkanoid.play import Brain

FIELD = (100.0, 100.0, 700.0, 950.0)
PADDLE = (400.0, 60.0, 860.0)


# --- пауза не должна становиться ловушкой -----------------------------------

def test_f9_is_retried_not_only_once():
    """Пауза от потери фокуса снимается только F9 — пробовать надо повторно.

    Было: F9 жался лишь первые 1.5 с после входа в 'dim', дальше бот вечно
    кликал мимо и не мог снять паузу.
    """
    b = Brain()
    seen = []
    t = 0.0
    while t < 12.0:
        act = b.step(t, 'dim', FIELD, PADDLE, None, {})
        if act.f9:
            seen.append(t)
        t += 0.3
    assert len(seen) >= 3, f'F9 нажат всего {len(seen)} раз(а): {seen}'
    assert max(seen) > 5.0, 'после 5 секунд F9 больше не пробуется'


def test_play_button_used_on_dim_screen():
    """Найденная кнопка «Играть» на затемнённом экране должна нажиматься."""
    b = Brain()
    act = b.step(0.0, 'dim', FIELD, PADDLE, None, {'play': (480.0, 848.0)})
    assert act.click == (480.0, 848.0)


def test_state_flicker_does_not_reset_timers():
    """Мигание dim<->other не должно обнулять таймеры фолбэков.

    Было: на мигании ни один фолбэк не наступал, бот бесконечно жал F9 и сам
    себе переключал паузу.
    """
    b = Brain(press_gap=0.0, fallbacks={'again': (480.0, 774.0)}, fallback_after=3.0)
    acts = []
    t = 0.0
    while t < 12.0:
        state = 'dim' if int(t * 2) % 2 == 0 else 'other'
        acts.append(b.step(t, state, FIELD, PADDLE, None, {}))
        t += 0.25
    notes = [a.note for a in acts]
    assert any('клик' in n for n in notes), f'фолбэк так и не сработал: {set(notes)}'


def test_stable_state_still_switches():
    """Гистерезис не должен мешать нормальной смене экрана."""
    b = Brain()
    b.step(0.0, 'other', FIELD, PADDLE, None, {})
    for t in (0.1, 0.5, 1.0):
        b.step(t, 'play', FIELD, PADDLE, None, {}, hint=True)
    assert b.last_state == 'play'


# --- зажатая клавиша ---------------------------------------------------------

class FakeKeys:
    def __init__(self):
        self.held = 0
        self.released = 0

    def hold(self, direction):
        self.held = direction

    def release_all(self):
        self.held = 0
        self.released += 1


def test_lost_frames_release_keys():
    """Кадры перестали приходить -> клавишу надо отпустить, а не держать вечно.

    Иначе A или D остаётся зажатой на уровне системы и ломает ввод везде.
    """
    bot = boot.Bot.__new__(boot.Bot)          # без запуска потоков
    bot.keys = FakeKeys()
    bot.keys.hold(-1)
    bot.no_frame_since = 0.0
    bot.region = [0, 0, 100, 100]
    bot._grab = lambda: None
    assert bot.tick(100.0) is None            # первый пропуск — просто ждём
    assert bot.keys.held == -1
    assert bot.tick(103.0) is None            # прошло больше двух секунд
    assert bot.keys.held == 0, 'клавиша осталась зажатой'
    assert bot.region is None, 'панель не помечена на переискивание'


# --- мелкие, но реальные ошибки ---------------------------------------------

def test_paddle_top_zero_is_not_treated_as_missing():
    """paddle_top == 0 — валидная координата, а не «платформы нет»."""
    img = np.zeros((400, 400, 3), np.uint8)
    other = img.copy()
    cv2.circle(other, (200, 200), 22, (250, 250, 250), -1)
    field = (0, 0, 399, 399)
    #с paddle_top=0 полоса поиска пустая -> мяч найтись не должен
    assert vision.find_ball(img, other, field, paddle_top=0) is None
    #а с полноценной нижней границей — находится
    assert vision.find_ball(img, other, field, paddle_top=399) is not None


def test_vertical_flight_is_smoothed():
    """Строго вертикальный полёт (vx == 0) — не отскок, сглаживание работает."""
    trk = physics.BallTracker()
    trk.update(0.00, 300.0, 100.0)
    trk.update(0.02, 300.0, 108.0)
    trk.update(0.04, 300.0, 118.0)
    vx, vy = trk.velocity()
    assert vx == 0.0
    assert abs(vy - 450.0) < 1.0          #среднее по двум парам (400 и 500)


def test_real_bounce_still_breaks_smoothing():
    trk = physics.BallTracker()
    trk.update(0.00, 300.0, 100.0)
    trk.update(0.02, 320.0, 120.0)
    trk.update(0.04, 300.0, 140.0)
    vx, _vy = trk.velocity()
    assert abs(vx - (-1000.0)) < 1.0


# --- конфиг ------------------------------------------------------------------

def test_config_reads_flat_keys(tmp_path, monkeypatch):
    """Ключ в корне config.json должен работать, а не игнорироваться молча."""
    import config
    path = tmp_path / 'config.json'
    path.write_text('{"loop_fps": 33, "window_title": "Dota Test"}', encoding='utf-8')
    monkeypatch.setattr(config, 'CONFIG_PATH', str(path))
    monkeypatch.setattr(config, 'load_raw', lambda p=None: config.json.load(
        open(str(path), encoding='utf-8')))
    cfg = boot.load_cfg()
    assert cfg['loop_fps'] == 33
    assert cfg['window_title'] == 'Dota Test'


def test_arkanoid_section_wins_over_flat(tmp_path, monkeypatch):
    import config
    path = tmp_path / 'config.json'
    path.write_text('{"loop_fps": 33, "arkanoid": {"loop_fps": 77}}', encoding='utf-8')
    monkeypatch.setattr(config, 'CONFIG_PATH', str(path))
    monkeypatch.setattr(config, 'load_raw', lambda p=None: config.json.load(
        open(str(path), encoding='utf-8')))
    assert boot.load_cfg()['loop_fps'] == 77


def test_typer_defaults_do_not_leak_into_arkanoid(tmp_path, monkeypatch):
    """У печаталки loop_fps=25 — он не должен подменять 120 у арканоида."""
    import config
    path = tmp_path / 'config.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(config, 'CONFIG_PATH', str(path))
    monkeypatch.setattr(config, 'load_raw', lambda p=None: {})
    assert boot.load_cfg()['loop_fps'] == boot.DEFAULTS['loop_fps']


def test_ball_near_wall_is_ignored_but_reachable():
    """Отступ от стен: мерцание рамки — не мяч, но настоящий мяч рядом виден.

    Дыра в покрытии (мутационная проверка): обнуление BALL_WALL_INSET не роняло
    ни одного теста, хотя без отступа бот ловил ложные пятна у самой рамки.
    """
    img = np.zeros((980, 980, 3), np.uint8)
    field = (172, 111, 791, 950)
    left, right = field[0], field[2]
    near = img.copy()
    cv2.circle(near, (left + 4, 700), 22, (250, 250, 250), -1)
    assert vision.find_ball(img, near, field, paddle_top=900) is None, \
        'пятно вплотную к стене принято за мяч'
    inside = img.copy()
    cv2.circle(inside, (left + 60, 700), 22, (250, 250, 250), -1)
    assert vision.find_ball(img, inside, field, paddle_top=900) is not None
    near_right = img.copy()
    cv2.circle(near_right, (right - 4, 700), 22, (250, 250, 250), -1)
    assert vision.find_ball(img, near_right, field, paddle_top=900) is None


def test_best_suffix_below_threshold_returns_nothing():
    """Мусорное чтение не должно давать «похожий» суффикс.

    Дыра в покрытии: снятие порога min_ratio не роняло тестов, а бот при этом
    начинал допечатывать выдуманный хвост вместо того, чтобы промолчать.
    """
    import words
    assert words.best_suffix('DAS', 'ZEUS') == ('', 0.0)
    assert words.best_suffix('M', 'HEADDRESS') == ('', 0.0)
    assert words.best_suffix('QQQ', 'BLOODSTONE') == ('', 0.0)
    #а честный хвост по-прежнему принимается
    got, score = words.best_suffix('EUS', 'ZEUS')
    assert got == 'EUS' and score >= 0.9


def test_window_title_is_in_defaults():
    """Ключ читается кодом — значит должен быть виден в дефолтах."""
    assert 'window_title' in boot.DEFAULTS
