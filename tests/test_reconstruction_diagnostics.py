import unittest
from olens_improve.reconstruction_diagnostics import paired_fit_change, grouped_fit_summary


class ReconstructionDiagnosticTests(unittest.TestCase):
    def test_absolute_mean_preserves_site_weights_and_valid_mask(self):
        fit={'a':.9,'b':.6,'c':0.,'missing':None}
        got=grouped_fit_summary(fit,{'a':'g','b':'g','c':'h'},replicates=2000,seed=4)
        self.assertEqual(got['independent_scored_groups'],2)
        self.assertEqual(got['defined_mean_bootstrap_draws'],2000)
        self.assertEqual(got['mean_fve_ci95'],[0.,.75])

    def test_absolute_empty_and_boundary_warnings(self):
        empty=grouped_fit_summary({'a':None},{})
        self.assertIsNone(empty['mean_fve_ci95'])
        self.assertEqual(empty['defined_mean_bootstrap_draws'],0)
        zero=grouped_fit_summary({'a':0.,'b':0.},{'a':'g','b':'h'},replicates=20)
        self.assertEqual(zero['mean_fve_ci95'],[0.,0.])
        self.assertEqual(len(zero['mean_fve_warnings']),2)

    def test_common_mask_and_unequal_group_site_weights(self):
        proposed = {'a':.9,'b':.8,'c':.7,'invalid':None}
        reference = {'a':.5,'b':.6,'c':.7,'invalid':.1,'other':.9}
        group = {'a':'paired-question-group','b':'paired-question-group','c':'different-group'}
        got = paired_fit_change(proposed,reference,group,replicates=2000,seed=4)
        self.assertEqual((got['paired_sites'],got['independent_groups']),(3,2))
        self.assertAlmostEqual(got['mean_delta'],.2)
        self.assertAlmostEqual(got['proposed_mean_same_mask']-got['reference_mean_same_mask'],.2)
        self.assertAlmostEqual(got['ci95_delta'][0],0.)
        self.assertAlmostEqual(got['ci95_delta'][1],.3)

    def test_single_related_group_keeps_zero_variation_warning(self):
        got = paired_fit_change({'a':.7,'b':.4},{'a':.3,'b':.2},{'a':'g','b':'g'},replicates=20)
        self.assertIsNotNone(got['warning'])
        self.assertEqual(got['independent_groups'],1)


if __name__ == '__main__': unittest.main()
