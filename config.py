# -*- coding: utf-8 -*-
"""Конфиг бота (JSON рядом со скриптом). Дефолты = рабочее поведение MVP."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, 'config.json')

#Где искать tesseract.exe. Порядок: рядом с проектом -> стандартные места ->
#переменная окружения TESSERACT_EXE -> PATH. Свой нестандартный путь можно
#не править в коде: пропиши "tesseract" в config.json или задай TESSERACT_EXE.
TESS_CANDIDATES = [
    os.path.join(HERE, 'Tesseract-OCR', 'tesseract.exe'),
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR',
                 'tesseract.exe'),
    os.environ.get('TESSERACT_EXE', ''),
]

DEFAULTS = {
    # --- область со словом (экранные координаты, [x, y, w, h]); задаётся калибровкой
    'region': None,
    # заголовок окна игры (часть строки) — клавиши шлём только когда оно в фокусе
    'window_title': 'Dota 2',
    # --- OCR
    'tesseract': '',            # пусто = автопоиск по TESS_CANDIDATES
    'ocr_psm': 7,               # 7 = одна строка
    'ocr_upscale': 2.0,         # во сколько раз увеличить вырезку перед OCR
    'bright_threshold': 165,    # порог яркости для маски текста
    'min_word_len': 3,
    # --- словарь (исправление ошибок OCR по названиям Dota)
    'dict_correct': True,
    'dict_min_ratio': 0.80,
    # --- ввод
    'key_delay_ms': 6,          # пауза между нажатиями букв
    'post_word_delay_ms': 30,   # пауза после слова
    'force_en_layout': True,    # переключить раскладку окна игры на EN перед вводом
    'retype_after_sec': 0.8,    # если слово не сменилось — напечатать ещё раз
    'type_labels': True,        # печатать по зелёной надписи, когда цель не выбрана
    'require_hud': True,        # печатать только когда виден HUD мини-игры
    'stall_limit': 2,           # столько «застреваний» -> печатать слово целиком
    'snap_min_ratio': 0.75,     # порог подгонки остатка к суффиксу текущего слова
    # --- цикл
    'loop_fps': 25.0,
    'hotkey_toggle': 0x79,      # F10 — старт/стоп
    'hotkey_quit': 0x7B,        # F12 — выход
    # --- отладка
    'debug_save': False,        # складывать вырезки со словами в Debug/
    'verbose': True,
}


def find_tesseract(path=''):
    """Путь к tesseract.exe: заданный -> переменная среды -> кандидаты -> PATH."""
    if path and os.path.exists(path):
        return path
    env = os.environ.get('TESSERACT_EXE', '')
    if env and os.path.exists(env):
        return env
    for candidate in TESS_CANDIDATES:
        if candidate and os.path.exists(candidate):
            return candidate
    return 'tesseract'  # надежда на PATH


def load_raw(path=None):
    """Только то, что реально лежит в файле, без подмешивания дефолтов.

    Нужно арканоиду: у него свои дефолты, и `load()` подсовывал бы ему чужие
    (например loop_fps печаталки), делая вид, что их задал пользователь.
    """
    try:
        with open(path or CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as err:
        print(f'[config] битый конфиг ({err}) — читаю как пустой')
        return {}


def load(path=CONFIG_PATH):
    """Читает конфиг, дополняя недостающие ключи дефолтами."""
    cfg = dict(DEFAULTS)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key, value in data.items():
                cfg[key] = value
    except FileNotFoundError:
        pass
    except Exception as err:
        print(f'[config] битый конфиг ({err}) — беру дефолты')
    return cfg


def save(cfg, path=CONFIG_PATH):
    """Пишет конфиг атомарно (tmp + replace), чтобы не оставить обрубок."""
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path
