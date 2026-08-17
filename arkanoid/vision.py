# -*- coding: utf-8 -*-
"""Что видно на кадре мини-игры «Сапожный снос».

Кадр сюда приходит УЖЕ вырезанным по панели мини-игры (panel.detect_panel),
все координаты — в пикселях панели.

Опорные замеры по живому кадру 1920x1080 (панель 976x976):
    поле (тёмно-синий фон)  x 171..792, y 111..950
    блоки                   оранжевые с белой диагональю, ряд серого камня снизу
    тележка                 красно-жёлтая, ездит в нижней полосе поля
    сапог (мяч)             светлый, единственный быстро движущийся объект
"""

import cv2
import numpy as np

#Цвета в HSV (OpenCV: H 0..179)
BACK_LO, BACK_HI = (100, 80, 20), (135, 255, 130)        # тёмно-синий фон поля
BRICK_LO, BRICK_HI = (10, 120, 120), (30, 255, 255)      # оранжевый блок
CART_LO, CART_HI = (0, 90, 90), (35, 255, 255)           # красно-жёлтая тележка

#Доли поля: где искать тележку и до какой линии считать мяч «в игре»
PADDLE_BAND = 0.78          # нижние 22% поля
#Замер по живой игре: пятно движения сапога — 1700..2300 px (медиана ~1800,
#90-й перцентиль ~2200). Прежний диапазон 60..2600 пропускал искры от сбитых
#блоков: мелкое пятно рядом с прогнозом перехватывало трек, и платформа
#уезжала не туда (в логе: цель 694, мяч упал в 390).
#Потолок с запасом: если кадр пропущен, мяч смещается сильнее и «ушёл/пришёл»
#сливаются в одно пятно до ~3700 px. От широких вспышек защищает предел по
#ширине и высоте (90 px), а не по площади.
BALL_MIN_AREA, BALL_MAX_AREA = 700, 4200
BALL_SEARCH_RADIUS = 170            # насколько мяч может отклониться от прогноза
#Отступ от боковых стен: у самого края мерцает анимированный декор доты, а
#центр сапога (~26 px шириной) ближе этого к стене физически не подходит.
BALL_WALL_INSET = 14


def _mask(img, lo, hi):
    return cv2.inRange(cv2.cvtColor(img, cv2.COLOR_BGR2HSV), lo, hi)


def field_bounds(panel_bgr, fallback=(0.175, 0.114, 0.812, 0.974)):
    """Границы игрового поля -> (left, top, right, bottom) в координатах панели.

    Поле = тёмно-синий фон между колоннами. Если фон не виден (открыто меню
    или экран затемнён), возвращаем долевую заглушку — по ней всё равно можно
    брать вырезки, а состояние экрана определит `screen_state`.
    """
    if panel_bgr is None or panel_bgr.size == 0:
        return None
    h, w = panel_bgr.shape[:2]
    back = _mask(panel_bgr, BACK_LO, BACK_HI)
    cols = back.sum(axis=0) / 255.0
    rows = back.sum(axis=1) / 255.0
    if cols.max() > 0.25 * h and rows.max() > 0.25 * w:
        xs = np.where(cols > 0.25 * cols.max())[0]
        ys = np.where(rows > 0.25 * rows.max())[0]
        if len(xs) > 10 and len(ys) > 10:
            return int(xs[0]), int(ys[0]), int(xs[-1]), int(ys[-1])
    fx0, fy0, fx1, fy1 = fallback
    return int(w * fx0), int(h * fy0), int(w * fx1), int(h * fy1)


def _largest_component(mask, min_area=1):
    """Самая крупная связная область -> (x, y, w, h, area) или None."""
    num, _lbl, stats, _cent = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < min_area:
            continue
        if best is None or area > best[4]:
            best = (int(x), int(y), int(w), int(h), int(area))
    return best


def find_paddle(panel_bgr, field, band=PADDLE_BAND):
    """Тележка -> (center_x, half_width, top_y) или None. Координаты панели."""
    if panel_bgr is None or field is None:
        return None
    left, top, right, bottom = field
    y0 = int(top + (bottom - top) * band)
    sub = panel_bgr[y0:bottom, left:right]
    if sub.size == 0:
        return None
    mask = _mask(sub, CART_LO, CART_HI)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    got = _largest_component(mask, min_area=400)
    if not got:
        return None
    x, y, w, _h, _area = got
    return left + x + w / 2.0, w / 2.0, y0 + y


