# -*- coding: utf-8 -*-
"""Решения бота: что делать на текущем кадре.

Без ввода-вывода: на вход — что увидели, на выход — действие. Так вся логика
(в том числе выход из паузы и перезапуск после проигрыша) проверяется тестами
без запущенной игры.
"""

import collections

from . import physics

#move: -1 влево, +1 вправо, 0 стоять; click — точка в координатах панели
Action = collections.namedtuple(
    'Action', 'move space f9 click note')


def _act(move=0, space=False, f9=False, click=None, note=''):
    return Action(move, space, f9, click, note)


class Brain:
    """Мозг арканоида: следит за мячом и выводит игру из любых экранов.

    paddle_speed — измеренная скорость тележки (px/с). Нужна, чтобы понимать,
    успеваем ли доехать: если нет, едем всё равно, но целимся краем.
    """

    def __init__(self, paddle_speed=200.0, dead_zone=10.0, press_gap=0.8,
                 lost_ball_sec=1.2, aim_offset=0.0, fallbacks=None,
                 fallback_after=3.0):
        self.paddle_speed = float(paddle_speed)
        self.dead_zone = float(dead_zone)
        self.press_gap = float(press_gap)
        self.lost_ball_sec = float(lost_ball_sec)
        self.aim_offset = float(aim_offset)
        #Куда кликать, если шаблон кнопки не нашёлся: координаты панели,
        #замерены по живым кликам («Играть» и «Сыграть ещё» стоят на месте).
        self.fallbacks = dict(fallbacks or {})
        self.fallback_after = float(fallback_after)
        self.tracker = physics.BallTracker()
        self.last_press = -99.0
        self.last_ball_seen = -99.0
        self.last_state = ''
        self.state_since = 0.0
        self.target = None

    # --- вспомогательное ----------------------------------------------------
    def _note_state(self, t, state):
        if state != self.last_state:
            self.last_state = state
            self.state_since = t

    def _can_press(self, t):
        return (t - self.last_press) >= self.press_gap

    def _press(self, t):
        self.last_press = t

    # --- главный шаг --------------------------------------------------------
    def step(self, t, state, field, paddle, ball, buttons=None, hint=False,
             brick_x=None):
        """Кадр -> действие.

        state   — 'play' | 'dim' | 'other' (из vision.screen_state)
        field   — (left, top, right, bottom) или None
        paddle  — (center_x, half_width, top_y) или None
        ball    — (x, y) или None
        buttons — {'play': (x, y), 'again': (x, y)} что нашли шаблонами
        """
        self._note_state(t, state)
        if state == 'dim':
            return self._step_dim(t, buttons)
        if state != 'play':
            return self._step_menu(t, buttons)
        return self._step_play(t, field, paddle, ball, hint, brick_x)

    # --- пауза и конец игры -------------------------------------------------
    def _step_dim(self, t, buttons):
        """Экран погас: сперва пробуем снять паузу, потом жмём кнопку."""
        again = (buttons or {}).get('again')
        if again and self._can_press(t):
            self._press(t)
            return _act(click=again, note='конец игры -> сыграть ещё')
        if (t - self.state_since) < 1.5:
            if self._can_press(t):
                self._press(t)
                return _act(f9=True, note='пауза -> F9')
            return _act(note='ждём выхода из паузы')
        spot = self.fallbacks.get('again')
        if spot and (t - self.state_since) > self.fallback_after and self._can_press(t):
            self._press(t)
            return _act(click=spot, note='экран не уходит -> клик «сыграть ещё»')
        if self._can_press(t):
            self._press(t)
            return _act(space=True, note='затемнение не уходит -> пробел')
        return _act(note='ждём')

    # --- меню, правила, межуровневая пауза ----------------------------------
    def _step_menu(self, t, buttons):
        play_btn = (buttons or {}).get('play')
        if play_btn and self._can_press(t):
            self._press(t)
            return _act(click=play_btn, note='меню -> играть')
        again = (buttons or {}).get('again')
        if again and self._can_press(t):
            self._press(t)
            return _act(click=again, note='меню -> сыграть ещё')
        #Порядок важен: сперва пробуем пробел (он безобиден), а если экран не
        #ушёл — жмём мышью туда, где кнопка стоит всегда. Иначе бот вечно
        #долбил бы пробел в застрявшем меню.
        spot = self.fallbacks.get('play')
        if spot and (t - self.state_since) > self.fallback_after and self._can_press(t):
            self._press(t)
            return _act(click=spot, note='экран не уходит -> клик «играть»')
        #между уровнями кнопок нет: игра сама продолжится, но пробел не мешает
        if (t - self.state_since) > 2.0 and self._can_press(t):
            self._press(t)
            return _act(space=True, note='экран без кнопок -> пробел')
        return _act(note='ждём экран')

    # --- собственно игра ----------------------------------------------------
    def _step_play(self, t, field, paddle, ball, hint=False, brick_x=None):
        if field is None or paddle is None:
            return _act(note='не вижу поле или платформу')
        left, _top, right, _bottom = field
        paddle_x, half, paddle_top = paddle

        if hint:
            #Видна подсказка с пробелом — сапог ещё не брошен. Это надёжнее
            #«мяча не видно»: ложные пятна по краям поля обманывали трекер,
            #и бот стоял на «Выбрать позицию», пока не кончались жизни.
            self.tracker.reset()
            centre = (left + right) / 2.0
            move = physics.move_decision(paddle_x, centre, self.dead_zone)
            if self._can_press(t):
                self._press(t)
                return _act(move=move, space=True, note='подсказка -> пробел')
            return _act(move=move, note='ждём броска')

        if ball is not None:
            self.last_ball_seen = t
            self.tracker.update(t, ball[0], ball[1])
        elif (t - self.last_ball_seen) > self.lost_ball_sec:
            #Мяча нет: либо ждём броска, либо сапог потерян. Жмём пробел
            #(в игре он безвреден) и держимся центра — оттуда ближе до всего.
            self.tracker.reset()
            centre = (left + right) / 2.0
            move = physics.move_decision(paddle_x, centre, self.dead_zone)
            if self._can_press(t):
                self._press(t)
                return _act(move=move, space=True, note='мяча нет -> бросок')
            return _act(move=move, note='мяча нет -> к центру')

        target = self._target_for(field, paddle, ball, brick_x)
        self.target = target
        move = physics.move_decision(paddle_x, target, self.dead_zone)
        note = '' if target is None else f'цель {target:.0f}'
        return _act(move=move, note=note)

    def _offset_for(self, field, paddle, hit, brick_x):
        """Смещение платформы под удар краем — только когда есть запас времени.

        Приём краем ускоряет снос блоков, но промахнуться им проще. Поэтому
        целимся краем, лишь если успеваем доехать с запасом (иначе — центром).
        """
        if brick_x is None or hit is None:
            return self.aim_offset
        paddle_x, half, paddle_top = paddle
        left, _top, right, _bottom = field
        _vx, vy = self.tracker.velocity()
        _bx, by = self.tracker.position()
        left_sec = physics.time_to_line(by, vy, paddle_top)
        want = physics.aim_offset_for(hit, brick_x, left, right)
        need = self.reach_time(paddle_x, hit + want * half)
        if left_sec is None or need is None or need > left_sec * 0.6:
            return self.aim_offset
        return want

    def _target_for(self, field, paddle, ball, brick_x=None):
        """Куда вести центр платформы."""
        left, _top, right, _bottom = field
        _paddle_x, half, paddle_top = paddle
        vx, vy = self.tracker.velocity()
        bx, by = self.tracker.position()
        if bx is None:
            bx, by = (ball if ball else (None, None))
        if vy is not None and vy > 0:
            hit = physics.predict_x(bx, by, vx, vy, left, right, paddle_top)
            if hit is not None:
                offset = self._offset_for(field, paddle, hit, brick_x)
                return physics.aim_with_offset(hit, half, left, right, offset)
        #Мяч летит вверх или скорость неизвестна: держимся под мячом —
        #так меньше ехать, когда он пойдёт вниз.
        if bx is None:
            return None
        return physics.clamp_paddle(bx, half, left, right)

    def expected_ball(self, t):
        """Где мяч должен быть сейчас: позиция + скорость × прошедшее время.

        По этой точке `vision.find_ball` выбирает нужное пятно движения —
        иначе оно цепляется за то место, ОТКУДА мяч ушёл.
        """
        x, y = self.tracker.position()
        if x is None:
            return None
        vx, vy = self.tracker.velocity()
        if vx is None:
            return x, y
        dt = max(0.0, t - self.tracker.samples[-1][0])
        return x + vx * dt, y + vy * dt

    # --- телеметрия ---------------------------------------------------------
    def reach_time(self, paddle_x, target_x):
        """За сколько секунд тележка доедет до цели."""
        if target_x is None or paddle_x is None:
            return None
        return abs(target_x - paddle_x) / max(1.0, self.paddle_speed)
