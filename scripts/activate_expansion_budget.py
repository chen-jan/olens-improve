"""Apply the explicitly approved expansion ceiling without altering charges."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.ledger, timeout=30, isolation_level=None) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            before = dict(db.execute('SELECT key,value FROM config'))
            if before.get('hard') not in (300_000_000_000, 340_000_000_000):
                raise RuntimeError('Unexpected existing ceiling; refusing to replace it')
            if before.get('target') != 200_000_000_000:
                raise RuntimeError('Unexpected existing target')
            balances = list(db.execute('SELECT status,COUNT(*),COALESCE(SUM(reserved),0),'
                                      'COALESCE(SUM(actual),0) FROM attempts GROUP BY status'))
            db.execute("UPDATE config SET value=340000000000 WHERE key='hard'")
            after = dict(db.execute('SELECT key,value FROM config'))
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
    receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'ledger': str(args.ledger),
               'authorization': 'User explicitly approved expanded plan and goal on 2026-10-11 UTC',
               'before': before, 'after': after, 'unchanged_balance_rows': balances,
               'charge_or_hold_mutations': 0, 'ceiling_usd': 340, 'target_usd': 200}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
