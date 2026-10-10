"""Atomic batch reservations on disposable ledgers, with no network or real data."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from olens_improve.budget import AtomicBudget, BudgetExceeded, NANODOLLARS, cost_units


def state(path):
    with closing(sqlite3.connect(path)) as db:
        return {t: db.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall()
                for t in ('config','run_limits','attempts','events')}


def request(aid, run='same', **extra):
    return dict(input_upper_tokens=512,max_output_tokens=128,run_id=run,
                metadata={'source':'offline','request':{'nested':['exact']}},attempt_id=aid,**extra)


class BudgetBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.ledger=AtomicBudget(Path(self.tmp.name)/'batch.sqlite3',bootstrap_claude=False)
    def tearDown(self): self.tmp.cleanup()
    def other(self,name='single',**kwargs):
        return AtomicBudget(Path(self.tmp.name)/(name+'.sqlite3'),bootstrap_claude=False,**kwargs)
    def seed_guard(self, ledger, *, future=False):
        with closing(sqlite3.connect(ledger.path,isolation_level=None)) as db:
            for i in range(100):
                stamp=('2099' if future else '2026')+f'-10-10T08:00:00.{i:06d}+00:00'
                db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',
                    (f'old-{i}','same','unknown' if i<6 else 'settled',1,0,'{}',stamp,stamp))

    def test_sequential_rows_events_pricing_holds_and_metadata_are_exact(self):
        single=self.other()
        for ledger in (self.ledger,single): ledger.set_run_limit('same',1)
        rows=[request('a'),request('b'),request('c',dispatch_guard={'since_utc':'2026-10-10T07:52:00+00:00'})]
        with patch('olens_improve.budget._utc',return_value='2026-10-10T10:00:00+00:00'):
            self.assertEqual(self.ledger.reserve_attempts(rows),['a','b','c'])
            for row in rows:
                copy=dict(row);n=copy.pop('input_upper_tokens');m=copy.pop('max_output_tokens')
                single.reserve_attempt(n,m,**copy)
            for ledger in (self.ledger,single):
                ledger.record_evidence('a','physical_response',{'fake':'exact'})
                ledger.settle('a',input_tokens=400,output_tokens=40,cache_write_tokens=100)
                ledger.mark_unknown('b','offline uncertainty')
        self.assertEqual(state(self.ledger.path),state(single.path))
        a,b=self.ledger.snapshot(),single.snapshot();a.pop('db_path');b.pop('db_path')
        self.assertEqual(a,b);self.assertGreater(a['unknown_usd'],0)

    def test_running_caps_exact_equality_mixed_runs_and_full_rollback(self):
        amount=cost_units(512,128,cache_write_tokens=512)
        hard=str(Decimal(2*amount)/NANODOLLARS)
        ledger=self.other('limited',hard_usd=hard,target_usd=hard)
        ledger.set_run_limit('r1',str(Decimal(amount)/NANODOLLARS))
        ledger.set_run_limit('r2',str(Decimal(amount)/NANODOLLARS))
        self.assertEqual(ledger.reserve_attempts([request('a','r1'),request('b','r2')]),['a','b'])
        before=state(ledger.path)
        with self.assertRaises(BudgetExceeded): ledger.reserve_attempts([request('c','r1')])
        self.assertEqual(state(ledger.path),before)
        other=self.other('runlimited');other.set_run_limit('same',str(Decimal(amount)/NANODOLLARS))
        before=state(other.path)
        with self.assertRaises(BudgetExceeded):other.reserve_attempts([request('a'),request('b')])
        self.assertEqual(state(other.path),before)
        global_limited=self.other('global',hard_usd=hard,target_usd=hard)
        before=state(global_limited.path)
        with self.assertRaises(BudgetExceeded): global_limited.reserve_attempts([request('a'),request('b'),request('c')])
        self.assertEqual(state(global_limited.path),before)

    def test_invalid_late_row_duplicate_or_existing_id_leave_no_partial_rows(self):
        for rows in ([request('a'),request('a')], [request('a'),request('bad',dispatch_guard={})],
                     [request('a'),dict(request('bad'),max_output_tokens=0)],
                     [request('a'),dict(request('bad'),surprise=True)]):
            before=state(self.ledger.path)
            with self.assertRaises((ValueError,KeyError)):self.ledger.reserve_attempts(rows)
            self.assertEqual(state(self.ledger.path),before)
        self.ledger.reserve_attempt(512,128,run_id='same',attempt_id='old')
        before=state(self.ledger.path)
        with self.assertRaises(sqlite3.IntegrityError):self.ledger.reserve_attempts([request('new'),request('old')])
        self.assertEqual(state(self.ledger.path),before)
        before=state(self.ledger.path)
        with self.assertRaises(TypeError):self.ledger.reserve_attempts([request('new'),dict(request('bad'),metadata={'bad':object()})])
        self.assertEqual(state(self.ledger.path),before)

    def test_bounds_halt_and_no_run_limit(self):
        for rows in ([],[request(str(i)) for i in range(17)],tuple([request('a')])):
            with self.assertRaises(ValueError):self.ledger.reserve_attempts(rows)
        self.assertEqual(len(self.ledger.reserve_attempts([request(str(i),'unlimited') for i in range(16)])),16)
        with closing(sqlite3.connect(self.ledger.path,isolation_level=None)) as db:db.execute("UPDATE config SET value=1 WHERE key='halted'")
        before=state(self.ledger.path)
        with self.assertRaises(BudgetExceeded):self.ledger.reserve_attempts([request('halted')])
        self.assertEqual(state(self.ledger.path),before)

    def test_guard_first_evaluation_uses_prior_unguarded_insert(self):
        self.seed_guard(self.ledger);single=self.other();self.seed_guard(single)
        guard={'since_utc':'2026-10-10T07:52:00+00:00'}
        rows=[request('first'),request('second',dispatch_guard=guard)]
        with patch('olens_improve.budget._utc',return_value='2026-10-10T10:00:00+00:00'):
            self.ledger.reserve_attempts(rows)
            for row in rows:
                copy=dict(row);n=copy.pop('input_upper_tokens');m=copy.pop('max_output_tokens');single.reserve_attempt(n,m,**copy)
        self.assertEqual(state(self.ledger.path),state(single.path))
        # All old uncertain amounts remain; aging out of latest100 never releases them.
        self.assertEqual(self.ledger.snapshot()['unknown_usd'],6/NANODOLLARS)

    def test_guard_failure_unknown_amount_and_late_guard_rollback(self):
        self.seed_guard(self.ledger)
        before=state(self.ledger.path)
        with self.assertRaises(BudgetExceeded): self.ledger.reserve_attempts([request('blocked',dispatch_guard={'since_utc':'2026-10-10T07:52:00+00:00'})])
        self.assertEqual(state(self.ledger.path),before)
        ledger=self.other('amount')
        ledger.reserve_attempt(1000000,1,run_id='same',attempt_id='held');ledger.mark_unknown('held','offline')
        before=state(ledger.path)
        with self.assertRaises(BudgetExceeded):ledger.reserve_attempts([request('unguarded'),request('guarded',dispatch_guard={'since_utc':'2020'})])
        self.assertEqual(state(ledger.path),before)
        # A future latest100 remains later than newly inserted rows: don't invent eviction.
        future=self.other('future');self.seed_guard(future,future=True);before=state(future.path)
        with self.assertRaises(BudgetExceeded):future.reserve_attempts([request('first'),request('second',dispatch_guard={'since_utc':'2020'})])
        self.assertEqual(state(future.path),before)

    def test_distinct_guard_epochs_and_run_windows_match_single(self):
        other=self.other()
        guards=[{'since_utc':'2020'},{'since_utc':'2099'}]
        rows=[request('a',dispatch_guard=guards[0]),request('b','another',dispatch_guard=guards[0]),
              request('c',dispatch_guard=guards[1]),request('d',dispatch_guard=guards[0])]
        with patch('olens_improve.budget._utc',return_value='2026-10-10T10:00:00+00:00'):
            self.ledger.reserve_attempts(rows)
            for row in rows:
                copy=dict(row);n=copy.pop('input_upper_tokens');m=copy.pop('max_output_tokens');other.reserve_attempt(n,m,**copy)
        self.assertEqual(state(self.ledger.path),state(other.path))

    def test_commit_failure_does_not_return_ids_or_replay(self):
        original=sqlite3.connect
        for after in (False,True):
            ledger=self.other('commit-'+str(after));calls=[]
            class Connection:
                def __init__(self,db):self.db=db
                def __getattr__(self,name):return getattr(self.db,name)
                def execute(self,sql,*args):
                    if sql=='COMMIT':
                        calls.append('commit')
                        if after:self.db.execute(sql)
                        raise sqlite3.OperationalError('offline commit failure')
                    return self.db.execute(sql,*args)
                def close(self):self.db.close()
            with patch('olens_improve.budget.sqlite3.connect',side_effect=lambda *a,**k:Connection(original(*a,**k))):
                with self.assertRaises(sqlite3.OperationalError):ledger.reserve_attempts([request('a'),request('b')])
            self.assertEqual(calls,['commit'])
            self.assertEqual(len(state(ledger.path)['attempts']),2 if after else 0)

    def test_batch_and_single_writers_cannot_exceed_shared_cap(self):
        amount=cost_units(512,128,cache_write_tokens=512)
        self.ledger.set_run_limit('same',str(Decimal(2*amount)/NANODOLLARS))
        def batch():
            try:self.ledger.reserve_attempts([request('a'),request('b')]);return 2
            except BudgetExceeded:return 0
        def single():
            try:self.ledger.reserve_attempt(512,128,run_id='same',attempt_id='c');return 1
            except BudgetExceeded:return 0
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda f:f(),[batch,single]))
        self.assertLessEqual(sum(results),2)
        self.assertLessEqual(self.ledger.snapshot()['reserved_usd'],2*amount/NANODOLLARS)

    def test_one_sum_and_guard_scan_per_run_epoch_on_normal_clock(self):
        self.ledger.set_run_limit('same',1)
        statements=[];original=sqlite3.connect
        def connection(*args,**kwargs):
            db=original(*args,**kwargs);db.set_trace_callback(statements.append);return db
        guard={'since_utc':'2026-10-10T07:52:00+00:00'}
        stamps=[f'2026-10-10T10:00:00.{i:06d}+00:00' for i in range(32)]
        with patch('olens_improve.budget.sqlite3.connect',side_effect=connection), \
             patch('olens_improve.budget._utc',side_effect=stamps):
            self.ledger.reserve_attempts([request(str(i),dispatch_guard=guard) for i in range(16)])
        self.assertEqual(sum('SUM(CASE' in sql for sql in statements),2) # Global plus this run.
        self.assertEqual(sum('SELECT status,created_utc' in sql for sql in statements),1)
        self.assertEqual(sum('SUM(reserved)' in sql for sql in statements),1)

if __name__=='__main__':unittest.main()
