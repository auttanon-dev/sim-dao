import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from narrative_factory.serial import Library
from narrative_factory.writer import SceneWriter
from narrative_factory.writer_backend import WriterBackend
from test_writer import FakeAgent, pick_scene
from narrative_factory import writer as W


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            sim, cfg, parsed, scene, ctx, by_cid = pick_scene()
        cls.pkg = W.build_package(scene, sim, ctx, by_cid.get(scene.focal_cid, []), config=cfg)

    def library(self, folder):
        with patch('narrative_factory.serial.PS.load_sim', return_value=NS(log=[])):
            return Library(folder, str(Path(folder)/'world.save'))

    def test_restart_keeps_completed_passes_and_writes_only_remaining_beats(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=self.library(folder); key=lib.checkpoint_key(self.pkg,WriterBackend())
            agent=FakeAgent()
            with self.assertRaises(InterruptedError):
                SceneWriter(agent=agent,should_stop=lambda:agent.prose_calls>=2,
                            checkpoint=lambda s:lib.save_checkpoint(key,s)).write(self.pkg)
            restored=self.library(folder).load_checkpoint(key)
            self.assertTrue(restored.outline_done)
            self.assertEqual(sum(bool(b.prose) for b in restored.beats),2)
            preserved=[b.prose for b in restored.beats[:2]]
            fresh_agent=FakeAgent()
            result=SceneWriter(agent=fresh_agent,resume=restored).write(self.pkg)
            self.assertEqual([b.prose for b in result.beats[:2]],preserved)
            self.assertEqual(fresh_agent.prose_calls,3)
            self.assertFalse(any(kind=='json' for kind, *_ in fresh_agent.prompts))
            self.assertTrue(result.passed)
            lib.save_checkpoint(key,result)
            idle_agent=FakeAgent()
            SceneWriter(agent=idle_agent,resume=lib.load_checkpoint(key)).write(self.pkg)
            self.assertEqual(idle_agent.prompts,[])

    def test_restart_repairs_only_the_failed_beat(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=self.library(folder); key=lib.checkpoint_key(self.pkg,WriterBackend())
            draft=SceneWriter(agent=FakeAgent(broken_stage='Peak'),repair_rounds=0,
                              checkpoint=lambda s:lib.save_checkpoint(key,s)).write(self.pkg)
            self.assertFalse(draft.passed)
            agent=FakeAgent()
            result=SceneWriter(agent=agent,resume=lib.load_checkpoint(key)).write(self.pkg)
            self.assertTrue(result.passed)
            self.assertEqual(agent.prose_calls,1)
            self.assertFalse(any(kind=='json' for kind, *_ in agent.prompts))
            for before,after in zip(draft.beats,result.beats):
                if before.stage!='Peak': self.assertEqual(before.prose,after.prose)

    def test_changed_model_or_context_does_not_reuse_old_work(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=self.library(folder); key=lib.checkpoint_key(self.pkg,WriterBackend())
            draft=SceneWriter(agent=None).write(self.pkg)
            lib.save_checkpoint(key,draft)
            other=lib.checkpoint_key(self.pkg,WriterBackend(prose_model='other-model'))
            self.assertIsNone(lib.load_checkpoint(other))
            self.assertNotEqual(key,other)
            self.assertIsNotNone(lib.load_checkpoint(key))

    def test_corrupt_checkpoint_is_reported_and_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=self.library(folder)
            path=Path(folder)/'work-in-progress.json'; path.write_text('{broken',encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'work-in-progress'):
                lib.load_checkpoint('key')
            self.assertEqual(path.read_text(encoding='utf-8'),'{broken')


if __name__=='__main__': unittest.main()
