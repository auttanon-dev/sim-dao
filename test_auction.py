# -*- coding: utf-8 -*-
"""งานประมูล — เหตุการณ์หมู่ที่ดึงคนในสถานที่เดียวกันมาสู้ราคากันจริง

    python -m unittest test_auction -v
"""
import contextlib
import io
import shutil
import tempfile
import unittest

from tiandao import config as C
from tiandao import sim as S
from tiandao.mind import backend as B
from tiandao.mind import storyteller as ST
from tiandao.mind.runner import RunConfig, open_world


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class Base(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5, tiers=2)
        self.w = self.sim.worlds[0]
        import collections
        place = collections.Counter(c.place for c in self.sim.living_in(0)).most_common(1)[0][0]
        self.people = [c for c in self.sim.living_in(0) if c.place == place][:8]
        for c in self.people:
            c.money[0] = 500
            c.hidden, c.travel_dest = False, -1
        self.host = self.people[0]


class TestAuction(Base):
    def test_many_people_bid_and_one_wins(self):
        outcome, text, d = self.sim.auction(self.host, self.w, self.sim.rng, {})
        self.assertEqual(outcome, "ประมูล")
        self.assertIn("ผู้ร่วมประมูล", d)
        self.assertGreaterEqual(len(d["ผู้ร่วมประมูล"].split(" · ")), 2)
        self.assertIn("ผู้ชนะ", d)
        self.assertIn(d["คู่แข่งคนสุดท้าย"], d["ผู้ร่วมประมูล"])

    def test_wealth_moves_from_winner_to_host(self):
        """ราคาคิดเป็นหน่วยปราณแล้ว ผู้ชนะจ่ายด้วยหินวิญญาณก่อน ขาดเท่าไรค่อยเติมด้วยทอง
        สิ่งที่ต้องล็อกคือ **ความมั่งคั่งรวมไม่หายและไม่งอก** มันย้ายมือเท่านั้น
        """
        from tiandao import economy as EC
        before_host = self.sim.bid_purse(self.host, self.w)
        _, _, d = self.sim.auction(self.host, self.w, self.sim.rng, {})
        winner_name, price = d["ผู้ชนะ"].split(" จ่าย ")
        price = float(price.split()[0])
        winner = next(c for c in self.people if c.name == winner_name)
        self.assertGreater(price, 0)
        self.assertAlmostEqual(self.sim.bid_purse(self.host, self.w),
                               before_host + price, places=4)
        self.assertAlmostEqual(self.sim.bid_purse(winner, self.w),
                               500 / C.STONE_GOLD_PER_QI - price, places=4)

    def test_winner_pays_second_price_not_own_ceiling(self):
        _, _, d = self.sim.auction(self.host, self.w, self.sim.rng, {})
        bids = [float(x.split("สู้ถึง ")[1].rstrip(")")) for x in d["ผู้ร่วมประมูล"].split(" · ")]
        price = float(d["ผู้ชนะ"].split(" จ่าย ")[1].split()[0])
        self.assertLessEqual(price, bids[0] + 1e-6)
        self.assertLessEqual(price, bids[1] * C.AUCTION_STEP + 1e-6)

    def test_reported_price_is_exactly_the_wealth_that_moved(self):
        """ราคาที่รายงานต้องเป็นราคาเดียวกับที่ย้ายมือจริง ไม่ใช่ราคาเต็มความละเอียดอันหนึ่ง
        กับราคาที่ถูกปัดให้อ่านง่ายอีกอันหนึ่ง — ไม่งั้นตรวจบัญชีย้อนหลังจากบันทึกไม่ได้
        """
        before = {c.cid: self.sim.bid_purse(c, self.w) for c in self.people}
        _, text, d = self.sim.auction(self.host, self.w, self.sim.rng, {})
        price = float(d["ผู้ชนะ"].split(" จ่าย ")[1].split()[0])
        winner = next(c for c in self.people if c.name == d["ผู้ชนะ"].split(" จ่าย ")[0])
        self.assertEqual(price, d["ราคาที่จ่าย"])
        self.assertIn(f"{price:.1f} หน่วยปราณ", text)
        after = {c.cid: self.sim.bid_purse(c, self.w) for c in self.people}
        self.assertAlmostEqual(after[self.host.cid] - before[self.host.cid], price, places=4)
        self.assertAlmostEqual(before[winner.cid] - after[winner.cid], price, places=4)
        # ความมั่งคั่งรวมของทุกคนในงานต้องไม่หายและไม่งอก — ย้ายมืออย่างเดียว
        self.assertAlmostEqual(sum(after.values()), sum(before.values()), places=4)
        for c in self.people:
            if c.cid not in (self.host.cid, winner.cid):
                self.assertAlmostEqual(after[c.cid], before[c.cid], places=6)

    def test_bidders_are_listed_from_the_highest_bid_down(self):
        """รายชื่อผู้ร่วมประมูลเรียงตามราคาที่เสนอ ผู้ชนะอยู่หัวแถว ผู้แพ้หวุดหวิดอยู่อันดับสอง"""
        _, _, d = self.sim.auction(self.host, self.w, self.sim.rng, {})
        entries = d["ผู้ร่วมประมูล"].split(" · ")
        bids = [float(x.split("สู้ถึง ")[1].rstrip(")")) for x in entries]
        self.assertEqual(bids, sorted(bids, reverse=True))
        self.assertTrue(entries[0].startswith(d["ผู้ชนะ"].split(" จ่าย ")[0]))
        self.assertTrue(entries[1].startswith(d["คู่แข่งคนสุดท้าย"]))
        self.assertEqual(bids[1], d["ราคาที่คู่แข่งสู้ถึง"])
        # กติกาวิกเครย์: จ่ายตามราคาอันดับสอง ไม่ใช่เพดานของตัวเอง
        self.assertLessEqual(d["ราคาที่จ่าย"], bids[1] * C.AUCTION_STEP + 1e-9)

    def test_runner_up_holds_a_grudge_and_winner_thanks_the_host(self):
        _, _, d = self.sim.auction(self.host, self.w, self.sim.rng, {})
        winner = next(c for c in self.people if c.name == d["ผู้ชนะ"].split(" จ่าย ")[0])
        runner = next(c for c in self.people if c.name == d["คู่แข่งคนสุดท้าย"])
        self.assertGreaterEqual(runner.rivals.get(winner.cid, 0), 1)
        self.assertGreaterEqual(winner.bonds.get(self.host.cid, 0), 1)

    def test_winner_gets_a_second_journal_line(self):
        n = len(self.sim.log)
        self.sim.auction(self.host, self.w, self.sim.rng, {})
        added = self.sim.log[n:]
        self.assertTrue(any(e.kind == "เปิดประมูล" and e.outcome == "ชนะประมูล" and e.target is not None
                            for e in added), "ผู้ชนะต้องได้บรรทัดของตัวเองด้วย (ชั้นจิตใจจะได้รับรู้)")

    def test_alone_means_no_auction(self):
        lonely = next(c for c in self.sim.living_in(0) if c.place not in (self.host.place,))
        for c in self.sim.living_in(0):
            if c.cid != lonely.cid:
                c.place = (lonely.place + 7) % 20
        outcome, text, _ = self.sim.auction(lonely, self.w, self.sim.rng, {})
        self.assertEqual(outcome, "ค้าขาย")
        self.assertIn("ไม่มีคนมากพอ", text)


