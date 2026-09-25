# -*- coding: utf-8 -*-
"""โหมดดีบักกายวิภาค — ทุกตัวเลขต้องย้อนกลับไปหาการคำนวณที่สร้างมันได้ (พรอมต์ §44)

    python -B tools/body_report.py                  ตัวละครตัวอย่างจากโลก seed 7
    python -B tools/body_report.py --cid 12         เจาะดูคนที่ cid 12
    python -B tools/body_report.py --seed 5 --cid 3
    python -B tools/body_report.py --population 4000   สถิติประชากรสำหรับสอบเทียบค่าคงที่

สถิติประชากรคือที่มาของ constants.REFERENCE_FORCE_RATIO — ถ้าแก้ค่าคงที่กายวิภาคตัวใด
ต้องรันโหมดนี้ใหม่แล้วอัปเดตค่าอ้างอิง ไม่งั้นดัชนีพลังกายจะเลื่อนออกจาก 1.0
"""
import argparse
import copy
import statistics as st
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tiandao import body as B                          # noqa: E402
from tiandao.body import balance as BAL                # noqa: E402
from tiandao.body import injury as INJ                 # noqa: E402
from tiandao.body import capability, constants as K    # noqa: E402
from tiandao.body import perception as PER             # noqa: E402
from tiandao.body.condition import Condition           # noqa: E402
from tiandao.models import Character                   # noqa: E402


