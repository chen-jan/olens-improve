"""Cache-write price bounds and append-only historical usage correction."""
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from olens_improve.budget import AtomicBudget, cost_units


class CacheWritePricingTests(unittest.TestCase):
    def test_mixed_input_and_flex_prices(self):
        self.assertEqual(cost_units(1000,100,200,'default',300),139500)
        self.assertEqual(cost_units(1000,100,200,'flex',300),69750)
        # Existing fourth positional argument remains the tier.
        self.assertEqual(cost_units(1000,100,200,'default'),132000)

    def test_invalid_counts_are_rejected(self):
        for args in [(10,1,6,'default',5),(10,1,0,'default',-1),
                     (10,1,0,'default',True),(10,1,0,'default',1.5)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                cost_units(*args)

    def test_reservation_covers_all_write_input(self):
        with TemporaryDirectory() as tmp:
            ledger=AtomicBudget(Path(tmp)/'ledger.sqlite3',bootstrap_claude=False)
            aid=ledger.reserve_attempt(1000,100,run_id='fixture')
            self.assertEqual(ledger.snapshot()['reserved_usd'],.000175)
            ledger.settle(aid,input_tokens=1000,output_tokens=100,cache_write_tokens=1000)
            self.assertEqual(ledger.snapshot()['actual_usd'],.000175)
            self.assertFalse(ledger.snapshot()['halted'])

    def test_reconciliation_preserves_events_and_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.sqlite3';ledger=AtomicBudget(path,bootstrap_claude=False)
            aid=ledger.reserve_attempt(1000,100,run_id='fixture')
            ledger.record_evidence(aid,'physical_response',{'billed_tier':'default','response_id':'fixture',
                'response':{'usage':{'prompt_tokens':1000,'completion_tokens':100,
                    'prompt_tokens_details':{'cached_tokens':200,'cache_write_tokens':300}}}})
            ledger.settle(aid,input_tokens=1000,output_tokens=100,cached_tokens=200)
            before=ledger.snapshot()['actual_usd'];plan=ledger.preview_cache_write_reconciliation()
            self.assertEqual(ledger.snapshot()['actual_usd'],before)
            self.assertAlmostEqual(plan['actual_delta_usd'],.0000075)
            with sqlite3.connect(path) as db:
                original=list(db.execute("SELECT sequence,kind,details FROM events WHERE kind IN ('physical_response','settled')"))
            ledger.reconcile_cache_write_pricing(evidence='Offline fixture; retained raw usage')
            self.assertEqual(ledger.snapshot()['actual_usd'],.0001395)
            again=ledger.reconcile_cache_write_pricing(evidence='Offline fixture repeat')
            self.assertEqual(again['settled_changes'],[])
            self.assertEqual(again['actual_delta_usd'],0)
            with sqlite3.connect(path) as db:
                self.assertEqual(original,list(db.execute("SELECT sequence,kind,details FROM events WHERE kind IN ('physical_response','settled')")))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE kind='pricing_correction'").fetchone()[0],1)

    def test_unknown_reservation_increases_and_missing_fields_stay_visible(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.sqlite3';ledger=AtomicBudget(path,bootstrap_claude=False)
            unknown=ledger.reserve_attempt(1000,100,run_id='fixture')
            ledger.mark_unknown(unknown,'Offline timeout fixture')
            # Simulate the previous lower tariff in this isolated fixture only.
            with sqlite3.connect(path) as db:
                db.execute('UPDATE attempts SET reserved=? WHERE attempt_id=?',(150000,unknown))
            settled=ledger.reserve_attempt(1000,100,run_id='fixture')
            ledger.record_evidence(settled,'physical_response',{'response':{'usage':{
                'prompt_tokens':1000,'completion_tokens':100,'prompt_tokens_details':{'cached_tokens':0}}}})
            ledger.settle(settled,input_tokens=1000,output_tokens=100)
            plan=ledger.preview_cache_write_reconciliation()
            self.assertEqual(plan['missing_usage'],[settled])
            self.assertAlmostEqual(plan['reservation_delta_usd'],.000025)
            ledger.reconcile_cache_write_pricing(evidence='Offline unknown reservation fixture')
            self.assertEqual(ledger.snapshot()['unknown_usd'],.000175)
            again=ledger.preview_cache_write_reconciliation()
            self.assertEqual(again['reservation_changes'],[])


if __name__=='__main__':unittest.main()