class TestMarketAuctionEvent(Base):
    def test_market_holds_an_auction_even_without_a_merchant(self):
        from tiandao import places as PL
        market = next(i for i, p in enumerate(PL.PLACES)
                      if p[1] == self.w.place_key and p[3] in C.AUCTION_PLACES)
        for c in self.people:
            c.place = market
        n = len(self.sim.log)
        self.sim.market_auction(self.w, self.sim.rng)
        added = [e for e in self.sim.log[n:] if e.kind == "เปิดประมูล"]
        self.assertTrue(added, "ตลาดที่มีคนพอต้องเปิดงานประมูลได้เอง")
        self.assertIn("เปิดงานประมูลใหญ่", added[-1].text)
        self.assertEqual({"ชนะประมูล", "พลาดประมูล", "ประมูล"}, {e.outcome for e in added})

    def test_runner_up_is_told_he_lost(self):
        n = len(self.sim.log)
        self.sim.auction(self.host, self.w, self.sim.rng, {})
        miss = [e for e in self.sim.log[n:] if e.outcome == "พลาดประมูล"]
        self.assertTrue(miss, "คนที่แพ้ไปหวุดหวิดต้องได้บรรทัดของตัวเองด้วย")
        self.assertIsNotNone(miss[0].target)

    def test_quiet_market_holds_nothing(self):
        for c in self.sim.living_in(0):
            c.place = 0 if c.cid % 2 else 1
        before = len(self.sim.log)
        for c in self.sim.living_in(0):
            c.hidden = True
        self.sim.market_auction(self.w, self.sim.rng)
        self.assertEqual(len(self.sim.log), before)


