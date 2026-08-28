import json
import sys
from collections import Counter

def analyze(log_path):
    war_count = 0
    treasure_rob_count = 0
    casualty_count = 0
    loot_money_total = 0
    
    heaven_wars = 0
    heaven_wars_won = 0
    heaven_wars_deaths = 0
    
    child_bonuses = 0

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                ev = json.loads(line)
            except:
                continue
            
            k = ev.get("kind", "")
            d = ev.get("deltas", {})
            
            if k == "สงครามสำนัก" and ev.get("outcome") == "จบสิ้น":
                war_count += 1
                casualty_count += d.get("ผู้เสียชีวิต", 0)
                loot_money_total += d.get("เงินปล้น", 0)
            
            if k == "ชิงสมบัติ" and "ชิงได้" in d:
                treasure_rob_count += 1
                
            if k == "สงครามเบิกฟ้า":
                heaven_wars += 1
                if 'ประตูปิดกั้นพังทลาย' in d:
                    heaven_wars_won += 1
                if ev.get("result") == "ตาย":
                    heaven_wars_deaths += 1
                    
            if k == "กำเนิดทายาท" and "ทายาทผู้ฝึกตน" in d:
                child_bonuses += 1
                
    print(f"--- Diagnostic Results ---")
    print(f"Sect Wars: {war_count}")
    print(f"War Casualties: {casualty_count}")
    print(f"War Loot Money: {loot_money_total}")
    print(f"Successful God-Tier Treasure Robs: {treasure_rob_count}")
    print(f"Heaven Wars Attempted: {heaven_wars}")
    print(f"Heaven Wars Won (Gates broken): {heaven_wars_won}")
    print(f"Heaven Wars Deaths: {heaven_wars_deaths}")
    print(f"Cultivator Children Born (Bonus applied): {child_bonuses}")

if __name__ == '__main__':
    analyze('out/events_0.jsonl')
