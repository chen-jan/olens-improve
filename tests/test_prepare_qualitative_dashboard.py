"""Quote preservation and uncertainty survive public case preparation."""
import unittest
from scripts import prepare_qualitative_dashboard as p


class PreparationTests(unittest.TestCase):
    def test_private_fields_removed_but_qualifications_and_numbers_exact(self):
        text='- I would join; however, I cannot physically attend. 2+2=4.\n'
        source={'text':text,'source_path':'/orcd/private','retained_raw_cache_record':{'response_id':'chatcmpl-private'},
                'claims':{'unverifiable':2},'source_bank_item':{'stimulus':'Marcus acted, not Priya.','generator':'private'}}
        clean=p.cleaned(source)
        self.assertEqual(clean['text'],text)
        self.assertEqual(clean['claims'],{'unverifiable':2})
        self.assertEqual(clean['source_bank_item'],{'stimulus':'Marcus acted, not Priya.'})
        self.assertNotIn('source_path',clean)
        with self.assertRaisesRegex(ValueError,'quote'):p.cleaned({'text':'- The file is /orcd/private.'})

    def test_empty_is_not_missing_and_unjudged_is_not_failure(self):
        self.assertEqual(p.view({'text':'','empty':True,'pass':False},'method')['verdict'],'Empty abstention')
        result=p.view(None,'method',{'text':'- unchanged'})
        self.assertEqual(result['text'],'- unchanged')
        self.assertIn('Not judged',result['verdict'])

    def test_pair_preserves_every_character_and_exact_parent_label(self):
        before={'text':'- DETRv2\n','class':'hallucinated','evidence':{'wrong':['DETRv2']}}
        after={'text':'- DETR-D and DETR-T\n','class':'consistent','evidence':{'claims':{'unverifiable':7}}}
        row=p.pair('id',before,after,'best_n_exact-n8','likelihood_true_minus_mean_two_controls-n8','Limited change','id')
        self.assertEqual(row['baseline']['text'],before['text'])
        self.assertEqual(row['proposed']['text'],after['text'])
        self.assertEqual(row['baseline']['label'],'Best of 8')
        self.assertEqual(row['judge_evidence']['after']['claims']['unverifiable'],7)


if __name__=='__main__':unittest.main()
