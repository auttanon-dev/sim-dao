"""Deterministic presentation identity; never consumes the simulation RNG."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog():
    path = Path(__file__).resolve().parent.parent / 'static' / 'jianghu' / 'character-art.json'
    return json.loads(path.read_text(encoding='utf-8'))


def appearance_for(character, day):
    entries = catalog()
    gender = getattr(character, 'gender', '')
    pool = [entry for entry in entries if entry['gender'] == gender] or entries
    age_group = 'elder' if character.age(day) >= 60 else 'adult'
    pool = [entry for entry in pool if entry['age_group'] == age_group] or pool
    dao = character.dao
    roles = None
    for words, choices in [
        (('ยา', 'โอสถ', 'รักษา'), ('healer', 'scholar')),
        (('ค้า',), ('trade', 'travel')),
        (('เหล็ก', 'ไฟ', 'แปรธาตุ'), ('craft', 'staff', 'scholar')),
        (('ดาบ', 'กระบี่', 'เลือด'), ('blade', 'spear')),
        (('มวย', 'วัชระ'), ('staff', 'spear')),
        (('ดาว', 'คำสัตย์', 'องเมียว', 'หยินหยาง'), ('scholar', 'staff')),
        (('พเนจร', 'ลม', 'น้ำ'), ('travel', 'spear', 'blade')),
    ]:
        if any(word in dao for word in words):
            roles = choices
            break
    if roles:
        matching = [entry for entry in pool if entry['role'] in roles]
        pool = matching or pool
    identity = f'{character.cid}:{character.born_day}:{gender}:{dao}'
    seed = int.from_bytes(hashlib.sha256(identity.encode('utf-8')).digest()[:8], 'big')
    chosen = pool[seed % len(pool)]
    return {key: chosen[key] for key in ('id', 'label', 'sheet', 'source')}
