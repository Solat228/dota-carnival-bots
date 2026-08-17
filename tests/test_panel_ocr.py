# -*- coding: utf-8 -*-
"""Тесты поиска панели мини-игры, конфига, ввода и сквозного распознавания."""

import os
import sys

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config    # noqa: E402
import ocr       # noqa: E402
import panel     # noqa: E402
import sendkeys  # noqa: E402
import wordfind  # noqa: E402
import words     # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


# --- панель -------------------------------------------------------------------

def test_detect_panel_on_real_frame():
    img = cv2.imread(os.path.join(FIXTURES, 'play_rubick.png'))
    got = panel.detect_panel(img)
    assert got is not None
    x, y, w, h = got
    assert 0.75 <= w / float(h) <= 1.30      #панель почти квадратная
    assert w > 500 and h > 500


def test_detect_panel_none_on_empty():
    assert panel.detect_panel(None) is None
    assert panel.detect_panel(np.zeros((100, 100, 3), np.uint8)) is None


def test_hud_zones_are_three_boxes_inside_panel():
    zones = panel.hud_zones((0, 0, 1000, 1000))
    assert len(zones) == 3
    for zx, zy, zw, zh in zones:
        assert 0 <= zx and zx + zw <= 1000
        assert 0 <= zy and zy + zh <= 1000
    assert panel.hud_zones(None) == []


def test_hud_zones_do_not_cover_word_area():
    #слова врагов появляются уже с ~13% высоты панели — зоны HUD не должны
    #съедать всю верхнюю полосу
    zones = panel.hud_zones((0, 0, 1000, 1000))
    assert not wordfind.in_zones((650, 140, 90, 17), zones)


def test_hud_present_true_on_gameplay():
    img = cv2.imread(os.path.join(FIXTURES, 'play_rubick.png'))
    got = panel.detect_panel(img)
    x, y, w, h = got
    crop = img[y:y + h, x:x + w]
    assert panel.hud_present(crop, panel.hud_zones(got))


def test_hud_present_false_on_gameover():
    img = cv2.imread(os.path.join(FIXTURES, 'gameover.png'))
    got = panel.detect_panel(img)
    if got is None:
        return                    #панели нет — печатать всё равно нечего
    x, y, w, h = got
    crop = img[y:y + h, x:x + w]
    assert not panel.hud_present(crop, panel.hud_zones(got))


def test_hud_present_guards_bad_input():
    assert not panel.hud_present(None, [(0, 0, 10, 10)])
    assert not panel.hud_present(np.zeros((10, 10, 3), np.uint8), [])


def test_shrink():
    assert panel.shrink((0, 0, 100, 100), 0.1) == (10, 10, 80, 80)
    assert panel.shrink(None) is None


# --- конфиг -------------------------------------------------------------------

def test_config_roundtrip(tmp_path):
    path = str(tmp_path / 'cfg.json')
    cfg = config.load(path)               #файла нет -> дефолты
    assert cfg['key_delay_ms'] == config.DEFAULTS['key_delay_ms']
    cfg['key_delay_ms'] = 42
    config.save(cfg, path)
    assert config.load(path)['key_delay_ms'] == 42


def test_config_broken_file_falls_back(tmp_path):
    path = tmp_path / 'cfg.json'
    path.write_text('{{{', encoding='utf-8')
    assert config.load(str(path))['loop_fps'] == config.DEFAULTS['loop_fps']


def test_find_tesseract_prefers_existing(tmp_path):
    exe = tmp_path / 'tesseract.exe'
    exe.write_text('', encoding='utf-8')
    assert config.find_tesseract(str(exe)) == str(exe)


# --- ввод ---------------------------------------------------------------------

def test_clean_text_drops_spaces_and_punctuation():
    #по правилам игры пробелы и знаки препинания вводить не нужно
    assert sendkeys.clean_text("Crystal Maiden!") == 'CRYSTALMAIDEN'
    assert sendkeys.clean_text('') == ''
    assert sendkeys.clean_text(None) == ''


def test_vk_for_char():
    assert sendkeys.vk_for_char('a') == ord('A')
    assert sendkeys.vk_for_char('7') == ord('7')
    assert sendkeys.vk_for_char('!') is None


def test_scan_for_vk_is_nonzero_for_letters():
    assert sendkeys.scan_for_vk(ord('A')) > 0


# --- OCR ----------------------------------------------------------------------

def test_ocr_clean_filters_whitelist():
    assert ocr.clean(' ru:BICK\n') == 'RUBICK'
    assert ocr.clean(None) == ''


def test_ocr_build_config_has_whitelist_and_psm():
    cfg = ocr.build_config(psm=7)
    assert '--psm 7' in cfg
    assert 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ' in cfg


def _tesseract_ready():
    #Путь ищем ТАК ЖЕ, как бот: сперва из config.json (там машинный путь,
    #файл не в репозитории), потом стандартные места. Иначе OCR-тесты молча
    #уходили в пропуск на машине, где tesseract лежит нестандартно.
    exe = config.find_tesseract(config.load().get('tesseract', ''))
    return os.path.exists(exe)


@pytest.mark.skipif(not _tesseract_ready(), reason='нет tesseract.exe')
def test_end_to_end_reads_word_from_real_frame():
    """Сквозной прогон: кадр -> остаток слова. На этом кадре набрано «LESHR»."""
    ocr.setup()
    img = cv2.imread(os.path.join(FIXTURES, 'play_leshrac.png'))
    box, letters = wordfind.find_progress_line(img)
    text = ocr.read_text(wordfind.prepare_for_ocr(wordfind.crop_mask(letters, box)))
    assert words.normalize(text) == 'AC'


@pytest.mark.skipif(not _tesseract_ready(), reason='нет tesseract.exe')
def test_label_above_reads_whole_word():
    """Страховка при «зависшем» слове: зелёная надпись = слово целиком."""
    ocr.setup()
    img = cv2.imread(os.path.join(FIXTURES, 'play_leshrac.png'))
    box, _ = wordfind.find_progress_line(img)
    lbox, gmask = wordfind.find_label_above(img, box)
    text = ocr.read_text(wordfind.prepare_for_ocr(wordfind.crop_mask(gmask, lbox)))
    assert words.normalize(text) == 'LESHRAC'


@pytest.mark.skipif(not _tesseract_ready(), reason='нет tesseract.exe')
def test_end_to_end_reads_full_word():
    """Слово ещё не начинали набирать — читается целиком."""
    ocr.setup()
    img = cv2.imread(os.path.join(FIXTURES, 'play_rubick.png'))
    box, letters = wordfind.find_progress_line(img)
    text = ocr.read_text(wordfind.prepare_for_ocr(wordfind.crop_mask(letters, box)))
    assert words.normalize(text) == 'RUBICK'
