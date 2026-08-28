# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_event = '''            if self.day % 30 == 0:'''
new_event = '''            # ------------------------------------------------
            # Grand Auction (งานประมูลใหญ่ระดับทวีป) Every 365 Days
            # ------------------------------------------------
            if self.day % 365 == 0:
                import tiandao.config as C
                auction_city = None
                if hasattr(C, "CITIES"):
                    major_cities = [c for c in C.CITIES if "เมืองหลวง" in c.get("type_desc", "") or "เมืองลับแล" in c.get("type_desc", "")]
                    if major_cities:
                        auction_city = self.rng.choice(major_cities)
                
                if auction_city:
                    print(f"\\n🏮 [งานประมูลระดับทวีป] จัดขึ้นที่ <{auction_city['name_th']}>!")
                    
                    # Generate an auction item
                    auction_items = ["คัมภีร์วิถีสวรรค์", "ธงค่ายกลเพลิงผลาญวิญญาณ", "แก่นอสูรบรรพกาล", "ยาโอสถระดับตำนาน"]
                    item = self.rng.choice(auction_items)
                    print(f" -> 💎 ของประมูลชิ้นเอก: [{item}]")
                    
                    # Gather wealthy participants
                    attendees = [c for c in self.cast.values() if c.alive and getattr(c, "spirit_stones", 0) > 5000 and c.realm >= 3]
                    if len(attendees) >= 2:
                        attendees.sort(key=lambda x: getattr(x, "spirit_stones", 0), reverse=True)
                        winner = attendees[0]
                        loser = attendees[1]
                        
                        bid_price = getattr(loser, "spirit_stones", 0) + 1000 # Win by outbidding the 2nd richest
                        if bid_price > getattr(winner, "spirit_stones", 0):
                            bid_price = getattr(winner, "spirit_stones", 0)
                            
                        winner.spirit_stones = max(0, getattr(winner, "spirit_stones", 0) - bid_price)
                        print(f" -> 💰 [{winner.name}] (ขั้น {winner.realm}) ประมูลชนะไปด้วยราคา {bid_price} ศิลาปราณ!")
                        
                        # Apply buff/item
                        winner.max_hp = getattr(winner, "max_hp", 100) + 50
                        
                        # Post-Auction Robbery
                        if winner.realm < loser.realm and auction_city.get("law_strictness", 50) < 50:
                            print(f" -> 🗡️ [ดักปล้นชิงทรัพย์] [{loser.name}] (ขั้น {loser.realm}) แค้นที่ประมูลแพ้ จึงดักซุ่มโจมตี [{winner.name}] หลังจบงาน!")
                            import tiandao.combat as combat
                            combat.resolve_combat(loser, winner, self.worlds[0], self)
                    else:
                        print(f" -> ❌ งานประมูลกร่อย ไม่มีใครมีกำลังทรัพย์พอที่จะประมูล")

            if self.day % 30 == 0:'''
content = content.replace(old_event, new_event)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Grand Auction!")
