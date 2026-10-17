import statistics
import tempfile
import time
import unittest

from loom_verath import LoomVerathRuntime
from loom_verath.build_pipeline import MechanicBuild


class BuildIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def _ledger_event_count(self):
        return self.runtime.database.connection.execute(
            "SELECT COUNT(*) AS count FROM ledger"
        ).fetchone()["count"]

    def test_isolated_run_leaves_caller_runtime_untouched(self):
        before = self._ledger_event_count()
        result = MechanicBuild(self.runtime).run(isolated=True)
        self.assertTrue(result["isolated"])
        self.assertTrue(result["local_acceptance_passed"])
        self.assertEqual(before, self._ledger_event_count())

    def test_isolated_run_passes_same_local_stages(self):
        result = MechanicBuild(self.runtime).run(isolated=True)
        states = {stage["stage"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(7, list(states.values()).count("passed"))
        self.assertEqual("blocked", states["bio_live"])
        self.assertTrue(result["report_ephemeral"])
        self.assertIsNotNone(result["report"])

    def test_repeated_isolated_runs_have_stable_timing(self):
        runs = 8
        durations = []
        first_statuses = None
        for _ in range(runs):
            started = time.perf_counter()
            result = MechanicBuild(self.runtime).run(isolated=True)
            durations.append(time.perf_counter() - started)
            statuses = [stage["status"] for stage in result["stages"]]
            if first_statuses is None:
                first_statuses = statuses
            else:
                self.assertEqual(first_statuses, statuses)
        early = statistics.median(durations[: runs // 2])
        late = statistics.median(durations[runs // 2 :])
        # No drift trend: later runs must not be systematically slower.
        self.assertLess(late, 2.0 * early)
        # Bounded jitter across all runs.
        self.assertLess(max(durations), 4.0 * min(durations))

    def test_non_isolated_default_preserved(self):
        result = MechanicBuild(self.runtime).run()
        self.assertNotIn("isolated", result)
        self.assertTrue((self.runtime.data_dir / "mechanic_builds").exists())


if __name__ == "__main__":
    unittest.main()
