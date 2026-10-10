import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'scripts')]
spec = importlib.util.spec_from_file_location('descriptive_grid', ROOT/'scripts/descriptive_grid_audit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GridAuditTests(unittest.TestCase):
    def test_related_items_are_one_group(self):
        r = mod.grouped_rate([('a',1,1),('b',0,1)], {'a':'same','b':'same'})
        self.assertEqual(r['value'],.5)
        self.assertEqual(r['independent_groups'],1)
        self.assertIsNone(r['ci95'])

    def test_zero_denominator_is_undefined(self):
        r=mod.grouped_rate([('a',0,0),('b',0,0)],{'a':'g1','b':'g2'},replicates=20)
        self.assertIsNone(r['value'])
        self.assertIsNone(r['ci95'])
        self.assertEqual(r['defined_draws'],0)

    def test_weighted_cell_rate_and_seed(self):
        rows=[('a',1,4),('b',2,2)]; groups={'a':'g1','b':'g2'}
        a=mod.grouped_rate(rows,groups,replicates=200)
        self.assertEqual(a['value'],.5)
        self.assertEqual(a,mod.grouped_rate(rows,groups,replicates=200))
        self.assertEqual(a['ci95'],[.25,1.])

    def test_test_rejected_before_source_access(self):
        with patch.object(Path,'read_text',side_effect=AssertionError('outcomes opened')):
            with self.assertRaisesRegex(ValueError,'DEV/VAL'):
                mod.load_stage({'stage':'test','manifest':'forbidden'})

    def test_missing_cell_is_not_zero(self):
        c=[{'cell_id':'a','family':'hallucination','item_id':'i','layer':20,
            'position':1,'group_id':'g'}]
        with self.assertRaisesRegex(ValueError,'Missing or foreign'):
            mod.audit_family(c,{},'hallucination')


if __name__=='__main__':unittest.main()
