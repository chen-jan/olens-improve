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
STANDARD_RATES = {'input': Decimal('0.10'), 'cached_input': Decimal('0.01'), 'output': Decimal('0.50')}
UNKNOWN_CLAUDE_ID = 'claude-review-unconfirmed-20261009'


class BudgetExceeded(RuntimeError):
    pass


def usd_units(value: str | float | Decimal) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError('Spend must be finite and nonnegative')
    return int((amount * NANODOLLARS).to_integral_value(rounding=ROUND_CEILING))


def cost_units(input_tokens: int, output_tokens: int, cached_tokens: int = 0,
               billed_tier: str = 'default') -> int:
    if min(input_tokens, output_tokens, cached_tokens) < 0 or cached_tokens > input_tokens:
        raise ValueError('Invalid token accounting')
    if billed_tier not in ('default', 'standard', 'flex'):
        raise ValueError(f'Unpriced service tier: {billed_tier}')
    discount = Decimal('0.5') if billed_tier == 'flex' else Decimal(1)
    dollars = ((input_tokens - cached_tokens) * STANDARD_RATES['input']
               + cached_tokens * STANDARD_RATES['cached_input']
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
                        attempt_id: str | None = None) -> str:
        if input_upper_tokens <= 0 or max_output_tokens <= 0:
            raise ValueError('Positive input/output bounds required')
        # Reserve Standard prices even for Flex: a billed tier fallback is covered.
        amount = cost_units(input_upper_tokens, max_output_tokens)
        aid = attempt_id or str(uuid.uuid4())
        details = dict(metadata or {})
        details.update(input_upper_tokens=input_upper_tokens, max_output_tokens=max_output_tokens,
                       reservation_pricing='standard; all input uncached')
        with self._transaction() as db:
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
               response_id: str | None = None) -> None:
        amount = cost_units(input_tokens, output_tokens, cached_tokens, billed_tier)
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
                        reservation_exceeded=amount > row[1]))
            if amount > row[1]:
                db.execute("UPDATE config SET value=1 WHERE key='halted'")
        if amount > row[1]:
            # Never conceal actual billing, even if an input-bound assumption failed.
            raise BudgetExceeded('Actual usage exceeded reservation; billing recorded, stop and reconcile bounds')

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
