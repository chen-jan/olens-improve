"""Offline fixtures from the real editor-ID failure; no model or API calls."""
import unittest
from olens_improve.helpers import canonicalize_edit_proposals


class EditorBookkeepingTests(unittest.TestCase):
    def test_valid_parent_survives_arbitrary_provider_ids_verbatim(self):
        result={'proposals':[{'id':'e0','parent_id':'s0','text':'- Original name, 12, and no reversal.\n','change_summary':'Simplified wording.'},
            {'id':'s1','parent_id':'s1','text':'- Other source remains unchanged.','change_summary':'Removed repetition.'}]}
        accepted,rejected=canonicalize_edit_proposals(result,{'s0':'source','s1':'other'},token_count=lambda t:len(t.split()))
        self.assertFalse(rejected)
        self.assertEqual([x['id'] for x in accepted],['p0','p1'])
        self.assertEqual(accepted[0]['provider_proposal_id'],'e0')
        self.assertEqual(accepted[0]['text'],result['proposals'][0]['text'])
    def test_swapped_parent_reference_is_rejected_without_guessing(self):
        result={'proposals':[{'id':'s0','parent_id':'p0','text':'- A tempting edit.','change_summary':'Edited.'}]}
        accepted,rejected=canonicalize_edit_proposals(result,{'s0':'source'},token_count=lambda t:len(t.split()))
        self.assertFalse(accepted)
        self.assertEqual(rejected[0]['reason'],'unresolved_parent_reference')
    def test_caps_reject_whole_output_and_explicit_abstention_survives(self):
        result={'proposals':[{'parent_id':'s0','text':'- '+('word '*257),'change_summary':'Long.'},
            {'parent_id':'s0','text':'','change_summary':'Abstain.'}]}
        accepted,rejected=canonicalize_edit_proposals(result,{'s0':'source'},token_count=lambda t:len(t.split()))
        self.assertEqual(len(rejected),1)
        self.assertEqual(accepted[0]['text'],'')


if __name__=='__main__':unittest.main()
