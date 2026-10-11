import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_expansion_qualitative_delta_v2 import content_identity, official_pairs


class ExactReviewInheritanceTests(unittest.TestCase):
    def test_same_words_in_different_context_require_distinct_review(self):
        unit={'family':'hallucination','cell_id':'site'}
        pair={'before':{'text':'name'},'after':{'text':'name removed'}}
        first=content_identity(unit,pair,'actual_parent_pairs',{'response':'actual source response'})
        changed=content_identity(unit,pair,'actual_parent_pairs',{'response':'different source response'})
        self.assertNotEqual(first,changed)
        self.assertNotEqual(first,content_identity(unit,pair,'capped_N1_pairs',{'response':'actual source response'}))

    def test_equal_words_do_not_hide_changed_official_evidence(self):
        before={'text':'same','class':'consistent'};after={'text':'same retained','class':'consistent'}
        prior={'references':[{'official_parent':before,'official_proposed':after}]}
        changed={'references':[{'official_parent':before,'official_proposed':after|{'class':'hallucinated'}}]}
        self.assertNotEqual(official_pairs(prior,'actual_parent_pairs'),official_pairs(changed,'actual_parent_pairs'))


if __name__=='__main__':unittest.main()
