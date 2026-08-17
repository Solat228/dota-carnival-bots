# -*- coding: utf-8 -*-
"""Куда упадёт сапог: предсказание точки на линии платформы.

Платформа медленная (замер по живой игре: ~200 px/с), а мяч успевает пересечь
поле быстрее, чем тележка доедет с края на край. Поэтому ехать нужно НЕ за
мячом, а в точку, где он окажется — с учётом отскоков от боковых стен.

Отскоки считаем «зеркальной развёрткой»: продлеваем прямую до линии платформы
и складываем полученный x обратно в поле треугольной волной. Это точнее и
дешевле пошагового моделирования, и целиком проверяется тестами.

Всё в пикселях кадра панели, ось y вниз (как в изображении).
"""

import math


def fold(x, left, right):
    """Складывает координату в отрезок [left, right] как отражение от стен."""
    width = right - left
    if width <= 0:
        return left
    period = 2.0 * width
    t = math.fmod(x - left, period)
    if t < 0:
        t += period
    return left + (t if t <= width else period - t)


def predict_x(x, y, vx, vy, left, right, target_y):
    """Где мяч пересечёт линию `target_y`. None — если он туда не летит.

    vy > 0 — мяч идёт вниз (ось y вниз). Радиус мяча не учитываем: он мал
    относительно платформы, а промах в полрадиуса всё равно перекрывается
    её шириной.
    """
    if vy is None or vy <= 0:
        return None
    if y >= target_y:
        return None
    dt = (target_y - y) / float(vy)
    return fold(x + vx * dt, left, right)


def time_to_line(y, vy, target_y):
    """Сколько секунд лететь до линии (None — если не летит туда)."""
    if vy is None or vy <= 0 or y >= target_y:
        return None
    return (target_y - y) / float(vy)


def clamp_paddle(center, half_width, left, right):
    """Держит платформу целиком внутри поля."""
    if right - left <= 2 * half_width:
        return (left + right) / 2.0
    return max(left + half_width, min(right - half_width, center))


def aim_center(predicted_x, half_width, left, right):
    """Куда вести ЦЕНТР платформы, чтобы принять мяч серединой."""
    if predicted_x is None:
        return None
    return clamp_paddle(predicted_x, half_width, left, right)


def aim_with_offset(predicted_x, half_width, left, right, offset_frac):
    """То же, но с подставлением края: сдвиг меняет угол отскока.

    offset_frac: -1 = принять правым краем (мяч уйдёт вправо),
                 +1 = левым краем (мяч уйдёт влево), 0 = центром.
    """
    if predicted_x is None:
        return None
    frac = max(-1.0, min(1.0, float(offset_frac)))
    return clamp_paddle(predicted_x + frac * half_width, half_width, left, right)


def aim_offset_for(hit_x, brick_x, left, right, strength=0.7):
    """Каким краем платформы принимать мяч, чтобы послать его к блокам.

    Отбивая ЛЕВЫМ краем, мяч уходит влево (см. `aim_with_offset`). Значит,
    если блоки левее точки падения — смещаем платформу так, чтобы мяч пришёл
    в её левую часть. Величина растёт с расстоянием до блоков, но ограничена:
    у самого края платформы промахнуться проще.
    """
    if hit_x is None or brick_x is None:
        return 0.0
    half_field = max(1.0, (right - left) / 2.0)
    frac = (hit_x - brick_x) / half_field
    return max(-1.0, min(1.0, frac)) * float(strength)


class BallTracker:
    """Скорость мяча по последним замерам + защита от «телепортов».

    Мяч исчезает (сбитый блок перекрывает, кадр смазан) и появляется в другом
    месте — по таким скачкам скорость считать нельзя, иначе платформа уедет
    не туда. Скачок дальше `jump_limit` за тик считаем новым мячом.
    """

    def __init__(self, jump_limit=260.0, stale_sec=0.35):
        self.jump_limit = float(jump_limit)
        self.stale_sec = float(stale_sec)
        self.samples = []            # (t, x, y)

    def reset(self):
        self.samples = []

    def update(self, t, x, y):
        """Добавляет замер. True — трек продолжился, False — начат заново."""
        if x is None or y is None:
            return False
        if self.samples:
            pt, px, py = self.samples[-1]
            dt = t - pt
            if dt <= 0:
                return True
            dist = math.hypot(x - px, y - py)
            if dt > self.stale_sec or dist > self.jump_limit:
                self.samples = [(t, x, y)]
                return False
        self.samples.append((t, x, y))
        if len(self.samples) > 4:
            self.samples = self.samples[-4:]
        return True

    def position(self):
        if not self.samples:
            return None, None
        _t, x, y = self.samples[-1]
        return x, y

    @staticmethod
    def _pair_speed(a, b):
        (t0, x0, y0), (t1, x1, y1) = a, b
        dt = t1 - t0
        if dt <= 0:
            return None, None
        return (x1 - x0) / dt, (y1 - y0) / dt

    def velocity(self, smooth=True):
        """(vx, vy) px/с. None — данных мало.

        По двум точкам скорость дёргается от шума детекта (кадры идут каждые
        17 мс, а мяч мог сместиться на пару пикселей). Усредняем с прошлой
        парой — но ТОЛЬКО если направление не изменилось: иначе усреднение
        размажет отскок и платформа поедет не туда.
        """
        if len(self.samples) < 2:
            return None, None
        vx, vy = self._pair_speed(self.samples[-2], self.samples[-1])
        if vx is None or not smooth or len(self.samples) < 3:
            return vx, vy
        px, py = self._pair_speed(self.samples[-3], self.samples[-2])
        if px is None:
            return vx, vy
        #Отскок = смена ЗНАКА. Строго вертикальный полёт (vx == 0) сменой знака
        #не является: сравнение «<= 0» считало его отскоком на каждом кадре и
        #навсегда отключало сглаживание.
        if (px < 0) != (vx < 0) and px != 0 and vx != 0:
            return vx, vy
        if (py < 0) != (vy < 0) and py != 0 and vy != 0:
            return vx, vy
        if abs(vx - px) > 0.6 * max(abs(vx), abs(px), 1.0):
            return vx, vy
        return (vx + px) / 2.0, (vy + py) / 2.0

    def ready(self):
        vx, vy = self.velocity()
        return vx is not None and vy is not None


def move_decision(paddle_x, target_x, dead_zone=8.0):
    """Куда ехать: -1 влево, +1 вправо, 0 стоять.

    Мёртвая зона нужна, иначе платформа дребезжит вокруг цели и теряет
    скорость на смене направления.
    """
    if target_x is None or paddle_x is None:
        return 0
    diff = target_x - paddle_x
    if abs(diff) <= dead_zone:
        return 0
    return 1 if diff > 0 else -1


def press_time(distance, speed, min_sec=0.02, max_sec=0.35):
    """Сколько держать клавишу, чтобы проехать `distance` пикселей."""
    if speed <= 0:
        return min_sec
    return max(min_sec, min(max_sec, abs(distance) / float(speed)))
