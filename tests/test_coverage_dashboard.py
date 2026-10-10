"""Synthetic coverage/rank/missingness contracts; no inference or quality data."""
import copy
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).parents[1]/'scripts'/'coverage_dashboard.py'
s=importlib.util.spec_from_file_location('coverage_test',p);coverage=importlib.util.module_from_spec(s);s.loader.exec_module(coverage)


def fixture(stage='validation'):
    cells=[]
    for f in coverage.FAMILIES:
        for item,offset in [('a',0),('b',100)]:
            for layer in [20,44]:
                for pos in ([10,20] if f in ('hallucination','role_bound_association') else [20]):
                    cells.append({'cell_id':f'{f}:{item}:{layer}:{pos+offset}','family':f,'item_id':item,'layer':layer,'position':pos+offset})
    grids=coverage.grouped_grid(cells)
    section={'stage':stage,'source_sha256':'a'*64,'review_metadata_sha256':'b'*64,
        'identities':{'manifest_sha256':'c'*64},'condition_ids':['capped_n1-n1'],
        'review':{},'family_counts':{f:{'cells':g['cells'],'items':g['items']} for f,g in grids.items()}}
    return section,{'split':stage,'cells':cells}


class CoverageTests(unittest.TestCase):
    def reviewed(self):
        section,manifest=fixture();row=coverage.prepare(section,manifest,'c'*64)
        row.update(status='root_reviewed',reviewed_by='synthetic reviewer')
        return section,manifest,row

    def test_within_item_rank_not_absolute_token_bucket(self):
        _,manifest=fixture();g=coverage.grouped_grid(manifest['cells'])
        role=g['role_bound_association'];self.assertEqual(role['position_ranks'],[1,2])
        self.assertEqual([(r['layer'],r['position_rank'],r['expected_cells']) for r in role['slots']],[(20,1,2),(20,2,2),(44,1,2),(44,2,2)])
        self.assertEqual(g['chain_intermediates']['position_ranks'],[1])

    def test_duplicate_cell_is_not_another_vote(self):
        _,manifest=fixture();manifest['cells'].append(manifest['cells'][0])
        with self.assertRaises(ValueError):coverage.grouped_grid(manifest['cells'])

    def test_pending_metadata_and_foreign_manifest_rejected(self):
        section,manifest=fixture();row=coverage.prepare(section,manifest,'c'*64)
        with self.assertRaises(ValueError):coverage.render(row,section,str)
        with self.assertRaises(ValueError):coverage.prepare(section,manifest,'d'*64)

    def test_missing_stays_unknown_and_html_escaped(self):
        section,_,row=self.reviewed();r=row['families']['role_bound_association']['slots'][0]
        r.update(accounted_cells=None,missing_required_results=None)
        row['position_definition']='rank <unsafe>'
        rendered=coverage.render(row,section,str)
        self.assertIn('Required-result coverage: unknown',rendered)
        self.assertIn('coverage unknown',rendered);self.assertIn('&lt;unsafe&gt;',rendered)
        self.assertIn('Single final prompt-token',rendered)

    def test_test_remains_sealed(self):
        section,manifest=fixture('test')
        with self.assertRaises(ValueError):coverage.prepare(section,manifest,'c'*64)
        section['review']['test_reveal_authorized']=True
        row=coverage.prepare(section,manifest,'c'*64);row.update(status='root_reviewed',reviewed_by='synthetic reviewer')
        coverage.validate(row,section)
        section['review']['test_reveal_authorized']=False
        with self.assertRaises(ValueError):coverage.validate(row,section)

    def test_counts_missingness_and_menu_are_bound(self):
        section,_,row=self.reviewed()
        bad=copy.deepcopy(row);bad['condition_ids'].append('foreign-n32')
        with self.assertRaises(ValueError):coverage.validate(bad,section)
        bad=copy.deepcopy(row);bad['families']['hallucination']['slots'][0]['missing_required_results']=1
        with self.assertRaises(ValueError):coverage.validate(bad,section)
        bad=copy.deepcopy(row);bad['families']['hallucination']['slots'][0].update(accounted_cells=1,missing_required_results=1)
        with self.assertRaises(ValueError):coverage.validate(bad,section)
        bad=copy.deepcopy(row);bad['families']['hallucination']['slots'].append(bad['families']['hallucination']['slots'][0])
        with self.assertRaises(ValueError):coverage.validate(bad,section)

if __name__=='__main__':unittest.main()
