"""Offline reader locks/cleanup; no endpoint, production ledger or charge changes."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


observer = module('reader_observer', 'scripts/observe_judge_queue_window.py')
watch = module('reader_watch', 'infra/watch_resources.py')


class ReaderTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='olens-reader-test-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'fixture.sqlite3'
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute('CREATE TABLE example(value INTEGER)')
            db.execute('INSERT INTO example VALUES(1)')

    def reader(self):
        return sqlite3.connect(f'file:{self.path}?mode=ro', uri=True,
                               isolation_level=None, timeout=.05)

    def writer(self):
        return sqlite3.connect(self.path, isolation_level=None, timeout=.05)

    def test_finished_autocommit_read_allows_commit_with_connection_still_open(self):
        with closing(self.reader()) as reader, closing(self.writer()) as writer:
            with closing(reader.execute('SELECT value FROM example')) as cursor:
                self.assertEqual(cursor.fetchall(), [(1,)])
            self.assertFalse(reader.in_transaction)
            writer.execute('BEGIN IMMEDIATE')
            writer.execute('INSERT INTO example VALUES(2)')
            writer.execute('COMMIT')
            self.assertEqual(reader.execute('SELECT COUNT(*) FROM example').fetchone()[0], 2)

    def test_explicit_read_transaction_blocks_commit_until_closed_without_replaying_write(self):
        with closing(self.reader()) as reader, closing(self.writer()) as writer:
            reader.execute('BEGIN')
            with closing(reader.execute('SELECT value FROM example')) as cursor:
                cursor.fetchall()
            writer.execute('BEGIN IMMEDIATE')
            writer.execute('INSERT INTO example VALUES(2)')
            with self.assertRaises(sqlite3.OperationalError) as caught:
                writer.execute('COMMIT')
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_BUSY)
            self.assertTrue(writer.in_transaction)
            reader.execute('ROLLBACK')
            writer.execute('COMMIT')
            self.assertEqual(writer.execute('SELECT value FROM example ORDER BY value').fetchall(),
                             [(1,), (2,)])

    def tracked_connect(self):
        original = sqlite3.connect
        opened = []

        class TrackedConnection(sqlite3.Connection):
            closed_by_caller = False

            def close(self):
                self.closed_by_caller = True
                return super().close()

        def connect(*args, **kwargs):
            db = original(*args, **kwargs, factory=TrackedConnection)
            opened.append(db)
            return db

        return opened, connect

    def test_observer_closes_connection_if_bounded_read_fails(self):
        opened, connect = self.tracked_connect()
        output = Path(self.temporary.name) / 'not-written.json'
        arguments = ['observer', '--ledger', str(self.path), '--run-id', 'synthetic',
                     '--epoch', '2026-10-10T00:00:00+00:00', '--active-pid', '1',
                     '--output', str(output)]
        with patch.object(sys, 'argv', arguments), patch.object(observer.sqlite3, 'connect', connect), \
                patch.object(observer, 'active_pid_checkpoint', side_effect=RuntimeError('synthetic read failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic read failure'):
                observer.main()
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed_by_caller)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute('SELECT 1')
        self.assertFalse(output.exists())

    def make_watch_schema(self):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.executescript('''
                CREATE TABLE config(key TEXT,value INTEGER);
                INSERT INTO config VALUES('hard',300000000000),('target',200000000000);
                CREATE TABLE attempts(status TEXT,reserved INTEGER,actual INTEGER);
                INSERT INTO attempts VALUES('settled',100,5),('unknown',7,NULL),('reserved',3,NULL);
            ''')

    def test_watcher_preserves_snapshot_values_and_closes_before_return(self):
        self.make_watch_schema()
        opened, connect = self.tracked_connect()
        with patch.object(watch.sqlite3, 'connect', connect):
            result = watch.budget_snapshot(self.path)
        self.assertEqual(result['status'], 'observed_read_only')
        self.assertEqual(result['actual_usd'], 5 / 1e9)
        self.assertEqual(result['reserved_usd'], 10 / 1e9)
        self.assertEqual(result['unknown_usd'], 7 / 1e9)
        self.assertEqual(result['attempt_counts'], {'reserved': 1, 'settled': 1, 'unknown': 1})
        self.assertTrue(opened[0].closed_by_caller)

    def test_watcher_closes_failed_snapshot_and_reports_unavailable(self):
        opened, connect = self.tracked_connect()
        with patch.object(watch.sqlite3, 'connect', connect):
            result = watch.budget_snapshot(self.path)
        self.assertEqual(result['status'], 'temporarily_unavailable')
        self.assertTrue(opened[0].closed_by_caller)
        # Error cleanup must not leave a read lock behind.
        with closing(self.writer()) as writer:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute('INSERT INTO example VALUES(2)')
            writer.execute('COMMIT')

    def test_watcher_interrupted_aggregate_releases_read_lock_for_pending_commit(self):
        self.make_watch_schema()
        with closing(sqlite3.connect(self.path)) as db:
            db.executemany('INSERT INTO attempts VALUES(?,?,?)',
                           [('settled', 100, 5)] * 2000)
            db.commit()
        original_connect = sqlite3.connect
        opened = []
        with closing(self.writer()) as writer:
            test = self

            class InterruptedConnection(sqlite3.Connection):
                closed_by_caller = False
                checked_shared_lock = False

                def set_progress_handler(self, handler, instructions):
                    if handler is None:
                        return super().set_progress_handler(None, instructions)

                    def while_reading():
                        if not self.checked_shared_lock:
                            self.checked_shared_lock = True
                            writer.execute('BEGIN IMMEDIATE')
                            writer.execute('INSERT INTO example VALUES(2)')
                            with test.assertRaises(sqlite3.OperationalError) as caught:
                                writer.execute('COMMIT')
                            test.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_BUSY)
                        return handler()

                    return super().set_progress_handler(while_reading, instructions)

                def close(self):
                    self.closed_by_caller = True
                    return super().close()

            def connect(*args, **kwargs):
                db = original_connect(*args, **kwargs, factory=InterruptedConnection)
                opened.append(db)
                return db

            # Deterministically cross the real callback's monotonic deadline;
            # the aggregate still executes SQLite bytecode on a disposable DB.
            with patch.object(watch.sqlite3, 'connect', connect), \
                    patch.object(watch.time, 'monotonic', side_effect=[0.0, 3.0]):
                result = watch.budget_snapshot(self.path)
            self.assertEqual(result['status'], 'temporarily_unavailable')
            self.assertTrue(result['query_deadline_exceeded'])
            self.assertNotIn('actual_usd', result)
            self.assertNotIn('attempt_counts', result)
            self.assertTrue(opened[0].checked_shared_lock)
            self.assertTrue(opened[0].closed_by_caller)
            # Commit the already-written transaction; never replay its body.
            writer.execute('COMMIT')
            self.assertEqual(writer.execute('SELECT value FROM example ORDER BY value').fetchall(),
                             [(1,), (2,)])

    def test_legacy_cli_uses_bounded_reader_and_retains_unknown_hold(self):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.executescript('''
                CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY,run_id TEXT,status TEXT,
                    reserved INTEGER,actual INTEGER,created_utc TEXT,metadata TEXT);
                CREATE TABLE events(sequence INTEGER PRIMARY KEY,attempt_id TEXT,kind TEXT,details TEXT);
                CREATE INDEX attempts_run_committed ON attempts(run_id,status,actual,reserved);
                CREATE INDEX attempts_run_recovery ON attempts(run_id,created_utc DESC,status,reserved);
                CREATE INDEX events_attempt_kind_sequence ON events(attempt_id,kind,sequence DESC);
            ''')
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?)',
                       ('uncertain', 'fixture', 'unknown', 123, None,
                        '2026-10-10T01:00:00+00:00', json.dumps({'pid': 7})))
        output = Path(self.temporary.name) / 'legacy-checkpoint.json'
        process = subprocess.run([sys.executable, str(ROOT / 'scripts/observe_judge_queue.py'),
            '--ledger', str(self.path), '--run-id', 'fixture',
            '--epoch', '2026-10-10T00:00:00+00:00', '--active-pid', '7',
            '--output', str(output)], capture_output=True, text=True, timeout=5)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(output.read_text())
        self.assertEqual(result['monitor_mode'], 'indexed_active_pid')
        self.assertEqual(result['network_model_calls'], 0)
        self.assertEqual(result['all_workers']['unknown_reserved_nanodollars'], 123)
        self.assertEqual(result['workers']['7']['attempt_counts'], {'unknown': 1})
        with closing(self.writer()) as writer:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute('INSERT INTO example VALUES(2)')
            writer.execute('COMMIT')


if __name__ == '__main__':
    unittest.main()
