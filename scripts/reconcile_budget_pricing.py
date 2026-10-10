"""Preview by default; explicit reviewed application preserves original billing events."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.budget import AtomicBudget


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--evidence')
    args=parser.parse_args()
    if args.apply and not args.evidence:parser.error('--apply requires reviewed pricing evidence')
    # Preview opens only a read connection, without reinitializing the live DB.
    ledger=AtomicBudget.__new__(AtomicBudget);ledger.path=args.ledger
    if args.apply:
        ledger=AtomicBudget(args.ledger)
        result=ledger.reconcile_cache_write_pricing(evidence=args.evidence)
    else:result=ledger.preview_cache_write_reconciliation()
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'applied':args.apply,'actual_delta_usd':result['actual_delta_usd'],
        'reservation_delta_usd':result['reservation_delta_usd'],
        'settled_changes':len(result['settled_changes']),
        'reservation_changes':len(result['reservation_changes']),
        'missing_usage':len(result['missing_usage']),'invalid_usage':len(result['invalid_usage']),
        'unpriced_unknown_metadata':len(result['unpriced_unknown_metadata']),
        'invoice_reconciled':False}))


if __name__=='__main__':main()
