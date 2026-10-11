"""Presentation conversion fixtures never rescore or mutate source objects."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node') or '${HOME}/.nvm/versions/node/v24.14.0/bin/node'


@unittest.skipUnless(Path(NODE).exists(), 'Requires an existing Node executable')
class PresentationConversion(unittest.TestCase):
    def evaluate(self, payload, expression):
        program = '''const fs=require('node:fs'),vm=require('node:vm');
const payload=JSON.parse(fs.readFileSync(0,'utf8'));const context=vm.createContext({payload});
const source=fs.readFileSync(process.argv[1],'utf8').replace(/\\nstart\\(\\);\\s*$/,'');
vm.runInContext(source,context);process.stdout.write(JSON.stringify(vm.runInContext(process.argv[2],context)));'''
        result = subprocess.run([NODE, '-e', program, str(ROOT/'dashboard/expansion.js'), expression],
                                input=json.dumps(payload), text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_budget_uses_actual_settled_usage_and_preserves_retained_holds(self):
        ledger = {'global_commitment': [
            {'status': 'settled', 'reserved_usd': 2771.8302011, 'actual_usd': 127.137685285},
            {'status': 'unknown', 'reserved_usd': 4.8945515, 'actual_usd': 0},
            {'status': 'reserved', 'reserved_usd': 0.49453675, 'actual_usd': 0}], 'limits': {'hard': 340}}
        result = self.evaluate(ledger, '({accounting:projectAccounting(payload),source:payload})')
        self.assertEqual(result['source'], ledger)
        self.assertAlmostEqual(result['accounting']['settled'], 127.137685285)
        self.assertAlmostEqual(result['accounting']['committed'], 132.526773535)
        self.assertEqual(result['accounting']['ceiling'], 340)

    def test_percent_and_percentage_point_conversion_keeps_negative_fit(self):
        result = self.evaluate({}, '({mean:fve(.425004),change:fveDelta(.054074),negative:fve(-.05),missing:fve(null)})')
        self.assertEqual(result, {'mean': '42.50%', 'change': '+5.41 pp', 'negative': '-5.00%', 'missing': 'Unavailable'})

    def test_parent_names_escape_labels_and_keep_exact_id_in_tooltip(self):
        result = self.evaluate({}, '''data={conditions:[{condition_id:'best_n_exact-n32',label:'Choose the best complete readout (32 samples)'}]}; conditionLabel('best_n_exact-n32')''')
        self.assertEqual(result, "<span title='best_n_exact-n32'>Choose the best complete readout (32 samples)</span>")


if __name__ == '__main__':
    unittest.main()
