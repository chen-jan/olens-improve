import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
import sys
sys.path.insert(0, str(SCRIPTS))
import expanded_api
import expanded_judges
from olens_improve.helpers import HelperCache


def test_records_preserve_atomic_generation_envelopes(tmp_path):
    path = tmp_path/'records.jsonl'
    path.write_text(json.dumps({'records':[{'cell_id':'a','text':'original'},
                                         {'cell_id':'b','text':'unchanged'}]})+'\n'+
                    json.dumps({'cell_id':'c','text':'third'})+'\n')
    assert list(expanded_api.records(path)) == [
        {'cell_id':'a','text':'original'},{'cell_id':'b','text':'unchanged'},
        {'cell_id':'c','text':'third'}]


def test_helper_coalesces_identical_inflight_requests_and_uses_exact_cache(tmp_path):
    async def check():
        class Completion:
            calls = 0
            async def create(self, **request):
                self.calls += 1
                await asyncio.sleep(.01)
                return SimpleNamespace(id='response1',choices=[SimpleNamespace(finish_reason='stop',
                    message=SimpleNamespace(content='{"ok":true}',refusal=None))])
        completions = Completion()
        helper = expanded_api.ForecastingHelper(
            SimpleNamespace(chat=SimpleNamespace(completions=completions)),
            HelperCache(tmp_path/'cache.sqlite3'),forecast_log=tmp_path/'forecast.jsonl',
            concurrency=64, attempts=1)
        schema = {'type':'json_schema','json_schema':{'name':'test','schema':{'type':'object'}}}
        def validate(result):
            assert result == {'ok':True}
        values = await asyncio.gather(*(helper.call('system',{'text':'same'},schema,
            version='test-v1',validate=validate) for _ in range(8)))
        assert values == [{'ok':True}]*8
        assert completions.calls == 1
        assert helper.fresh_completions == 1
        assert await helper.call('system',{'text':'same'},schema,version='test-v1',validate=validate) == {'ok':True}
        assert completions.calls == 1
        forecast = [json.loads(line) for line in (tmp_path/'forecast.jsonl').read_text().splitlines()]
        assert len({r['request_key'] for r in forecast}) == 1
        assert sum(r['coalesced_inflight'] for r in forecast) == 7
        assert forecast[-1]['validated_cache_hit']
    asyncio.run(check())


def test_expansion_cohort_requires_whole_family_and_original_split(tmp_path):
    rows = [{'cell_id':str(i),'family':'hallucination','item_id':str(i),'layer':20,
             'position':i,'split':'test','activation_sha256':str(i)*64} for i in range(2)]
    fresh = tmp_path/'fresh.json'
    fresh.write_text(json.dumps({'cells':rows}))
    inventory = {'fresh_manifest':{'path':str(fresh),'sha256':expanded_api.digest(fresh)}}
    cohort = tmp_path/'cohort.json'
    cohort.write_text(json.dumps({'inventory_sha256':'sealed','cells':rows}))
    expanded_judges.expansion_cohort(cohort,inventory,'sealed')
    changed = json.loads(cohort.read_text())
    changed['cells'][0]['split'] = 'development'
    cohort.write_text(json.dumps(changed))
    with unittest.TestCase().assertRaisesRegex(ValueError,'Original split'):
        expanded_judges.expansion_cohort(cohort,inventory,'sealed')
    cohort.write_text(json.dumps({'inventory_sha256':'sealed','cells':rows[:1]}))
    with unittest.TestCase().assertRaisesRegex(ValueError,'full-bank'):
        expanded_judges.expansion_cohort(cohort,inventory,'sealed')


def test_ready_descriptor_accepts_reviewed_singular_selection_hash(tmp_path):
    cohort = tmp_path/'cohort.json'
    cohort.write_text(json.dumps({'cells':[{'family':'hallucination'}]}))
    selections = tmp_path/'selections.jsonl'
    selections.write_text('{}\n')
    descriptor = tmp_path/'family.ready.json'
    descriptor.write_text(json.dumps({'family':'hallucination','ready':True,
        'manifest':str(cohort),'manifest_sha256':expanded_api.digest(cohort),
        'selections':str(selections),'selection_sha256':expanded_api.digest(selections),
        'conditions':[{'method':'method','n':16}]}))
    args = SimpleNamespace(family='hallucination',inventory_sha256='sealed')
    inventory = {'conditions':[{'method':'method','n':16,'status':'scheduled_full_bank'}]}
    assert expanded_judges.validate_ready(descriptor,args,inventory)[1] == [{'method':'method','n':16}]


def load_tests(loader, suite, pattern):
    result = unittest.TestSuite()
    for name, function in sorted(globals().items()):
        if name.startswith('test_') and callable(function):
            def run(fn=function):
                with tempfile.TemporaryDirectory() as directory:
                    fn(Path(directory))
            result.addTest(unittest.FunctionTestCase(run, description=name))
    return result
