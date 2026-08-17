# -*- coding: utf-8 -*-
"""Обёртка над Tesseract: распознаём короткие слова из подготовленной маски."""

import pytesseract

import config

WHITELIST = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
_READY = False


def setup(path=''):
    """Прописывает путь к tesseract.exe (один раз за процесс).

    Путь без аргумента берём из config.json — там машинный путь, который не
    лежит в репозитории. Иначе на машине с нестандартной установкой OCR молча
    получал несуществующий 'tesseract' из PATH и возвращал пустые строки.
    """
    global _READY
    if not path:
        try:
            path = config.load().get('tesseract', '')
        except Exception:
            path = ''
    exe = config.find_tesseract(path)
    pytesseract.pytesseract.tesseract_cmd = exe
    _READY = True
    return exe


def build_config(psm=7, whitelist=WHITELIST):
    """Строка параметров tesseract: один блок текста, только латиница."""
    return (f'--psm {int(psm)} --oem 3 '
            f'-c tessedit_char_whitelist={whitelist} '
            f'-c load_system_dawg=0 -c load_freq_dawg=0')


def read_text(img, psm=7, whitelist=WHITELIST):
    """Распознаёт подготовленную (чёрное на белом) картинку -> строка A-Z."""
    if img is None or getattr(img, 'size', 0) == 0:
        return ''
    if not _READY:
        setup()
    try:
        raw = pytesseract.image_to_string(img, config=build_config(psm, whitelist))
    except Exception as err:
        print(f'[ocr] сбой: {err}')
        return ''
    return clean(raw, whitelist)


def clean(raw, whitelist=WHITELIST):
    """Оставляет только разрешённые символы в верхнем регистре."""
    allowed = set(whitelist)
    return ''.join(ch for ch in (raw or '').upper() if ch in allowed)
