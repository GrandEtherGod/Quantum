import sqlite3
import tempfile
import unittest
from pathlib import Path

from loom_verath import LoomVerathRuntime
from loom_verath.db import Database, SCHEMA_VERSION
from loom_verath.errors import InvariantViolation
from loom_verath.version import VERSION


class MigrationTests(unittest.TestCase):
    def test_legacy_schema_stamp_advances_and_records_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version=2")
            connection.close()
            database = Database(path)
            try:
                self.assertEqual({"current": SCHEMA_VERSION, "supported": SCHEMA_VERSION}, database.schema_version())
                versions = [row[0] for row in database.connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
                self.assertEqual(list(range(1, SCHEMA_VERSION + 1)), versions)
            finally:
                database.close()

    def test_newer_database_fails_before_runtime_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version=999")
            connection.close()
            with self.assertRaises(RuntimeError):
                Database(path)

    def test_runtime_version_and_database_schema_are_monotonic(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = LoomVerathRuntime(directory)
            try:
                self.assertEqual(VERSION, runtime.state.value("runtime.version"))
                self.assertEqual("0.4.1", VERSION)
                self.assertEqual(SCHEMA_VERSION, runtime.verify()["database_schema"]["current"])
                self.assertEqual(4, SCHEMA_VERSION)
                with self.assertRaises(InvariantViolation):
                    runtime.state.set("runtime.version", "0.2.0", actor="tester")
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
