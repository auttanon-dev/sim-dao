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
from tiandao import tuning as TN
from tiandao import chronicle as CH
from tiandao import persist as PS
from tiandao import event_log as EL
from tiandao.ai import config_ai as ACFG




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
    ap.add_argument("--no-autotune", action="store_true",
                     help="ไม่โหลดค่าที่เอนจินเรียนรู้ไว้ข้ามรัน (learned_config.json) ใช้ค่าตั้งต้นใน config.py")
    ap.add_argument("--no-chronicle", action="store_true",
                     help="ไม่บันทึกตำนานของรันนี้ลง tiandao/chronicle.json")
    ap.add_argument("--legends", action="store_true",
                     help="แสดงตำนานที่สะสมไว้จากทุกรันที่ผ่านมา แล้วจบโปรแกรมทันที ไม่รันซิมใหม่")
    ap.add_argument("--save-path", default=PS.DEFAULT_PATH,
                     help="ตำแหน่งไฟล์บันทึกสถานะโลกทั้งก้อน (ดีฟอลต์ tiandao/world.save)")
    ap.add_argument("--keep-recent-events", type=int, default=5000,
                    help="ตอน --save เก็บเหตุการณ์ล่าสุดไว้ใน world.save เท่านี้ ที่เหลือต่อท้ายไฟล์ {save-path}.events.jsonl "
                         "(เหมือน daemon.py) รายงานของรอบนี้ยังใช้ log เต็ม")
    ap.add_argument("--no-trim-log", action="store_true",
                    help="ตอน --save ไม่ตัด log — world.save โตไม่มีเพดานเมื่อ --resume --save ซ้ำหลายรอบ")
    ap.add_argument("--resume", action="store_true",
                     help="เดินต่อจากไฟล์ --save-path แทนที่จะสร้างโลกใหม่จาก --seed "
                          "(ถ้าไม่พบไฟล์ จะสร้างโลกใหม่แทนแล้วเตือน)")
    ap.add_argument("--save", action="store_true",
                     help="บันทึกสถานะโลกทั้งก้อนไว้ที่ --save-path หลังรันจบ (คนละอย่างกับ chronicle "
                          "ที่บันทึกแค่ตำนานสรุป — อันนี้บันทึกตัวโลกจริง เดินต่อได้ด้วย --resume)")
    ap.add_argument("--llm", action="store_true",
                     help="เปิด Layer 3 (Ollama) จริง — ต้องมี Ollama รันอยู่ที่ localhost:11434 พร้อม "
                          "โมเดลที่ตั้งไว้ใน tiandao/ai/config_ai.py (ดีฟอลต์ qwen2.5vl:7b) "
                          "(Phase G) sim.run() เองไม่บล็อกอีกต่อไป — งาน LLM เข้าคิวไว้แล้วประมวลผล "
                          "ทั้งหมดหลัง sim.run() จบครั้งเดียว (ยังกินเวลารวมเท่าเดิม แค่ไม่บล็อกระหว่างเดิน)")
    ap.add_argument("--llm-budget", type=int, default=0,
                     help="จำกัดจำนวนงาน LLM ที่จะ drain หลัง sim.run() จบ (0 = ทั้งคิวเหมือนเดิม) — "
                          "สำคัญมากตอนรันยาว: คิวโตตามจำนวนเหตุการณ์ (341,000 เหตุการณ์เคยได้ 121,302 งาน) "
                          "ถ้า drain ทั้งคิวจะใช้เวลาระดับสัปดาห์และ --save จะไม่ได้ทำงานเลยเพราะยังไม่ถึง "
                          "บรรทัดนั้น ตั้ง budget ไว้เพื่อให้ได้ dataset จริงพร้อมเซฟในเวลาที่คุมได้")
    ap.add_argument("--decision", action="store_true",
                     help="เปิด Decision Engine แบบ Hybrid (tiandao/decision) — Utility+Softmax+Belief+"
                          "Memory+Social+GOAP ตัดสินใจแทนการสุ่มตามน้ำหนักสำหรับทุกคนที่ไม่มีจิตใจ LLM")
    ap.add_argument("--decision-mode", choices=("stochastic", "deterministic"), default=None,
                     help="stochastic = จำลองจริง (softmax) · deterministic = argmax สำหรับดีบัก")
    ap.add_argument("--explain", type=int, default=None, metavar="CID",
                     help="พิมพ์คำอธิบายการตัดสินใจล่าสุดของตัวละคร cid นี้ (ต้องใช้กับ --decision)")
    a = ap.parse_args()

    if a.llm:
        ACFG.LLM_ENABLED = True

    if a.legends:
        print(CH.format_hall_of_legends())
        return

    if not a.no_autotune:
        state = TN.load_state()
        if state.get("overrides"):
            TN.apply_overrides(state["overrides"])
            print(f"[autotune] โหลดค่าที่เรียนรู้ไว้: {state['overrides']}")

    sim = None
    if a.resume:
        try:
            sim = PS.load_sim(a.save_path)
            print(f"[persist] เดินต่อจากไฟล์ {a.save_path} — วันที่ {sim.day} (ปีที่ {sim.day//365})")
        except FileNotFoundError:
            print(f"[persist] ไม่พบไฟล์ {a.save_path} — เริ่มโลกใหม่จาก seed {a.seed} แทน")
    if sim is None:
        sim = Sim(seed=a.seed, tiers=a.tiers)
    if a.decision or a.explain is not None:
        from tiandao import decision as DE
        if getattr(sim, "decision_engine", None) is None:
            DE.attach(sim, mode=a.decision_mode,
                      focus=(a.explain,) if a.explain is not None else ())
        elif a.decision_mode:
            sim.decision_engine.mode = a.decision_mode
        if a.explain is not None:
            sim.decision_engine.focus.add(a.explain)
    sim.run(a.events)
    if getattr(sim, "decision_engine", None) is not None:
        print(f"[decision] {sim.decision_engine.summary()}")
        if a.explain is not None:
            print(sim.decision_engine.explain_text(a.explain, n=3) or
                  f"[decision] ตัวละคร {a.explain} ยังไม่ได้ตัดสินใจผ่าน engine ในรอบนี้")
    if getattr(sim, "last_run_steps", a.events) < a.events:
        print(f"[warning] scheduler stopped early after {sim.last_run_steps}/{a.events} events "
              "— ตรวจไฟล์ save/log ก่อนเดินต่อ")

    if a.llm:
        queued = len(sim.brain_manager.llm_queue)
        print(f"[llm] คิว Layer 3 มีทั้งหมด {queued} งาน — จะประมวลผล "
              f"{'ทั้งหมด' if a.llm_budget <= 0 else f'{a.llm_budget} งานแรก'} "
              f"(~20 วินาที/งาน โดยประมาณ)")
        n = sim.brain_manager.drain_llm_queue(sim, budget=a.llm_budget)
        left = len(sim.brain_manager.llm_queue)
        print(f"[llm] ประมวลผลคิว Layer 3 แล้ว {n} งาน (เหลือค้างคิว {left} งาน — งานที่เหลือถูกเซฟ "
              f"ไปกับ world.save ด้วย ถ้าใช้ --save จึง drain ต่อได้ทีหลังด้วย --resume)")

    if a.save:
        save_dir = os.path.dirname(a.save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        whole = sim.log
        if not a.no_trim_log:
            # เหตุการณ์เก่าไปต่อท้ายไฟล์คู่ save แล้วเซฟแค่ล่าสุด — เดิม --resume --save ซ้ำๆ ทำให้ log ใน world.save
            # สะสมทุกเหตุการณ์ตั้งแต่เริ่มโลก (100 ปีจำลอง ~290,000 เหตุการณ์) รายงานข้างล่างยังใช้ log เต็มของรอบนี้
            EL.flush_and_trim(sim, EL.default_log_path(a.save_path), a.keep_recent_events)
        PS.save_sim(sim, a.save_path)
        sim.log = whole
        print(f"[persist] บันทึกสถานะโลกไว้ที่ {a.save_path}")

    os.makedirs(a.out, exist_ok=True)
    with open(f"{a.out}/events_{a.seed}.jsonl", "w", encoding="utf-8") as f:
        for e in sim.log:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

    print(f"seed {a.seed} | {len(sim.log)} เหตุการณ์ | ผ่านไป {sim.day//365} ปี | "
          f"มีชีวิต {len(sim.living())} | แดนลับ {len(sim.caches)} | องค์กร {len(sim.orgs)}")
    for w in sim.worlds:
        print(f"   {w.name} (ชั้น {w.tier}): ยุคที่ {w.era} · {w.state()} · คลังฟ้า {w.ratio()*100:.0f}% "
              f"· คน {len(sim.living_in(w.wid))}")

    if not a.no_chronicle:
        entry = CH.record_run(sim, a.seed, a.events)
        top_name = entry["legends"][0]["name"] if entry["legends"] else None
        if top_name:
            print(f"[ตำนาน] บันทึกรันนี้ไว้แล้ว — ผู้เด่นที่สุดคือ [{top_name}] "
                  f"(ดูทั้งหมดด้วย python run.py --legends)")

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
