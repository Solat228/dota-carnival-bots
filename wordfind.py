# -*- coding: utf-8 -*-
"""Поиск слова мини-игры на кадре и его распознавание.

Как устроена картинка в игре (разобрано по кадрам, см. Screens/):
  * над каждым врагом висит ЗЕЛЁНАЯ надпись — полное слово врага;
  * у ТЕКУЩЕЙ цели под зелёной надписью есть БОЛЬШАЯ строка прогресса:
        серые буквы  — уже набраны,
        ЖЁЛТАЯ буква — следующая,
        БЕЛЫЕ буквы  — что осталось набрать.
Поэтому «что печатать» = жёлтая + белые буквы большой строки. Серые в маску
не попадают, значит повторный ввод уже набранного исключён.

Если строки прогресса нет (цель не выбрана) — берём зелёную надпись врага
и печатаем слово целиком.

Все функции чистые (кадр -> данные), чтобы гонять офлайн по PNG и в тестах.
"""

import cv2
import numpy as np

#--- Цвета (замерены по кадрам) ------------------------------------------------
# зелёная надпись врага     ~ RGB (165, 210, 100)
# жёлтая «следующая» буква  ~ RGB (245, 245,  70)
# белые «осталось» буквы    ~ RGB (240, 240, 240)
# серые «набрано» буквы     ~ RGB (128, 128, 128) — намеренно НЕ ловим


def _split(bgr):
    return (bgr[:, :, 0].astype(np.int16),
            bgr[:, :, 1].astype(np.int16),
            bgr[:, :, 2].astype(np.int16))


def mask_green(bgr):
    """Маска зелёных надписей (полное слово над врагом)."""
    b, g, r = _split(bgr)
    m = (g > 150) & (r > 110) & (r < 225) & (b < 150) & (g - b > 55) & (g - r > 15)
    return m.astype(np.uint8) * 255


def mask_yellow(bgr):
    """Маска жёлтой буквы (следующая к набору)."""
    b, g, r = _split(bgr)
    m = (r > 195) & (g > 185) & (b < 150) & (r - b > 85) & (np.abs(r - g) < 50)
    return m.astype(np.uint8) * 255


def mask_white(bgr, thr=205, spread=30):
    """Маска белых букв (осталось набрать). Серые (~128) сюда не попадают."""
    b, g, r = _split(bgr)
    mx = np.maximum(np.maximum(b, g), r)
    mn = np.minimum(np.minimum(b, g), r)
    m = (mn > thr) & (mx - mn < spread)
    return m.astype(np.uint8) * 255


