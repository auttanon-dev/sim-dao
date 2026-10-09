# -*- coding: utf-8 -*-
"""ข่าวความตายเดินทางถึงคนไกลช้ากว่าคนที่เห็น (แบบ §7.4 ข้อ 8)

    python -m unittest test_news -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest

from tiandao import config as C
from tiandao import news as NEWS
from tiandao import persist as PS
from tiandao import sim as S
from test_food import places_by_hops, setup_person


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class DeathNewsTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.dead, self.mate, self.killer, self.kin = (setup_person(self.sim, c, self.a) for c in self.sim.cast[:4])
        for c in (self.dead, self.mate, self.killer, self.kin):
            c.rivals, c.clan, c.org, c.parents, c.children, c.spouse = {}, -1, None, [], [], None
        self.dead.spouse, self.mate.spouse = self.mate.cid, self.dead.cid
        self.sim.death_news = []

    def kill(self):
        quiet(self.sim.kill, self.dead, "ทดสอบ", killer=self.killer)

    def deliver_after(self, days):
        self.sim.day += days
        NEWS.tick(self.sim)

    def test_a_distant_spouse_learns_only_when_the_news_arrives(self):
        self.mate.place = self.far
        wait = NEWS.delay_days(self.sim, self.dead, self.mate)
        self.assertGreater(wait, 0)
        self.kill()
        self.assertEqual(self.mate.spouse, self.dead.cid, "ยังไม่รู้ จึงยังไม่เป็นหม้าย")
        self.assertNotIn(self.killer.cid, self.mate.rivals)
        self.deliver_after(wait - 1)
        self.assertEqual(self.mate.spouse, self.dead.cid)
        self.deliver_after(1)
        self.assertIsNone(self.mate.spouse, "ข่าวถึงแล้วเป็นหม้าย แต่งงานใหม่ได้")
        self.assertEqual(self.mate.rivals[self.killer.cid], C.GRUDGE_KIN)

    def test_a_witness_at_the_same_place_knows_at_once(self):
        self.kill()
        self.assertIsNone(self.mate.spouse)
        self.assertEqual(self.mate.rivals[self.killer.cid], C.GRUDGE_KIN)
        self.assertEqual(self.sim.death_news, [])

    def test_a_distant_clansman_bears_a_moderate_grudge_once_the_news_arrives(self):
        self.dead.clan = self.kin.clan = 7
        self.kin.place = self.far
        wait = NEWS.delay_days(self.sim, self.dead, self.kin)
        self.kill()
        self.assertNotIn(self.killer.cid, self.kin.rivals)
        self.deliver_after(wait)
        self.assertEqual(self.kin.rivals[self.killer.cid], C.GRUDGE_NEAR)

    def test_a_spouse_who_kills_is_widowed_at_once_and_bears_no_grudge_against_themselves(self):
        quiet(self.sim.kill, self.dead, "ทดสอบ", killer=self.mate)
        self.assertIsNone(self.mate.spouse)
        self.assertNotIn(self.mate.cid, self.mate.rivals)

    def test_someone_hidden_on_the_spot_hears_only_after_coming_out(self):
        self.kin.hidden, self.kin.seclude_until = True, self.sim.day + 200
        self.dead.parents = [self.kin.cid]
        self.assertEqual(NEWS.delay_days(self.sim, self.dead, self.kin), 200)
        self.kill()
        self.assertNotIn(self.killer.cid, self.kin.rivals)

    def test_news_across_realms_takes_the_cross_realm_delay(self):
        self.mate.world_id = next(w.wid for w in self.sim.worlds if w.wid != self.dead.world_id)
        self.assertEqual(NEWS.delay_days(self.sim, self.dead, self.mate), C.NEWS_CROSS_REALM_DAYS)

    def test_news_to_someone_who_died_first_is_dropped(self):
        self.mate.place = self.far
        # รอนานกว่าที่ข่าวใช้เดินทางจริง — เมื่อระยะทางเป็นของจริง ข่าวในแดนเดียวกันใช้เวลาเกินปีได้
        wait = NEWS.delay_days(self.sim, self.dead, self.mate)
        self.kill()
        quiet(self.sim.kill, self.mate, "ทดสอบ")
        self.deliver_after(max(wait, C.NEWS_CROSS_REALM_DAYS) + 365)
        self.assertEqual(self.sim.death_news, [])
        self.assertGreaterEqual(self.sim.news_stats.get("dropped", 0), 1)

    def test_sending_news_draws_no_random_numbers(self):
        self.mate.place = self.far
        state = self.sim.rng.getstate()
        NEWS.on_death(self.sim, self.dead, self.killer)
        self.assertEqual(self.sim.rng.getstate(), state)

    def test_a_version_30_save_gets_an_empty_news_queue_without_touching_the_rng(self):
        del self.sim.__dict__["death_news"], self.sim.__dict__["news_stats"]
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 30, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertEqual(back.death_news, [])
        self.assertEqual(back.rng.getstate(), state)

    def test_pending_news_survives_a_save_and_arrives_on_time(self):
        self.mate.place = self.far
        wait = NEWS.delay_days(self.sim, self.dead, self.mate)
        self.kill()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "mid.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": PS.SAVE_VERSION, "sim": self.sim}, f)
            back = PS.load_sim(path)
        mate = back.cast[self.mate.cid]
        self.assertEqual(mate.spouse, self.dead.cid)
        back.day += wait
        NEWS.tick(back)
        self.assertIsNone(mate.spouse)


if __name__ == "__main__":
    unittest.main()
