import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import analyze_development_scaling as report


class DevelopmentScalingTests(unittest.TestCase):
    def test_exact_order_and_no_extra_arms(self):
        rows = [{'method':m,'n':n} for m,n in report.ORDER]
        report.validate_menu(rows)
        for wrong in [rows[:-1], rows[::-1], rows+[{'method':'pooled_greedy_swap','n':32}]]:
            with self.assertRaises(ValueError): report.validate_menu(wrong)

    def test_reject_literal_text_mismatch_and_missing_cell(self):
        conditions = [{'method':'best_n_exact','n':2}]
        cells = {'c':{'family':'hallucination'}}
        retained = {'best_n_exact-n2':{'c':{'text':'the exact judged text'}}}
        row = {'cell_id':'c','family':'hallucination','selections':[
            {'method':'best_n_exact','n':2,'text':'different','token_count':2,'bullet_count':1}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'s.jsonl';path.write_text(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError,'differs'):
                report.collect_lengths(path,cells,conditions,retained)
            path.write_text('')
            with self.assertRaisesRegex(ValueError,'lacks'):
                report.collect_lengths(path,cells,conditions,retained)

    def test_empty_output_is_retained_and_duplicate_rejected(self):
        conditions = [{'method':'best_n_exact','n':1}]
        cells = {'c':{'family':'role_bound_association'}}
        retained = {'best_n_exact-n1':{'c':{'text':''}}}
        row = {'cell_id':'c','family':'role_bound_association','selections':[
            {'method':'best_n_exact','n':1,'text':'','token_count':0,'bullet_count':0}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'s.jsonl';line=json.dumps(row)+'\n';path.write_text(line)
            result=report.collect_lengths(path,cells,conditions,retained)
            self.assertEqual(result['best_n_exact-n1']['role_bound_association']['empty_outputs'],1)
            path.write_text(line+line)
            with self.assertRaisesRegex(ValueError,'duplicate'):
                report.collect_lengths(path,cells,conditions,retained)


if __name__ == '__main__': unittest.main()
