import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_expansion_qualitative import choose_cases

def verdict(text,passed=False,kind=None):
    return {'text':text,'pass':passed,'class':kind}

def test_question_win_requires_whole_grid_change_and_passing_witness():
    cells={'a0':{'item_id':'a'},'a1':{'item_id':'a'},'b0':{'item_id':'b'},'b1':{'item_id':'b'}}
    base={'a0':verdict('before'),'a1':verdict('before',True),'b0':verdict('before'),'b1':verdict('before')}
    prop={'a0':verdict('after',True),'a1':verdict('before'),'b0':verdict('after'),'b1':verdict('after',True)}
    cases,counts=choose_cases(base,prop,cells,'chain_intermediates')
    wins=[case for case in cases if case[0]=='win']
    assert wins[0][1]=='b1'
    assert wins[0][2]['grid_cells']==2
    assert wins[0][2]['baseline_item_pass'] is False
    assert counts['changed_no_endpoint_change']==1

def test_hall_deletion_or_offtopic_is_not_a_consistent_win():
    cells={cid:{'item_id':cid} for cid in ('a','b','c','d')}
    base={cid:verdict('before',kind='hallucinated') for cid in cells}
    prop={'a':verdict('',kind='empty'),'b':verdict('unrelated',kind='off_topic'),
          'c':verdict('after',kind='consistent'),'d':verdict('changed wrong',kind='hallucinated')}
    cases,counts=choose_cases(base,prop,cells,'hallucination')
    assert [(category,cid) for category,cid,outcome in cases]==[('win','c'),('changed_no_endpoint_change','d')]
    assert counts=={'win':1,'changed_no_endpoint_change':1}

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for fn in
        (test_question_win_requires_whole_grid_change_and_passing_witness,
         test_hall_deletion_or_offtopic_is_not_a_consistent_win))
