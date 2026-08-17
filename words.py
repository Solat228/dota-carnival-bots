# -*- coding: utf-8 -*-
"""Словарь слов мини-игры (герои/предметы Dota) и починка ошибок OCR.

Особенность: строка прогресса показывает ОСТАТОК слова (что ещё не набрано),
поэтому сравнивать надо не со словами целиком, а со всеми их СУФФИКСАМИ:
    ZEUS -> ZEUS, EUS, US, S
Тогда «LEUS» (OCR перепутал Z и L) чинится в «ZEUS», а честный остаток «EUS»
остаётся как есть.

Слова хранятся нормализованными: только A-Z, без пробелов и апострофов —
в игре пробелы и знаки препинания печатать не нужно.
"""

import difflib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNED_PATH = os.path.join(HERE, 'learned_words.json')

#Герои Dota 2 (имена целиком, через запятую)
HEROES = """
Abaddon, Alchemist, Ancient Apparition, Anti-Mage, Arc Warden, Axe, Bane,
Batrider, Beastmaster, Bloodseeker, Bounty Hunter, Brewmaster, Bristleback,
Broodmother, Centaur Warrunner, Chaos Knight, Chen, Clinkz, Clockwerk,
Crystal Maiden, Dark Seer, Dark Willow, Dawnbreaker, Dazzle, Death Prophet,
Disruptor, Doom, Dragon Knight, Drow Ranger, Earth Spirit, Earthshaker,
Elder Titan, Ember Spirit, Enchantress, Enigma, Faceless Void, Grimstroke,
Gyrocopter, Hoodwink, Huskar, Invoker, Io, Jakiro, Juggernaut,
Keeper of the Light, Kez, Kunkka, Legion Commander, Leshrac, Lich, Lifestealer,
Lina, Lion, Lone Druid, Luna, Lycan, Magnus, Marci, Mars, Medusa, Meepo,
Mirana, Monkey King, Morphling, Muerta, Naga Siren, Natures Prophet, Necrophos,
Night Stalker, Nyx Assassin, Ogre Magi, Omniknight, Oracle, Outworld Destroyer,
Pangolier, Phantom Assassin, Phantom Lancer, Phoenix, Primal Beast, Puck, Pudge,
Pugna, Queen of Pain, Razor, Riki, Ringmaster, Rubick, Sand King, Shadow Demon,
Shadow Fiend, Shadow Shaman, Silencer, Skywrath Mage, Slardar, Slark, Snapfire,
Sniper, Spectre, Spirit Breaker, Storm Spirit, Sven, Techies, Templar Assassin,
Terrorblade, Tidehunter, Timbersaw, Tinker, Tiny, Treant Protector,
Troll Warlord, Tusk, Underlord, Undying, Ursa, Vengeful Spirit, Venomancer,
Viper, Visage, Void Spirit, Warlock, Weaver, Windranger, Winter Wyvern,
Witch Doctor, Wraith King, Zeus, Roshan
"""

