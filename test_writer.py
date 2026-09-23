# -*- coding: utf-8 -*-
"""ตรวจชั้นเขียนฉาก (narrative_factory/writer.py) โดยไม่ต้องมี Ollama

ใช้ agent ปลอมที่ตอบตามสคริปต์ เพื่อแยกสองเรื่องออกจากกันให้ชัด:
  - เรื่องที่ **โค้ดเรารับผิดชอบ** — สำนวนฉากครบไหม, บทพูดของคนนอกบัญชีถูกทิ้งไหม, ตัวตรวจต่อเนื่อง
    จับของเสียได้จริงไหม, สั่งเขียนซ้ำเฉพาะบีตที่ผิดจริงไหม  ← เทสต์นี้ตรวจทั้งหมด
  - เรื่องที่ **โมเดลรับผิดชอบ** — สำนวนสวยไหม  ← ตรวจด้วยเทสต์อัตโนมัติไม่ได้ ไม่พยายามตรวจ

ทำแบบนี้เพราะเครื่องที่รันซิมกับเครื่องที่มี Ollama ไม่จำเป็นต้องเป็นเครื่องเดียวกัน และเทสต์ที่ต้อง
รอโมเดล 8B ตอบทีละบีตจะช้าเกินกว่าจะรันเป็นประจำ
"""
import sys

from tiandao import sim as S
from tiandao.ai import config_ai as ACFG
from narrative_factory import context_builder as CB
from narrative_factory import pacing as PACE
from narrative_factory import parser as P
from narrative_factory import scene_cast as SCAST
from narrative_factory import scene_extractor as SE
from narrative_factory import writer as W

STEPS = 6000
SEED = 2026


class FakeAgent:
    """ตอบแทน Ollama ตามลำดับ pass — บันทึก prompt ทุกครั้งไว้ให้เทสต์ตรวจย้อนหลัง"""

    def __init__(self, intruder="ผู้ไม่มีตัวตน", broken_stage=None):
        self.prompts = []
        self.intruder = intruder
        self.broken_stage = broken_stage      # บีตที่จงใจให้เขียนสั้นในรอบแรก
        self.prose_calls = 0

    def complete_json(self, system, user, **kw):
        self.prompts.append(("json", system, user, kw))
        if '"beats"' in system:
            return {"beats": [{"stage": s, "outline": f"โครงของบีต {s}", "speakers": []}
                              for s in PACE.BEAT_STAGES]}
        names = [n for n in self._roster(user)]
        me = names[0] if names else "ใครสักคน"
        you = names[1] if len(names) > 1 else me
        lines = [{"speaker": me if i % 2 == 0 else you,
                  "line": f"ถ้อยคำที่ {i} ของบีตนี้ ยาวพอให้จับต้นชนปลายได้",
                  "action": "กำหมัดแน่น"} for i in range(ACFG.SCENE_DIALOGUE_LINES)]
        lines.append({"speaker": self.intruder, "line": "ข้าคือคนที่ไม่ควรมีอยู่ในฉากนี้"})
        return {"lines": lines}

    def complete(self, system, user, **kw):
        self.prompts.append(("prose", system, user, kw))
        self.prose_calls += 1
        stage = user.split("[บีตที่กำลังเขียน] ", 1)[1].split(" —", 1)[0].strip()
        body = " ".join(f'เขาเอ่ยว่า "{q}" แล้วเงียบไป' for q in self._quoted(user))
        if stage == self.broken_stage and "[ต้องแก้ให้ได้ในรอบนี้]" not in user:
            return "สั้นมาก"      # รอบแรกจงใจให้เสีย เพื่อดูว่าตัวตรวจสั่งเขียนซ้ำจริงไหม
        filler = ("ลมพัดผ่านชายคาแล้วพาเอากลิ่นดินเปียกเข้ามาในห้องโถงอย่างเงียบเชียบ "
                  "แสงสลัวทาบลงบนพื้นหินจนเห็นรอยร้าวเก่าที่ไม่มีใครเคยซ่อม ") * 12
        return f"{body}\n\n{filler}"

    @staticmethod
    def _quoted(user):
        """ดึงบทพูดที่ prompt สั่งให้ร้อยเข้าไป — เลียนแบบโมเดลที่เชื่อฟังคำสั่งทุกบรรทัด"""
        if "[บทพูดที่ต้องร้อยเข้าไป" not in user:
            return []
        block = user.split("[บทพูดที่ต้องร้อยเข้าไป", 1)[1]
        out = []
        for line in block.splitlines():
            if line.startswith("- ") and '"' in line:
                out.append(line.split('"')[1])
        return out

    @staticmethod
    def _roster(user):
        for line in user.splitlines():
            if line.startswith("- ตัวละครที่เอ่ยชื่อได้มีเพียง: "):
                head = line.split(": ", 1)[1].split(" ห้ามเพิ่ม")[0]
                return [n.strip() for n in head.split(",") if n.strip()]
        return []


