# -*- coding: utf-8 -*-
"""Грабер кадров экрана для мини-игры «Атака автоматонов» (Dota 2).

Снимает экран с заданной частотой и складывает PNG в папку, чтобы потом
по этим кадрам настраивать области распознавания и шаблоны букв.

Запуск:
    python grab.py --secs 90 --fps 2
    python grab.py --secs 90 --fps 2 --out Screens --changed-only

Ключи:
    --secs N          сколько секунд снимать (0 = до Ctrl+C / до нажатия F9)
    --fps N           кадров в секунду (по умолчанию 2)
    --out DIR         папка для кадров (по умолчанию Screens)
    --changed-only    сохранять кадр только если картинка заметно изменилась
    --jpeg            сохранять в JPEG (в 10 раз легче, но с артефактами)

Каждый кадр сопровождается строкой в meta.jsonl: имя файла, время,
заголовок и прямоугольник активного окна (чтобы знать, где была Dota).
"""

import argparse
import ctypes
import json
import os
import sys
import time

# --- захват экрана: mss -> PIL -> win32 (что найдётся) ------------------------

_GRABBER = None
_GRABBER_NAME = ''


def _make_grabber():
    """Возвращает (функция_снимка -> numpy/PIL, имя способа)."""
    try:
        import mss  # type: ignore
        import numpy as np  # noqa: F401  (нужен для конверсии)
        sct = mss.mss()
        mon = sct.monitors[1]

        def grab_mss():
            import numpy as np
            raw = sct.grab(mon)
            arr = np.asarray(raw)          # BGRA
            return arr[:, :, :3][:, :, ::-1]  # -> RGB
        return grab_mss, 'mss'
    except Exception:
        pass

    try:
        from PIL import ImageGrab  # type: ignore
        import numpy as np

        def grab_pil():
            img = ImageGrab.grab(all_screens=False)
            return np.asarray(img.convert('RGB'))
        return grab_pil, 'pillow'
    except Exception:
        pass

    raise RuntimeError('Нет ни mss, ни Pillow: pip install mss pillow')


# --- сведения об активном окне ------------------------------------------------

def foreground_info():
    """Заголовок и прямоугольник активного окна (без сторонних библиотек)."""
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        length = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)

        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
        r = RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        return buf.value, [r.left, r.top, r.right, r.bottom]
    except Exception:
        return '', [0, 0, 0, 0]


def key_down(vk):
    """Нажата ли клавиша прямо сейчас (для аварийной остановки)."""
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


def diff_score(a, b):
    """Грубая мера различия двух кадров (0..1). Считается по прореженной сетке."""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    import numpy as np
    sa = a[::8, ::8].astype('int16')
    sb = b[::8, ::8].astype('int16')
    return float(np.abs(sa - sb).mean() / 255.0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--secs', type=float, default=90.0)
    ap.add_argument('--fps', type=float, default=2.0)
    ap.add_argument('--out', default='Screens')
    ap.add_argument('--changed-only', action='store_true')
    ap.add_argument('--threshold', type=float, default=0.004,
                    help='порог различия кадров для --changed-only')
    ap.add_argument('--jpeg', action='store_true')
    args = ap.parse_args(argv)

    grab, name = _make_grabber()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    os.makedirs(out_dir, exist_ok=True)
    meta_path = os.path.join(out_dir, 'meta.jsonl')

    from PIL import Image
    period = 1.0 / max(0.1, args.fps)
    t_end = time.time() + args.secs if args.secs > 0 else float('inf')
    prev = None
    saved = 0
    seen = 0

    print(f'[grab] способ={name} папка={out_dir} fps={args.fps} '
          f'секунд={args.secs if args.secs > 0 else "∞"} (F9 — стоп)')
    sys.stdout.flush()

    try:
        while time.time() < t_end:
            t0 = time.time()
            if key_down(0x78):  # F9
                print('[grab] F9 — остановка')
                break
            frame = grab()
            seen += 1
            if args.changed_only and diff_score(prev, frame) < args.threshold:
                prev = frame
                time.sleep(max(0.0, period - (time.time() - t0)))
                continue
            prev = frame

            stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{int(time.time() * 1000) % 1000:03d}'
            ext = 'jpg' if args.jpeg else 'png'
            fname = f'shot_{stamp}.{ext}'
            img = Image.fromarray(frame)
            if args.jpeg:
                img.save(os.path.join(out_dir, fname), quality=92)
            else:
                img.save(os.path.join(out_dir, fname), compress_level=1)
            title, rect = foreground_info()
            with open(meta_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'file': fname, 'ts': time.time(),
                                    'title': title, 'rect': rect},
                                   ensure_ascii=False) + '\n')
            saved += 1
            if saved % 10 == 0:
                print(f'[grab] сохранено {saved} кадров (окно: {title[:40]})')
                sys.stdout.flush()
            time.sleep(max(0.0, period - (time.time() - t0)))
    except KeyboardInterrupt:
        print('[grab] Ctrl+C')

    print(f'[grab] готово: снято {seen}, сохранено {saved} -> {out_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