class TestAuctionReachesMinds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sim = open_world(RunConfig(out_dir=self.tmp, seed=3, capacity=10, story=False), B.MockThinker())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_winner_mind_gets_the_crowd_list_and_a_story(self):
        from tiandao import places as PL
        w = self.sim.worlds[0]
        mind_cid = self.sim.mind.active()[0].cid
        market = next(i for i, p in enumerate(PL.PLACES)
                      if p[1] == w.place_key and p[3] in C.AUCTION_PLACES)
        folk = [c for c in self.sim.living_in(0) if c.cid != mind_cid][:5] + [self.sim.cast[mind_cid]]
        for c in folk:
            c.place, c.hidden, c.travel_dest = market, False, -1
            c.money[0] = 100
        self.sim.cast[mind_cid].money[0] = 5000
        self.sim.cast[mind_cid].greed = 0.99
        host = folk[0]
        # มูลค่าในใจของผู้เข้าประมูลเป็นค่าส่วนตัวแบบล็อกนอร์มัลแล้ว (independent private
        # values) การมีเงินเยอะจึงไม่ได้แปลว่าชนะทุกครั้ง — เงินเป็นแค่เพดาน ไม่ใช่ราคาที่เสนอ
        # เทสนี้ล็อกเรื่อง "ผู้มีจิตใจได้รับรู้งานประมูล" ไม่ใช่ "เขาชนะในการทอยครั้งเดียว"
        for _ in range(25):
            for c in folk:
                c.place, c.hidden, c.travel_dest = market, False, -1
                c.money[0] = 100
            self.sim.cast[mind_cid].money[0] = 5000
            self.sim.auction(host, w, self.sim.rng, {})
            if any(e.get("action") == "เปิดประมูล" for e in self.sim.mind.recent):
                break
        entries = [e for e in self.sim.mind.recent if e.get("action") == "เปิดประมูล"]
        self.assertTrue(entries, "ผู้มีจิตใจต้องได้บรรทัดงานประมูล")
        self.assertTrue(any((e.get("details") or {}).get("ผู้ร่วมประมูล") for e in entries),
                        "บันทึกต้องพารายชื่อผู้ร่วมงานมาด้วย ไม่งั้นเขียนฉากหมู่ไม่ได้")
        queued = [e for e in self.sim.mind.story_queue if e.get("action") == "เปิดประมูล"]
        self.assertTrue(queued, "ฉากงานประมูลต้องเข้าคิวแต่งเรื่อง")
        _, user = ST.build(self.sim, queued[0])
        self.assertIn("ฉากงานชุมนุม", user)


class TestAuctionScene(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sim = open_world(RunConfig(out_dir=self.tmp, seed=3, capacity=10, story=False), B.MockThinker())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_story_prompt_asks_for_a_crowd_scene(self):
        cid = self.sim.mind.active()[0].cid
        entry = {"id": "d-5", "seq": 5, "day": self.sim.day, "year": 0, "cid": cid,
                 "name": self.sim.cast[cid].name, "place": "ตลาดมืด", "action": "เปิดประมูล", "target": "",
                 "dest": "", "why": "หาเงิน", "thought": "", "emotion": "", "long_goal": "",
                 "outcome": "ประมูล", "text": "เปิดงานประมูล", "alive": True, "side": [],
                 "details": {"ของที่ประมูล": "แผนที่แดนลับ",
                             "ผู้ร่วมประมูล": "ฉินลั่ว (สู้ถึง 280) · มู่หรงม่อ (สู้ถึง 167) · เซียวเจี้ยน (สู้ถึง 139)",
                             "ผู้ชนะ": "ฉินลั่ว จ่าย 168 เหรียญ", "คู่แข่งคนสุดท้าย": "มู่หรงม่อ"}}
        _, user = ST.build(self.sim, entry)
        self.assertIn("ฉากงานชุมนุม", user)
        self.assertIn("ฉินลั่ว", user)
        self.assertIn("มู่หรงม่อ", user)
        self.assertIn("ผู้ที่พลาดไปอย่างหวุดหวิด", user)


if __name__ == "__main__":
    unittest.main()
