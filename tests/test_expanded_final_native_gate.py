import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('gate',Path(__file__).resolve().parents[1]/'scripts/expanded_final_native_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
class FinalGateTests(unittest.TestCase):
 def records(self):
  return [(Path('canonical')/(f+'.ready.json'),{'ready':True,'inventory_sha256':gate.MANIFEST_SHA,'family':f,'conditions':[{'method':'a','n':1},{'method':'b','n':2}]})for f in ('left','right')]
 def test_complete_exact_menu(self):self.assertEqual(len(gate.index_descriptors(self.records(),{'a-n1','b-n2'},('left','right'))),4)
 def test_missing_family_cannot_seal(self):
  with self.assertRaisesRegex(ValueError,'incomplete'):gate.index_descriptors(self.records()[:1],{'a-n1','b-n2'},('left','right'))
 def test_duplicate_same_condition_cannot_double_count(self):
  rows=self.records()
  with self.assertRaisesRegex(ValueError,'Duplicate'):gate.index_descriptors(rows+[rows[0]],{'a-n1','b-n2'},('left','right'))
 def test_queue_copy_cannot_enter_canonical_snapshot(self):
  rows=self.records();rows[0]=(Path('_queue_semantic')/'left.ready.json',rows[0][1])
  with self.assertRaisesRegex(ValueError,'Queue alias'):gate.index_descriptors(rows,{'a-n1','b-n2'},('left','right'))
 def test_boolean_n_is_not_integer_condition(self):
  rows=self.records();rows[0][1]['conditions'][0]['n']=True
  with self.assertRaisesRegex(ValueError,'Malformed'):gate.index_descriptors(rows,{'a-n1','b-n2'},('left','right'))
 def test_changed_source_pin_is_rejected(self):
  with tempfile.TemporaryDirectory()as folder:
   p=Path(folder)/'terminal.json';p.write_text('first');pins={str(p):gate.sha(p)};gate.pins_unchanged(pins);p.write_text('changed')
   with self.assertRaisesRegex(ValueError,'Pinned source changed'):gate.pins_unchanged(pins)
if __name__=='__main__':unittest.main()
