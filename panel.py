# -*- coding: utf-8 -*-
"""Поиск окна мини-игры (яркая панель на затемнённом фоне доты).

Зачем: искать текст по всему экрану дороже и опаснее (в интерфейсе доты своя
жёлтая/зелёная графика). Панель находится один раз и дальше кадр берём только
из неё. Плюс отсюда же считаются зоны HUD (счёт/время/рекорд), где текст ловить
не надо.
"""

import cv2
import numpy as np


def detect_panel(bgr, min_area_frac=0.10, aspect_range=(0.75, 1.30)):
    """Ищет панель мини-игры -> (x, y, w, h) или None.

    Панель — самый крупный светлый прямоугольник: дота вокруг неё затемнена.
    """
    if bgr is None or bgr.size == 0:
        return None
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    #«не затемнено» — порог низкий, фон вокруг панели заметно темнее
    mask = (gray > 45).astype(np.uint8) * 255
    #Ядро было 25x25 и «мостило» панель с соседним светлым окном в один
    #контур — панель переставала находиться. 9x9 хватает, чтобы закрыть
    #дырки внутри панели, и не склеивает её с тем, что рядом.
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, ker)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    frame_area = bgr.shape[0] * bgr.shape[1]
    best = None
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        if area < min_area_frac * frame_area:
            continue
        aspect = w / max(1.0, float(h))
        if not (aspect_range[0] <= aspect <= aspect_range[1]):
            continue
        fill = cv2.contourArea(cnt) / max(1.0, float(area))
        if fill < 0.6:            #контур должен быть похож на прямоугольник
            continue
        if best is None or area > best[4]:
            best = (int(x), int(y), int(w), int(h), area)
    return best[:4] if best else None


#Доли панели: счёт, время, рекорд (замерено по кадрам, панель 988x988).
#Именно три коробки, а не вся верхняя полоса: слова врагов появляются уже
#на высоте ~13% панели, полосой их бы срезало.
HUD_FRACTIONS = (
    (0.03, 0.01, 0.26, 0.15),   #СЧЁТ + множитель x1.0
    (0.38, 0.01, 0.23, 0.15),   #ВРЕМЯ
    (0.74, 0.01, 0.24, 0.15),   #РЕКОРД
)


def hud_zones(panel, fractions=HUD_FRACTIONS):
    """Зоны HUD внутри панели -> список (x, y, w, h) в координатах кадра панели.

    Кадр берётся уже вырезанным по панели, поэтому отсчёт от нуля.
    """
    if not panel:
        return []
    w, h = panel[2], panel[3]
    return [(int(fx * w), int(fy * h), int(fw * w), int(fh * h))
            for fx, fy, fw, fh in fractions]


def hud_present(panel_bgr, zones, min_h=26, max_h=52, need=2):
    """Похоже ли, что мини-игра реально открыта: в зонах HUD есть зелёные цифры.

    Защита от печати мимо игры: если мини-игру закрыли, а бот ещё активен,
    ловить текст в интерфейсе доты и жать клавиши нельзя.
    """
    import wordfind                     #локальный импорт: panel не тянет OCR
    if panel_bgr is None or not zones:
        return False
    hits = 0
    for zx, zy, zw, zh in zones:
        y0, y1 = max(0, zy), min(panel_bgr.shape[0], zy + zh)
        x0, x1 = max(0, zx), min(panel_bgr.shape[1], zx + zw)
        if y1 - y0 < 5 or x1 - x0 < 5:
            continue
        sub = panel_bgr[y0:y1, x0:x1]
        boxes = wordfind.components(wordfind.mask_green(sub), min_h=min_h,
                                    max_h=max_h, min_w=4, min_area=60)
        if boxes:
            hits += 1
    return hits >= need


def shrink(panel, frac=0.0):
    """Немного ужимает область (иногда рамка панели даёт блики)."""
    if not panel:
        return panel
    x, y, w, h = panel[:4]
    dx, dy = int(w * frac), int(h * frac)
    return (x + dx, y + dy, w - 2 * dx, h - 2 * dy)
