"""Atomic, cross-process API reservations. Unknown charges stay committed.

SQLite DELETE journals and BEGIN IMMEDIATE are deliberate: the shared storage
is NFS. Validate filesystem locking before enabling real requests. Each SDK
physical attempt needs its own reservation; SDK automatic retries must be off.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import sqlite3
from typing import Iterator
import uuid

NANODOLLARS = 1_000_000_000
STANDARD_RATES = {'input': Decimal('0.10'), 'cached_input': Decimal('0.01'),
                  'cache_write': Decimal('0.125'), 'output': Decimal('0.50')}
PRICING_REVISION = 'luna-cache-write-v1'
UNKNOWN_CLAUDE_ID = 'claude-review-unconfirmed-20261009'


class BudgetExceeded(RuntimeError):
    pass


def usd_units(value: str | float | Decimal) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError('Spend must be finite and nonnegative')
    return int((amount * NANODOLLARS).to_integral_value(rounding=ROUND_CEILING))


def cost_units(input_tokens: int, output_tokens: int, cached_tokens: int = 0,
               billed_tier: str = 'default', cache_write_tokens: int = 0) -> int:
    values = (input_tokens, output_tokens, cached_tokens, cache_write_tokens)
    if any(not isinstance(v, int) or isinstance(v, bool) for v in values):
        raise ValueError('Token accounting requires integer counts')
    if min(values) < 0 or cached_tokens + cache_write_tokens > input_tokens:
        raise ValueError('Invalid token accounting')
    if billed_tier not in ('default', 'standard', 'flex'):
        raise ValueError(f'Unpriced service tier: {billed_tier}')
    discount = Decimal('0.5') if billed_tier == 'flex' else Decimal(1)
    dollars = ((input_tokens - cached_tokens - cache_write_tokens) * STANDARD_RATES['input']
               + cached_tokens * STANDARD_RATES['cached_input']
               + cache_write_tokens * STANDARD_RATES['cache_write']
               + output_tokens * STANDARD_RATES['output']) * discount / 1_000_000
    return usd_units(dollars)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class AtomicBudget:
    def __init__(self, path: str | Path, hard_usd: str | float = '300',
                 target_usd: str | float = '200', bootstrap_claude: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.hard = usd_units(hard_usd)
        self.target = usd_units(target_usd)
        if self.target > self.hard:
            raise ValueError('Target exceeds hard cap')
        with self._transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value INTEGER NOT NULL)')
            db.execute('''CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, status TEXT NOT NULL,
                reserved INTEGER NOT NULL, actual INTEGER,
                metadata TEXT NOT NULL, created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS attempts_run ON attempts(run_id)')
            db.execute('''CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT NOT NULL,
                kind TEXT NOT NULL, details TEXT NOT NULL, utc TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS run_limits (run_id TEXT PRIMARY KEY, cap INTEGER NOT NULL)')
            for key, value in [('hard', self.hard), ('target', self.target)]:
                old = db.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
                if old is not None and old[0] != value:
                    raise ValueError(f'Existing ledger {key} differs; explicit reconciliation required')
                db.execute('INSERT OR IGNORE INTO config VALUES (?,?)', (key, value))
            db.execute("INSERT OR IGNORE INTO config VALUES ('halted',0)")
            if bootstrap_claude and db.execute('SELECT 1 FROM attempts WHERE attempt_id=?', (UNKNOWN_CLAUDE_ID,)).fetchone() is None:
                amount = usd_units('2')
                if self._committed(db) + amount > self.hard:
                    raise BudgetExceeded('Cannot reserve historical unknown Claude charge')
                now = _utc()
                db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',
                           (UNKNOWN_CLAUDE_ID, 'historical-review', 'unknown', amount, None,
                            json.dumps({'reason': 'CLI timeout; no usage or charge returned; availability unverified'}), now, now))
                self._event(db, UNKNOWN_CLAUDE_ID, 'bootstrap_unknown', {'usd': 2})

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=30000')
            mode = db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]
            if mode.casefold() != 'delete':
                raise RuntimeError(f'Unsupported journal mode {mode}')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    @staticmethod
    def _committed(db: sqlite3.Connection, run_id: str | None = None) -> int:
        where = '' if run_id is None else ' WHERE run_id=?'
        values = () if run_id is None else (run_id,)
        return db.execute('''SELECT COALESCE(SUM(CASE
            WHEN status='settled' THEN actual WHEN status IN ('reserved','unknown') THEN reserved ELSE 0 END),0)
            FROM attempts''' + where, values).fetchone()[0]

    @staticmethod
    def _event(db: sqlite3.Connection, attempt_id: str, kind: str, details: dict) -> None:
        db.execute('INSERT INTO events(attempt_id,kind,details,utc) VALUES (?,?,?,?)',
                   (attempt_id, kind, json.dumps(details, sort_keys=True), _utc()))

    def set_run_limit(self, run_id: str, cap_usd: str | float) -> None:
        cap = usd_units(cap_usd)
        with self._transaction() as db:
            old = db.execute('SELECT cap FROM run_limits WHERE run_id=?', (run_id,)).fetchone()
            if old is not None and old[0] != cap:
                raise ValueError('Run limit is frozen; use a new authorized run ID')
            if self._committed(db, run_id) > cap:
                raise BudgetExceeded('Run already exceeds requested limit')
            db.execute('INSERT OR IGNORE INTO run_limits VALUES (?,?)', (run_id, cap))

    def reserve_attempt(self, input_upper_tokens: int, max_output_tokens: int, *,
                        run_id: str, metadata: dict | None = None,
                        attempt_id: str | None = None, dispatch_guard: dict | None = None) -> str:
        if input_upper_tokens <= 0 or max_output_tokens <= 0:
            raise ValueError('Positive input/output bounds required')
        # Reserve Standard prices even for Flex: a billed tier fallback is covered.
        amount = cost_units(input_upper_tokens, max_output_tokens,
                            cache_write_tokens=input_upper_tokens)
        aid = attempt_id or str(uuid.uuid4())
        details = dict(metadata or {})
        details.update(input_upper_tokens=input_upper_tokens, max_output_tokens=max_output_tokens,
                       reservation_pricing='standard; all input at cache-write rate',
                       pricing_revision=PRICING_REVISION)
        if dispatch_guard is not None:
            details['transport_recovery_guard'] = dispatch_guard
        with self._transaction() as db:
            if dispatch_guard is not None:
                # A transport incident guard is scoped to this recovery epoch,
                # checked atomically across workers before reserving a request.
                since = dispatch_guard['since_utc']
                recent = db.execute('SELECT status FROM attempts WHERE run_id=? AND created_utc>=? '
                    'ORDER BY created_utc DESC LIMIT 100', (run_id, since)).fetchall()
                unknown = db.execute("SELECT COALESCE(SUM(reserved),0) FROM attempts WHERE run_id=? "
                    "AND created_utc>=? AND status='unknown'", (run_id, since)).fetchone()[0]
                if sum(row[0] == 'unknown' for row in recent) > 5 or unknown > usd_units('.10'):
                    raise BudgetExceeded('Transport recovery paused: new uncertain attempts exceed frozen guard')
            if db.execute("SELECT value FROM config WHERE key='halted'").fetchone()[0]:
                raise BudgetExceeded('Ledger halted after accounting-bound failure; explicit reconciliation required')
            if self._committed(db) + amount > self.hard:
                raise BudgetExceeded('Hard API cap would be exceeded by this physical attempt')
            limit = db.execute('SELECT cap FROM run_limits WHERE run_id=?', (run_id,)).fetchone()
            if limit is not None and self._committed(db, run_id) + amount > limit[0]:
                raise BudgetExceeded(f'Frozen run API cap would be exceeded: {run_id}')
            now = _utc()
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',
                       (aid, run_id, 'reserved', amount, None, json.dumps(details, sort_keys=True), now, now))
            self._event(db, aid, 'reserved', details)
        return aid

    def mark_unknown(self, attempt_id: str, reason: str) -> None:
        with self._transaction() as db:
            row = db.execute('SELECT status FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(attempt_id)
            if row[0] not in ('reserved', 'unknown'):
                raise ValueError(f'Cannot mark {row[0]} attempt unknown')
            db.execute('UPDATE attempts SET status=?,updated_utc=? WHERE attempt_id=?', ('unknown', _utc(), attempt_id))
            self._event(db, attempt_id, 'unknown', {'reason': reason})

    def settle(self, attempt_id: str, *, input_tokens: int, output_tokens: int,
               cached_tokens: int = 0, billed_tier: str = 'default',
               response_id: str | None = None, cache_write_tokens: int = 0) -> None:
        amount = cost_units(input_tokens, output_tokens, cached_tokens, billed_tier, cache_write_tokens)
        with self._transaction() as db:
            row = db.execute('SELECT status,reserved,actual FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(attempt_id)
            if row[0] == 'settled' and row[2] == amount:
                return  # idempotent reconciliation
            if row[0] not in ('reserved', 'unknown'):
                raise ValueError(f'Cannot settle {row[0]} attempt')
            db.execute('UPDATE attempts SET status=?,actual=?,updated_utc=? WHERE attempt_id=?',
                       ('settled', amount, _utc(), attempt_id))
            self._event(db, attempt_id, 'settled', dict(input_tokens=input_tokens, output_tokens=output_tokens,
                        cached_tokens=cached_tokens, billed_tier=billed_tier, response_id=response_id,
                        cache_write_tokens=cache_write_tokens, pricing_revision=PRICING_REVISION,
                        reservation_exceeded=amount > row[1]))
            if amount > row[1]:
                db.execute("UPDATE config SET value=1 WHERE key='halted'")
        if amount > row[1]:
            # Never conceal actual billing, even if an input-bound assumption failed.
            raise BudgetExceeded('Actual usage exceeded reservation; billing recorded, stop and reconcile bounds')

    @staticmethod
    def _cache_write_plan(db: sqlite3.Connection) -> dict:
        """Reconstruct prices from retained usage, never from guessed missing fields."""
        responses = {}
        for aid, details in db.execute("SELECT attempt_id,details FROM events WHERE kind='physical_response' ORDER BY sequence"):
            responses[aid] = json.loads(details)
        plan = {'pricing_revision': PRICING_REVISION, 'invoice_reconciled': False,
                'settled_changes': [], 'reservation_changes': [], 'missing_usage': [],
                'invalid_usage': [], 'unpriced_unknown_metadata': [], 'unchanged_settled': 0}
        for aid, status, reserved, actual, metadata in db.execute(
                'SELECT attempt_id,status,reserved,actual,metadata FROM attempts ORDER BY attempt_id'):
            if status == 'settled':
                d = responses.get(aid, {}); raw = d.get('response') or {}; usage = raw.get('usage') or {}
                detail = usage.get('prompt_tokens_details') or {}
                required = ('prompt_tokens', 'completion_tokens')
                if any(k not in usage or usage[k] is None for k in required) or any(
                        k not in detail or detail[k] is None for k in ('cached_tokens','cache_write_tokens')):
                    plan['missing_usage'].append(aid)
                    continue
                tier = d.get('billed_tier') or raw.get('service_tier') or 'default'
                try:
                    after = cost_units(usage['prompt_tokens'], usage['completion_tokens'],
                                       detail['cached_tokens'], tier, detail['cache_write_tokens'])
                except ValueError as error:
                    plan['invalid_usage'].append({'attempt_id': aid, 'error': str(error)})
                    continue
                if after == actual:
                    plan['unchanged_settled'] += 1
                else:
                    plan['settled_changes'].append({'attempt_id': aid, 'before_units': actual,
                        'after_units': after, 'original_reserved_units': reserved,
                        'input_tokens': usage['prompt_tokens'], 'output_tokens': usage['completion_tokens'],
                        'cached_tokens': detail['cached_tokens'], 'cache_write_tokens': detail['cache_write_tokens'],
                        'billed_tier': tier, 'response_id': d.get('response_id') or raw.get('id')})
            elif status in ('reserved', 'unknown'):
                meta = json.loads(metadata)
                if 'input_upper_tokens' not in meta or 'max_output_tokens' not in meta:
                    plan['unpriced_unknown_metadata'].append(aid)
                    continue
                try:
                    bound = cost_units(meta['input_upper_tokens'], meta['max_output_tokens'],
                                       cache_write_tokens=meta['input_upper_tokens'])
                except ValueError as error:
                    plan['invalid_usage'].append({'attempt_id': aid, 'error': str(error)})
                    continue
                if bound > reserved:
                    plan['reservation_changes'].append({'attempt_id': aid, 'status': status,
                        'before_units': reserved, 'after_units': bound})
        plan['actual_delta_usd'] = sum(r['after_units'] - r['before_units'] for r in plan['settled_changes']) / NANODOLLARS
        plan['reservation_delta_usd'] = sum(r['after_units'] - r['before_units'] for r in plan['reservation_changes']) / NANODOLLARS
        return plan

    def preview_cache_write_reconciliation(self) -> dict:
        """Read-only snapshot; no price, evidence or reservation changes."""
        with sqlite3.connect(f'file:{self.path}?mode=ro', uri=True, timeout=30) as db:
            db.execute('BEGIN')
            return self._cache_write_plan(db)

    def reconcile_cache_write_pricing(self, *, evidence: str) -> dict:
        """Explicit, atomic and idempotent correction; preserve original events."""
        if not evidence.strip():
            raise ValueError('Pricing reconciliation requires explicit evidence')
        with self._transaction() as db:
            plan = self._cache_write_plan(db)
            for row in plan['settled_changes']:
                db.execute('UPDATE attempts SET actual=?,updated_utc=? WHERE attempt_id=?',
                           (row['after_units'], _utc(), row['attempt_id']))
                self._event(db, row['attempt_id'], 'pricing_correction',
                            {**row, 'pricing_revision': PRICING_REVISION, 'evidence': evidence})
                if row['after_units'] > row['original_reserved_units']:
                    db.execute("UPDATE config SET value=1 WHERE key='halted'")
            for row in plan['reservation_changes']:
                metadata = json.loads(db.execute('SELECT metadata FROM attempts WHERE attempt_id=?',
                                                 (row['attempt_id'],)).fetchone()[0])
                metadata.update(reservation_pricing='standard; all input at cache-write rate',
                                pricing_revision=PRICING_REVISION)
                db.execute('UPDATE attempts SET reserved=?,metadata=?,updated_utc=? WHERE attempt_id=?',
                           (row['after_units'], json.dumps(metadata,sort_keys=True), _utc(), row['attempt_id']))
                self._event(db, row['attempt_id'], 'reservation_pricing_correction',
                            {**row, 'pricing_revision': PRICING_REVISION, 'evidence': evidence})
            if self._committed(db) > self.hard or any(self._committed(db, run) > cap
                    for run, cap in db.execute('SELECT run_id,cap FROM run_limits')):
                db.execute("UPDATE config SET value=1 WHERE key='halted'")
            if plan['settled_changes'] or plan['reservation_changes']:
                self._event(db, 'ledger', 'cache_write_reconciliation', {
                    'pricing_revision': PRICING_REVISION, 'evidence': evidence,
                    'settled_corrected': len(plan['settled_changes']),
                    'reservations_increased': len(plan['reservation_changes']),
                    'actual_delta_usd': plan['actual_delta_usd'],
                    'reservation_delta_usd': plan['reservation_delta_usd'],
                    'missing_usage_count': len(plan['missing_usage']),
                    'invalid_usage_count': len(plan['invalid_usage']), 'invoice_reconciled': False})
        return plan

    def clear_accounting_halt(self, *, reconciliation_evidence: str) -> None:
        """Administrative action only after the bound failure has been investigated."""
        if not reconciliation_evidence.strip():
            raise ValueError('Explicit accounting reconciliation evidence required')
        with self._transaction() as db:
            db.execute("UPDATE config SET value=0 WHERE key='halted'")
            self._event(db, 'ledger', 'explicit_halt_reconciliation', {'evidence': reconciliation_evidence})

    def record_evidence(self, attempt_id: str, kind: str, details: dict) -> None:
        with self._transaction() as db:
            if db.execute('SELECT 1 FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone() is None:
                raise KeyError(attempt_id)
            self._event(db, attempt_id, kind, details)

    def release_uncharged(self, attempt_id: str, *, evidence: str) -> None:
        if not evidence.strip():
            raise ValueError('Definitive uncharged evidence required; timeout alone is insufficient')
        with self._transaction() as db:
            row = db.execute('SELECT status FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(attempt_id)
            if row[0] not in ('reserved', 'unknown'):
                raise ValueError(f'Cannot release {row[0]} attempt')
            db.execute('UPDATE attempts SET status=?,updated_utc=? WHERE attempt_id=?', ('released', _utc(), attempt_id))
            self._event(db, attempt_id, 'released_uncharged', {'evidence': evidence})

    def snapshot(self) -> dict:
        with self._transaction() as db:
            rows = db.execute('SELECT status,COUNT(*),SUM(reserved),SUM(actual) FROM attempts GROUP BY status').fetchall()
            committed = self._committed(db)
            halted = bool(db.execute("SELECT value FROM config WHERE key='halted'").fetchone()[0])
        counts = {r[0]: r[1] for r in rows}
        actual = sum((r[3] or 0) for r in rows if r[0] == 'settled')
        reserved = sum((r[2] or 0) for r in rows if r[0] in ('reserved', 'unknown'))
        unknown = sum((r[2] or 0) for r in rows if r[0] == 'unknown')
        return {
            'db_path': str(self.path), 'hard_usd': self.hard / NANODOLLARS,
            'target_usd': self.target / NANODOLLARS, 'actual_usd': actual / NANODOLLARS,
            'reserved_usd': reserved / NANODOLLARS, 'unknown_usd': unknown / NANODOLLARS,
            'committed_usd': committed / NANODOLLARS,
            'remaining_hard_usd': (self.hard - committed) / NANODOLLARS,
            'remaining_target_usd': (self.target - committed) / NANODOLLARS,
            'attempt_counts': counts, 'journal_mode': 'DELETE',
            'halted': halted,
            'pricing_revision': PRICING_REVISION,
            'invoice_reconciled': False,
            'forecast_usd': None,  # forecasts are not charges or reservations
        }


def request_input_upper_bound(request: dict) -> int:
    """Conservative byte/token bound for text-only Chat messages + strict schema.

UTF-8 bytes upper-bound byte-level tokenization. Add generous protocol/schema
overhead; forbid unknown multimodal/tool inputs rather than guess their price.
"""
    messages = request.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('Text-only messages required')
    for message in messages:
        if not isinstance(message.get('content'), str) or set(message) - {'role', 'content', 'name'}:
            raise ValueError('Unsupported non-text or tool message')
    if any(k in request for k in ('tools', 'functions', 'audio', 'prediction', 'stream')):
        raise ValueError('Only non-streaming text/schema calls are budgeted')
    payload = {'messages': messages, 'response_format': request.get('response_format', {})}
    return len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) + 4096 + 256 * len(messages)
