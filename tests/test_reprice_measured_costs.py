"""Physical-attempt accounting and frozen-source guards."""
import importlib.util
from pathlib import Path
import sqlite3
import unittest

spec = importlib.util.spec_from_file_location('reprice', Path(__file__).parents[1] / 'scripts/reprice_measured_costs.py')
reprice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reprice)


class RepricingTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE attempts(attempt_id TEXT,status TEXT,actual INTEGER)')
        self.db.executemany('INSERT INTO attempts VALUES(?,?,?)', [('a','settled',1000),('b','settled',2000),('pending','unknown',None)])

    def tearDown(self):
        self.db.close()

    def test_changed_and_unchanged_physical_requests_are_both_counted(self):
        original={'physical_attempt_ids':['a','b'],'actual_usd':.000003}
        revised=reprice.corrected_cost(original,self.db,{'a':{'before_units':1000,'after_units':1250,'cache_write_tokens':10}})
        self.assertEqual(revised['actual_usd'],.00000325)
        self.assertEqual(original['actual_usd'],.000003)
        self.assertFalse(revised['invoice_reconciled'])
        self.assertNotIn('physical_attempt_ids',revised)

    def test_duplicate_attempt_cannot_double_count(self):
        with self.assertRaisesRegex(ValueError,'Repeated'):
            reprice.corrected_cost({'physical_attempt_ids':['a','a'],'actual_usd':.000002},self.db,{})

    def test_source_total_or_correction_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'differs'):
            reprice.corrected_cost({'physical_attempt_ids':['a'],'actual_usd':0},self.db,{})
        with self.assertRaisesRegex(ValueError,'does not bind'):
            reprice.corrected_cost({'physical_attempt_ids':['a'],'actual_usd':.000001},self.db,{'a':{'before_units':999,'after_units':1250,'cache_write_tokens':10}})

    def test_unknown_request_never_promoted_to_actual_cost(self):
        with self.assertRaisesRegex(ValueError,'settled'):
            reprice.corrected_cost({'physical_attempt_ids':['pending'],'actual_usd':0},self.db,{})


if __name__=='__main__':
    unittest.main()