def components(mask, min_h=8, max_h=60, min_w=2, min_area=15, max_w=400):
    """Связные компоненты маски -> список боксов (x, y, w, h, area)."""
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(mask, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if min_h <= h <= max_h and min_w <= w <= max_w and area >= min_area:
            out.append((x, y, w, h, area))
    return out


def union_box(boxes):
    """Общий прямоугольник для списка боксов."""
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return (x0, y0, x1 - x0, y1 - y0)


def same_line(a, b, tol=0.45):
    """Лежат ли два бокса на одной текстовой строке (по вертикальному перекрытию)."""
    ay0, ay1 = a[1], a[1] + a[3]
    by0, by1 = b[1], b[1] + b[3]
    overlap = min(ay1, by1) - max(ay0, by0)
    if overlap <= 0:
        return False
    return overlap >= tol * min(a[3], b[3])


def group_line(seed, boxes, max_gap=None):
    """Собирает буквы одной строки вокруг seed: та же строка + разрывы не больше max_gap."""
    if max_gap is None:
        max_gap = max(12, int(seed[3] * 1.4))
    line = [b for b in boxes if same_line(seed, b)]
    line.sort(key=lambda b: b[0])
    if seed not in line:
        line.append(seed)
        line.sort(key=lambda b: b[0])
    idx = line.index(seed)
    keep = [seed]
    #влево
    cur = seed
    for b in reversed(line[:idx]):
        if cur[0] - (b[0] + b[2]) <= max_gap:
            keep.append(b)
            cur = b
        else:
            break
    #вправо
    cur = seed
    for b in line[idx + 1:]:
        if b[0] - (cur[0] + cur[2]) <= max_gap:
            keep.append(b)
            cur = b
        else:
            break
    keep.sort(key=lambda b: b[0])
    return keep


def in_zones(box, zones):
    """Пересекается ли бокс с одной из запретных зон (HUD: счёт/время/рекорд)."""
    x, y, w, h = box[0], box[1], box[2], box[3]
    for zx, zy, zw, zh in zones or ():
        if x < zx + zw and zx < x + w and y < zy + zh and zy < y + h:
            return True
    return False


def find_progress_line(bgr, min_h=20, max_h=55, zones=None):
    """Строка прогресса текущей цели -> (bbox, маска_букв) или (None, None).

    Ищем ЖЁЛТУЮ букву нужной высоты, добираем к ней белые буквы той же строки.
    """
    ym = mask_yellow(bgr)
    wm = mask_white(bgr)
    yellow = [b for b in components(ym, min_h=min_h, max_h=max_h, min_w=3)
              if not in_zones(b, zones)]
    if not yellow:
        return None, None
    white = [b for b in components(wm, min_h=min_h - 6, max_h=max_h, min_w=2)
             if not in_zones(b, zones)]
    best = None
    for seed in sorted(yellow, key=lambda b: -b[4]):
        line = group_line(seed, white + [seed])
        box = union_box(line)
        if box is None:
            continue
        score = (len(line), box[2])
        if best is None or score > best[0]:
            best = (score, box, line)
    if best is None:
        return None, None
    box = best[1]
    letters = cv2.bitwise_or(ym, wm)
    return box, letters


def find_label_lines(bgr, min_h=11, max_h=26, min_w=25, zones=None):
    """Зелёные надписи врагов -> список (bbox, ...) сверху вниз по площади."""
    gm = mask_green(bgr)
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
    closed = cv2.morphologyEx(gm, cv2.MORPH_CLOSE, ker)
    boxes = [b for b in components(closed, min_h=min_h, max_h=max_h, min_w=min_w, min_area=90)
             if not in_zones(b, zones) and b[2] / max(1, b[3]) > 1.3]
    boxes.sort(key=lambda b: -b[4])
    return boxes, gm


def find_label_above(bgr, box, max_gap_ratio=2.2, min_h=11, max_h=26):
    """Зелёная надпись (ПОЛНОЕ слово) прямо над строкой прогресса.

    Нужна как страховка: если чтение остатка сбоит и слово «зависло»,
    печатаем слово целиком — лишние буквы игра просто игнорирует.
    """
    if box is None:
        return None, None
    bx, by, bw, bh = box[:4]
    gm = mask_green(bgr)
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
    closed = cv2.morphologyEx(gm, cv2.MORPH_CLOSE, ker)
    best = None
    for cand in components(closed, min_h=min_h, max_h=max_h, min_w=20, min_area=90):
        cx, cy, cw, ch = cand[:4]
        if cy + ch > by + bh * 0.4:                 #должна быть выше строки прогресса
            continue
        if by - (cy + ch) > bh * max_gap_ratio:     #и не слишком далеко
            continue
        overlap = min(bx + bw, cx + cw) - max(bx, cx)
        if overlap <= 0:                            #и по горизонтали пересекаться
            continue
        score = overlap - abs((cx + cw / 2.0) - (bx + bw / 2.0))
        if best is None or score > best[0]:
            best = (score, cand)
    if best is None:
        return None, None
    return best[1], gm


def crop_mask(mask, box, pad=6):
    """Вырезка маски по боксу с полями (чтобы OCR не резал буквы по краю)."""
    x, y, w, h = box[:4]
    y0 = max(0, y - pad)
    x0 = max(0, x - pad)
    y1 = min(mask.shape[0], y + h + pad)
    x1 = min(mask.shape[1], x + w + pad)
    return mask[y0:y1, x0:x1]


def prepare_for_ocr(mask_crop, upscale=3.0):
    """Маска букв -> чёрный текст на белом, увеличенный (так тессеракт точнее)."""
    if mask_crop is None or mask_crop.size == 0:
        return None
    img = 255 - mask_crop
    if upscale and upscale != 1.0:
        img = cv2.resize(img, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
        img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)[1]
    return cv2.copyMakeBorder(img, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
