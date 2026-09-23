"""Readable Thai fiction: one continuous scene, length proportional to events."""
import copy
import re

from .writer import SceneWriter, SceneScript, WrittenBeat

STYLE_VERSION = 'natural-thai-1'


def scene_length(pkg):
    # A single act of gathering supplies is a short scene, not a 4,500-char chapter.
    return min(pkg.target_chars, 2400, 650 + 350 * max(0, len(pkg.events) - 1))


def build_prompt(pkg, notes=()):
    active = [c for c in pkg.cast if 'ไม่ได้ลงมือ' not in c.role]
    cast = '\n'.join(f'- {c.name}: {c.role}' for c in active)
    facts = '\n'.join(f'- {event}' for event in pkg.events)
    system = (
        'คุณเขียนนิยายภาษาไทยที่อ่านง่าย เล่าเป็นบุคคลที่สามตามตัวละครหลัก '
        'ใช้คำธรรมดา ประโยคกระชับ และลำดับการกระทำที่ชัดเจน '
        'บอกให้รู้ว่าใครทำอะไร เกิดผลอะไร แล้วทำอะไรต่อ '
        'ส่งเฉพาะเนื้อเรื่อง แบ่งย่อหน้าสั้น ๆ ไม่ใส่ชื่อบท หัวข้อ หรือคำอธิบายการเขียน'
    )
    continuity = ('\n[ท้ายฉากก่อนหน้า ใช้ต่อเรื่อง ห้ามคัดลอกหรือเล่าซ้ำ]\n' + pkg.previous_chapter[-800:]
                  if pkg.previous_chapter else '')
    dialogue = ('ตัวละครอยู่คนเดียว ใช้การกระทำและความคิดสั้น ๆ ไม่ต้องมีบทพูด '
                'ห้ามสร้างคู่สนทนาหรือคนที่ซ่อนอยู่'
                if len(active) <= 1 else
                'ใส่บทสนทนาเมื่อมีเหตุให้พูด โต้ตอบกันด้วยคำพูดที่คนใช้จริง '
                'ระบุผู้พูดให้ชัด ใช้ข้า/เจ้าให้คงเส้นคงวา ไม่พูดเป็นปริศนาหรือคำคม')
    user = (
        f'[ตัวละครหลัก] {pkg.focal_name}\n[สถานที่] {pkg.place_name}\n[คนในเหตุการณ์]\n{cast}\n'
        f'[เหตุการณ์ที่ต้องเล่าตามลำดับ ห้ามเปลี่ยนผลหรือจำนวนสิ่งของ]\n{facts}\n'
        + ('[ผลที่เปลี่ยนไป]\n' + '\n'.join(pkg.changes) + '\n' if pkg.changes else '')
        + continuity + '\n[แนวทางการเล่า]\n'
        '- เปิดด้วยชื่อตัวละครและสิ่งที่เขากำลังทำ เรียกชื่อเต็มครั้งแรก แล้วใช้ชื่อสั้นหรือเขา\n'
        '- แต่ละย่อหน้าต้องทำให้การกระทำคืบหน้า ไม่ย้อนเริ่มฉากเดิมอีก\n'
        '- บรรยายสถานที่เท่าที่จำเป็น ไม่เปิดด้วยดวงอาทิตย์ สายลม กลิ่นอาย หรือพลังงาน\n'
        '- ใช้กริยาตรง ๆ เช่น หยิบ มอง เก็บ หยุด เดิน ไม่เขียนอวัยวะหรือธรรมชาติมีความคิด\n'
        '- ไม่เปรียบเทียบซ้อน ไม่ใส่โชคชะตา สัญญาณลึกลับ รอยสลัก พลังวิเศษ หรือเหตุการณ์ที่ไม่มีในข้อมูล\n'
        '- ห้ามเพิ่มสมบัติ อุปกรณ์พิเศษ ศัตรู ผู้เฝ้ามอง หรือแผนการใหม่ รายละเอียดเล็กน้อยต้องไม่เปลี่ยนเหตุการณ์\n'
        '- ไม่ใส่คำสอน ไม่ปิดด้วยข้อคิดหรือปริศนาที่ไม่มีที่มา ไม่บรรยายสิ่งเดิมหลายครั้ง\n'
        f'- {dialogue}\n'
        '- เขียนไทยทั้งหมด ใช้ย่อหน้าละ 1–3 ประโยค บทพูดขึ้นย่อหน้าใหม่\n'
        f'[ความยาว] ราว {scene_length(pkg)} ตัวอักษร ถ้าเหตุการณ์หมดให้จบ ไม่เติมคำเพื่อยืดความยาว\n'
        '[จบฉาก] จบเมื่อการกระทำในบันทึกเสร็จ ให้เห็นผลชัด ไม่แต่งเหตุการณ์ถัดไป'
    )
    if notes:
        user += '\n[จุดที่ต้องแก้]\n' + '\n'.join(notes)
    return system, user


