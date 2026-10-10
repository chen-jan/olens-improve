"""Exact coalescing provenance; synthetic records only, no inference or API."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1]/'scripts'
with patch.object(sys, 'path', [str(SCRIPTS)]+sys.path):
    spec = importlib.util.spec_from_file_location('signed_trace_aliases', SCRIPTS/'analyze_signed_menu.py')
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)


class TraceCacheAliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root/'arm-n32'/'role_bound_association'
        self.folder.mkdir(parents=True)
        self.target = 'a__L020__p3'
        self.representative = 'a__L028__p3'
        self.readouts = [dict(id='a',layer=20,pos=3,samples=['identical claim']),
                         dict(id='a',layer=28,pos=3,samples=['identical claim'])]
        self.raw = {'key':self.representative,'fp':'expected-fingerprint',
                    'meta':{'id':'a','layer':28,'pos':3,'golds':[1,1,1]},
                    'result':{'q1_choice':1,'q2_choice':1,'q3_choice':1,'evidence':'retained response'}}
        self.write_sources()

    def write_sources(self):
        (self.folder.parent/'role_bound_association.readouts.jsonl').write_text(
            ''.join(json.dumps(row)+'\n' for row in self.readouts))
        (self.folder/'cells.jsonl').write_text(json.dumps(self.raw)+'\n')

    @staticmethod
    def builder(row):
        # Deliberately constant fp: tests must also prove full-request equality.
        request = {'model':'gpt-6-luna','reasoning_effort':'none','max_completion_tokens':8192,
                   'messages':[{'role':'system','content':'fixed prompt'},
                               {'role':'user','content':json.dumps({
                                   'text':row['samples'][0],'options':row.get('options','A')})}],
                   'response_format':{'type':'json_schema','json_schema':{'name':'synthetic'}}}
        return request, 'expected-fingerprint'

    def recover(self, records=None):
        return analyzer.recover_coalesced_trace_records(self.folder,'role_bound_association',
            {self.target},records or {self.raw['key']:self.raw},{},request_builder=self.builder)

    def test_exact_alias_preserves_original_response_key_meta_and_sources(self):
        before = copy.deepcopy(self.raw)
        rows, hashes = self.recover()
        recovered = rows[self.target]
        self.assertEqual({k:recovered[k] for k in self.raw}, before)
        self.assertEqual(self.raw, before)
        provenance = recovered['trace_alias_recovery']
        self.assertEqual(provenance['requested_cell_key'],self.target)
        self.assertEqual(provenance['representative_cell_key'],self.representative)
        self.assertEqual(len(provenance['complete_request_key']),64)
        self.assertEqual(provenance['readouts_sha256'],hashes[provenance['readouts_path']])
        self.assertEqual(provenance['representative_cache_sha256'],analyzer.digest(self.folder/'cells.jsonl'))

    def test_same_text_different_item_options_or_fingerprint_cannot_alias(self):
        for change in ('item','options','fingerprint'):
            with self.subTest(change=change):
                self.setUp()
                if change=='item':
                    self.readouts[1]['id']='b';self.raw['key']='b__L028__p3'
                elif change=='options':self.readouts[1]['options']='different options'
                else:self.raw['fp']='wrong-fingerprint'
                self.write_sources()
                with self.assertRaisesRegex(ValueError,'exact retained representative'):self.recover()

    def test_conflicting_exact_responses_are_not_chosen_arbitrarily(self):
        second=copy.deepcopy(self.raw);second['key']='a__L036__p3';second['result']['q1_choice']=2
        self.readouts.append(dict(id='a',layer=36,pos=3,samples=['identical claim']))
        self.write_sources()
        with self.assertRaisesRegex(ValueError,'Ambiguous retained responses'):
            self.recover({self.raw['key']:self.raw,second['key']:second})

    def test_alias_still_rejects_target_official_choice_mismatch(self):
        official={'id':'a','layer':20,'pos':3,'key':self.target,'correct':[True,True,True]}
        (self.folder/'results.json').write_text(json.dumps({'rows':[official]}))
        cell={'item_id':'a','layer':20,'position':3};cells={'target':cell}
        sample={'empty':False,'text':'identical claim'}
        traces=[{'baseline_condition':'arm-n32','condition':'arm-n32','families':{
            'role_bound_association':{'examples':{'unchanged':[{'cell_id':'target',
                'baseline':copy.deepcopy(sample),'proposed':copy.deepcopy(sample)}]}}}}]
        measurement={'conditions':[{'condition':'arm-n32','condition_root':str(self.root)}]}
        contexts={'a':{'exact_upstream_mc_block':'synthetic options','gold_choice_indexes':[1,1,1]}}
        with patch.object(analyzer,'role_contexts',return_value=(contexts,{})), \
             patch.object(analyzer,'trace_request_builder',return_value=self.builder):
            analyzer.enrich_traces(traces,measurement,cells)
            self.raw['result']['q1_choice']=2;self.write_sources()
            with self.assertRaisesRegex(ValueError,'Retained role choices'):
                analyzer.enrich_traces(traces,measurement,cells)


if __name__=='__main__':unittest.main()