def make(cid, seed, gender):
    ch = Character(cid=cid, name=f"NPC_{cid:03d}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender=gender)
    ch.body_seed = seed
    return ch


def show(node, indent=2):
    pad = " " * indent
    for key, value in node.items():
        if isinstance(value, dict):
            print(f"{pad}{key}:")
            show(value, indent + 2)
        else:
            print(f"{pad}{key}: {value}")


def one(cid, seed, gender, friction, fatigue, hurt_j=0.0, hurt_region="left_leg"):
    ch = make(cid, seed, gender)
    ch.fatigue = fatigue          # ความล้าเป็นสภาพของตัวละคร ทุกฟังก์ชันอ่านเองจากตรงนี้
    cond = Condition.of(ch)
    body = B.body_of(ch)
    blow = B.hurt(ch, hurt_j, region=hurt_region, key=("report",)) if hurt_j else None
    print("=" * 74)
    print(f"  {ch.name}  (โลก seed {seed} · cid {cid} · {gender})")
    print("=" * 74)
    show(B.explain(ch, friction=friction))

    # ---- โซ่การคำนวณที่นำไปสู่ "แรงที่พื้น" ให้เห็นทีละขั้น ----
    leg = body.muscles["leg"]
    weight = body.mass * K.GRAVITY
    print("\n  โซ่การคำนวณของแรงที่ปลายขา (ตรวจย้อนได้ทุกขั้น):")
    print(f"    มวลกล้ามเนื้อขาทั้งกลุ่ม           {leg.mass:8.2f} kg")
    print(f"    × ส่วนที่เป็นฝั่งเหยียด {K.AGONIST_SHARE['leg']:.2f}        {leg.agonist_mass:8.2f} kg")
    print(f"    ÷ (ความหนาแน่น × ความยาวเส้นใย)    PCSA = {leg.pcsa * 1e4:8.1f} cm²")
    print(f"    × ความตึงจำเพาะ {body.gen.specific_tension / 1000:.0f} kPa      F = {leg.max_force:8.0f} N")
    print(f"    × ประสิทธิภาพประสาท {body.gen.neuro_efficiency:.3f}         F = {body.group_force('leg'):8.0f} N")
    print(f"    × แขนโมเมนต์เข่า {body.moment_arm('knee'):.4f} m         τ = {body.joint_torque('knee'):8.0f} N·m")
    print(f"    ÷ แขนกลประสิทธิผล {body.effective_limb_length('leg'):.3f} m       F = {body.leg_force():8.0f} N")
    print(f"    เทียบน้ำหนักตัว {weight:.0f} N              = {body.leg_force() / weight:8.2f} เท่า")

    print("\n  ความสามารถบนพื้นแต่ละแบบ (m/s):")
    for name, mu in sorted(K.TERRAIN_FRICTION.items(), key=lambda kv: -kv[1]):
        print(f"    {name:<10} μ={mu:.2f}   {capability.max_running_speed(body, mu, cond):5.2f}")

    print("\n  โครงกระดูกรับแรงได้แค่ไหน (กระดูกต้นขา · แรงผ่านตัวมันเอง):")
    femur = body.skeleton["femur"]
    print(f"    ยาว {femur.length:.3f} m · รัศมี {femur.radius:.4f} m · "
          f"หน้าตัด {femur.area * 1e4:.2f} cm² · {femur.count} ชิ้น")
    print(f"    {'แรง':>14}{'แนวแกน MPa':>13}{'โอกาสหัก':>11}{'ดัด MPa':>11}{'โอกาสหัก':>11}")
    for mult in (1, 3, 8, 14, 25):
        f_n = weight * mult
        ax, bd = femur.stress(f_n), femur.bending_stress(f_n)
        print(f"    {f'{mult}x นน.ตัว':>14}{ax / 1e6:>13.1f}"
              f"{femur.fracture_risk(ax, 'compressive'):>11.3f}"
              f"{bd / 1e6:>11.1f}{femur.fracture_risk(bd, 'bending'):>11.3f}")

    print("\n  การทรงตัวเมื่อถือของไว้ข้างหน้า:")
    show(BAL.explain(body), indent=4)
    print(f"    {'ของที่ถือ':>11}{'ระยะถือ':>9}{'COM (m)':>10}{'เหลือถึงขอบ':>13}{'ยืนได้':>8}")
    for load, arm in ((0, 0.30), (20, 0.30), (40, 0.30), (40, 0.60), (80, 0.60)):
        print(f"    {f'{load} kg':>11}{f'{arm:.2f} m':>9}"
              f"{BAL.com_offset(body, load, arm):>10.4f}"
              f"{BAL.balance_margin(body, load, arm):>13.4f}"
              f"{str(BAL.is_stable(body, load, arm)):>8}")
    print(f"    เกณฑ์ที่บีบก่อน: หลังรับไหว {capability.carry_capacity(body):.1f} kg"
          f" · สมดุลที่ 0.30 m {BAL.max_stable_load(body, 0.30):.1f} kg"
          f" · สมดุลที่ 0.60 m {BAL.max_stable_load(body, 0.60):.1f} kg")

    if blow is not None:
        print(f"\n  การกระทบ {hurt_j:.0f} J ที่ {hurt_region} — ทีละชั้น:")
        show(blow, indent=4)
        print("\n  บาดเจ็บและความสามารถที่เหลือหลังโดน:")
        show(INJ.explain(body, ch.injuries), indent=4)
        print(f"    วิ่งได้ {capability.max_running_speed(body, friction, Condition.of(ch)):.2f} m/s"
              f"  (ก่อนโดน {capability.max_running_speed(body, friction, cond):.2f})")
        print("\n  เวลาเยียวยา:")
        for days in (0, 30, 90, 180, 365, 730):
            state = copy.deepcopy(ch.injuries)
            INJ.heal(state, days)
            print(f"    {days:>4} วัน   ความสามารถขา {INJ.capacity(state, 'leg'):.3f}"
                  f"   ความบาดเจ็บรวม {INJ.severity(state):.4f}")

    print("\n  ถ้าความล้าเพิ่มขึ้น (ค่าจริงมาจาก circulation.exert ระหว่างที่โลกเดิน):")
    for f in (0.0, 0.25, 0.50, 0.75):
        tired = Condition(fatigue=f)
        print(f"    ความล้า {f:.0%}  วิ่ง {capability.max_running_speed(body, friction, tired):5.2f} m/s"
              f" · กระโดด {capability.jump_height(body, tired):5.3f} m"
              f" · แบก {capability.carry_capacity(body, tired):5.1f} kg"
              f" · ตอบสนอง {capability.reaction_time(body, tired):.3f} s")

    # ---- §32: สิ่งที่ระบบตัดสินใจถาม · §33: สิ่งที่เจ้าตัวคิดว่าตัวเองเป็น ----
    print("\n  คำถามที่ระบบตัดสินใจถามร่างกายนี้ (§32):")
    caps = B.capabilities(ch, friction=friction)
    print(f"    ยืนไหว {caps['can_stand']} · วิ่งไหว {caps['can_run']} · สู้ไหว {caps['can_fight']}"
          f" · รู้สึกตัว {caps['conscious']}")
    print(f"    วิ่ง {caps['speed']:.2f} m/s · ตอบสนอง {caps['reaction']:.3f} s"
          f" · แบก {caps['carry']:.1f} kg · หมัด {caps['strike']:.0f} J"
          f" · อดได้ {caps['endurance']:.0f} วัน")
    print(f"    แขนใช้ได้ {caps['arm']:.2f} · ขาใช้ได้ {caps['leg']:.2f}"
          f" · แรงที่เรียกใช้ได้ {caps['effort']:.2f} · สรุปด้วยคำเดียว: {caps['word']}")

    print("\n  ร่างจริง vs ร่างที่เจ้าตัวรู้สึก (§33 — คนละอย่างกันโดยตั้งใจ):")
    print(f"    ความเร็วที่ *คิดว่า* ตัวเองวิ่งได้ (ของจริง {caps['speed']:.2f} m/s) — "
          f"แต่ละวันรู้สึกไม่เท่ากัน")
    print(f"    {'อคติ':>10}" + "".join(f"{f'วันที่ {d}':>12}" for d in range(5))
          + f"{'คำที่จะพูด':>14}")
    for label, bias in (("ขลาด", -1.0), ("กลางๆ", 0.0), ("กล้า", 1.0)):
        seen = [B.capabilities(ch, felt=B.felt(ch, day=d, bias=bias), friction=friction)
                for d in range(5)]
        print(f"    {label:>10}" + "".join(f"{s['speed']:>12.2f}" for s in seen)
              + f"{seen[0]['word']:>14}")
    lo, hi = PER.band(ch)["blood"]
    print(f"    ช่วงที่พอบอกได้เรื่องเลือด: {lo:.0%}–{hi:.0%}"
          f"  (ของจริง {1.0 - cond.blood:.0%})")


def population(n, seed, friction):
    cols = {"มวล (kg)": [], "ส่วนสูง (m)": [], "BMI": [], "แรงปลายขา (N)": [],
            "แรง/นน.ตัว (เท่า)": [], "วิ่ง (m/s)": [], "กระโดด (m)": [],
            "แบก (kg)": [], "ตอบสนอง (s)": [], "ดัชนีพลังกาย": []}
    for cid in range(n):
        body = B.body_of(make(cid, seed, "ชาย" if cid % 2 == 0 else "หญิง"))
        w = body.mass * K.GRAVITY
        cols["มวล (kg)"].append(body.mass)
        cols["ส่วนสูง (m)"].append(body.gen.height)
        cols["BMI"].append(body.bmi)
        cols["แรงปลายขา (N)"].append(body.leg_force())
        cols["แรง/นน.ตัว (เท่า)"].append(body.leg_force() / w)
        cols["วิ่ง (m/s)"].append(capability.max_running_speed(body, friction))
        cols["กระโดด (m)"].append(capability.jump_height(body))
        cols["แบก (kg)"].append(capability.carry_capacity(body))
        cols["ตอบสนอง (s)"].append(capability.reaction_time(body))
        cols["ดัชนีพลังกาย"].append(capability.strength_index(body))
    print("=" * 74)
    print(f"  สถิติประชากร {n:,} ร่าง (โลก seed {seed} · พื้น μ={friction})")
    print("=" * 74)
    print(f"  {'ค่า':<22}{'เฉลี่ย':>10}{'ส่วนเบี่ยงเบน':>14}{'ต่ำสุด':>10}{'สูงสุด':>10}")
    for name, xs in cols.items():
        print(f"  {name:<22}{st.mean(xs):>10.3f}{st.pstdev(xs):>14.3f}"
              f"{min(xs):>10.3f}{max(xs):>10.3f}")
    ratio = st.mean(cols["แรง/นน.ตัว (เท่า)"])
    print(f"\n  ค่าอ้างอิงที่ควรตั้งใน constants.REFERENCE_FORCE_RATIO = {ratio:.2f}")
    print(f"  ค่าที่ตั้งไว้ตอนนี้                                    = {K.REFERENCE_FORCE_RATIO:.2f}")
    if abs(ratio - K.REFERENCE_FORCE_RATIO) > 0.05:
        print("  ⚠️  ห่างกันเกิน 0.05 — ดัชนีพลังกายจะไม่อยู่รอบ 1.0 ควรอัปเดตค่าอ้างอิง")


def main():
    ap = argparse.ArgumentParser(description="รายงานกายวิภาคแบบตรวจย้อนได้")
    ap.add_argument("--cid", type=int, default=18)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--gender", default="ชาย")
    ap.add_argument("--friction", type=float, default=K.DEFAULT_FRICTION)
    ap.add_argument("--fatigue", type=float, default=0.0)
    ap.add_argument("--hurt", type=float, default=0.0,
                    help="ส่งพลังงานกระทบเข้าร่างกี่จูลก่อนพิมพ์รายงาน")
    ap.add_argument("--hurt-region", default="left_leg")
    ap.add_argument("--population", type=int, default=0,
                    help="พิมพ์สถิติประชากรกี่ร่าง (0 = ไม่พิมพ์)")
    a = ap.parse_args()
    if a.population:
        population(a.population, a.seed, a.friction)
    else:
        one(a.cid, a.seed, a.gender, a.friction, a.fatigue, a.hurt, a.hurt_region)


if __name__ == "__main__":
    main()
