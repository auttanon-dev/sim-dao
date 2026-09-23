# -*- coding: utf-8 -*-
"""เศรษฐกิจปราณ — ทรัพยากรเดียวของโลก และกฎ "หยุดฝึกไม่ได้"

    python -m unittest test_qi_economy -v

กฎของโลกที่ไฟล์นี้ล็อกไว้
  1. **หินวิญญาณคือปราณอัดก้อน** มูลค่าเท่ากับปริมาณปราณ ไม่มีตารางราคาแยก
     เกรดผูกกับชั้นของแดนที่มันเกิด และเป็นทวีคูณ ไม่ใช่เชิงเส้น
  2. **ปราณสร้างขึ้นมาเองไม่ได้** ทุกหน่วยที่เข้ากระเป๋าใครต้องออกจากคลังฟ้ามาก่อน
     (ข้อนี้คือสิ่งที่จะจับ "เครื่องปั๊มเงิน" แบบ org.monthly_resource = 10000 ได้ในปีแรก
     แทนที่จะรู้ตัวตอนปีที่ 152 ที่คนเดียวถือเงิน 60% ของทั้งโลก)
  3. **หยุดฝึกไม่ได้** ขั้นที่เลี้ยงตัวไม่ไหวจะคลายลงแบบเอกซ์โพเนนเชียลจนหล่น
  4. **จนก็ฝึกได้** ที่ที่ปราณหนาเลี้ยงคนได้โดยไม่ต้องมีเงินสักเหรียญ — ถ้าไม่มีข้อนี้
     การถดถอยจะกลายเป็นหลุมมรณะที่คนจนตกลงไปแล้วไม่มีวันขึ้นมา
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import economy as EC
from tiandao import physics as PHYS
from tiandao import rules as R
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class TestAStoneIsQiInSolidForm(unittest.TestCase):
    def test_value_is_the_qi_it_holds(self):
        for g in range(3):
            self.assertEqual(EC.stone_qi(g), C.STONE_QI_BASE * C.STONE_PER_GRADE ** g)

    def test_a_higher_world_mints_a_stone_worth_a_whole_purse_below(self):
        """ถ้าเป็นเชิงเส้น หินแดนบนก็แค่ 'หินแดนล่างหลายก้อนมัดรวม' ไม่มีเหตุให้ข้ามฟ้า"""
        self.assertGreaterEqual(EC.stone_qi(1) / EC.stone_qi(0), 50.0)

    def test_burning_spends_the_small_change_first(self):
        ch = quiet(S.Sim, seed=1).cast[0]
        ch.stones = {}
        EC.add_stones(ch, 0, 10)
        EC.add_stones(ch, 1, 1)
        got = EC.burn_qi(ch, 5.0)
        self.assertAlmostEqual(got, 5.0, places=6)
        self.assertAlmostEqual(ch.stones[0], 5.0, places=6)
        self.assertAlmostEqual(ch.stones[1], 1.0, places=6)

    def test_burning_never_conjures_what_is_not_there(self):
        ch = quiet(S.Sim, seed=1).cast[0]
        ch.stones = {}
        EC.add_stones(ch, 0, 3)
        self.assertAlmostEqual(EC.burn_qi(ch, 999.0), 3.0, places=6)
        self.assertEqual(EC.purse_qi(ch), 0.0)


class TestWhereYouStandDecidesHowHighYouHold(unittest.TestCase):
    def test_a_rich_place_holds_a_higher_realm_than_a_poor_one(self):
        poor = EC.place_ceiling(120.0)
        fair = EC.place_ceiling(240.0)
        rich = EC.place_ceiling(360.0)
        self.assertLess(poor, fair)
        self.assertLess(fair, rich)

    def test_a_mined_out_valley_cannot_hold_even_the_first_realm(self):
        self.assertLess(EC.place_ceiling(48.0), 1.0,
                        "ที่ที่ถูกขุดจนโทรมต้องบีบให้คนย้ายหรือไหลลง")

    def test_a_higher_world_outclasses_every_ceiling_below(self):
        """เหตุผลเชิงกลไกของการข้ามฟ้า ไม่ใช่แค่ธรรมเนียมของแนวเรื่อง"""
        self.assertGreater(EC.place_ceiling(684.0), EC.place_ceiling(360.0) + 5.0)

    def test_the_exponents_leave_room_between_realms(self):
        """β ต้องน้อยกว่า b ไม่งั้นที่หนึ่งจะเลี้ยงได้ทุกขั้นหรือไม่ได้สักขั้น ไม่มีตรงกลาง"""
        self.assertLess(C.ABSORB_POW, C.UPKEEP_QI_POW)

    def test_upkeep_and_supported_realm_are_the_same_equation(self):
        for r in range(0, 9):
            self.assertAlmostEqual(EC.supported_realm(EC.upkeep_qi(r)), r, places=6)


class TestAPoorCultivatorCanStillTrain(unittest.TestCase):
    def test_absorption_needs_no_money_at_all(self):
        sim = quiet(S.Sim, seed=4)
        w = sim.worlds[0]
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        ch.realm = 1
        ch.money = {}
        ch.stones = {}
        got, drawn = R.sustain(sim, ch, w, 1.0)
        self.assertGreater(got, 0.0, "ปราณฟ้าดินไม่ได้เป็นของใคร คนไม่มีเงินต้องดูดได้")
        self.assertGreater(drawn, 0.0)

    def test_what_he_absorbs_comes_out_of_the_world(self):
        sim = quiet(S.Sim, seed=4)
        w = sim.worlds[0]
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        ch.realm = 2
        before = w.heaven
        _got, drawn = R.sustain(sim, ch, w, 1.0)
        self.assertAlmostEqual(w.heaven, before - drawn, places=6)

    def test_an_empty_world_gives_nothing_and_does_not_go_negative(self):
        sim = quiet(S.Sim, seed=4)
        w = sim.worlds[0]
        w.heaven = 0.0
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        ch.realm = 3
        ch.stones = {}
        got, drawn = R.sustain(sim, ch, w, 1.0)
        self.assertEqual(drawn, 0.0)
        self.assertEqual(got, 0.0)
        self.assertGreaterEqual(w.heaven, 0.0)


class TestYouCannotStopCultivating(unittest.TestCase):
    def a_cultivator(self, realm=5):
        sim = quiet(S.Sim, seed=6)
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        ch.realm = realm
        ch.grip = 1.0
        return sim, ch

    def test_a_starved_realm_loosens_its_grip(self):
        _sim, ch = self.a_cultivator()
        R.hold_realm(ch, 0.0, 365)
        self.assertLess(ch.grip, 1.0)

    def test_a_fed_realm_holds_firm(self):
        _sim, ch = self.a_cultivator()
        ch.grip = 0.4
        R.hold_realm(ch, EC.upkeep_qi(ch.realm) * 3.0, 365)
        self.assertGreater(ch.grip, 0.4, "เลี้ยงไหวแล้วต้องกลับมามั่นคงขึ้น")

    def test_starving_long_enough_actually_costs_him_a_realm(self):
        _sim, ch = self.a_cultivator()
        start = ch.realm
        for _ in range(40):
            R.hold_realm(ch, 0.0, 365)
        self.assertLess(ch.realm, start, "หยุดหาทรัพยากรแล้วต้องถดถอยจริง ไม่ใช่แค่ตัวเลขขยับ")

    def test_falling_resets_the_grip_because_the_lower_realm_is_easier(self):
        _sim, ch = self.a_cultivator(realm=3)
        for _ in range(60):
            R.hold_realm(ch, 0.0, 365)
            if ch.realm < 3:
                break
        self.assertGreater(ch.grip, 0.0)

    def test_how_far_he_overreaches_sets_the_speed_not_the_destination(self):
        """เกินไปหนึ่งขั้นกับสามขั้นจบเหมือนกันคือหล่น ต่างกันที่ความเร็ว ซึ่งอ่านเป็นเรื่องได้"""
        _s1, mild = self.a_cultivator(realm=2)
        _s2, dire = self.a_cultivator(realm=8)
        fed = EC.upkeep_qi(1)
        R.hold_realm(mild, fed, 3650)
        R.hold_realm(dire, fed, 3650)
        self.assertGreater(mild.grip, dire.grip)

    def test_the_half_life_is_a_number_we_can_state(self):
        """ตั้ง λ แล้วต้องพูดเป็นปีได้ ไม่ใช่ตัวเลขวิเศษที่อธิบายไม่ได้"""
        years = PHYS.half_life_days(C.GRIP_LAMBDA) / 365.0
        self.assertGreater(years, 4.0)
        self.assertLess(years, 15.0)


class TestNobodyMakesQiOutOfNothing(unittest.TestCase):
    def test_a_world_run_keeps_its_books(self):
        """ปราณที่เข้ากระเป๋าคนทั้งโลก ต้องไม่เกินที่ถูกดูดออกจากคลังฟ้า"""
        sim = quiet(S.Sim, seed=9)
        quiet(sim.run, 20000)
        taken = sum(getattr(c, "qi_taken", 0.0) for c in sim.cast)
        held = sum(EC.purse_qi(c) for c in sim.cast)
        self.assertGreater(taken, 0.0, "ต้องมีการดูดจริงพอจะวัดได้")
        # ของในกระเป๋าเป็นเศษที่เหลือจากที่ดูดมา (ส่วนใหญ่ถูกเผาไปกับค่าบำรุงแล้ว)
        # บวกของที่ตกค้างจากซากแดนลับซึ่งถูกขุดไปตั้งแต่รุ่นก่อน จึงหลวมไว้หนึ่งเท่าตัว
        self.assertLess(held, taken * 2.0 + 500.0,
                        "ปราณในกระเป๋าคนทั้งโลกงอกเกินที่โลกจ่ายไป = มีเครื่องปั๊มอยู่ที่ไหนสักแห่ง")

    def test_the_world_pool_never_goes_negative(self):
        sim = quiet(S.Sim, seed=9)
        quiet(sim.run, 20000)
        for w in sim.worlds:
            self.assertGreaterEqual(w.heaven, 0.0, f"{w.name} ติดลบ")


class TestAnEraCollapseDoesNotConjureQi(unittest.TestCase):
    """เดิม check_world เขียน `world.heaven = world.cap() * 0.7` ตอนยุคล่ม = เสกปราณ
    49,000 หน่วยจากอากาศทุกครั้ง เป็นบั๊กคลาสเดียวกับ org.monthly_resource = 10000
    เจอด้วยการรันยาวแล้วเห็นคลังฟ้าเด้ง 13% -> 65% โดยไม่มีเหตุการณ์ไหนอธิบายได้
    """

    def test_a_collapse_never_leaves_the_world_richer_than_what_died_gave_back(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 3000)
        w = sim.worlds[0]
        w.heaven = w.cap() * 0.02
        bound = sum(getattr(c, "drawn", 0.0) for c in sim.living_in(w.wid))
        before = w.heaven
        quiet(R.check_world, sim, w, sim.rng)
        gained = w.heaven - before
        self.assertLessEqual(gained, bound + 1e-6,
                             "โลกฟื้นเกินปราณที่คนตายและคนถูกกดขั้นคืนมาได้ = มีการเสกพลัง")

    def test_a_dying_world_stays_poor_when_nobody_had_drawn_anything(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 3000)
        w = sim.worlds[0]
        for c in sim.living_in(w.wid):
            c.drawn = 0.0
        w.heaven = w.cap() * 0.02
        quiet(R.check_world, sim, w, sim.rng)
        self.assertLess(w.ratio(), 0.2,
                        "ยุคเสื่อมต้องยาวต่อไปถ้าไม่มีปราณจากใครให้คืน")

    def test_being_pushed_down_a_realm_gives_the_qi_back(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 3000)
        w = sim.worlds[0]
        ch = next((c for c in sim.living_in(w.wid) if c.realm >= 2), None)
        if ch is None:
            self.skipTest("รันสั้นเกินกว่าจะมีคนขั้นสูงพอ")
        ch.drawn = 100.0
        before_pool, before_realm = w.heaven, ch.realm
        w.heaven = w.cap() * 0.02
        quiet(R.check_world, sim, w, sim.rng)
        if ch.alive and ch.realm < before_realm:
            self.assertLess(ch.drawn, 100.0, "ปราณที่ผูกกับขั้นที่เสียไปต้องคืนสู่ฟ้า")


class TestSectsEarnWhatTheyHold(unittest.TestCase):
    def test_disciples_without_land_produce_nothing(self):
        self.assertEqual(EC.sect_output(500, 0.0), 0.0,
                         "ศิษย์พันคนบนแผ่นดินที่ปราณแห้งต้องได้ศูนย์")

    def test_land_without_disciples_produces_nothing(self):
        self.assertEqual(EC.sect_output(0, 9999.0), 0.0)

    def test_doubling_disciples_does_not_double_output(self):
        one = EC.sect_output(50, 500.0)
        two = EC.sect_output(100, 500.0)
        self.assertGreater(two, one)
        self.assertLess(two, one * 2.0, "ผลตอบแทนต้องลดน้อยถอยลง ไม่งั้นสำนักใหญ่โตไม่หยุด")

    def test_doubling_both_doubles_output(self):
        """ผลตอบแทนต่อขนาดคงที่ — กันสำนักที่ชนะสงครามครั้งเดียวแล้วโตพรวด"""
        one = EC.sect_output(50, 500.0)
        both = EC.sect_output(100, 1000.0)
        self.assertAlmostEqual(both / one, 2.0, places=6)


class TestPricesSeeWhatIsRunningOut(unittest.TestCase):
    def test_a_scarce_reserve_costs_more_than_a_full_one(self):
        self.assertGreater(PHYS.hotelling_price(10.0, 0.1, C.HOTELLING_ELASTICITY),
                           PHYS.hotelling_price(10.0, 1.0, C.HOTELLING_ELASTICITY))

    def test_it_is_bounded_on_both_sides(self):
        for frac in (1e-9, 0.001, 0.5, 1.0, 5.0):
            p = PHYS.hotelling_price(10.0, frac, C.HOTELLING_ELASTICITY,
                                     C.HOTELLING_LO, C.HOTELLING_HI)
            self.assertGreaterEqual(p, 10.0 * C.HOTELLING_LO)
            self.assertLessEqual(p, 10.0 * C.HOTELLING_HI)


class TestTheHarvestedPoolBehavesLikeAFishery(unittest.TestCase):
    def test_taking_more_than_the_sustainable_yield_drains_it(self):
        cap, rate = 1000.0, 0.001
        msy = PHYS.max_sustainable_yield(rate, cap)
        # เหนือ rK/4 ไม่มีจุดสมดุลเหลืออยู่เลย คลังจึงไหลลงศูนย์เสมอ ไม่ว่าจะเริ่มจากเต็มแค่ไหน
        # (ใช้ขอบฟ้ายาว เพราะขาลงช่วงแรกช้า — ซึ่งเองก็เป็นเหตุผลที่โลกจริงมองไม่เห็นว่ากำลังพัง)
        over = PHYS.harvest_step(cap * 0.9, cap, rate, msy * 1.6, 0.0, 40000)
        self.assertEqual(over, 0.0, "เก็บเกินผลผลิตยั่งยืนแล้วต้องไหลลงศูนย์")

    def test_taking_less_than_it_settles_instead_of_dying(self):
        cap, rate = 1000.0, 0.001
        msy = PHYS.max_sustainable_yield(rate, cap)
        held = PHYS.harvest_step(cap * 0.9, cap, rate, msy * 0.5, 0.0, 3650)
        self.assertGreater(held, cap * 0.3)

    def test_a_dead_pool_never_returns_without_a_seed(self):
        """คุณสมบัติของสมการ ไม่ใช่บั๊ก — และเป็นเหตุผลที่ปุถุชนต้องเติมพลังให้โลก"""
        dead = PHYS.harvest_step(0.0, 1000.0, 0.01, 0.0, 0.0, 36500)
        self.assertEqual(dead, 0.0)
        alive = PHYS.harvest_step(0.0, 1000.0, 0.01, 0.0, 0.05, 36500)
        self.assertGreater(alive, 0.0, "เมล็ดจากปุถุชนคือสิ่งที่ทำให้ศูนย์ไม่ใช่กับดักถาวร")


if __name__ == "__main__":
    unittest.main()
