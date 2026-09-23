"""Regression checks for autonomous execution and full death bookkeeping."""
import collections
import contextlib
import heapq
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tiandao import config as C, metrics as M, persist as PS, worldloop as WL
from tiandao.sim import Sim
from tiandao.models import Org


class AutonomyTests(unittest.TestCase):
    def test_lord_defeat_does_not_duplicate_turn(self):
        sim = Sim(seed=7)
        lord = sim.cast[sim.lord_cid]
        for _ in range(3):
            lord.hidden = False
            sim.kill(lord, "audit")
            self.assertEqual(sum(cid == lord.cid for _, cid in sim.queue), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            sim.run(3000)
        counts = collections.Counter(cid for _, cid in sim.queue if sim.cast[cid].alive)
        self.assertEqual(set(counts), sim.alive_cids)
        self.assertTrue(all(n == 1 for n in counts.values()))

    def test_old_save_duplicate_turns_are_repaired(self):
        sim = Sim(seed=7)
        lord = sim.cast[sim.lord_cid]
        heapq.heappush(sim.queue, (999999, lord.cid))
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "audit.save")
            PS.save_sim(sim, path)
            loaded = PS.load_sim(path)
        self.assertEqual(sum(cid == lord.cid for _, cid in loaded.queue), 1)

    def test_war_death_runs_bookkeeping(self):
        sim = Sim(seed=7)
        a, b = sim.living_in(0)[:2]
        a.org, b.org, b.fate = 0, 1, 0
        a.realm, b.realm = 9, 0
        b.skills = []  # No cycle rebirth in this casualty assertion.
        sim.orgs = [Org(0, "sect", "A", 0, a.cid, 0, members=[a.cid]),
                    Org(1, "sect", "B", 0, b.cid, 0, members=[b.cid])]
        sim.recount_worlds()
        before = sim.world(0).n_alive
        living_before = {c.cid for c in sim.living_in(0)}
        rng = Mock()
        rng.random.return_value = 0.0
        sim.resolve({"kind": "สงครามสำนัก"}, a, b, sim.world(0), 1, rng)
        self.assertFalse(b.alive)
        self.assertEqual(b.death_cause, "สงครามสำนัก")
        self.assertNotIn(b.cid, sim.alive_cids)
        # ฝ่ายชนะก็เสียคนได้ด้วยตั้งแต่ใช้กฎกำลังสองของแลนเชสเตอร์ (ดู physics.lanchester)
        # เทสนี้บังคับ rng.random() = 0.0 ทุกครั้ง ซึ่งทำให้ "ทอยแล้วตาย" เป็นจริงเสมอแม้อัตรา
        # จะน้อยนิด — สิ่งที่เทสนี้ล็อกไว้คือ **บัญชีคนเป็นตรงกับคนที่ตายจริง** ไม่ใช่ว่าต้องตาย
        # พอดีหนึ่งคน (ของเดิมสมมติไว้อย่างนั้นเพราะฝ่ายชนะไม่เคยเสียใครเลย)
        dead = len(living_before - {c.cid for c in sim.living_in(0)})
        self.assertGreaterEqual(dead, 1)
        self.assertEqual(sim.world(0).n_alive, before - dead)

    def test_metrics_only_count_current_round(self):
        sim = Sim(seed=7)
        sim.world(0).era = 8
        sim.orgs = [SimpleNamespace()] * 10
        baseline = M.checkpoint(sim)
        metrics = M.summarize(sim, 100, baseline)
        self.assertEqual(metrics["era_rate"], 0)
        self.assertEqual(metrics["org_rate"], 0)
        sim.orgs.append(SimpleNamespace())
        self.assertEqual(M.summarize(sim, 100000, baseline)["org_rate"], 1)

    def test_metrics_ignore_dead_history(self):
        sim = Sim(seed=7)
        for living in sim.living():
            living.realm = living.peak_realm = 0
        dead = sim.living()[1]
        dead.alive = False
        sim.alive_cids.discard(dead.cid)
        sim._alive_ver += 1
        dead.peak_realm = 9
        self.assertEqual(M.summarize(sim, 1)["advancement_rate"], 0.0)

    def test_exhausted_round_reports_actual_work(self):
        sim = Sim(seed=7)
        with tempfile.TemporaryDirectory() as td, patch.object(sim, "step", side_effect=[object(), None]):
            cfg = WL.LoopConfig(save_path=str(Path(td) / "nested" / "audit.save"),
                                chunk_events=10, autotune=False)
            with patch.object(PS, "save_sim") as save:
                result = WL.run_round(sim, cfg, {})
        self.assertEqual(result["events_run"], 1)
        self.assertTrue(result["exhausted"])
        save.assert_called_once()

    def test_tuning_applies_and_llm_results_are_saved(self):
        sim = Sim(seed=7)
        with tempfile.TemporaryDirectory() as td:
            cfg = WL.LoopConfig(save_path=str(Path(td) / "audit.save"),
                                chunk_events=1, autotune=True, llm=True)
            with patch.object(sim, "step", return_value=object()), \
                 patch.object(sim.brain_manager, "drain_llm_queue", return_value=1), \
                 patch.object(PS, "save_sim") as save, \
                 patch.object(WL.TN, "save_state"), \
                 patch.object(WL.TN, "propose_update", return_value={"BREAK_BASE_P": 0.51}), \
                 patch.object(WL.TN, "apply_overrides") as apply:
                WL.run_round(sim, cfg, {})
                self.assertEqual(save.call_count, 2)
                apply.assert_called_once_with({"BREAK_BASE_P": 0.51})

    def test_cannot_restart_while_worker_is_stopping(self):
        runner = WL.WorldRunner()
        runner.state = "stopping"
        runner._thread = Mock()
        runner._thread.is_alive.return_value = True
        with self.assertRaises(RuntimeError):
            runner.start(WL.LoopConfig())


if __name__ == "__main__":
    unittest.main()
