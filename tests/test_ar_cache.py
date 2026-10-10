import json
import unittest
from olens_improve.ar_cache import input_records, vector_key
from olens_improve.contrastive import control_specificity


class ARCacheTests(unittest.TestCase):
    def test_committed_envelopes_and_rows(self):
        data = json.dumps({'records': [{'text': 'first'}, {'text': 'second'}]})+'\n'
        data += json.dumps({'text': 'third'})+'\n{"text":'
        self.assertEqual([r['text'] for r in input_records(data.encode())], ['first', 'second', 'third'])

    def test_bad_completed_line_rejected(self):
        with self.assertRaises(json.JSONDecodeError):
            list(input_records(b'{invalid}\n'))

    def test_effective_input_keys(self):
        key = vector_key('contract', [1, 2], [3, 4])
        self.assertEqual(key, vector_key('contract', [1, 2], [3, 4]))
        for args in [('other', [1, 2], [3, 4]), ('contract', [1, 9], [3, 4]), ('contract', [1, 2], [3, 5])]:
            self.assertNotEqual(key, vector_key(*args))

    def test_mean_primary_max_ablation(self):
        result = control_specificity(.3, {'a': .1, 'b': .2})
        self.assertAlmostEqual(result['score'], .15)
        self.assertAlmostEqual(result['max_specificity'], .1)
        self.assertEqual(result['aggregation'], 'mean')
        self.assertAlmostEqual(control_specificity(.3, {'a': .1, 'b': .2}, aggregation='max')['score'], .1)
