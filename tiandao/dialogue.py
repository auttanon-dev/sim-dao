# -*- coding: utf-8 -*-
"""Personality & Dao Dialogue Engine for Tiandao World Simulator.

Generates dynamic, rich contextual Wuxia/Xianxia conversations between cultivators
based on Personality traits (fear, greed, compassion), Dao paths, Bloodlines,
Realm disparity, Relationship/Debts, and Encounter Location.
"""
import random
from typing import Dict, List, Any, Optional

from . import config as C
from . import places as PL


def generate_encounter_dialogue(speaker, listener, location_name: str = "โรงเตี๊ยม", location_type: str = "เมือง") -> Dict[str, Any]:
    """สร้างบทสนทนาระหว่างตัวละคร 2 ตัวที่พบกันในสถานที่หนึ่งๆ"""
    if speaker is None or listener is None:
        return {
            "speaker_name": "ผู้บำเพ็ญนิรนาม",
            "listener_name": "สหายร่วมทาง",
            "lines": [{"speaker": "ผู้บำเพ็ญนิรนาม", "text": "วิถีแห่งฟ้านั้นกว้างใหญ่ ยินดีที่ได้พบพาน", "tone": "neutral"}]
        }

    s_name = speaker.name
    l_name = listener.name
    s_realm = getattr(speaker, "realm", 0)
    l_realm = getattr(listener, "realm", 0)
    s_dao = getattr(speaker, "dao", "วิถีดาบ")
    l_dao = getattr(listener, "dao", "วิถีดาบ")
    s_greed = getattr(speaker, "greed", 0.5)
    s_fear = getattr(speaker, "fear", 0.5)
    s_compassion = getattr(speaker, "compassion", 0.5)
    
    # Check relationship & debt
    has_debt = False
    if hasattr(speaker, "debts") and isinstance(speaker.debts, dict):
        has_debt = listener.cid in speaker.debts
        
    same_dao = (s_dao == l_dao)
    realm_diff = s_realm - l_realm

    dialogue_script = []

    # Case 1: มีหนี้แค้นต่อกัน (Debt / Vendetta)
    if has_debt:
        dialogue_script.append({
            "speaker": s_name,
            "text": f"เจ้าคิดว่าจะหนีพ้นเงื้อมมือข้าหรือ {l_name}! หนี้เลือดในอดีต วันนี้ต้องสะสาง ณ {location_name}!",
            "tone": "hostile",
            "action": "ชักอาวุธขึ้นมาจ่อ"
        })
        if s_realm > l_realm:
            dialogue_script.append({
                "speaker": l_name,
                "text": f"พลังขั้น {speaker.realm_name()} ช่างน่าเกรงขาม... แต่ข้าก็ไม่ยอมจำนนง่ายๆ หรอก!",
                "tone": "fearful",
                "action": "ถอยหลังตั้งการ์ด"
            })
        else:
            dialogue_script.append({
                "speaker": l_name,
                "text": f"ฮ่าๆๆ! พลังกระจ้อยร่อยแค่นี้ยังกล้ามาทวงแค้น จงรับกระบวนท่าข้าเสียเถิด!",
                "tone": "arrogant",
                "action": "เปล่งปราณคุ้มกาย"
            })
        return {
            "context": "หนี้แค้นสะสาง",
            "speaker_name": s_name,
            "listener_name": l_name,
            "location": location_name,
            "lines": dialogue_script
        }

    # Case 2: พบกันในลานประลอง / โดโจ (Martial Dojo / Arena)
    if "ลานประลอง" in location_name or "ค่ายมวย" in location_name or "โดโจ" in location_name:
        dialogue_script.append({
            "speaker": s_name,
            "text": f"สหาย {l_name}! ข้าบำเพ็ญ {s_dao} มายาวนาน วันนี้ขอลองแลกเปลี่ยนกระบวนท่ากับ {l_dao} ของเจ้าสักครา!",
            "tone": "challenging",
            "action": "ประสานมือคารวะก่อนตั้งการ์ด"
        })
        dialogue_script.append({
            "speaker": l_name,
            "text": "ยอดเยี่ยม! การประลองแลกเปลี่ยนความเข้าใจคือทางลัดสู่การเบิกเนตรเต๋า ขอคำชี้แนะด้วย!",
            "tone": "eager",
            "action": "ก้าวขึ้นสู่ลานประลอง"
        })
        return {
            "context": "ท้าประลองวิชา",
            "speaker_name": s_name,
            "listener_name": l_name,
            "location": location_name,
            "lines": dialogue_script
        }

    # Case 3: พบกันในตลาด / หอประมูล (Market / Merchant Barter)
    if "ตลาด" in location_name or "ประมูล" in location_name or s_greed > 0.6:
        dialogue_script.append({
            "speaker": s_name,
            "text": f"สหาย {l_name} ท่าทางเจ้าเพิ่งกลับมาจากแดนลับ มีศิลาปราณหรือโอสถชั้นเลิศจะปล่อยขายบ้างหรือไม่?",
            "tone": "mercantile",
            "action": "หยิบถุงศิลาปราณขึ้นมาเขย่า"
        })
        if getattr(listener, "greed", 0.5) > 0.5:
            dialogue_script.append({
                "speaker": l_name,
                "text": "หึหึ ของดีมีแน่นอน แต่ราคาในตลาดช่วงนี้พุ่งสูง เจ้าสู้ไหวหรือไม่เล่า?",
                "tone": "shrewd",
                "action": "นำเทียบราคาสมุนไพรออกมาคลี่"
            })
        else:
            dialogue_script.append({
                "speaker": l_name,
                "text": "ข้าเน้นบำเพ็ญจิตใจ หากเจ้าต้องการโอสถสมานแผล ข้ายกให้ในราคามิตรภาพได้",
                "tone": "generous",
                "action": "ส่งขวดยาหยกให้"
            })
        return {
            "context": "การค้าและการเจรจา",
            "speaker_name": s_name,
            "listener_name": l_name,
            "location": location_name,
            "lines": dialogue_script
        }

    # Case 4: บำเพ็ญวิถีเต๋าเดียวกัน (Same Dao Enlightenment)
    if same_dao:
        dialogue_script.append({
            "speaker": s_name,
            "text": f"กลิ่นอายปราณของเจ้า... เจ้าเองก็เดินบนเส้นทาง {s_dao} เหมือนกันหรือ?",
            "tone": "friendly",
            "action": "รินสุราคารวะ"
        })
        dialogue_script.append({
            "speaker": l_name,
            "text": f"มิผิดเลย! {s_dao} นั้นลึกซึ้งดั่งห้วงสมุทร ได้พบผู้ร่วมอุดมการณ์เช่นเจ้านับเป็นวาสนายิ่งนัก!",
            "tone": "harmonious",
            "action": "ยกจอกสุราขึ้นดื่ม"
        })
        return {
            "context": "สนทนาธรรมและมรรค",
            "speaker_name": s_name,
            "listener_name": l_name,
            "location": location_name,
            "lines": dialogue_script
        }

    # Case 5: ผู้อาวุโสพบผู้เยาว์ (Elder Mentor or Intimidation)
    if realm_diff >= 2:
        dialogue_script.append({
            "speaker": s_name,
            "text": f"เจ้าหนุ่มน้อย {l_name} รากฐานเจ้ายังไม่มั่นคง อย่ารีบร้อนทะลวงขั้นจนธาตุไฟเข้าแทรกเล่า",
            "tone": "mentor",
            "action": "ลูบเคราพร้อมส่งกระแสปราณอุ่น"
        })
        dialogue_script.append({
            "speaker": l_name,
            "text": f"ขอบพระคุณผู้อาวุโส {s_name} สำหรับคำสั่งสอน ข้าน้อยจะจดจำไว้ใส่ใจ!",
            "tone": "respectful",
            "action": "คุกเข่าคำนับด้วยความเคารพ"
        })
        return {
            "context": "คำชี้แนะจากผู้อาวุโส",
            "speaker_name": s_name,
            "listener_name": l_name,
            "location": location_name,
            "lines": dialogue_script
        }

    # Default: สนทนาข่าวสารทั่วไปในโรงเตี๊ยม
    dialogue_script.append({
        "speaker": s_name,
        "text": f"สหาย {l_name} เจ้าได้ยินข่าวลือเรื่องมหาผนึกสะกดหมื่นมารที่กำลังสั่นคลอนหรือไม่?",
        "tone": "inquisitive",
        "action": "นั่งลงร่วมโต๊ะน้ำชา"
    })
    dialogue_script.append({
        "speaker": l_name,
        "text": "ได้ยินมาว่ายุทธภพเริ่มปั่นป่วน เหล่าสำนักใหญ่กำลังเตรียมระดมพล ข้าว่าพวกเราควรรีบสะสมศิลาปราณไว้ให้พร้อม",
        "tone": "concerned",
        "action": "พยักหน้าอย่างสุขุม"
    })
    return {
        "context": "สนทนาข่าวสารยุทธภพ",
        "speaker_name": s_name,
        "listener_name": l_name,
        "location": location_name,
        "lines": dialogue_script
    }