#Предметы, расходники и рецепты
ITEMS = """
Abyssal Blade, Aegis, Aeon Disk, Aghanims Scepter, Aghanims Shard, Arcane Blink,
Arcane Boots, Assault Cuirass, Banana, Battle Fury, Belt of Strength,
Black King Bar, Blade Mail, Blade of Alacrity, Blades of Attack, Blight Stone,
Blink Dagger, Blitz Knuckles, Blood Grenade, Bloodstone, Bloodthorn,
Boots of Speed, Bottle, Bracer, Broadsword, Buckler, Butterfly, Chainmail,
Cheese, Circlet, Clarity, Claymore, Cloak, Crimson Guard, Crown, Daedalus,
Demon Edge, Desolator, Diadem, Diffusal Blade, Disperser, Divine Rapier,
Dragon Lance, Drum of Endurance, Dust of Appearance, Eaglesong, Echo Sabre,
Enchanted Mango, Energy Booster, Ethereal Blade, Euls Scepter, Eye of Skadi,
Faerie Fire, Falcon Blade, Force Staff, Gauntlets, Gem of True Sight, Gleipnir,
Gloves of Haste, Guardian Greaves, Hand of Midas, Harpoon, Headdress,
Heart of Tarrasque, Heavens Halberd, Helm of Iron Will, Helm of the Dominator,
Hood of Defiance, Hurricane Pike, Hyperstone, Iron Branch, Javelin, Kaya,
Khanda, Linkens Sphere, Lotus Orb, Maelstrom, Magic Stick, Magic Wand,
Manta Style, Mantle of Intelligence, Mask of Madness, Mekansm, Meteor Hammer,
Mjollnir, Monkey King Bar, Moon Shard, Mystic Staff, Necronomicon,
Null Talisman, Nullifier, Observer Ward, Octarine Core, Ogre Axe,
Orb of Corrosion, Orb of Venom, Orchid Malevolence, Overwhelming Blink,
Parasma, Pavise, Perseverance, Phase Boots, Pipe of Insight, Platemail,
Point Booster, Power Treads, Quarterstaff, Quelling Blade, Radiance, Reaver,
Refresher Orb, Refresher Shard, Revenants Brooch, Ring of Aquila,
Ring of Basilius, Ring of Health, Ring of Protection, Ring of Regen,
Robe of the Magi, Rod of Atos, Sacred Relic, Sange, Satanic, Scythe of Vyse,
Sentry Ward, Shadow Blade, Shawl, Shivas Guard, Shrapnel, Silver Edge,
Skull Basher, Slippers of Agility, Smoke of Deceit, Solar Crest, Soul Booster,
Soul Ring, Spirit Vessel, Staff of Wizardry, Swift Blink, Talisman of Evasion,
Tango, Tome of Knowledge, Town Portal Scroll, Tranquil Boots, Travel Boots,
Ultimate Orb, Urn of Shadows, Vanguard, Veil of Discord, Vitality Booster,
Vladmirs Offering, Void Stone, Wind Lace, Wind Waker, Witch Blade, Wraith Band,
Yasha, Sange and Yasha, Manta, Basher, Vessel, Greaves, Deso, Bkb,
Crystalys, Ghost Scepter, Splint Mail, Healing Lotus, Roshans Banner,
Giants Ring, Iron Talon, Blitz Knuckles, Diadem, Hex, Battle Fury
"""

#Способности и юниты — встретились в игре 2026-08-17, в списке предметов их нет
ABILITIES = """
Frostbite, Meat Hook, Spirit Bear, Chain Frost, Laguna Blade, Black Hole,
Ravage, Echo Slam, Reverse Polarity, Berserkers Call, Sun Strike, Mana Void,
Fissure, Ice Path, Static Storm, Rearm, Metamorphosis, Poof, Death Ward,
Song of the Siren, Global Silence, Tombstone, Roshan
"""


def normalize(text):
    """Оставляет только A-Z в верхнем регистре (пробелы/дефисы не печатаются)."""
    return re.sub(r'[^A-Z]', '', (text or '').upper())


def parse_list(blob):
    """Список имён через запятую -> набор нормализованных слов."""
    out = set()
    for piece in (blob or '').replace('\n', ' ').split(','):
        token = normalize(piece)
        if len(token) >= 2:
            out.add(token)
    return out


def base_words():
    """Полный базовый словарь (герои + предметы + способности), без пробелов."""
    return parse_list(HEROES) | parse_list(ITEMS) | parse_list(ABILITIES)


