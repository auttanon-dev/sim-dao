import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch, Mock

from narrative_factory.serial import Library, SerialRunner, ProcessLease
from narrative_factory.writer import SceneWriter
from narrative_factory.writer_backend import WriterBackend


class SerialTests(unittest.TestCase):
    def library(self, folder):
        with patch('narrative_factory.serial.PS.load_sim', return_value=NS(log=[])):
            return Library(folder, str(Path(folder)/'world.save'))

    def test_chapters_survive_restart_and_duplicate_scene_is_not_appended(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=self.library(folder)
            chapter={'scene_id':'0-15','cid':1,'anchor_seq':15,'prose':'ตอนที่เขียนแล้ว'}
            self.assertTrue(lib.append(chapter))
            self.assertFalse(lib.append(chapter))
            restored=self.library(folder)
            self.assertEqual(restored.chapters()[0]['prose'],chapter['prose'])
            self.assertEqual(len(restored.chapters()),1)
            Path(folder,'chapter-000002.json.tmp').write_text('partial')
            self.assertEqual(len(restored.chapters()),1)

    def test_next_chapter_uses_new_scene_and_preserves_protagonist(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=SerialRunner(); runner.library=self.library(folder)
            runner.library.book['cid']=1
            runner.library.append({'scene_id':'0-15','cid':1,'anchor_seq':15,'prose':'เดิม'})
            old=NS(scene_id='0-15',events=[NS(seq=15)])
            new=NS(scene_id='0-19',events=[NS(seq=19)])
            world=NS(sim=NS(seq=19),scenes_of=lambda cid:[new,old])
            self.assertEqual(runner._next(world).scene_id,'0-19')
            self.assertEqual(runner.library.book['cid'],1)
            world.sim.seq=10
            with self.assertRaises(RuntimeError): runner._next(world)

    def test_same_world_cannot_have_two_serial_writers(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'world.save')
            first=ProcessLease(path)
            try:
                with self.assertRaises(RuntimeError): ProcessLease(path)
            finally: first.close()
            second=ProcessLease(path); second.close()

    def test_stop_prevents_another_model_call(self):
        writer=SceneWriter(agent=object(),should_stop=lambda:True)
        with self.assertRaises(InterruptedError):
            writer._prose('system','prompt',NS(calls=0),500)

    def test_consumed_events_with_a_different_scene_id_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=SerialRunner(); runner.library=self.library(folder)
            runner.library.book['cid']=1
            runner.library.append({'scene_id':'0-15','cid':1,'anchor_seq':20,'prose':'เดิม'})
            overlap=NS(scene_id='0-18',events=[NS(seq=18),NS(seq=20)])
            world=NS(sim=NS(seq=20,cast={1:NS(alive=True)}),scenes_of=lambda cid:[overlap])
            self.assertIsNone(runner._next(world))

    def test_missing_model_does_not_advance_world_or_write(self):
        runner=SerialRunner(); runner._lease=Mock()
        def stop(_): runner._stop.set(); return True
        with patch.object(WriterBackend,'readiness',return_value=(False,'รอ LM Studio')), \
             patch.object(runner,'_grow_world') as grow, \
             patch('narrative_factory.serial.NaturalSceneWriter') as writer, \
             patch.object(runner._stop,'wait',side_effect=stop):
            runner._run()
        grow.assert_not_called(); writer.assert_not_called()
        runner._lease.close.assert_called_once()

    def test_lmstudio_chapter_is_saved_with_model_and_resumes_at_next_event(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=SerialRunner(); runner.library=self.library(folder); runner._lease=Mock()
            runner.backend=WriterBackend('lmstudio','http://localhost:1234/v1','gemma','gemma')
            runner.library.book.update(cid=1,name='ตัวเอก')
            runner.library.append({'scene_id':'0-10','cid':1,'anchor_seq':10,'prose':'ท้ายตอนเดิม'})
            scene=NS(scene_id='0-20',events=[NS(seq=10,day=1),NS(seq=20,day=2)],day_end=2)
            pkg=NS(scene_type_th='การพบพาน',place_name='โรงเตี๊ยม')
            script=NS(used_llm=True,issues=[],beats=[],prose='นิยายตอนใหม่')
            def stop(_): runner._stop.set(); return True
            with patch.object(WriterBackend,'readiness',return_value=(True,'')), \
                 patch('narrative_factory.serial.studio.WorldCache'), \
                 patch.object(runner,'_next',return_value=scene), \
                 patch('narrative_factory.serial.studio._package_for',return_value=pkg), \
                 patch('narrative_factory.serial.NaturalSceneWriter') as writer, \
                 patch.object(runner._stop,'wait',side_effect=stop):
                writer.return_value.write.return_value=script
                runner._run()
            chapter=self.library(folder).chapters()[-1]
            self.assertEqual(chapter['event_seqs'],[20])
            self.assertEqual(chapter['provider'],'lmstudio')
            self.assertEqual(chapter['model'],'gemma')
            self.assertEqual(pkg.previous_chapter,'ท้ายตอนเดิม')
            self.assertEqual(writer.call_args.kwargs['prose_model'],'gemma')
            self.assertEqual(writer.call_args.kwargs['structure_model'],'gemma')

    def test_failed_draft_does_not_become_a_chapter_or_consume_the_scene(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=SerialRunner(); runner.library=self.library(folder); runner._lease=Mock()
            runner.library.book.update(cid=1,name='ตัวเอก')
            event=NS(seq=30,day=10)
            scene=NS(scene_id='0-30',events=[event],day_end=10)
            pkg=NS(scene_type_th='การพบพาน',place_name='โรงเตี๊ยม')
            script=NS(used_llm=True,issues=['บทสั้นเกินไป'],beats=[],prose='ร่างยังไม่ผ่าน')
            def stop_after_retry(_): runner._stop.set(); return True
            with patch('narrative_factory.serial.WriterBackend.readiness',return_value=(True,'')), \
                 patch('narrative_factory.serial.studio.WorldCache'), \
                 patch.object(runner,'_next',return_value=scene), \
                 patch('narrative_factory.serial.studio._package_for',return_value=pkg), \
                 patch('narrative_factory.serial.NaturalSceneWriter') as writer, \
                 patch.object(runner._stop,'wait',side_effect=stop_after_retry):
                writer.return_value.write.return_value=script
                runner._run()
            self.assertEqual(runner.library.chapters(),[])
            self.assertEqual(json.loads(Path(folder,'draft.json').read_text(encoding='utf-8'))['scene_id'],'0-30')
            runner._lease.close.assert_called_once()


if __name__=='__main__': unittest.main()
