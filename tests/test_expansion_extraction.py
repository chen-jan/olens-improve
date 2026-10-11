"""Native endpoint and partial-grid extraction fixtures, without API calls."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_expansion import filtered_result
from olens_improve.reporting import family_counts, original_grid_pairs

def cell(item,layer,pos=0):return {'cell_id':f'{item}:{layer}:{pos}','item_id':item,'layer':layer,'position':pos}
def read(item,layer,text='- source',pos=0):return {'id':item,'layer':layer,'pos':pos,'samples':[text]}

class ExpansionExtractionTests(unittest.TestCase):
    def test_arithmetic_full_question_any_is_distinct_from_cell_accuracy(self):
        cells=[cell('x',20),cell('x',24),cell('x',28),cell('y',20),cell('y',24)]
        reads=[read(c['item_id'],c['layer']) for c in cells]
        result={'rows':[{'id':'x','pass':True,'kind_by_layer':{'20':'hit','24':'miss','28':'miss'}},
                        {'id':'y','pass':False,'kind_by_layer':{'20':'miss','24':'miss'}}],
                'numbers':{'metric':'pass_rate','value':.5}}
        values,coverage=family_counts('chain_intermediates',cells,reads,result)
        self.assertEqual(values['cell_recovery'],{'x':(1,3),'y':(0,2)})
        self.assertEqual(original_grid_pairs('chain_intermediates',values,result)['original_grid_item_pass_rate'],{'x':(1,1),'y':(0,1)})
        self.assertEqual(coverage['missing_stage1'],0)

    def test_hall_native_denominator_keeps_offtopic_and_empty_coverage(self):
        cells=[cell('x',20,i) for i in range(4)]
        reads=[read('x',20,'' if i==3 else '- source',i) for i in range(4)]
        rows=[]
        for i,kind in enumerate(('hallucinated','off_topic','consistent')):
            rows.append({'id':'x','layer':20,'pos':i,'samples':['- source'],'verdict':[{'idx':0,'class':kind,'claims':{'false':int(i==0),'true':int(i==2),'unverifiable':int(i==1)}}]})
        result={'rows':rows,'numbers':{'metric':'hallucination_rate','value':1/3}}
        values,coverage=family_counts('hallucination',cells,reads,result)
        self.assertEqual(values['contradiction_rate']['x'],(1,3))
        self.assertEqual(values['assertion_share']['x'],(3,4))
        self.assertEqual(values['off_topic_rate']['x'],(1,3))
        self.assertEqual(coverage['empty_abstentions'],1)
        original_grid_pairs('hallucination',values,result)
        result['rows'][0]['verdict'][0].pop('claims')
        _,missing=family_counts('hallucination',cells,reads,result)
        self.assertEqual(missing['missing_stage2'],1)

    def test_multihop_requires_every_bridge_at_one_site(self):
        cells=[cell('x',20),cell('x',24)];reads=[read('x',20),read('x',24)]
        result={'rows':[{'id':'x','roles':['a','b'],'pass':True,
            'layers':{'20':{'hits':{'a':True,'b':False}},'24':{'hits':{'a':True,'b':True}}}}],
            'numbers':{'metric':'pass_rate','value':1.}}
        values,coverage=family_counts('multihop_mt',cells,reads,result)
        self.assertEqual(values['cell_recovery']['x'],(1,2))
        self.assertEqual(original_grid_pairs('multihop_mt',values,result)['original_grid_item_pass_rate']['x'],(1,1))

    def test_partial_pilot_drops_unselected_hall_and_role_rows(self):
        result={'rows':[{'id':'x','layer':20,'pos':0},{'id':'x','layer':20,'pos':1},{'id':'y','layer':20,'pos':0}]}
        for family in ('hallucination','role_bound_association'):
            subset=filtered_result(result,family,[cell('x',20,1)])
            self.assertEqual(subset['rows'],[result['rows'][1]])

if __name__=='__main__':unittest.main()
