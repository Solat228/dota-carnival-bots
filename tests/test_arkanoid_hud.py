# -*- coding: utf-8 -*-
"""Чтение HUD арканоида и склейка бота (без запущенной игры)."""
import os
import sys

import cv2
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import panel as panelmod
from arkanoid import hud, vision

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def _tesseract_ready():
    #Как и бот: сначала путь из config.json (машинный, вне репозитория).
    exe = config.find_tesseract(config.load().get('tesseract', ''))
    return bool(exe) and os.path.exists(exe)


def panel_of(name):
    full = cv2.imread(os.path.join(FIXTURES, name))
    x, y, w, h = panelmod.detect_panel(full)
    return full[y:y + h, x:x + w]


def test_hud_digits_prepares_image():
    img = panel_of('boot_play.jpg')
    prep = vision.hud_digits(img, vision.HUD_LEVEL)
    assert prep is not None
    assert prep.shape[0] > 30 and prep.max() == 255      #белый фон есть


def test_hud_digits_degenerate():
    assert vision.hud_digits(None, vision.HUD_LEVEL) is None


@pytest.mark.skipif(not _tesseract_ready(), reason='нет tesseract.exe')
def test_read_status_on_real_frame():
    """На кадре первого уровня: уровень 1, счёт 0."""
    img = panel_of('boot_play.jpg')
    level, score = hud.read_status(img)
    assert level == 1
    assert score == 0


@pytest.mark.skipif(not _tesseract_ready(), reason='нет tesseract.exe')
def test_read_number_out_of_frame():
    img = panel_of('boot_play.jpg')
    #пустая область поля — цифр там нет
    assert hud.read_number(img, (300, 400, 60, 30)) is None


def test_count_lives_finds_boots():
    img = panel_of('boot_play.jpg')
    got = vision.count_lives(img)
    assert got is not None and got >= 1
