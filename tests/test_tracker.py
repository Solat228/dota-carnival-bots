# -*- coding: utf-8 -*-
"""Якорная починка остатков: по СЛОВУ, а не по всему словарю.

Случаи взяты из живого прогона 2026-08-17 (Debug/dry.log) — там словарь
портил честные остатки.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import words


def tracker():
    return words.WordTracker(words.Vocabulary())


def feed_all(trk, readings):
    return [trk.feed(r)[0] for r in readings]


# --- регресс живого прогона -------------------------------------------------

def test_live_bug_maelstrom_not_master():
    """'MAELSTR' (обрезанное чтение MAELSTROM) НЕ должно стать 'MASTER'."""
    trk = tracker()
    assert trk.feed('MAELSTROM')[0] == 'MAELSTROM'
    assert trk.feed('MAELSTR')[0] != 'MASTER'


def test_live_bug_frostbite_tail_kept():
    """'ITE' — хвост FROSTBITE (слова нет в словаре), чинить в 'IT' нельзя."""
    trk = tracker()
    trk.feed('FROSTBITE')
    assert trk.feed('ITE')[0] == 'ITE'


def test_live_bug_muer_not_mer():
    """'MUER' при наборе MUERTA не должно превращаться в 'MER'."""
    trk = tracker()
    trk.feed('MUERTA')
    assert trk.feed('MUER')[0] != 'MER'


def test_live_bug_other_enemy_phrase_not_snapped():
    """Цель сменилась на другого врага: 'BEPOSITIVE' нельзя тянуть к 'BENEGATIVE'."""
    trk = tracker()
    trk.feed('DONTBENEGATIVE')
    assert trk.feed('BEPOSITIVE')[0] == 'BEPOSITIVE'


def test_live_bug_garbage_anchor_yields_to_longer_read():
    """Мусорный якорь не должен переживать более длинное верное чтение."""
    trk = tracker()
    trk.feed('FRVERWARD')                      #мусор от OCR
    assert trk.feed('SERVERWARD')[0] == 'SERVERWARD'
    assert trk.anchor == 'SERVERWARD'


def test_phrases_are_typed_as_is():
    """В мини-игре бывают целые реплики — словаря для них нет и не надо."""
    trk = tracker()
    assert trk.feed('HAHACOULDEATAWALRUS')[0] == 'HAHACOULDEATAWALRUS'
    assert trk.feed('COULDEATAWALRUS')[0] == 'COULDEATAWALRUS'
    assert trk.feed('WALRUS')[0] == 'WALRUS'


def test_unknown_word_typed_as_is():
    """Слова вне словаря (способности, шмот из ивента) печатаются как есть."""
    trk = tracker()
    assert trk.feed('FROSTBITE')[0] == 'FROSTBITE'


# --- обычный ход набора -----------------------------------------------------

def test_shrinking_remainders_pass_through():
    trk = tracker()
    got = feed_all(trk, ['LESHRAC', 'ESHRAC', 'HRAC', 'AC', 'C'])
    assert got == ['LESHRAC', 'ESHRAC', 'HRAC', 'AC', 'C']


def test_new_word_resets_anchor():
    trk = tracker()
    trk.feed('BRACER')
    trk.feed('ACER')
    assert trk.feed('HEADDRESS')[0] == 'HEADDRESS'
    assert trk.anchor == 'HEADDRESS'


def test_anchor_fixes_ocr_slip_inside_word():
    """Пропущенная буква в середине остатка чинится по якорю."""
    trk = tracker()
    trk.feed('BATRIDER')
    assert trk.feed('ATRDER')[0] == 'ATRIDER'


def test_full_word_dict_fix_on_anchor():
    """Словарь применяется к слову целиком: 'LEUS' -> 'ZEUS'."""
    trk = tracker()
    assert trk.feed('LEUS')[0] == 'ZEUS'


def test_label_sets_anchor():
    trk = tracker()
    assert trk.note_label('BLOODTHORN')
    #M вместо N — типичная промашка OCR на последней букве
    assert trk.feed('BLOODTHORM')[0] == 'BLOODTHORN'


def test_short_label_ignored():
    trk = tracker()
    assert not trk.note_label('AB')


def test_reset_clears_state():
    trk = tracker()
    trk.feed('RUBICK')
    trk.reset()
    assert trk.anchor == '' and trk.last == ''


def test_empty_reading():
    assert tracker().feed('')[0] == ''


# --- чистые функции ---------------------------------------------------------

def test_best_suffix_prefers_same_first_letter():
    assert words.best_suffix('ADDRESS', 'HEADDRESS')[0] == 'ADDRESS'


def test_best_suffix_allows_lost_tail_letters():
    """OCR теряет гаснущие последние буквы — кандидат может быть длиннее."""
    got, score = words.best_suffix('MUER', 'MUERTA')
    assert got == 'MUERTA' and score > 0.6


def test_best_suffix_rejects_alien_text():
    assert words.best_suffix('QQQQQ', 'HEADDRESS')[0] == ''


def test_best_suffix_empty_args():
    assert words.best_suffix('', 'ZEUS') == ('', 0.0)
    assert words.best_suffix('ZEUS', '') == ('', 0.0)


def test_correct_full_only_whole_words():
    idx = words.full_word_index(words.base_words())
    #MASTER — не отдельный предмет: 'MAELSTR' чинить не во что
    assert words.correct_full('MAELSTR', idx)[0] == 'MAELSTR'
    assert words.correct_full('LEUS', idx)[0] == 'ZEUS'


def test_edit_distance():
    assert words.edit_distance('ZEUS', 'ZEUS') == 0
    assert words.edit_distance('LEUS', 'ZEUS') == 1
    assert words.edit_distance('', 'AXE') == 3
    assert words.edit_distance('SERVERWARD', 'SENTRYWARD') == 4


def test_plausible_fix_allows_ocr_slips():
    assert words.plausible_fix('LEUS', 'ZEUS')            #одна буква
    assert words.plausible_fix('TINIBERSAW', 'TIMBERSAW')  #M прочиталось как NI
    assert words.plausible_fix('MEKANSNT', 'MEKANSM')
    assert words.plausible_fix('ERSEVERANCE', 'PERSEVERANCE')
    assert words.plausible_fix('MUER', 'MUERTA')          #потерян хвост


def test_plausible_fix_rejects_other_words():
    assert not words.plausible_fix('SERVERWARD', 'SENTRYWARD')
    assert not words.plausible_fix('BEPOSITIVE', 'BENEGATIVE')
    assert not words.plausible_fix('', 'ZEUS')


def test_full_word_index_groups_by_length():
    idx = words.full_word_index({'ZEUS', 'AXE', 'BANE'})
    assert set(idx[4]) == {'ZEUS', 'BANE'} and idx[3] == ['AXE']
