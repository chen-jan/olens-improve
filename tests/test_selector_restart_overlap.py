"""A restart audit may exclude bookkeeping, never scientific differences."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('overlap',Path(__file__).parents[1]/'scripts/audit_selector_restart_overlap.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class OverlapTests(unittest.TestCase):
    def test_only_empty_added_atom_metadata_is_ignored(self):
        old={'cell_id':'c','selections':[{'text':'- fact','fve':.5}],'config_sha256':'old','seconds_since_start':3}
        new=old|{'config_sha256':'new','seconds_since_start':8,'invalid_AR_atoms_by_sample':{}}
        self.assertEqual(audit.scientific(old,True),audit.scientific(new,True))
        new['invalid_AR_atoms_by_sample']={'0':[{'reason':'empty'}]}
        with self.assertRaisesRegex(ValueError,'must have empty'):audit.scientific(new,True)

    def test_text_and_numeric_changes_remain_visible(self):
        old={'selections':[{'text':'- fact','fve':.5}]}
        new={'selections':[{'text':'- changed','fve':.51}]}
        changed=audit.differences(old,new)
        self.assertEqual({r['kind'] for r in changed},{'numeric','non_numeric'})
        self.assertAlmostEqual(next(r['absolute_delta'] for r in changed if r['kind']=='numeric'),.01)


if __name__=='__main__':unittest.main()