def find_ball(prev_bgr, cur_bgr, field, paddle_top=None, expect_pos=None):
    """Мяч по разнице кадров -> (x, y) или None.

    Блоки и фон статичны, поэтому «что изменилось» = мяч (и тележка, которую
    мы сами двигаем — её полосу исключаем). Шаблон не используем: сапог в
    полёте вращается, а пятно движения видно всегда.

    `expect_pos` — куда мяч должен был долететь (позиция + скорость × dt).
    Это важнее яркости: двигаясь, мяч даёт ДВА пятна (ушёл / появился), а над
    блоками он не светлее фона, и по одной яркости его теряет.
    """
    if prev_bgr is None or cur_bgr is None or field is None:
        return None
    if prev_bgr.shape != cur_bgr.shape:
        return None
    fl, top, fr, bottom = field
    left, right = fl + BALL_WALL_INSET, fr - BALL_WALL_INSET
    low = int(paddle_top) if paddle_top else bottom
    if low - top < 20 or right - left < 40:
        return None
    a = cv2.cvtColor(prev_bgr[top:low, left:right], cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(cur_bgr[top:low, left:right], cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(a, b)
    _ret, mask = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    #Сменился весь кадр (новый уровень, затемнение, пауза) — мяча тут нет,
    #иначе платформа погонится за случайным пятном.
    if mask.sum() / 255.0 > 0.15 * mask.size:
        return None
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    num, _lbl, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    #Движущийся мяч даёт ДВА пятна: он ушёл со старого места и появился на
    #новом. Нужное — то, где кадр посветлел (сапог светлый на тёмном фоне);
    #на старом месте и на месте сбитого блока картинка, наоборот, темнеет.
    cands = _ball_candidates(stats, cent, num, a, b, left, top)
    if not cands and expect_pos is not None:
        #Мяч бывает еле заметен (тёмный сапог на тёмном фоне, слабый контраст
        #у нижней стенки). Там, где он ДОЛЖЕН быть, ищем повторно с мягким
        #порогом — по маленькому окну это почти бесплатно.
        _ret2, soft = cv2.threshold(diff, 14, 255, cv2.THRESH_BINARY)
        soft = cv2.morphologyEx(soft, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        wx = int(expect_pos[0] - left)
        wy = int(expect_pos[1] - top)
        half = 70
        x0, x1 = max(0, wx - half), min(soft.shape[1], wx + half)
        y0, y1 = max(0, wy - half), min(soft.shape[0], wy + half)
        if x1 - x0 > 10 and y1 - y0 > 10:
            window = np.zeros_like(soft)
            window[y0:y1, x0:x1] = soft[y0:y1, x0:x1]
            n2, _l2, st2, ct2 = cv2.connectedComponentsWithStats(window, 8)
            cands = _ball_candidates(st2, ct2, n2, a, b, left, top,
                                     min_area=BALL_MIN_AREA // 2)
    global LAST_BALL_AREA
    if not cands:
        return None
    if expect_pos is not None:
        best = min(cands, key=lambda c: np.hypot(c[0] - expect_pos[0],
                                                 c[1] - expect_pos[1]))
        if np.hypot(best[0] - expect_pos[0], best[1] - expect_pos[1]) <= BALL_SEARCH_RADIUS:
            LAST_BALL_AREA = best[3]
            return float(best[0]), float(best[1])
    #Трека нет (только бросили или потеряли). Тут нельзя мерить среднюю
    #разницу по пятну: при пропущенном кадре «ушёл» и «пришёл» слипаются в
    #одно, и минус гасит плюс. Берём маску ТОЛЬКО посветлевшего — это и есть
    #место, куда сапог прилетел (сбитый блок, наоборот, оставляет тёмное).
    up = cv2.subtract(b, a)
    _r3, mask_up = cv2.threshold(up, 28, 255, cv2.THRESH_BINARY)
    mask_up = cv2.morphologyEx(mask_up, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    mask_up = cv2.dilate(mask_up, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    n3, _l3, st3, ct3 = cv2.connectedComponentsWithStats(mask_up, 8)
    lit = _ball_candidates(st3, ct3, n3, a, b, left, top,
                           min_area=BALL_MIN_AREA // 2)
    if not lit:
        return None
    best = max(lit, key=lambda c: c[3])          #самое крупное прибытие
    LAST_BALL_AREA = best[3]
    return float(best[0]), float(best[1])


LAST_BALL_AREA = 0          # площадь выбранного пятна (для замеров и отладки)


def _ball_candidates(stats, cent, num, a, b, left, top, min_area=None):
    """Пятна подходящего размера -> [(x, y, посветлело, площадь), ...]."""
    floor = BALL_MIN_AREA if min_area is None else min_area
    cands = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if not (floor <= area <= BALL_MAX_AREA):
            continue
        if w > 90 or h > 90:                  #широкая полоса — это не мяч
            continue
        delta = float(b[y:y + h, x:x + w].mean()) - float(a[y:y + h, x:x + w].mean())
        cands.append((left + float(cent[i][0]), top + float(cent[i][1]),
                      delta, int(area)))
    return cands


def find_ball_on_cart(panel_bgr, field, paddle_top):
    """До броска сапог лежит на тележке — берём его как стартовую позицию."""
    paddle = find_paddle(panel_bgr, field)
    if not paddle:
        return None
    cx, _half, top_y = paddle
    return cx, float(top_y if paddle_top is None else paddle_top)


def brick_stats(panel_bgr, field):
    """Оранжевые блоки внутри поля -> (сколько пикселей, нижняя граница y).

    Нужно, чтобы понимать: уровень ещё жив, и докуда достают блоки.
    """
    if panel_bgr is None or field is None:
        return 0, None
    left, top, right, bottom = field
    sub = panel_bgr[top:bottom, left:right]
    if sub.size == 0:
        return 0, None
    mask = _mask(sub, BRICK_LO, BRICK_HI)
    count = int(mask.sum() // 255)
    rows = np.where(mask.sum(axis=1) > 0)[0]
    return count, (top + int(rows[-1]) if len(rows) else None)


def brick_centroid(panel_bgr, field):
    """Центр массы оставшихся блоков -> (x, y) или None.

    Нужен для прицеливания: отбивать мяч краем платформы в ту сторону, где
    блоков больше, — иначе мяч ходит по вертикали и уровень тянется вечно.
    """
    if panel_bgr is None or field is None:
        return None
    left, top, right, bottom = field
    sub = panel_bgr[top:bottom, left:right]
    if sub.size == 0:
        return None
    mask = _mask(sub, BRICK_LO, BRICK_HI)
    #Порог: на экране правил золотой декор даёт ~250 «блочных» пикселей, а
    #один настоящий блок — около 800. Берём между.
    if mask.sum() < 255 * 600:
        return None
    cols = mask.sum(axis=0).astype(np.float64)
    rows = mask.sum(axis=1).astype(np.float64)
    cx = float((cols * np.arange(len(cols))).sum() / cols.sum())
    cy = float((rows * np.arange(len(rows))).sum() / rows.sum())
    return left + cx, top + cy


def field_brightness(panel_bgr, field):
    """Средняя яркость поля: при паузе и конце игры экран затемняется."""
    if panel_bgr is None or field is None:
        return 0.0
    left, top, right, bottom = field
    sub = panel_bgr[top:bottom, left:right]
    if sub.size == 0:
        return 0.0
    return float(cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY).mean())


def field_colorfulness(panel_bgr, field):
    """Средняя насыщенность поля: затемнение гасит цвет сильнее яркости."""
    if panel_bgr is None or field is None:
        return 0.0
    left, top, right, bottom = field
    sub = panel_bgr[top:bottom, left:right]
    if sub.size == 0:
        return 0.0
    return float(cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)[:, :, 1].mean())


def brick_fraction(panel_bgr, field):
    """Доля поля, занятая оранжевыми блоками."""
    if field is None:
        return 0.0
    left, top, right, bottom = field
    area = max(1, (bottom - top) * (right - left))
    count, _low = brick_stats(panel_bgr, field)
    return count / float(area)


def screen_state(panel_bgr, field, min_bricks=0.02, dim_saturation=60.0,
                 min_cart_half=40):
    """Состояние экрана: 'play' | 'dim' | 'other'.

    Замеры по живым кадрам (панель 976x976):
        игра          блоки 0.073..0.083 поля, насыщенность ~226
        экран правил  блоки 0.001,       насыщенность ~114
        пауза/конец   всё серое -> насыщенность падает почти в ноль

    ВАЖНО: по одним оранжевым блокам судить нельзя — с 4-го уровня кладка
    КАМЕННАЯ, и бот считал живую игру за меню, щёлкая вместо игры. Поэтому
    вторым признаком идёт тележка: она есть только в игре и всегда красно-жёлтая.
    'other' — правила, награды или пауза между уровнями; что именно, решает
    `play.py` по кнопкам (шаблоны), а не по цвету.
    """
    if panel_bgr is None or field is None:
        return 'other'
    if brick_fraction(panel_bgr, field) >= min_bricks:
        return 'play'
    if field_colorfulness(panel_bgr, field) < dim_saturation:
        return 'dim'
    cart = find_paddle(panel_bgr, field)
    if cart and cart[1] >= min_cart_half:
        return 'play'
    return 'other'


#Полосы HUD над полем (координаты панели 976x976). Замерено по светлым
#компонентам кадра: подписи на y 44..53, ЗНАЧЕНИЯ на y 57..82; цифра «1»
#всего 7x20 px, поэтому увеличиваем сильно, а порог держим низким (цифры
#светло-голубые, ярче деревянного фона, но до 150 не дотягивают).
HUD_LIVES = (215, 55, 100, 30)
HUD_LEVEL = (445, 55, 75, 30)
HUD_SCORE = (655, 55, 140, 30)


def hud_digits(panel_bgr, box, upscale=5.0, thr=100):
    """Готовит вырезку HUD под OCR цифр: светлое на тёмном -> чёрное на белом."""
    if panel_bgr is None:
        return None
    x, y, w, h = box
    sub = panel_bgr[y:y + h, x:x + w]
    if sub.size == 0:
        return None
    grey = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    _ret, mask = cv2.threshold(grey, thr, 255, cv2.THRESH_BINARY)
    big = cv2.resize(mask, None, fx=upscale, fy=upscale,
                     interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(255 - big, 20, 20, 20, 20,
                              cv2.BORDER_CONSTANT, value=255)


def count_lives(panel_bgr, box=HUD_LIVES):
    """Сколько сапог осталось: считаем светлые значки в полосе жизней."""
    if panel_bgr is None:
        return None
    x, y, w, h = box
    sub = panel_bgr[y:y + h, x:x + w]
    if sub.size == 0:
        return None
    grey = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    _ret, mask = cv2.threshold(grey, 110, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 7)))
    num, _lbl, stats, _cent = cv2.connectedComponentsWithStats(mask, 8)
    return sum(1 for i in range(1, num) if stats[i][4] >= 40)


#Полоса, где игра рисует подсказку «␣ ВЫБРАТЬ ПОЗИЦИЮ» / «␣ БРОСИТЬ САПОГ»
HINT_BAND = (0.55, 0.70)            # доли высоты поля


def find_hint(panel_bgr, template, field, threshold=0.70):
    """Видна ли подсказка с иконкой пробела -> (x, y) или None.

    Это ПРЯМОЙ признак «мяч ещё не брошен». Раньше бот определял это по
    отсутствию мяча, и ложные пятна по краям поля держали его в заблуждении:
    сапог был потерян, а бот считал, что игра идёт, и не жал пробел.
    Ищем только в узкой полосе — matchTemplate по всей панели слишком дорог
    для 45 кадров в секунду.
    """
    if panel_bgr is None or template is None or field is None:
        return None
    left, top, right, bottom = field
    height = bottom - top
    y0 = top + int(height * HINT_BAND[0])
    y1 = top + int(height * HINT_BAND[1])
    band = panel_bgr[y0:y1, left:right]
    th, tw = template.shape[:2]
    if band.shape[0] < th or band.shape[1] < tw:
        return None
    res = cv2.matchTemplate(band, template, cv2.TM_CCOEFF_NORMED)
    _mn, mx, _mnl, mxl = cv2.minMaxLoc(res)
    if mx < threshold:
        return None
    return left + mxl[0] + tw / 2.0, y0 + mxl[1] + th / 2.0


#Кнопки «Играть» и «Сыграть ещё» всегда внизу панели — искать по всей панели
#дорого (замер: 44 мс на кнопку против 6 мс по полосе).
BUTTON_BAND = (0.68, 0.97)


def find_button(panel_bgr, template, threshold=0.75, band=BUTTON_BAND):
    """Ищет кнопку по шаблону -> (x, y) центра в координатах панели или None."""
    if panel_bgr is None or template is None:
        return None
    th, tw = template.shape[:2]
    ph, pw = panel_bgr.shape[:2]
    y0, y1 = (0, ph) if not band else (int(ph * band[0]), int(ph * band[1]))
    sub = panel_bgr[y0:y1, :]
    if th > sub.shape[0] or tw > sub.shape[1]:
        return None
    res = cv2.matchTemplate(sub, template, cv2.TM_CCOEFF_NORMED)
    _mn, mx, _mnl, mxl = cv2.minMaxLoc(res)
    if mx < threshold:
        return None
    return mxl[0] + tw / 2.0, y0 + mxl[1] + th / 2.0