def check_natural_scene(pkg, text):
    issues = []
    if len(text.strip()) < 180:
        issues.append('เนื้อเรื่องสั้นจนยังไม่เห็นการกระทำและผล เขียนให้เป็นฉากสั้นที่ครบ')
    if len(text) > scene_length(pkg) * 2:
        issues.append('ฉากยืดเยื้อเกินเหตุการณ์ ตัดคำบรรยายซ้ำและจบเมื่อทำสิ่งในบันทึกเสร็จ')
    if re.search(r'[一-鿿]|</?think>|<\|channel>', text) or len(re.findall(r'\b[A-Za-z]{3,}\b', text)) >= 6:
        issues.append('ส่งเฉพาะเนื้อเรื่องภาษาไทย ไม่ใส่คำอธิบายหรือข้อความวางแผน')
    if text.count('ราวกับ') + text.count('ดุจ') > 2:
        issues.append('เปลี่ยนคำเปรียบเทียบเป็นการกระทำที่ตรงและเข้าใจง่าย')
    paragraphs = [re.sub(r'\s+', '', p) for p in re.split(r'\n\s*\n', text) if len(p.strip()) > 30]
    if len(set(paragraphs)) < len(paragraphs):
        issues.append('มีย่อหน้าซ้ำ ให้เล่าแต่ละการกระทำครั้งเดียว')
    if pkg.focal_name not in text:
        issues.append(f'ระบุชื่อตัวละครหลัก {pkg.focal_name} ในครั้งแรกให้ผู้อ่านรู้ว่ากำลังติดตามใคร')
    return issues


class NaturalSceneWriter(SceneWriter):
    """Use the same transport, pause, token retry and durable-draft interface."""
    def _write(self, pkg):
        script = copy.deepcopy(self.resume) if self.resume is not None else SceneScript(
            scene_id=pkg.scene_id, beats=[WrittenBeat(stage='Scene')])
        if script.scene_id != pkg.scene_id or [b.stage for b in script.beats] != ['Scene']:
            raise ValueError('ร่างที่บันทึกไว้ไม่ตรงกับรูปแบบนิยายปัจจุบัน')
        beat = script.beats[0]
        for attempt in range(self.repair_rounds + 1):
            if beat.prose:
                script.issues = check_natural_scene(pkg, beat.prose)
                if not script.issues:
                    break
            system, user = build_prompt(pkg, script.issues)
            self.progress('กำลังเขียนฉากแบบนิยายอ่านง่าย' if attempt == 0 else 'กำลังแก้ฉากให้อ่านง่ายขึ้น')
            if self.agent is None:
                break
            out = self._complete(self.agent.complete, system, user, script,
                                 max(1200, scene_length(pkg)), self.prose_model, .55)
            if not out:
                raise RuntimeError('โมเดลยังไม่ส่งเนื้อเรื่องกลับมา ร่างเดิมยังเก็บไว้')
            beat.prose = out.strip()
            script.used_llm = True
            if attempt:
                beat.rewrites += 1
            script.issues = check_natural_scene(pkg, beat.prose)
            self.checkpoint(script)
        script.issues = check_natural_scene(pkg, beat.prose)
        return script
