import pickle
import unittest

from tiandao.character_art import appearance_for, catalog
from tiandao.models import Character


class CharacterArtTests(unittest.TestCase):
    def test_gender_age_and_dao_guide_appearance_without_mutating_character(self):
        for gender in ['ชาย', 'หญิง']:
            actor = Character(cid=82, name='ผู้ทดสอบ', world_id=0, dao='วิถีดาบ',
                              dao_tags=[], born_day=0, gender=gender)
            before = pickle.dumps(actor)
            by_id = {entry['id']: entry for entry in catalog()}
            young = by_id[appearance_for(actor, 20*365)['id']]
            elder = by_id[appearance_for(actor, 70*365)['id']]
            self.assertEqual(young['gender'], gender)
            self.assertEqual(elder['gender'], gender)
            self.assertEqual(young['age_group'], 'adult')
            self.assertEqual(elder['age_group'], 'elder')
            self.assertIn(young['role'], ('blade', 'spear'))
            self.assertEqual(pickle.dumps(actor), before)

    def test_reload_location_and_activity_do_not_change_identity(self):
        actor = Character(cid=6, name='ผู้ทดสอบ', world_id=0, dao='วิถีพเนจร', dao_tags=[], born_day=0)
        original = appearance_for(actor, 365)
        restored = pickle.loads(pickle.dumps(actor))
        restored.place = 8; restored.current_state = 'Working'; restored.world_id = 2
        self.assertEqual(appearance_for(restored, 366), original)
        self.assertEqual(len(catalog()), 32)
        self.assertEqual(len({entry['id'] for entry in catalog()}), 32)

    def test_a_population_uses_more_than_the_old_eight_looks(self):
        appearances = set()
        for cid in range(256):
            actor = Character(cid=cid, name='ผู้ทดสอบ', world_id=0, dao='วิถีความว่าง',
                              dao_tags=[], born_day=0, gender='หญิง' if cid%2 else 'ชาย')
            appearances.add(appearance_for(actor, (70 if cid%3 == 0 else 20)*365)['id'])
        self.assertGreater(len(appearances), 24)


if __name__ == '__main__':
    unittest.main()
