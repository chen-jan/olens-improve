from types import SimpleNamespace
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from expanded_edit_pruning import controls

class Score:
    def score(self,ids):return .5 if 'a' in ids else 0.
    def fit(self,ids):return SimpleNamespace(fve=self.score(ids))

def test_editor_pruning_retains_useful_whole_bullet_and_matches_control_count():
    parent={'candidate_id':'edited','text':'- useful assertion\n- redundant detail','exact_fve':.5,
            'atom_metadata':[{'phrase_id':'a','text':'useful assertion'},{'phrase_id':'b','text':'redundant detail'}]}
    rows=controls('real-cell',parent,Score(),lambda text:len(text.split()))
    assert len(rows)==4
    for prune,random in (rows[:2],rows[2:]):
        assert prune['text']=='- useful assertion'
        assert prune['phrase_ids']==['a']
        assert prune['bullet_count']==random['bullet_count']==1
        assert random['text'] in ('- useful assertion','- redundant detail')

def test_unchanged_single_bullet_preserves_exact_parent_bytes():
    parent={'candidate_id':'edited','text':'  - useful assertion  ','exact_fve':.5,
            'atom_metadata':[{'phrase_id':'a','text':'useful assertion'}]}
    assert all(row['text']==parent['text'] for row in controls('real-cell',parent,Score(),lambda text:len(text.split())))

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for fn in
        (test_editor_pruning_retains_useful_whole_bullet_and_matches_control_count,
         test_unchanged_single_bullet_preserves_exact_parent_bytes))
