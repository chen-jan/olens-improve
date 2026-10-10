"""Operational observer tests; synthetic SQLite only, no endpoint or real ledger."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest


spec = importlib.util.spec_from_file_location('judge_observer',
    Path(__file__).parents[1]/'scripts/observe_judge_queue_window.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class ObserverTests(unittest.TestCase):
    def fixture(self):
        db = sqlite3.connect(':memory:', isolation_level=None)
        db.row_factory = sqlite3.Row
        db.executescript('''
            CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY,run_id TEXT,status TEXT,
                reserved INTEGER,actual INTEGER,created_utc TEXT,metadata TEXT);
            CREATE TABLE events(sequence INTEGER PRIMARY KEY,attempt_id TEXT,kind TEXT,details TEXT);
            CREATE INDEX attempts_run_committed ON attempts(run_id,status,actual,reserved);
            CREATE INDEX attempts_run_recovery ON attempts(run_id,created_utc DESC,status,reserved);
            CREATE INDEX events_attempt_kind_sequence ON events(attempt_id,kind,sequence DESC);
        ''')
        # A large older history must affect exact totals without parsing its metadata.
        db.executemany('INSERT INTO attempts VALUES(?,?,?,?,?,?,?)',
            [(f'old{i}','run','settled',9,3,'2026-10-10T07:00:00+00:00',
              json.dumps({'pid':99,'history':i})) for i in range(10000)])
        for i in range(220):
            pid = 1 if i % 2 else 2
            created = f'2026-10-10T09:{i//60:02d}:{i%60:02d}+00:00'
            status = 'reserved' if i >= 218 else 'settled'
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?)',
                (f'new{i}','run',status,11,5 if status=='settled' else None,
                 created,json.dumps({'pid':pid})))
            if status=='settled':
                db.execute('INSERT INTO events(attempt_id,kind,details) VALUES(?,?,?)',
                    (f'new{i}','physical_response',json.dumps({'latency_s':2.0})))
        db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?)',
            ('old-unknown','run','unknown',123,None,'2026-10-10T07:01:00+00:00',json.dumps({'pid':99})))
        db.execute('INSERT INTO events(attempt_id,kind,details) VALUES(?,?,?)',
            ('old-unknown','transport_failure',json.dumps({'cause_chain':[{'class':'ReadError'}]})))
        db.execute('PRAGMA query_only=ON')
        return db

    def test_covering_totals_bounded_metadata_and_old_hold_are_preserved(self):
        db = self.fixture()
        metadata_reads = []
        def extract(text, path):
            if path=='$.pid':metadata_reads.append(text)
            value = json.loads(text).get(path[2:])
            return json.dumps(value) if isinstance(value,(list,dict)) else value
        db.create_function('json_extract',2,extract)
        before = db.total_changes
        result = observer.active_pid_checkpoint(db,'run','2026-10-10T08:00:00+00:00',[1,2],
            now=datetime(2026,10,10,9,5,tzinfo=timezone.utc))
        self.assertEqual(result['all_workers']['attempt_counts'],
                         {'reserved':2,'settled':10218,'unknown':1})
        self.assertEqual(result['all_workers']['actual_usage_nanodollars'],10000*3+218*5)
        self.assertEqual(result['all_workers']['unknown_reserved_nanodollars'],123)
        self.assertEqual(result['unknown_attempts'][0]['cause'],'ReadError')
        self.assertEqual(result['all_workers']['latest_100_unknown_count'],0)
        self.assertEqual(result['all_workers']['recent_physical_response_latency_samples'],198)
        self.assertTrue(all(r['window_coverage']['available_attempts']==100
                            for r in result['workers'].values()))
        self.assertTrue(all(r['window_coverage']['missing_latency_samples']==1
                            for r in result['workers'].values()))
        self.assertLess(len(metadata_reads),1000)
        self.assertFalse(any('history' in value for value in metadata_reads))
        self.assertEqual(db.total_changes,before)
        plan = db.execute('EXPLAIN QUERY PLAN SELECT status,COUNT(*),SUM(reserved),SUM(actual) '
            'FROM attempts INDEXED BY attempts_run_committed WHERE run_id=? GROUP BY status',
            ('run',)).fetchall()
        self.assertTrue(any('COVERING INDEX attempts_run_committed' in row[3] for row in plan))
        db.close()

    def test_absent_pid_has_explicit_zero_coverage_and_no_latency(self):
        db = self.fixture()
        result = observer.active_pid_checkpoint(db,'run','2026-10-10T08:00:00+00:00',[777],
            now=datetime(2026,10,10,9,5,tzinfo=timezone.utc))
        worker = result['workers']['777']
        self.assertEqual(worker['window_coverage'],{'requested_attempts':100,
            'available_attempts':0,'physical_response_latencies_observed':0,'missing_latency_samples':0})
        self.assertIsNone(worker['recent_latency_p95_seconds'])
        self.assertIsNone(result['all_workers']['recent_latency_p95_seconds'])
        self.assertEqual(result['all_workers']['unknown_reserved_nanodollars'],123)
        self.assertEqual(result['unknown_attempts'][0]['cause'],'ReadError')
        db.close()


if __name__=='__main__':unittest.main()
