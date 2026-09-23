# -*- coding: utf-8 -*-
from tiandao import rules as R
from tiandao import config as C
import random

DAO_ADVANTAGE = C.DAO_ADVANTAGE   # ตารางย้ายไปอยู่ config.py แล้ว (rules.py ก็ต้องใช้)


def resolve_combat(attacker, defender, world, sim):
    log_parts = []
    log_parts.append(f"⚔️ [{attacker.name}] ปะทะ [{defender.name}]")
    
    # Analyze inventories for manuals
    def get_combat_multipliers(char):
        mult = 1.0
        used_skill = None
        for iid in getattr(char, "items", []):
            if iid in sim.items:
                item = sim.items[iid]
                if item.kind == "วิชาต่อสู้" or item.kind == "คัมภีร์บ่มเพาะ":
                    # MP Cost check
                    mp_cost = 50 + (item.grade * 100)
                    if getattr(char, "current_mp", 0) >= mp_cost:
                        char.current_mp -= mp_cost
                        mult += item.grade * 1.5 # Massive boost for high grade manual
                        used_skill = item.name
                        break # Only use one skill per combat
        return mult, used_skill
        
    atk_skill_mult, atk_skill = get_combat_multipliers(attacker)
    def_skill_mult, def_skill = get_combat_multipliers(defender)
    
    if atk_skill: log_parts.append(f"   -> [{attacker.name}] ผลาญลมปราณ ใช้เคล็ดวิชา: [{atk_skill}]!")
    if def_skill: log_parts.append(f"   -> [{defender.name}] โต้กลับด้วยเคล็ดวิชา: [{def_skill}]!")

    # Realm Suppression
    realm_diff = attacker.realm - defender.realm
    realm_mult_a = max(0.1, 1.0 + (realm_diff * 0.5))
    realm_mult_d = max(0.1, 1.0 - (realm_diff * 0.5))
    
    if realm_diff > 0:
        log_parts.append(f"   -> [{attacker.name}] พลังขั้นสูงกว่า ข่มขวัญศัตรู!")
    elif realm_diff < 0:
        log_parts.append(f"   -> [{attacker.name}] ฝืนลิขิตฟ้า ท้าทายผู้แข็งแกร่งกว่า!")

    # Dao Advantage
    dao_mult_a = 1.0
    dao_mult_d = 1.0
    
    if attacker.dao in DAO_ADVANTAGE and defender.dao in DAO_ADVANTAGE[attacker.dao]:
        dao_mult_a = C.DAO_EDGE_MULT
        log_parts.append(f"   -> {attacker.dao} ข่ม {defender.dao} ได้เปรียบ!")
    elif defender.dao in DAO_ADVANTAGE and attacker.dao in DAO_ADVANTAGE[defender.dao]:
        dao_mult_d = C.DAO_EDGE_MULT
        log_parts.append(f"   -> {defender.dao} ของเป้าหมาย ปัดเป่าการรุกคืบ!")
        
    # Calculate Base Power
    atk_power = R.power(attacker, world) * realm_mult_a * dao_mult_a * atk_skill_mult
    def_power = R.power(defender, world) * realm_mult_d * dao_mult_d * def_skill_mult
    
    atk_power *= sim.rng.uniform(0.8, 1.2)
    def_power *= sim.rng.uniform(0.8, 1.2)
    
    if atk_power >= def_power:
        winner, loser = attacker, defender
        log_parts.append(f"   💥 [{attacker.name}] เป็นฝ่ายชนะ!")
    else:
        winner, loser = defender, attacker
        log_parts.append(f"   💥 [{defender.name}] พลิกสถานการณ์กลับมาเอาชนะได้!")
        
    # Looting logic
    if getattr(loser, "items", []):
        winner.items.extend(loser.items)
        loser.items = []
        log_parts.append(f"   💰 [{winner.name}] ริบสมบัติทั้งหมดของผู้แพ้!")
    
    # Talisman Escape Check
    escaped = False
    for iid in getattr(loser, "items", []):
        if iid in sim.items and sim.items[iid].kind == "ยันต์วิเศษ (ใช้แล้วทิ้ง)":
            talisman = sim.items[iid]
            loser.items.remove(iid)
            del sim.items[iid]
            log_parts.append(f"   🚨 [หนีตาย] [{loser.name}] ใช้ {talisman.name} หลบหนีความตายไปได้ฉิวเฉียด!")
            escaped = True
            break
            
    return winner, loser, "\n".join(log_parts), escaped
