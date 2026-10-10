"""Parent/provenance regression fixtures; no model loading or fitting."""
import importlib.util
from pathlib import Path
import unittest
import contextlib
import io

spec=importlib.util.spec_from_file_location('combine_pruning',Path(__file__).parents[1]/'scripts/combine_pruning.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CombinationParentTests(unittest.TestCase):
    def base_args(self):
        return [part for field in ('selectors','manifest','fresh-manifest','production-cache','whitener-directory','output') for part in ('--'+field,'fixture')]
    def selectors(self):
        return {'selections':[{'method':m,'n':32,'text':m,'atoms':[{'phrase_id':m}],'fits':{'exact':{'fve':.5}}} for m in module.parent_methods(False)]}
    def test_no_edit_paths_required_and_no_edit_provenance(self):
        args=module.parse_args(self.base_args())
        self.assertIsNone(args.edits);self.assertIsNone(args.editing_cache)
        self.assertEqual([p[0] for p in module.parent_records(self.selectors())],['pooled_greedy_swap','best_n_specificity_mean'])
        self.assertNotIn('editing_history_sha256',module.optional_edit_provenance(None))
    def test_edit_paths_must_be_a_pair(self):
        for flag in ('--edits','--editing-cache'):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):module.parse_args(self.base_args()+[flag,'fixture'])
    def test_old_parent_order_and_fields_preserved_with_edits(self):
        edit={'best':{'text':'edited','atom_metadata':[{'source_phrase_id':'edited'}],'exact_fve':.7}}
        parents=module.parent_records(self.selectors(),edit)
        self.assertEqual([p[0] for p in parents],module.parent_methods(True))
        self.assertEqual(parents[-1],('editing_round2','edited',edit['best']['atom_metadata'],.7))
        self.assertEqual(module.optional_edit_provenance('frozen'),{'editing_history_sha256':'frozen'})
    def test_missing_or_duplicate_selector_parent_rejected(self):
        row=self.selectors();row['selections'].append(row['selections'][0])
        with self.assertRaises(ValueError):module.parent_records(row)

if __name__=='__main__':unittest.main()
