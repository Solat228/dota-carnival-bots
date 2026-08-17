# -*- coding: utf-8 -*-
"""Какие слова встретились в логах и какие из них НЕ знает словарь.

Незнакомые слова важны вдвойне: их нельзя починить по словарю, и именно на них
OCR ошибается безнаказанно. Отчёт подсказывает, что дописать в `words.py`.

    python tools/words_report.py Debug/dry.log Debug/live2.log
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import words as wordsmod  # noqa: E402

LINE = re.compile(r'^\[(?:dry|бот)\]\s+([^:]+):\s+([A-Z]+)', re.M)
TRACK = re.compile(r'^\S+\.png\s+([A-Z]+)', re.M)


def read_words(path):
    """Лог -> список прочитанных строк по порядку."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            blob = f.read()
    except OSError:
        return []
    out = [m.group(2) for m in LINE.finditer(blob)]
    return out or [m.group(1) for m in TRACK.finditer(blob)]


def full_words(readings):
    """Оставляет только НАЧАЛА слов: остатки короче предыдущего чтения."""
    out, prev = [], ''
    for text in readings:
        if len(text) > len(prev):
            out.append(text)
        prev = text
    return out


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv:
        argv = sorted(glob.glob(os.path.join(ROOT, 'Debug', '*.log'))) + \
               sorted(glob.glob(os.path.join(ROOT, 'Debug', 'track.txt')))
    vocab = wordsmod.Vocabulary()
    seen = {}
    for path in argv:
        for word in full_words(read_words(path)):
            seen[word] = seen.get(word, 0) + 1
    known = {w: c for w, c in seen.items() if w in vocab.words}
    alien = {w: c for w, c in seen.items() if w not in vocab.words}
    print(f'файлы: {len(argv)}, разных слов: {len(seen)} '
          f'(знакомых {len(known)}, незнакомых {len(alien)})\n')
    print('НЕ в словаре (кандидаты на добавление):')
    for word, count in sorted(alien.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'   {count:3d}  {word}')
    print('\nв словаре:')
    print('   ' + ', '.join(sorted(known)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
