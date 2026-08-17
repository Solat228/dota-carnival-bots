# -*- coding: utf-8 -*-
"""Единый запуск ботов мини-игр Dota 2 (Dark Carnival).

    python run.py                — меню выбора
    python run.py typer          — бот «Атака автоматонов» (печатает слова)
    python run.py typer --dry    — он же вхолостую (ничего не нажимает)
    python run.py boot           — бот «Сапожный снос» (арканоид)
    python run.py boot --dry     — он же вхолостую
    python run.py grab           — грабер кадров (для настройки распознавания)
    python run.py tests          — прогон тестов
    python run.py doctor         — проверка окружения (питон, tesseract, окно игры)

Всё, что нужно знать перед запуском: горячие клавиши **F10 — старт/стоп**,
**F12 — выход**. Они работают глобально, жать можно прямо из игры.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#Цвета консоли (Windows 10+ понимает ANSI). Без них вывод остаётся читаемым.
C_OK, C_WARN, C_ERR, C_DIM, C_END = '\033[92m', '\033[93m', '\033[91m', '\033[90m', '\033[0m'

GAMES = {
    'typer': ('main.py', 'Атака автоматонов — печатает слова с экрана'),
    'boot': ('boot.py', 'Сапожный снос — арканоид, играет платформой'),
    'grab': ('grab.py', 'Грабер кадров — снимает экран для настройки'),
}


def enable_colors():
    """Включает ANSI-цвета в консоли Windows (иначе печатаются кракозябры)."""
    global C_OK, C_WARN, C_ERR, C_DIM, C_END
    if not sys.stdout.isatty():
        #вывод перенаправлен в файл или в другой процесс — цвета там мусор
        C_OK = C_WARN = C_ERR = C_DIM = C_END = ''
        return
    if os.name != 'nt':
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetConsoleMode(k32.GetStdHandle(-11), 7)    # ENABLE_VIRTUAL_TERMINAL
    except Exception:
        pass


def say(text, color=''):
    print(f'{color}{text}{C_END}' if color else text)


def run(script, args):
    """Запускает скрипт проекта тем же питоном, что и лаунчер."""
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        say(f'нет файла {script}', C_ERR)
        return 1
    return subprocess.call([sys.executable, '-u', path] + list(args))


def doctor():
    """Проверяет всё, что нужно ботам: питон, зависимости, tesseract, игру."""
    say('Проверка окружения', C_DIM)
    ok = True
    say(f'  питон           {sys.version.split()[0]}', C_OK)
    for mod in ('cv2', 'numpy', 'pytesseract', 'win32gui'):
        try:
            __import__(mod)
            say(f'  {mod:15s} есть', C_OK)
        except ImportError:
            say(f'  {mod:15s} НЕТ — поставь: pip install -r requirements.txt', C_ERR)
            ok = False
    try:
        sys.path.insert(0, HERE)
        import config
        exe = config.find_tesseract('')
        if exe and os.path.exists(exe):
            say(f'  tesseract       {exe}', C_OK)
        else:
            say('  tesseract       НЕ НАЙДЕН — счёт и слова читаться не будут', C_WARN)
            ok = False
    except Exception as err:
        say(f'  tesseract       сбой проверки: {err}', C_WARN)
    try:
        import capture
        hwnd, title = capture.find_window('Dota 2')
        if hwnd:
            say(f'  окно игры       {title}', C_OK)
        else:
            say('  окно игры       не найдено (запусти Dota 2)', C_WARN)
    except Exception as err:
        say(f'  окно игры       сбой проверки: {err}', C_WARN)
    say('Готово' if ok else 'Есть замечания — смотри выше',
        C_OK if ok else C_WARN)
    return 0 if ok else 1


def menu():
    """Меню для тех, кто запустил файл двойным кликом."""
    say('\n  БОТЫ МИНИ-ИГР DOTA 2\n', C_OK)
    items = [
        ('1', 'Арканоид «Сапожный снос» — играть', ('boot', ['--start'])),
        ('2', 'Арканоид — вхолостую (без нажатий)', ('boot', ['--dry', '--start'])),
        ('3', 'Печаталка «Атака автоматонов» — играть', ('typer', ['--start'])),
        ('4', 'Печаталка — вхолостую', ('typer', ['--dry', '--start'])),
        ('5', 'Проверить окружение', ('doctor', [])),
        ('6', 'Прогнать тесты', ('tests', [])),
        ('0', 'Выход', None),
    ]
    for key, title, _cmd in items:
        say(f'   {key}. {title}')
    say('\n   F10 — старт/стоп, F12 — выход из бота\n', C_DIM)
    choice = input('  Выбор: ').strip()
    for key, _title, cmd in items:
        if key == choice:
            if cmd is None:
                return 0
            name, args = cmd
            return dispatch(name, args)
    say('  не понял выбор', C_WARN)
    return 1


def dispatch(name, args):
    if name == 'doctor':
        return doctor()
    if name == 'tests':
        return subprocess.call([sys.executable, '-m', 'pytest', 'tests', '-q'],
                               cwd=HERE)
    if name in GAMES:
        script, about = GAMES[name]
        say(f'  {about}', C_DIM)
        return run(script, args)
    say(f'не знаю команду {name!r}', C_ERR)
    return 2


def main(argv=None):
    enable_colors()
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        return menu()
    name, args = argv[0], argv[1:]
    if name in ('-h', '--help', 'help'):
        print(__doc__)
        return 0
    return dispatch(name, args)


if __name__ == '__main__':
    raise SystemExit(main())
