# -*- coding: utf-8 -*-
import argparse, json, os, sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from tiandao.sim import Sim
from tiandao import story, config as C




def format_currency(amount, realm):
    # Base amount is considered as "อีแปะ" (coins)
    # If realm < 5, use mortal currency
    if realm < 5:
        gold = int(amount // 10000)
        silver = int((amount % 10000) // 100)
        coins = int(amount % 100)
        parts = []
        if gold > 0: parts.append(f"{gold} ตำลึงทอง")
        if silver > 0: parts.append(f"{silver} ตำลึงเงิน")
        if coins > 0 or not parts: parts.append(f"{coins} อีแปะ")
        return " ".join(parts)
    else:
        # If realm >= 5, they use spirit stones. 1 low spirit stone = 10000 coins (1 gold tael)
        ss_amount = int(amount // 10000)
        if ss_amount == 0:
            ss_amount = 1 
        
        supreme = ss_amount // 1000000
        high = (ss_amount % 1000000) // 10000
        mid = (ss_amount % 10000) // 100
        low = ss_amount % 100
        
        parts = []
        if supreme > 0: parts.append(f"{supreme} ศิลาปราณบริสุทธิ์")
        if high > 0: parts.append(f"{high} ศิลาปราณระดับสูง")
        if mid > 0: parts.append(f"{mid} ศิลาปราณระดับกลาง")
        if low > 0 or not parts: parts.append(f"{low} ศิลาปราณระดับต่ำ")
        return " ".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--events", type=int, default=30000)
    ap.add_argument("--tiers", type=int, default=3)
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--bio", type=int, default=None)
    ap.add_argument("--leaderboard", action="store_true")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    sim = Sim(seed=a.seed, tiers=a.tiers).run(a.events)
    os.makedirs(a.out, exist_ok=True)
    with open(f"{a.out}/events_{a.seed}.jsonl", "w", encoding="utf-8") as f:
        for e in sim.log:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

    print(f"seed {a.seed} | {len(sim.log)} เหตุการณ์ | ผ่านไป {sim.day//365} ปี | "
          f"มีชีวิต {len(sim.living())} | แดนลับ {len(sim.caches)} | องค์กร {len(sim.orgs)}")
    for w in sim.worlds:
        print(f"   {w.name} (ชั้น {w.tier}): ยุคที่ {w.era} · {w.state()} · คลังฟ้า {w.ratio()*100:.0f}% "
              f"· คน {len(sim.living_in(w.wid))}")

    print()

    if getattr(a, "leaderboard", False):
        print("=======================================================")
        print("🏆 📜 [ทำเนียบยอดฝีมือผู้ขึ้นสู่จุดสูงสุดแห่งยุทธภพ] 📜 🏆")
        print("=======================================================")
        survivors = [c for c in sim.cast if getattr(c, "alive", True) and c.age(sim.day) >= 18]
        if not survivors:
            print("💀 อนิจจา... โลกยุทธภพสิ้นสูญ ไม่มีใครเหลือรอดชีวิต!")
        else:
            survivors.sort(key=lambda x: (x.realm, sum(getattr(x, "money", {}).values())), reverse=True)
            for index, char in enumerate(survivors[:5], 1):
                medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🎖️"
                sect_info = f"สำนัก: {char.sect_name} ({char.sect_role})" if getattr(char, "sect_name", None) else "ศิษย์อิสระ"
                money = sum(getattr(char, "money", {}).values())
                print(f"{medal} อันดับ {index}: [{char.name}] อายุ {char.age(sim.day)} ปี (รุ่นที่ {getattr(char, 'generation', 1)})")
                title = getattr(char, 'title', 'ชาวยุทธนิรนาม')
                print(f" ↳ ฉายา: '{title}' | 🥋 Level: {char.realm} | 🪙 ทรัพย์สิน: {format_currency(money, char.realm)}")
                print(f" ↳ สถานะคุณธรรม: {getattr(char, 'moral', 0)} | 🏯 {sect_info} | ⚔️ ฆ่าศัตรูแค้นไปแล้ว: {getattr(char, 'enemies_defeated', 0)} คน")
        print("=======================================================\n")

    elif a.bio is not None:
        print(story.biography(sim.cast[a.bio], sim)); return
    for sc, ch in story.rank(sim, a.top):
        st = "ยังอยู่" if ch.alive else ch.death_cause
        print(f"[{sc:5.1f}] cid={ch.cid:<4} {ch.name} · {ch.race()} · {ch.dao} · "
              f"เกิดเป็น{ch.origin} → {C.realm_name(ch.peak_tier, ch.peak_realm)} "
              f"(โลกชั้น {ch.peak_tier}) · {st}")
    print(f"\nชีวประวัติเต็ม: python run.py --seed {a.seed} --events {a.events} --bio <cid>")


if __name__ == "__main__":
    main()