def load_learned(path=LEARNED_PATH):
    """Слова, выученные в бою (из зелёных надписей над врагами)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return {normalize(w) for w in data if normalize(w)}
    except Exception:
        pass
    return set()


def save_learned(words, path=LEARNED_PATH):
    """Сохраняет выученные слова (атомарно: tmp + replace)."""
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(sorted(words), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def suffix_index(vocabulary):
    """Суффиксы слов, разложенные по длине: {длина: {суффикс: слово}}."""
    index = {}
    for word in vocabulary:
        for i in range(len(word)):
            suffix = word[i:]
            index.setdefault(len(suffix), {}).setdefault(suffix, word)
    return index


def has_suffix(text, index):
    """Является ли строка суффиксом какого-нибудь слова словаря."""
    return text in index.get(len(text), {})


def correct(text, index, min_ratio=0.80):
    """Чинит OCR-строку по индексу суффиксов.

    Возвращает (строка, уверенность 0..1). Точное совпадение -> 1.0, «не нашёл»
    -> исходная строка и 0.0 (лучше напечатать как есть, чем угадать неверно).
    Кандидаты берём той же длины ±1: OCR обычно путает букву, а не теряет её.
    """
    text = normalize(text)
    if not text:
        return '', 0.0
    if has_suffix(text, index):
        return text, 1.0
    best, best_score = text, 0.0
    for length in (len(text), len(text) - 1, len(text) + 1):
        for candidate in index.get(length, ()):
            ratio = difflib.SequenceMatcher(None, text, candidate).ratio()
            score = ratio + (0.06 if length == len(text) else 0.0)
            if candidate[:1] == text[:1]:
                score += 0.04
            if score > best_score:
                best, best_score = candidate, score
    if best_score >= min_ratio:
        return best, min(1.0, best_score)
    return text, 0.0


def edit_distance(a, b):
    """Расстояние Левенштейна (вставка/удаление/замена)."""
    if a == b:
        return 0
    if not a or not b:
        return len(a) + len(b)
    prev = list(range(len(b) + 1))
    for i, ch in enumerate(a, 1):
        cur = [i]
        for j, other in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ch != other)))
        prev = cur
    return prev[-1]


def plausible_fix(text, candidate, per=4):
    """Похожа ли замена на промашку OCR, а не на ДРУГОЕ слово.

    Разницу в длине не штрафуем: OCR регулярно теряет крайние буквы (гаснут,
    обрезаются рамкой). Считаем только «лишние» несовпадения сверх этой разницы
    и допускаем примерно букву на каждые `per` букв слова.

    Живой лог 2026-08-17: без этого фильтра остаток `SERVERWARD` (от OBSERVER
    WARD) чинился в предмет `SENTRYWARD`, а `BEPOSITIVE` — в `BENEGATIVE`.
    """
    text, candidate = normalize(text), normalize(candidate)
    if not text or not candidate:
        return False
    extra = edit_distance(text, candidate) - abs(len(text) - len(candidate))
    return extra <= max(1, max(len(text), len(candidate)) // per)


def full_word_index(vocabulary):
    """Слова целиком, разложенные по длине: {длина: [слово, ...]}."""
    index = {}
    for word in vocabulary:
        index.setdefault(len(word), []).append(word)
    return index


def correct_full(text, full_index, min_ratio=0.80):
    """Чинит СЛОВО ЦЕЛИКОМ (не остаток) по словарю.

    Отличие от `correct`: кандидаты — только полные слова. Именно тут словарь
    полезен и безопасен: `LEUS` -> `ZEUS`. Сравнение с суффиксами всего словаря
    для остатков ОПАСНО — на живом прогоне честный остаток `MAELSTR` чинился
    в `MASTER` (суффикс BREWMASTER), а `ITE` (хвост FROSTBITE) — в `IT`.
    """
    text = normalize(text)
    if not text:
        return '', 0.0
    if text in full_index.get(len(text), ()):
        return text, 1.0
    best, best_score = text, 0.0
    for length in (len(text), len(text) - 1, len(text) + 1):
        for candidate in full_index.get(length, ()):
            if not plausible_fix(text, candidate):
                continue
            ratio = difflib.SequenceMatcher(None, text, candidate).ratio()
            score = ratio + (0.06 if length == len(text) else 0.0)
            if candidate[:1] == text[:1]:
                score += 0.04
            if score > best_score:
                best, best_score = candidate, score
    if best_score >= min_ratio:
        return best, min(1.0, best_score)
    return text, 0.0


def best_suffix(reading, anchor, min_ratio=0.62):
    """Лучший суффикс слова-якоря для прочитанного остатка -> (суффикс, счёт).

    Длину кандидата берём от len-1 до len+2: OCR чаще теряет последние буквы
    (они гаснут/обрезаются), чем добавляет лишние. Лишняя буква не страшна —
    опечатки игра не засчитывает, а вот недобор букв слово не закроет.
    """
    reading, anchor = normalize(reading), normalize(anchor)
    if not reading or not anchor:
        return '', 0.0
    if anchor.endswith(reading):
        return reading, 1.0
    best, best_score = '', 0.0
    for i in range(len(anchor)):
        suffix = anchor[i:]
        if not (len(reading) - 1 <= len(suffix) <= len(reading) + 2):
            continue
        if not plausible_fix(reading, suffix):
            continue
        score = difflib.SequenceMatcher(None, reading, suffix).ratio()
        if suffix[:1] == reading[:1]:
            score += 0.05
        if len(suffix) == len(reading):
            score += 0.03
        if score > best_score:
            best, best_score = suffix, score
    if best_score >= min_ratio:
        return best, min(1.0, best_score)
    return '', 0.0


class WordTracker:
    """Помнит слово, которое сейчас набирается, и чинит остатки по нему.

    Строка прогресса — суффикс слова, он только УКОРАЧИВАЕТСЯ. Поэтому:
      * новое слово (чтение выросло) -> якорь, чиним по словарю целиком;
      * дальше остаток подгоняем к суффиксам ЯКОРЯ, а не всего словаря.
    """

    def __init__(self, vocab=None, min_ratio=0.80, snap_ratio=0.75):
        self.vocab = vocab
        self.min_ratio = min_ratio
        self.snap_ratio = snap_ratio
        self.anchor = ''
        self.last = ''

    def reset(self):
        self.anchor = ''
        self.last = ''

    def note_label(self, text):
        """Зелёная надпись над врагом — слово целиком, самый надёжный якорь."""
        text = normalize(text)
        if len(text) >= 3:
            self.anchor = text
            self.last = text
            return True
        return False

    def _fix_full(self, text):
        if self.vocab is None:
            return text, 0.0
        return self.vocab.fix_full(text, self.min_ratio)

    def feed(self, reading):
        """Прочитанный остаток -> (что печатать, уверенность, пометка)."""
        reading = normalize(reading)
        if not reading:
            return '', 0.0, ''
        #Остаток слова может только УКОРАЧИВАТЬСЯ. Чтение подлиннее прошлого —
        #это уже другой враг (или чтение стало точнее), якорь надо менять.
        #Мягкое «+1» подводило: мусорный якорь 'FRVERWARD' переживал верное
        #чтение 'SERVERWARD' и портил его обратно (боевой лог 2026-08-17).
        grew = len(reading) > len(self.last)
        if self.anchor and not grew:
            if self.anchor.endswith(reading):
                self.last = reading
                return reading, 1.0, ''
            snapped, score = best_suffix(reading, self.anchor, self.snap_ratio)
            if snapped:
                self.last = snapped
                return snapped, score, ('по слову' if snapped != reading else '')
        text, conf = self._fix_full(reading)
        self.anchor = text
        self.last = text
        return text, conf, ('новое слово' if text != reading else '')


class Vocabulary:
    """Словарь + индекс суффиксов + дозапись выученных слов."""

    def __init__(self, learned_path=LEARNED_PATH):
        self.learned_path = learned_path
        self.base = base_words()
        self.words = set(self.base) | load_learned(learned_path)
        self.index = suffix_index(self.words)
        self.full = full_word_index(self.words)
        self._pending = {}

    def fix(self, text, min_ratio=0.80):
        """OCR-строка -> (исправленная, уверенность). Кандидаты — суффиксы."""
        return correct(text, self.index, min_ratio)

    def fix_full(self, text, min_ratio=0.80):
        """То же, но кандидаты — только СЛОВА ЦЕЛИКОМ (для якоря)."""
        return correct_full(text, self.full, min_ratio)

    def add(self, text):
        """Добавляет слово в словарь и индекс."""
        text = normalize(text)
        if len(text) < 3 or text in self.words:
            return False
        self.words.add(text)
        for i in range(len(text)):
            self.index.setdefault(len(text) - i, {}).setdefault(text[i:], text)
        self.full.setdefault(len(text), []).append(text)
        return True

    def observe_full_word(self, text, need=3):
        """Слово из зелёной надписи: после `need` одинаковых чтений — в словарь."""
        text = normalize(text)
        if len(text) < 3 or text in self.words:
            return False
        self._pending[text] = self._pending.get(text, 0) + 1
        if self._pending[text] < need:
            return False
        self.add(text)
        try:
            save_learned(self.words - self.base, self.learned_path)
        except Exception:
            pass
        return True
