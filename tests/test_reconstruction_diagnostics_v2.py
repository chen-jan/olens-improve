import unittest
from olens_improve.reconstruction_diagnostics_v2 import paired_fit_change


class NumericalClassificationTests(unittest.TestCase):
    def test_boundary_and_tiny_noise_are_neutral_without_changing_raw_mean(self):
        deltas={'zero':0.,'noise':3.2e-8,'positive_boundary':1e-5,'negative_boundary':-1e-5,
                'improved':1.0001e-5,'worsened':-1.0001e-5}
        got=paired_fit_change(deltas,{k:0. for k in deltas},{k:k for k in deltas},replicates=100)
        self.assertEqual(got['improved_sites'],1)
        self.assertEqual(got['worsened_sites'],1)
        self.assertEqual(got['unchanged_or_within_numerical_tolerance'],4)
        self.assertEqual(got['site_change_equivalence_tolerance'],1e-5)
        self.assertAlmostEqual(got['mean_delta'],sum(deltas.values())/len(deltas))

    def test_v1_raw_means_and_intervals_remain_exact(self):
        from olens_improve.reconstruction_diagnostics import paired_fit_change as old
        proposed={'a':.6,'b':.40000003,'c':.2};reference={'a':.4,'b':.4,'c':.3};groups={'a':'g','b':'g','c':'h'}
        before=old(proposed,reference,groups,replicates=1000,seed=7,stream='frozen')
        after=paired_fit_change(proposed,reference,groups,replicates=1000,seed=7,stream='frozen')
        for key in ('mean_delta','median_delta','ci95_delta','reference_mean_same_mask','proposed_mean_same_mask','paired_sites','independent_groups'):
            self.assertEqual(before[key],after[key])


if __name__=='__main__':unittest.main()
