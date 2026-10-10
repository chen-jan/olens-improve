import unittest
from olens_improve.editing import validate_lineage,validated_sample


class EditingTests(unittest.TestCase):
    def test_wrong_parent_and_changed_history_rejected(self):
        row={'parents':[{'candidate_id':'source','text':'- A does not own 3 books.'}],
             'editing':{'proposals':[{'candidate_id':'new','parent_candidate_id':'source','text':'- A owns 3 books.'}]}}
        validate_lineage(row,[],1)
        row['editing']['proposals'][0]['parent_candidate_id']='other-cell'
        with self.assertRaises(ValueError):validate_lineage(row,[],1)
        row['editing']['proposals']=[]
        with self.assertRaises(ValueError):validate_lineage(row,[{'candidate_id':'source','text':'- A owns 3 books.'}],2)

    def test_full_verbatim_atom_and_cap(self):
        text='- A owns books.\n  Bob does not.\n'
        sample=validated_sample(text,'candidate',len)
        self.assertEqual(sample.bullets[0].text,text[sample.bullets[0].start:sample.bullets[0].end])
        with self.assertRaises(ValueError):validated_sample('- '+('x'*257),'overlong',len)
        with self.assertRaises(ValueError):validated_sample('Unmarked wrong content','bad',len)
        self.assertEqual(validated_sample('','empty',len).bullets,())
