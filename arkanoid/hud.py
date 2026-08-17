# -*- coding: utf-8 -*-
"""Чтение HUD арканоида (жизни, уровень, счёт).

Вынесено из `vision`, чтобы то осталось чистым CV без зависимости от OCR.
Цифры мелкие (7x20 px), поэтому: низкий порог + сильное увеличение, а psm
пробуем два — 7 (строка) и 10 (один символ): однозначный счёт «0» читается
только вторым.
"""

import ocr

from . import vision

DIGITS = '0123456789'


def read_number(panel_bgr, box):
    """Число из полосы HUD или None."""
    prep = vision.hud_digits(panel_bgr, box)
    if prep is None:
        return None
    text = ocr.read_text(prep, psm=7, whitelist=DIGITS)
    if not text:
        text = ocr.read_text(prep, psm=10, whitelist=DIGITS)
    return int(text) if text.isdigit() else None


def read_status(panel_bgr):
    """(уровень, счёт) — то, чем меряем прогресс бота."""
    return (read_number(panel_bgr, vision.HUD_LEVEL),
            read_number(panel_bgr, vision.HUD_SCORE))
