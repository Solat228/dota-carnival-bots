# -*- coding: utf-8 -*-
"""Тесты словаря и починки OCR."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import words  # noqa: E402


def test_normalize_strips_everything_but_letters():
    assert words.normalize("Aghanim's Scepter") == 'AGHANIMSSCEPTER'
    assert words.normalize('anti-mage') == 'ANTIMAGE'
    assert words.normalize('  ') == ''
    assert words.normalize(None) == ''


def test_parse_list_keeps_multiword_names_whole():
    got = words.parse_list('Crystal Maiden, Zeus, Anti-Mage')
    assert got == {'CRYSTALMAIDEN', 'ZEUS', 'ANTIMAGE'}


def test_base_words_has_seen_words():
    base = words.base_words()
    for word in ('ZEUS', 'LESHRAC', 'BLOODTHORN', 'RUBICK', 'TIMBERSAW',
                 'MEKANSM', 'SHRAPNEL', 'HEADDRESS', 'BANANA', 'PARASMA'):
        assert word in base, word


def test_suffix_index_groups_by_length():
    index = words.suffix_index({'ZEUS'})
    assert index[4]['ZEUS'] == 'ZEUS'
    assert index[3]['EUS'] == 'ZEUS'
    assert index[1]['S'] == 'ZEUS'


def test_has_suffix():
    index = words.suffix_index({'ZEUS'})
    assert words.has_suffix('EUS', index)
    assert not words.has_suffix('EUX', index)


def test_correct_keeps_honest_remainder():
    #честный остаток слова менять нельзя
    index = words.suffix_index(words.base_words())
    assert words.correct('EUS', index) == ('EUS', 1.0)
    assert words.correct('ICK', index)[0] == 'ICK'


def test_correct_fixes_ocr_letter_swap():
    index = words.suffix_index(words.base_words())
    #настоящие ошибки OCR из офлайн-прогона
    assert words.correct('TINIBERSAW', index)[0] == 'TIMBERSAW'
    assert words.correct('MEKANSNT', index)[0] == 'MEKANSM'


def test_correct_gives_up_on_garbage():
    index = words.suffix_index(words.base_words())
    text, conf = words.correct('QQWWZZXX', index)
    assert conf == 0.0
    assert text == 'QQWWZZXX'      #лучше напечатать как есть, чем угадать неверно


def test_correct_empty():
    assert words.correct('', {}) == ('', 0.0)


def test_vocabulary_add_extends_index():
    voc = words.Vocabulary(learned_path=os.devnull)
    assert voc.fix('ZZZTOP')[1] == 0.0
    assert voc.add('ZZZTOP')
    assert voc.fix('ZZZTOP') == ('ZZZTOP', 1.0)
    assert voc.fix('ZZTOP')[0] == 'ZZTOP'     #суффикс тоже известен
    assert not voc.add('ZZZTOP')              #повторно не добавляем


def test_vocabulary_learns_after_repeats(tmp_path):
    path = str(tmp_path / 'learned.json')
    voc = words.Vocabulary(learned_path=path)
    assert not voc.observe_full_word('NEWTHING', need=3)
    assert not voc.observe_full_word('NEWTHING', need=3)
    assert voc.observe_full_word('NEWTHING', need=3)
    assert 'NEWTHING' in words.load_learned(path)


def test_vocabulary_ignores_short_words(tmp_path):
    voc = words.Vocabulary(learned_path=str(tmp_path / 'l.json'))
    assert not voc.observe_full_word('AB', need=1)


def test_save_and_load_learned(tmp_path):
    path = str(tmp_path / 'l.json')
    words.save_learned({'ALPHA', 'BETA'}, path)
    assert words.load_learned(path) == {'ALPHA', 'BETA'}


def test_load_learned_broken_file(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{ не json', encoding='utf-8')
    assert words.load_learned(str(path)) == set()
