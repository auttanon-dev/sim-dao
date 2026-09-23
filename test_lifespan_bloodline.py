"""อายุขัย พรสายเลือดคงที่ และแรงกดดันพลังฟ้าดิน."""
import pickle
import unittest

from tiandao import config as C
from tiandao import rules as R
from tiandao.models import Character
from tiandao.sim import Sim


def person(cid=0, natural=50):
    return Character(cid=cid, name=f"คน{cid}", world_id=0, dao="วิถีดาบ",
                     dao_tags=["วิถีดาบ"], born_day=0,
                     natural_lifespan=natural, blood={"human": 1.0})


class LifespanBloodlineTests(unittest.TestCase):
    def test_lifespan_accumulates_minor_and_major_realms(self):
        ch = person(natural=47)
        self.assertEqual(ch.lifespan(), 47)
        ch.realm = 1
        self.assertEqual(ch.lifespan(), 147)
        ch.tier, ch.realm = 1, 0
        self.assertEqual(ch.lifespan(), 47 + C.REALM_CAP * 100 + 300)
        ch.tier, ch.realm = 2, C.REALM_CAP
        self.assertEqual(ch.lifespan(), 20000)
        ch.longevity_bonus = 500
        self.assertEqual(ch.lifespan(), 20000)

    def test_grant_uses_birth_concentration_and_stays_fixed(self):
        sim = Sim(seed=71)
        apex, direct, distant = sim.living_in(0)[:3]
        apex.tier, apex.realm = 2, C.REALM_CAP
        apex.blood = {"human": 1.0}
        apex.bloodline_blessings = {"human": 0.2}
        direct.blood, direct.bloodline_affinity = {"human": 1.0}, {"human": 1.0}
        distant.blood, distant.bloodline_affinity = {"human": 0.1}, {"human": 1.0}
        direct.bloodline_grants = {}
        distant.bloodline_grants = {}
        sim.update_apex_blessing(apex)
        self.assertAlmostEqual(direct.bloodline_buff, 0.2)
        self.assertAlmostEqual(distant.bloodline_buff, 0.02)
        distant.blood["human"] = 0.01
        sim.apply_bloodline_buff(distant)
        self.assertAlmostEqual(distant.bloodline_buff, 0.02)
        restored = pickle.loads(pickle.dumps(sim))
        self.assertAlmostEqual(restored.cast[distant.cid].bloodline_buff, 0.02)

    def test_receivers_roll_different_fixed_affinities(self):
        sim = Sim(seed=711)
        rolls = [c.bloodline_affinity.get("human") for c in sim.living_in(0)
                 if "human" in c.bloodline_affinity]
        self.assertGreater(len(set(rolls)), 1)
        before = dict(sim.cast[0].bloodline_affinity)
        for _ in range(3):
            sim.apply_bloodline_buff(sim.cast[0])
        self.assertEqual(sim.cast[0].bloodline_affinity, before)

    def test_one_apex_dies_other_apex_keeps_own_grant(self):
        sim = Sim(seed=72)
        first, second, heir = sim.living_in(0)[:3]
        for apex, strength in ((first, 0.2), (second, 0.08)):
            apex.tier, apex.realm = 2, C.REALM_CAP
            apex.blood = {"human": 1.0}
            apex.bloodline_blessings = {"human": strength}
            sim.update_apex_blessing(apex)
        heir.blood = {"human": 1.0}
        heir.bloodline_affinity = {"human": 1.0}
        heir.bloodline_grants = {}
        sim.apply_bloodline_buff(heir)
        self.assertAlmostEqual(heir.bloodline_buff, 0.2)
        sim.kill(first, "ทดสอบ")
        self.assertAlmostEqual(heir.bloodline_buff, 0.08)
        sim.kill(second, "ทดสอบ")
        self.assertEqual(heir.bloodline_buff, 0.0)

    def test_low_heaven_makes_same_breakthrough_harder(self):
        class FixedRng:
            @staticmethod
            def random():
                return 0.4

        sim = Sim(seed=73)
        world = sim.worlds[0]
        req = R.need(person(), world)
        high = person()
        high.insight, high.inner_none = req, True
        world.heaven = world.cap()
        self.assertEqual(R.attempt_break(sim, high, world, FixedRng())[0], "ผ่าน")

        low = person()
        low.insight, low.inner_none = req, True
        world.heaven = world.cap() * 0.1
        self.assertEqual(R.attempt_break(sim, low, world, FixedRng())[0], "ล้มเหลว")

    def test_longevity_pill_is_consumed_once_and_extends_life(self):
        sim = Sim(seed=74)
        ch = sim.living_in(0)[0]
        sim.day = 101 * 365
        ch.born_day = 0
        ch.natural_lifespan = 100
        ch.realm = ch.tier = 0
        ch.longevity_bonus = 0
        pill = sim.make_item("ยาวิเศษ", 0, 1)
        pill.lifespan_bonus = 20
        ch.items = [pill.iid]
        R.age_and_decay(sim, ch, sim.worlds[0], 0, sim.rng)
        self.assertTrue(ch.alive)
        self.assertEqual(ch.longevity_bonus, 20)
        self.assertNotIn(pill.iid, ch.items)


if __name__ == "__main__":
    unittest.main()