def pick_scene():
    sim = S.Sim(seed=SEED, tiers=3)
    for _ in range(STEPS):
        sim.step()
    cfg = P.load_config()
    parsed = P.parse_log(sim)
    scenes = SE.extract_scenes(parsed, sim, cfg)
    by_cid = SE.index_by_character(parsed)
    # เลือกฉากที่มีทั้งเหตุการณ์นำและผู้ร่วมมากกว่าหนึ่งคน — ฉากที่มีอะไรให้เขียนจริง
    rich = [s for s in scenes if len(s.events) >= 3 and len(s.participants) >= 2]
    assert rich, "ไม่มีฉากที่มีทั้งเหตุการณ์นำและคู่กรณีเลย"
    scene = rich[len(rich) // 2]
    ctx_map = CB.build_scene_context(scene, sim, by_cid, cfg)
    return sim, cfg, parsed, scene, ctx_map, by_cid


def test_package(sim, cfg, scene, ctx_map, by_cid, parsed):
    print("\n=== 1. สำนวนฉากต้องมีของครบพอให้เขียนบทสนทนาได้ ===")
    presence = SCAST.Presence(sim.log)
    pkg = W.build_package(scene, sim, ctx_map, by_cid.get(scene.focal_cid, []),
                          presence=presence, config=cfg)
    assert pkg.roster, "ไม่มีบัญชีรายชื่อผู้พูด"
    assert pkg.events, "ไม่มีเหตุการณ์จริงในสำนวนฉาก"
    assert len(pkg.beats) == 5, f"บีตไม่ครบ 5: {[b.stage for b in pkg.beats]}"
    assert pkg.place_name and pkg.season and pkg.weather
    for block in (pkg.setting_block(), pkg.cast_block(), pkg.truth_block(), pkg.rules_block()):
        assert block.strip()
    assert all(n in pkg.rules_block() for n in pkg.roster), "กติกาไม่ได้ประกาศบัญชีรายชื่อครบ"
    print(f"  ปีที่ {pkg.year} {pkg.place_name} ({pkg.place_kind}) ฤดู{pkg.season} ฟ้า{pkg.weather}")
    print(f"  ผู้อยู่ในฉาก {len(pkg.cast)} คน: {', '.join(pkg.roster)}")
    print(f"  เหตุการณ์จริง {len(pkg.events)} รายการ | ฉากนี้เปลี่ยน: {pkg.changes or ['-']}")
    return pkg


def test_dry_run(pkg):
    print("\n=== 2. โหมดแห้ง (ไม่มีโมเดล) ต้องไม่พังและต้องรายงานว่ายังไม่ได้เขียน ===")
    script = W.SceneWriter(agent=None).write(pkg)
    assert script.calls == 0 and not script.used_llm
    assert not script.prose.strip(), "ไม่มีโมเดลแต่ได้ร้อยแก้วมา — แปลว่ามีการแต่งเองที่ไหนสักแห่ง"
    assert script.issues, "ฉากว่างเปล่าแต่ตัวตรวจบอกว่าผ่าน"
    assert all(b.outline for b in script.beats), "ควร fallback โครงจากเหตุการณ์ดิบได้แม้ไม่มีโมเดล"
    print(f"  ✓ ไม่เรียกโมเดลเลย และรายงานปัญหา {len(script.issues)} ข้อ")


def test_full_write(pkg):
    print("\n=== 3. เขียนเต็ม 4 pass ด้วย agent ปลอม ===")
    agent = FakeAgent()
    script = W.SceneWriter(agent=agent).write(pkg)
    print(f"  เรียกโมเดล {script.calls} ครั้ง | ร้อยแก้ว {len(script.prose)} ตัวอักษร "
          f"| บทพูด {script.dialogue_count} บรรทัด")
    assert script.used_llm and script.calls >= 1 + len(PACE.DIALOGUE_BEATS) + 5
    assert len(script.prose) >= ACFG.SCENE_MIN_CHARS, "ฉากสั้นกว่าเกณฑ์ฉากเต็ม"
    assert script.dialogue_count > 0
    for b in script.beats:
        assert b.prose.strip(), f"บีต {b.stage} ว่างเปล่า"
    print("  ✓ ครบทั้ง 5 บีต ยาวพอเป็นฉากเต็ม")
    return agent, script


def test_intruder_dropped(agent, script, pkg):
    print("\n=== 4. บทพูดของคนที่ไม่อยู่ในฉากต้องถูกทิ้งตั้งแต่ก่อนเขียนร้อยแก้ว ===")
    speakers = {l["speaker"] for b in script.beats for l in b.lines}
    assert agent.intruder not in speakers, "ปล่อยให้ตัวละครนอกบัญชีพูดได้"
    assert speakers and speakers <= set(pkg.roster)
    assert agent.intruder not in script.prose
    print(f"  ✓ ผู้พูดทั้งหมด {sorted(speakers)} อยู่ในบัญชีทั้งหมด, '{agent.intruder}' ถูกทิ้ง")


def test_checks_catch_garbage(pkg, script):
    print("\n=== 5. ตัวตรวจต่อเนื่องต้องจับของเสียได้จริง (ไม่ใช่ผ่านทุกอย่าง) ===")
    beat = pkg.beats[2]
    good = next(b for b in script.beats if b.stage == beat.stage)
    assert not W.check_beat(pkg, beat, good), f"ของดีถูกตีตก: {W.check_beat(pkg, beat, good)}"

    cases = {
        "สั้นเกินไป": W.WrittenBeat(stage=beat.stage, prose="สั้นมาก", lines=good.lines),
        "อักษรจีนปน": W.WrittenBeat(stage=beat.stage, prose=good.prose + " 天道酬勤", lines=good.lines),
        "วันที่ปลอม": W.WrittenBeat(stage=beat.stage, prose=good.prose + " วันที่ 999999 นั้นเอง",
                                    lines=good.lines),
        "บทพูดหาย": W.WrittenBeat(stage=beat.stage, prose="ก" * 4000, lines=good.lines),
    }
    for label, wb in cases.items():
        found = W.check_beat(pkg, beat, wb)
        assert found, f"ตรวจไม่เจอกรณี {label}"
        print(f"  ✓ {label}: {found[0][:70]}")

    empty = W.SceneScript(scene_id=pkg.scene_id,
                          beats=[W.WrittenBeat(stage=s) for s in PACE.BEAT_STAGES])
    assert W.check_scene(pkg, empty), "ฉากว่างเปล่าแต่ตรวจผ่าน"


def test_repair_only_broken_beat(pkg):
    print("\n=== 6. เมื่อบีตเดียวเสีย ต้องสั่งเขียนซ้ำเฉพาะบีตนั้น ไม่ทิ้งทั้งฉาก ===")
    agent = FakeAgent(broken_stage="Rising")
    script = W.SceneWriter(agent=agent).write(pkg)
    rewrites = {b.stage: b.rewrites for b in script.beats}
    print(f"  จำนวนครั้งที่เขียนซ้ำต่อบีต: {rewrites}")
    assert rewrites["Rising"] == 1, "บีตที่เสียไม่ถูกเขียนซ้ำ"
    assert sum(v for k, v in rewrites.items() if k != "Rising") == 0, "ไปเขียนบีตที่ดีอยู่แล้วซ้ำด้วย"
    assert not any(b.issues for b in script.beats), f"เขียนซ้ำแล้วยังไม่ผ่าน: {script.beats[2].issues}"
    print("  ✓ ซ่อมเฉพาะจุดที่เสีย และผ่านหลังซ่อม")


def test_prompt_budget(agent):
    print("\n=== 7. ทุกการเรียกต้องขอเพดานความยาวจริง (ไม่งั้นฉากยาวจะถูกตัดเงียบๆ) ===")
    prose = [kw for kind, _s, _u, kw in agent.prompts if kind == "prose"]
    assert prose, "ไม่มีการเรียก pass ร้อยแก้วเลย"
    for kw in prose:
        assert kw.get("num_predict", 0) >= 384, f"ไม่ได้ขอ num_predict: {kw}"
        assert kw.get("num_ctx") == ACFG.SCENE_NUM_CTX
        assert kw.get("model") == ACFG.OLLAMA_PROSE_MODEL
    js = [kw for kind, _s, _u, kw in agent.prompts if kind == "json"]
    for kw in js:
        assert kw.get("model") == ACFG.OLLAMA_STRUCTURE_MODEL, "pass โครงต้องใช้โมเดลจัดโครง"
    print(f"  ✓ ร้อยแก้ว {len(prose)} ครั้งใช้ {ACFG.OLLAMA_PROSE_MODEL.split('/')[-1][:40]}")
    print(f"  ✓ โครง/บทพูด {len(js)} ครั้งใช้ {ACFG.OLLAMA_STRUCTURE_MODEL}")


def main():
    print(f"รันซิม {STEPS} เหตุการณ์เพื่อหาฉากจริงมาทดสอบ...")
    sim, cfg, parsed, scene, ctx_map, by_cid = pick_scene()
    print(f"  ฉาก {scene.scene_id} ({scene.scene_type}) วันที่ {scene.day_start}-{scene.day_end} "
          f"เหตุการณ์ {len(scene.events)} รายการ")
    pkg = test_package(sim, cfg, scene, ctx_map, by_cid, parsed)
    test_dry_run(pkg)
    agent, script = test_full_write(pkg)
    test_intruder_dropped(agent, script, pkg)
    test_checks_catch_garbage(pkg, script)
    test_repair_only_broken_beat(pkg)
    test_prompt_budget(agent)
    print("\n--- ตัวอย่างร้อยแก้วบีต Peak (จาก agent ปลอม — ดูโครง ไม่ใช่ดูสำนวน) ---")
    peak = next(b for b in script.beats if b.stage == "Peak")
    print(peak.prose[:300] + "...")
    print("\n✓ ชั้นเขียนฉากทำงานครบทั้ง 4 pass")


if __name__ == "__main__":
    main()
