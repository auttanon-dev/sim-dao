"""ส่งออกข้อมูลคงที่ของโลก (สถานที่ ถนน ชื่อ อาชีพ ฯลฯ) จากต้นฉบับ Python เป็น simdao_core/data/world.json
รันครั้งเดียวตอนย้ายไป Rust — หลังจากนี้ world.json คือแหล่งข้อมูลจริง"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tiandao import config as C, events as E, places as P, geo as G, branches as BR

def key(k):
    return k if isinstance(k, str) else f"t{k}"

out = {
    "realms": C.REALMS, "realm_prefix": C.REALM_PREFIX, "realm_ranks": C.REALM_RANKS,
    "tier_names": C.TIER_NAMES,
    "sister_realms": [["siam", C.SIAM_WORLD_NAME], ["fusang", C.FUSANG_WORLD_NAME],
                      ["steppe", C.STEPPE_WORLD_NAME], ["oasis", C.OASIS_WORLD_NAME],
                      ["bharata", C.BHARATA_WORLD_NAME], ["abyss", C.ABYSS_WORLD_NAME],
                      ["ocean", C.OCEAN_WORLD_NAME]],
    "branch_realms": [{"name": b.name, "skill_line": b.skill_line, "origin": b.origin,
                       "key": P.BRANCH_PLACE_KEYS[i]} for i, b in enumerate(BR.build(C.BRANCH_REALMS))],
    "places": [{"name": p[0], "world": key(p[1]), "grade": p[2], "kind": p[3],
                "material": p[4], "forge": p[5],
                "secret_of": None if p[6] is None else key(p[6]), "sealed": bool(p[7]),
                "x": G.COORDS[i][0], "y": G.COORDS[i][1]} for i, p in enumerate(P.PLACES)],
    "edges": [{"a": a, "b": b, "dist": d, "kind": k, "open": bool(t)} for a, b, d, k, t in G.EDGES],
    "names": {
        "han": [E.SURNAME, E.GIVEN], "siam": [E.THAI_GIVEN, E.THAI_SURNAME],
        "fusang": [E.JAPAN_SURNAME, E.JAPAN_GIVEN], "steppe": [E.STEPPE_SURNAME, E.STEPPE_GIVEN],
        "oasis": [E.ARAB_GIVEN, E.ARAB_SURNAME], "bharata": [E.VEDIC_GIVEN, E.VEDIC_SURNAME],
    },
    "tribes": {"han": C.TRIBES, "siam": "ชาวสยาม", "fusang": "ชาวอาทิตย์อุทัย", "steppe": "ชาวทุ่งหญ้า",
               "oasis": "ชาวโอเอซิส", "bharata": "ชาวชมพูทวีป"},
    "origins": E.ORIGINS,
    "professions": C.PROFESSIONS,
    "dao_pool": {k: list(v) for k, v in C.DAO_POOL.items()},
    "org_words": [E.ORG_WORD, E.ORG_TAIL],
    "beast_kind": C.BEAST_KIND, "beast_trait": C.BEAST_TRAIT,
}
dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "simdao_core", "data", "world.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(dst, os.path.getsize(dst), "bytes;", len(out["places"]), "places", len(out["edges"]), "edges")
