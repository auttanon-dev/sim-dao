import json
import os

print("\n=======================================================")
print("🏆 📜 [ทำเนียบยอดฝีมือแห่งยุทธภพ - บันทึกผู้ที่ยังมีชีวิตอยู่] 📜 🏆")
print("=======================================================")

chars = {}
try:
    with open('out/chars_0.json', 'r', encoding='utf-8') as f:
        chars = json.load(f)
except FileNotFoundError:
    print("ไม่พบข้อมูลตัวละคร กรุณารันเกมก่อน (python run.py)")
    exit()

survivors = []
for cid, c in chars.items():
    if c.get("alive", False):
        survivors.append(c)

if not survivors:
    print("💀 อนิจจา... ยุทธภพนองเลือด ไม่มีชาวยุทธท่านใดรอดชีวิตเหลืออยู่เลย!")
else:
    # Sort by realm (which represents level) and then money
    survivors.sort(key=lambda x: (x.get("realm", 0), sum(x.get("money", {}).values())), reverse=True)
    
    for index, char in enumerate(survivors[:20], 1):
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🎖️"
        
        realm = char.get("realm", 0)
        money = sum(char.get("money", {}).values())
        visited = char.get("cities_visited", 0)
        defeated = char.get("enemies_defeated", 0)
        
        print(f"{medal} อันดับ {index}: [{char['name']}]")
        print(f"   ↳ 🥋 วรยุทธขั้น: Level {realm} | 🪙 เงินตรา: {money} Gold")
        print(f"   ↳ 🗺️  เดินทางผ่านมาแล้ว: {visited} เมือง | ⚔️ ปราบศัตรูไปได้: {defeated} คน")

print("=======================================================\n")
