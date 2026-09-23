"""Crisis consequences, calendar pacing, recovery and persistence regressions."""
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tiandao import config as C, crises as X, persist as P, portals as PORT
from tiandao.models import Org
from tiandao.sim import Sim


class CrisisTests(unittest.TestCase):
    def setUp(self):
        self.sim = Sim(seed=42)
        self.sim.crisis_last_tick = 0
        self.human = self.sim.worlds[0]
        for w in self.sim.worlds:
            w.resource = C.REALM_RESOURCE_MAX

    def test_betrayal_costs_resources_and_creates_enemies(self):
        s, w = self.sim, self.human
        members = s.living_in(w.wid)[:2]
        a, b = members
        a.ambition, a.loyalty, a.realm, a.org = 95, 5, 3, 0
        s.orgs = [Org(0, "สำนัก", "ทดสอบ", w.wid, b.cid, 0, members=[a.cid, b.cid])]
        with patch.object(s, "living_in", return_value=[a, b]), patch.object(s.rng, "choice", return_value=a):
            self.assertTrue(X._betray(s, w))
        self.assertEqual(w.resource, C.REALM_RESOURCE_MAX * (1 - C.CRISIS_BETRAYAL_LOSS))
        self.assertIsNone(a.org)
        self.assertNotIn(a.cid, s.orgs[0].members)
        self.assertGreater(b.rivals[a.cid], 0)
        self.assertEqual(w.defense_array, 50)

    def test_warning_waves_and_recovery_persist(self):
        s = self.sim
        s.crisis_pressure = C.CRISIS_PRESSURE_TRIGGER
        s.day = C.CRISIS_TICK_DAYS
        with patch.object(s.rng, "random", return_value=1):
            X.tick(s)
        self.assertEqual(s.chaos_campaign["waves"], 0)
        due = s.chaos_campaign["next_day"]
        s.day += 1
        X.tick(s)
        self.assertEqual(s.chaos_campaign["waves"], 0)
        with tempfile.TemporaryDirectory() as td:
            name = str(Path(td) / "crisis.save")
            P.save_sim(s, name)
            loaded = P.load_sim(name)
        self.assertEqual(loaded.chaos_campaign, s.chaos_campaign)
        for world in (s, loaded):
            for _ in range(C.CRISIS_WAVES):
                world.day = world.chaos_campaign["next_day"]
                X.tick(world)
            self.assertIsNone(world.chaos_campaign)
            world.day += C.CRISIS_TICK_DAYS
            X.tick(world)
            self.assertIsNone(world.chaos_campaign)
        self.assertEqual([e.to_dict() for e in s.log], [e.to_dict() for e in loaded.log])

    def test_breaches_have_real_losses_and_aid_costs(self):
        s, w = self.sim, self.human
        s.chaos_campaign = {"waves": 0, "next_day": C.CRISIS_TICK_DAYS}
        s.day = C.CRISIS_TICK_DAYS
        before = sum(x.resource for x in s.worlds)
        def invade(world, elapsed, rng):
            s.emit(world, "โกลาหลบุกโลกมนุษย์", None, None, [], "ทำลายสำเร็จ", "test", 0, {})
        heaven = w.heaven
        with patch.object(s, "chaos_invade", side_effect=invade):
            X.tick(s)
        self.assertLess(sum(x.resource for x in s.worlds), before)
        self.assertLess(w.heaven, heaven)
        self.assertGreaterEqual(w.resource, 0)
        self.assertEqual(s.chaos_campaign["waves"], 1)

    def test_resource_regen_is_independent_of_tick_size(self):
        a, b = self.sim, pickle.loads(pickle.dumps(self.sim))
        for w in a.worlds + b.worlds:
            w.resource = 100000
        PORT.regen(a, 3650)
        for _ in range(10):
            PORT.regen(b, 365)
        for wa, wb in zip(a.worlds, b.worlds):
            self.assertAlmostEqual(wa.resource, wb.resource, places=6)

    def test_empty_chaos_world_cannot_declare_campaign(self):
        s = self.sim
        s.chaos_wid = None
        s.day = 365
        s.crisis_pressure = 100
        X.tick(s)
        self.assertIsNone(getattr(s, "chaos_campaign", None))

    def test_hidden_chaos_cannot_attack(self):
        s = self.sim
        for c in s.living_in(s.chaos_wid):
            c.hidden = True
        before = len(s.log)
        s.chaos_invade(self.human, 365, s.rng)
        self.assertEqual(len(s.log), before)


if __name__ == "__main__":
    unittest.main()
