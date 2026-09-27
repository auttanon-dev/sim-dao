# -*- coding: utf-8 -*-
"""ความตายเป็นธุรกรรมเดียว การปะทะตัดสินที่เดียว และร่างกายเป็นด่านของเจตนา (แบบ §7.4, §10)

    python -m unittest test_death_and_succession -v
"""
import contextlib
import io
import unittest
from unittest import mock

from tiandao import body as BODY
from tiandao import combat
from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import sim as S
from tiandao import wages as WAGES
from tiandao.models import Item, Org


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class World(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.people = [c for c in self.sim.cast if c.alive and c.sentient and c.age(self.sim.day) >= 20
                       and c.world_id == 0][:10]
        for c in self.people:
            c.spouse, c.children, c.money, c.items, c.org, c.rivals = None, [], {}, [], None, {}
        self.tiers = {w.tier for w in self.sim.worlds}

    def gold(self):
        return {t: WAGES.total_gold(self.sim, t) for t in self.tiers}

    def die(self, ch, killer=None):
        quiet(self.sim.kill, ch, "ทดสอบ", killer=killer, natural=killer is None)


class InheritanceTests(World):
    def test_the_spouse_inherits_everything(self):
        dead, spouse, child = self.people[:3]
        dead.spouse, dead.children, dead.money = spouse.cid, [child.cid], {0: 90.0}
        before = self.gold()
        self.die(dead)
        self.assertAlmostEqual(spouse.money.get(0, 0), 90.0)
        self.assertEqual(child.money.get(0, 0), 0)
        for t, v in self.gold().items():
            self.assertAlmostEqual(v, before[t], places=6, msg="ทองรวมไม่เปลี่ยน")

    def test_without_a_spouse_adult_children_share_and_minors_do_not(self):
        dead, a, b, kid = self.people[:4]
        kid.born_day = self.sim.day - 5 * 365
        dead.children, dead.money = [a.cid, b.cid, kid.cid], {0: 90.0}
        self.die(dead)
        self.assertAlmostEqual(a.money.get(0, 0), 45.0)
        self.assertAlmostEqual(b.money.get(0, 0), 45.0)
        self.assertEqual(kid.money.get(0, 0), 0)

    def test_no_heirs_goes_to_the_sect_then_stays_unclaimed(self):
        dead, loner = self.people[:2]
        org = Org(oid=len(self.sim.orgs), kind="สำนัก", name="สำนักทดสอบ", world_id=0, founder=self.people[5].cid,
                  founded_day=0, members=[dead.cid])
        self.sim.orgs.append(org)
        dead.org, dead.money, loner.money = org.oid, {0: 40.0}, {0: 30.0}
        before = self.gold()
        self.die(dead)
        self.die(loner)
        self.assertAlmostEqual(org.treasury_gold.get(0, 0), 40.0)
        self.assertAlmostEqual(loner.money.get(0, 0), 30.0, msg="ไม่มีใครรับ ค้างอยู่กับศพ")
        for t, v in self.gold().items():
            self.assertAlmostEqual(v, before[t], places=6)

    def test_regular_items_go_to_heirs_but_a_killer_takes_them(self):
        dead, spouse, killer, dead2, spouse2 = self.people[:5]
        for d, s in ((dead, spouse), (dead2, spouse2)):
            d.spouse = s.cid
            it = Item(iid=self.sim.nid("i"), kind="อาวุธ", tier=0, grade=1.0)
            self.sim.items[it.iid] = it
            d.items, d.money = [it.iid], {0: 10.0}
        self.die(dead)
        self.assertEqual(len(spouse.items), 1)
        self.die(dead2, killer=killer)
        self.assertEqual(len(killer.items), 1, "ผู้ฆ่าริบของ")
        self.assertAlmostEqual(spouse2.money.get(0, 0), 10.0, msg="แต่ทองยังตกถึงทายาท")


class SuccessionAndCleanupTests(World):
    def test_a_sect_and_its_hall_get_new_heads_at_once(self):
        head, core, inner, alch = self.people[:4]
        alch.alch_rank, inner.alch_rank = 3, 1
        org = Org(oid=len(self.sim.orgs), kind="สำนัก", name="สำนักทดสอบ", world_id=0, founder=head.cid,
                  founded_day=0, members=[head.cid, core.cid, inner.cid, alch.cid],
                  core_disciples=[core.cid], inner_disciples=[inner.cid])
        org.facilities["หอโอสถ"] = head.cid
        self.sim.orgs.append(org)
        self.die(head)
        self.assertEqual(self.sim.org_head(org), core.cid, "ศิษย์สายแกนรับช่วงก่อน")
        self.assertEqual(org.facilities["หอโอสถ"], alch.cid, "ฝีมือปรุงยาสูงสุด")
        self.assertEqual(org.founder, head.cid, "ผู้ก่อตั้งยังเป็นประวัติเดิม")

    def test_a_sect_whose_last_member_dies_is_dissolved(self):
        last = self.people[0]
        org = Org(oid=len(self.sim.orgs), kind="สำนัก", name="สำนักสุดท้าย", world_id=0, founder=last.cid,
                  founded_day=0, members=[last.cid])
        self.sim.orgs.append(org)
        self.die(last)
        self.assertFalse(org.alive)

    def test_a_same_sect_killer_usurps_the_sect_master(self):
        master, traitor, elder = self.people[:3]
        for c, role in ((master, "เจ้าสำนัก"), (traitor, "ศิษย์ในสำนัก"), (elder, "ศิษย์ในสำนัก")):
            c.sect_name, c.sect_role = "สำนักทดสอบ", role
        elder.realm = traitor.realm + 3
        self.die(master, killer=traitor)
        self.assertEqual(traitor.sect_role, "เจ้าสำนัก")
        self.assertEqual(elder.sect_role, "ศิษย์ในสำนัก")

    def test_without_a_usurper_the_strongest_in_the_sect_becomes_master(self):
        master, weak, strong, outsider = self.people[:4]
        for c, role in ((master, "เจ้าสำนัก"), (weak, "ศิษย์ในสำนัก"), (strong, "ศิษย์ในสำนัก")):
            c.sect_name, c.sect_role = "สำนักทดสอบ", role
        strong.realm = weak.realm + 3
        self.die(master, killer=outsider)
        self.assertEqual(strong.sect_role, "เจ้าสำนัก")
        self.assertEqual(weak.sect_role, "ศิษย์ในสำนัก")

    def test_a_city_gets_a_new_ruler(self):
        ruler, weak, strong = self.people[:3]
        city = {"id": 999, "name": "เมืองทดสอบ", "ruler_cid": ruler.cid}
        for c in (ruler, weak, strong):
            c.city_id = 999
        strong.realm = weak.realm + 2
        with mock.patch.object(self.sim, "cities", [city]):   # เมืองอยู่ในเซฟของโลก (Sim.cities)
            self.die(ruler)
        self.assertEqual(city["ruler_cid"], strong.cid)

    def test_grudges_against_the_dead_are_dropped_at_once(self):
        dead, holder = self.people[:2]
        holder.rivals = {dead.cid: 5}
        self.die(dead)
        self.assertNotIn(dead.cid, holder.rivals)


class OldSaveTests(World):
    def test_a_version_11_save_gets_heads_for_sects_whose_leader_already_died(self):
        import os, pickle, tempfile
        from tiandao import persist as PS
        head, core = self.people[:2]
        org = Org(oid=len(self.sim.orgs), kind="สำนัก", name="สำนักเก่า", world_id=0, founder=head.cid,
                  founded_day=0, members=[head.cid, core.cid], core_disciples=[core.cid])
        self.sim.orgs.append(org)
        head.alive = False                                   # ตายไปก่อนมีการสืบทอด
        self.sim.alive_cids.discard(head.cid)
        self.sim._alive_ver = getattr(self.sim, "_alive_ver", 0) + 1
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 11, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertEqual(back.org_head(back.orgs[org.oid]), core.cid)
        self.assertTrue(back.orgs[org.oid].alive, "ยังมีสมาชิกเหลือ ไม่สลาย")
        self.assertEqual(back.rng.getstate(), state, "ย้ายข้อมูลไม่แตะ RNG")

class BodyGateTests(World):
    def weights(self, ch):
        return IN.weigh(ch, self.sim, E.EVENT_TABLE, True)

    def test_someone_who_cannot_fight_does_not_pick_fights_but_can_still_travel(self):
        ch = self.people[0]
        with mock.patch.object(BODY, "can_fight", return_value=False):
            w = self.weights(ch)
        self.assertFalse(IN.COMBAT_KINDS & set(w))
        self.assertTrue(w, "ยังเหลือสิ่งที่ทำได้")

    def test_someone_who_cannot_stand_or_is_unconscious_does_nothing_physical(self):
        ch = self.people[0]
        for gate in ("can_stand", "conscious"):
            with mock.patch.object(BODY, gate, return_value=False):
                w = self.weights(ch)
            self.assertFalse(IN.PHYSICAL_KINDS & set(w), gate)


class OneCombatResolverTests(World):
    def pair(self):
        strong, weak = self.people[:2]
        strong.realm, weak.realm, weak.fate = weak.realm + 8, 0, 0
        return strong, weak

    def test_a_friendly_bout_injures_and_plunders_but_never_kills(self):
        strong, weak = self.pair()
        it = Item(iid=self.sim.nid("i"), kind="อาวุธ", tier=0, grade=1.0)
        self.sim.items[it.iid] = it
        weak.items = [it.iid]
        win, lose, _log, escaped = quiet(combat.resolve_combat, strong, weak, self.sim.world(0), self.sim)
        self.assertIs(lose, weak)
        self.assertTrue(weak.alive)
        self.assertIn(it.iid, strong.items)
        self.assertGreater(weak.decay, 0, "ผลต่อร่างมาจากที่เดียวกับการปะทะอื่น")

    def test_a_lethal_clash_can_kill_through_the_same_path(self):
        strong, weak = self.pair()
        quiet(combat.resolve_combat, strong, weak, self.sim.world(0), self.sim, lethal=True)
        self.assertFalse(weak.alive)


if __name__ == "__main__":
    unittest.main()
