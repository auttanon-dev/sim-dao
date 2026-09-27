# -*- coding: utf-8 -*-
"""กิจกรรมยาวเป็นกระบวนการที่ถูกขัดจังหวะได้ ผลคิดตามวันที่ทำไปจริง (แบบ §5.2) — models.ActionProcess

    python -m unittest test_processes -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest
from unittest import mock

from tiandao import body as BODY
from tiandao import config as C
from tiandao import food as FOOD
from tiandao import persist as PS
from tiandao import rules as R
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.day = 1000
        self.people = [c for c in self.sim.cast if c.alive and c.sentient and c.age(self.sim.day) >= 20
                       and c.world_id == 0][:4]

    def seclude(self, ch, years=3, gamma=2.0):
        ch.hidden = True
        return self.sim.start_process(ch, "seclusion", years * 365, {"snap": {"day": self.sim.day}}, gamma)

    def test_an_interrupted_seclusion_pays_only_for_the_days_spent(self):
        ch = self.people[0]
        insight = ch.insight
        self.seclude(ch)
        self.sim.day += 365
        self.assertTrue(quiet(self.sim.interrupt_process, ch, "ทดสอบ"))
        self.assertAlmostEqual(ch.insight - insight, C.SECLUDE_INSIGHT_PER_YEAR * 1 * 2.0)
        self.assertEqual((ch.seclude_until, ch.seclude_cut), (self.sim.day, "ทดสอบ"))
        self.assertIn((self.sim.day, ch.cid), self.sim.queue, "ออกจากด่านในเทิร์นวันนี้")

    def test_a_finished_seclusion_pays_exactly_its_length_even_if_the_exit_is_late(self):
        ch = self.people[0]
        insight = ch.insight
        self.seclude(ch, years=3, gamma=1.0)
        self.sim.day += 5 * 365
        self.sim.accrue_process(ch)
        self.sim.accrue_process(ch)                             # ซ้ำได้ ไม่จ่ายซ้ำ
        self.assertAlmostEqual(ch.insight - insight, C.SECLUDE_INSIGHT_PER_YEAR * 3)

    def test_a_fight_stops_a_journey_where_it_began(self):
        traveller, attacker = self.people[:2]
        origin = traveller.place
        self.sim.start_process(traveller, "travel", 40, {"dest": origin + 1, "origin": origin})
        quiet(R.fight, self.sim, self.sim.world(0), attacker, traveller, self.sim.rng, lethal_at=float("inf"))
        self.assertIsNone(traveller.process)
        self.assertEqual((traveller.travel_dest, traveller.place), (-1, origin))
        self.assertTrue(any(e.kind == "หยุดเดินทาง" and e.actor == traveller.cid for e in self.sim.log))

    def test_unconsciousness_stops_everything_but_lame_legs_only_stop_travel(self):
        monk, walker = self.people[:2]
        self.seclude(monk)
        self.sim.start_process(walker, "travel", 40, {"dest": walker.place + 1, "origin": walker.place})
        with mock.patch.object(BODY, "can_stand", return_value=False):
            quiet(self.sim.check_processes)
        self.assertIsNone(walker.process)
        self.assertGreater(monk.seclude_until, self.sim.day, "นั่งบำเพ็ญในด่านต่อได้")
        with mock.patch.object(BODY, "conscious", return_value=False):
            quiet(self.sim.check_processes)
        self.assertEqual(monk.seclude_until, self.sim.day)
        self.assertEqual(monk.seclude_cut, "หมดสติ")

    def test_cultivation_pays_by_the_day_and_an_attack_cuts_it_short(self):
        ch, attacker = self.people[:2]
        ch.decay = 0.0
        insight, refine = ch.insight, ch.refine
        self.sim.begin_cultivation(ch, 300)
        self.assertEqual((ch.insight, ch.process.kind), (insight, "cultivation"), "ยังไม่ได้ผลล่วงหน้า")
        self.sim.day += 100
        quiet(R.fight, self.sim, self.sim.world(0), attacker, ch, self.sim.rng, lethal_at=1e9)   # เจตนาฆ่า แต่ไม่ถึงตาย
        self.assertIsNone(ch.process)
        self.assertAlmostEqual(ch.insight - insight, 0.45 * 100 / 365 * R.eff(ch, "human"))
        self.assertAlmostEqual(ch.refine - refine, 0.10 * 100 / 365 * R.eff(ch, "spirit"))
        self.assertEqual(self.sim.process_stats.get("cultivation:ถูกโจมตี"), 1)

    def test_sparring_stops_cultivation_only_if_it_leaves_the_loser_unable_to_fight(self):
        ch, partner = self.people[:2]
        spar = lambda: quiet(R.fight, self.sim, self.sim.world(0), partner, ch, self.sim.rng,
                             lethal_at=1e9, lethal=False)
        self.sim.begin_cultivation(ch, 300)
        with mock.patch.object(R, "resolve_clash", return_value=(partner, ch, 0.1)),                 mock.patch.object(BODY, "can_fight", return_value=True):
            spar()
        self.assertEqual(ch.process.kind, "cultivation", "ประลองแล้วนั่งบำเพ็ญต่อได้")
        with mock.patch.object(R, "resolve_clash", return_value=(partner, ch, 0.1)),                 mock.patch.object(BODY, "can_fight", return_value=False):
            spar()
        self.assertIsNone(ch.process)
        self.assertEqual(self.sim.process_stats.get("cultivation:บาดเจ็บสาหัส"), 1)

    def test_an_uninterrupted_cultivation_pays_its_full_span_once(self):
        ch = self.people[0]
        ch.decay, ch.insight = 0.0, 0.0
        self.sim.begin_cultivation(ch, 200, rate=1.5)
        self.sim.day += 900                                     # เทิร์นถัดไปมาช้า ได้แค่ช่วงที่นัดไว้
        self.sim.settle_cultivation(ch)
        self.sim.settle_cultivation(ch)
        self.assertIsNone(ch.process)
        self.assertAlmostEqual(ch.insight, 0.45 * 300 / 365 * R.eff(ch, "human"))

    def test_hunger_and_unconsciousness_stop_cultivation(self):
        hungry, fainted = self.people[:2]
        for c in (hungry, fainted):
            self.sim.begin_cultivation(c, 300)
        self.sim.day += 30
        quiet(FOOD._respond, self.sim, hungry)
        self.assertFalse(hungry.process is not None and hungry.process.kind == "cultivation")
        with mock.patch.object(BODY, "conscious", return_value=False):
            quiet(self.sim.check_processes)
        self.assertIsNone(fainted.process)

    def test_cultivating_on_the_road_pays_at_once_and_keeps_the_journey(self):
        ch = self.people[0]
        self.sim.start_process(ch, "travel", 40, {"dest": ch.place + 1, "origin": ch.place})
        insight = ch.insight
        self.sim.begin_cultivation(ch, 100)
        self.assertEqual(ch.process.kind, "travel")
        self.assertGreater(ch.insight, insight)

    def test_the_old_fields_read_and_write_through_the_process(self):
        ch = self.people[0]
        ch.travel_dest, ch.travel_arrival_day = 7, 1040
        self.assertEqual((ch.process.kind, ch.process.end_day, ch.travel_dest), ("travel", 1040, 7))
        ch.travel_dest = -1
        self.assertIsNone(ch.process)
        self.assertEqual(ch.seclude_until, 0)

    def test_a_version_13_save_turns_its_old_fields_into_processes_without_moving_the_rng(self):
        monk, walker = self.people[:2]
        monk.hidden = True
        monk.__dict__.update(seclude_until=self.sim.day + 400, seclude_snap={"day": self.sim.day - 10, "gamma": 1.5})
        walker.__dict__.update(travel_dest=walker.place + 1, travel_arrival_day=self.sim.day + 20)
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 13, "sim": self.sim}, f)
            back = PS.load_sim(path)
        m, w = back.cast[monk.cid], back.cast[walker.cid]
        self.assertEqual((m.process.kind, m.seclude_until, m.process.start_day, m.process.yield_rate),
                         ("seclusion", self.sim.day + 400, self.sim.day - 10, 1.5))
        self.assertEqual((w.process.kind, w.travel_dest, w.travel_arrival_day),
                         ("travel", walker.place + 1, self.sim.day + 20))
        self.assertNotIn("travel_dest", w.__dict__)
        self.assertEqual(back.rng.getstate(), state)


if __name__ == "__main__":
    unittest.main()
