# -*- coding: utf-8 -*-
"""Тесты поиска слова на кадре (маски, группировка строк, реальные кадры)."""

import os
import sys

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import wordfind  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def solid(color, w=20, h=20):
    """Однотонная картинка BGR."""
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :] = color
    return img


def test_mask_green_catches_label_color():
    #зелёная надпись врага ~ RGB (165, 210, 100) -> BGR (100, 210, 165)
    assert wordfind.mask_green(solid((100, 210, 165))).all()


def test_mask_green_ignores_white_and_yellow():
    assert not wordfind.mask_green(solid((240, 240, 240))).any()
    assert not wordfind.mask_green(solid((70, 245, 245))).any()


def test_mask_yellow_catches_next_letter():
    #жёлтая буква ~ RGB (245, 245, 70) -> BGR (70, 245, 245)
    assert wordfind.mask_yellow(solid((70, 245, 245))).all()


def test_mask_white_catches_remaining_but_not_typed_gray():
    assert wordfind.mask_white(solid((240, 240, 240))).all()
    #серые (уже набранные) буквы ловить НЕЛЬЗЯ — иначе бот наберёт их заново
    assert not wordfind.mask_white(solid((128, 128, 128))).any()


def test_mask_white_ignores_colored_bright():
    assert not wordfind.mask_white(solid((60, 240, 240))).any()


def test_components_filters_by_size():
    mask = np.zeros((60, 60), np.uint8)
    mask[10:30, 10:20] = 255           #годный блок 10x20
    mask[50:52, 50:52] = 255           #мелкий шум
    boxes = wordfind.components(mask, min_h=8, max_h=40, min_w=2, min_area=15)
    assert len(boxes) == 1
    assert boxes[0][:4] == (10, 10, 10, 20)


def test_same_line_and_union_box():
    a = (0, 10, 10, 20, 200)
    b = (20, 12, 10, 18, 180)
    c = (40, 90, 10, 20, 200)
    assert wordfind.same_line(a, b)
    assert not wordfind.same_line(a, c)
    assert wordfind.union_box([a, b]) == (0, 10, 30, 20)
    assert wordfind.union_box([]) is None


def test_group_line_breaks_on_big_gap():
    seed = (100, 10, 10, 20, 200)
    near = (115, 10, 10, 20, 200)
    far = (400, 10, 10, 20, 200)
    got = wordfind.group_line(seed, [seed, near, far], max_gap=20)
    assert got == [seed, near]


def test_in_zones():
    assert wordfind.in_zones((5, 5, 10, 10), [(0, 0, 20, 20)])
    assert not wordfind.in_zones((50, 50, 10, 10), [(0, 0, 20, 20)])
    assert not wordfind.in_zones((5, 5, 10, 10), [])


def test_crop_mask_clamps_to_image():
    mask = np.zeros((30, 30), np.uint8)
    got = wordfind.crop_mask(mask, (0, 0, 10, 10), pad=20)
    assert got.shape == (30, 30)


def test_prepare_for_ocr_inverts_and_pads():
    mask = np.zeros((10, 10), np.uint8)
    mask[2:8, 2:8] = 255
    prepared = wordfind.prepare_for_ocr(mask, upscale=2.0)
    assert prepared.shape[0] > 20 and prepared.shape[1] > 20
    assert prepared[0, 0] == 255        #фон белый
    assert prepared.min() == 0          #текст чёрный


def test_prepare_for_ocr_empty():
    assert wordfind.prepare_for_ocr(None) is None


# --- реальные кадры -----------------------------------------------------------

@pytest.mark.parametrize('name', ['play_leshrac.png', 'play_rubick.png'])
def test_find_progress_line_on_real_frames(name):
    img = cv2.imread(os.path.join(FIXTURES, name))
    assert img is not None
    box, letters = wordfind.find_progress_line(img)
    assert box is not None, 'строка прогресса должна находиться'
    x, y, w, h = box[:4]
    assert 20 <= h <= 55                #высота большой строки
    assert w >= h                       #строка шире одной буквы
    assert letters is not None


def test_find_progress_line_absent_on_gameover_screen():
    img = cv2.imread(os.path.join(FIXTURES, 'gameover.png'))
    assert img is not None
    box, _ = wordfind.find_progress_line(img)
    assert box is None, 'на экране «конец игры» слова нет'


def test_find_label_above_progress_line():
    """Над строкой прогресса должна находиться зелёная надпись с полным словом."""
    img = cv2.imread(os.path.join(FIXTURES, 'play_leshrac.png'))
    box, _ = wordfind.find_progress_line(img)
    lbox, gmask = wordfind.find_label_above(img, box)
    assert lbox is not None
    assert lbox[1] + lbox[3] <= box[1] + box[3] * 0.4     #выше строки прогресса
    assert gmask is not None
    #по горизонтали надпись пересекается со строкой прогресса
    assert min(lbox[0] + lbox[2], box[0] + box[2]) - max(lbox[0], box[0]) > 0


def test_find_label_above_without_box():
    assert wordfind.find_label_above(None, None) == (None, None)


def test_find_label_lines_on_real_frame():
    img = cv2.imread(os.path.join(FIXTURES, 'play_rubick.png'))
    boxes, mask = wordfind.find_label_lines(img)
    assert boxes, 'зелёные надписи должны находиться'
    assert mask is not None
