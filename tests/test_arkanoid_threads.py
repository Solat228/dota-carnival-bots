# -*- coding: utf-8 -*-
"""Фоновые потоки бота: захват кадров и OCR HUD.

Зачем потоки (замеры 2026-08-17): BitBlt стоит 16.7 мс независимо от размера
(ожидание кадра монитора), а один проход OCR по HUD — 322 мс. В главном цикле
это давало 28 кадров/с и треть секунды слепоты каждую секунду.
"""
import os
import sys
import time

import cv2
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boot
import capture
import config
import panel as panelmod

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def _tesseract_ready():
    #Как и бот: сначала путь из config.json (машинный, вне репозитория).
    exe = config.find_tesseract(config.load().get('tesseract', ''))
    return bool(exe) and os.path.exists(exe)


def panel_of(name):
    full = cv2.imread(os.path.join(FIXTURES, name))
    x, y, w, h = panelmod.detect_panel(full)
    return full[y:y + h, x:x + w]


# --- захват -----------------------------------------------------------------

def test_grabber_reuses_objects_and_survives_resize():
    g = capture.Grabber()
    try:
        a = g.grab(0, 0, 120, 80)
        b = g.grab(0, 0, 120, 80)
        assert a is not None and a.shape == (80, 120, 3)
        assert b is not None
        c = g.grab(0, 0, 200, 150)         #смена размера -> пересоздание
        assert c is not None and c.shape == (150, 200, 3)
    finally:
        g.close()


def test_grabber_rejects_empty_region():
    g = capture.Grabber()
    try:
        assert g.grab(0, 0, 0, 10) is None
        assert g.grab(0, 0, 10, -5) is None
    finally:
        g.close()


def test_frame_source_delivers_fresh_frames():
    src = boot.FrameSource([0, 0, 160, 120])
    src.start()
    try:
        got, stamp = None, 0.0
        for _ in range(100):
            got, stamp = src.latest()
            if got is not None:
                break
            time.sleep(0.02)
        assert got is not None and got.shape == (120, 160, 3)
        first = stamp
        for _ in range(100):               #кадр должен обновиться
            time.sleep(0.02)
            _img, stamp = src.latest()
            if stamp > first:
                break
        assert stamp > first
    finally:
        src.stop()
        src.join(timeout=2.0)


def test_frame_source_without_region_waits():
    src = boot.FrameSource(None)
    src.start()
    try:
        time.sleep(0.15)
        img, _stamp = src.latest()
        assert img is None
    finally:
        src.stop()
        src.join(timeout=2.0)


# --- OCR в фоне -------------------------------------------------------------

@pytest.mark.skipif(not _tesseract_ready(), reason='нет tesseract.exe')
def test_hud_worker_reads_in_background():
    worker = boot.HudWorker(period=0.1)
    worker.start()
    try:
        worker.submit(panel_of('boot_play.jpg'))
        level = score = None
        for _ in range(120):
            level, score = worker.status()
            if level is not None:
                break
            time.sleep(0.05)
        assert level == 1 and score == 0
    finally:
        worker.stop()
        worker.join(timeout=3.0)


def test_hud_worker_submit_does_not_block():
    worker = boot.HudWorker(period=0.1)
    img = panel_of('boot_play.jpg')
    t0 = time.time()
    for _ in range(50):
        worker.submit(img)
    assert (time.time() - t0) < 1.0        #сабмит — это копия, а не OCR


# --- клавиши ----------------------------------------------------------------

def test_keys_hold_transitions():
    keys = boot.Keys(dry=True)
    assert keys.held == 0
    keys.hold(-1)
    assert keys.held == -1
    keys.hold(-1)                          #повтор ничего не меняет
    assert keys.held == -1
    keys.hold(1)
    assert keys.held == 1
    keys.release_all()
    assert keys.held == 0
