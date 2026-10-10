"""Recurring medium helper costs include the reused proposal phase."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('costs',Path(__file__).parents[1]/'scripts/extend_measured_costs.py')
costs=importlib.util.module_from_spec(spec);spec.loader.exec_module(costs)


class CostTests(unittest.TestCase):
    def phases(self):
        return {'none_phases':{
            'candidate-pair-proposal-local-ids-v2':{'calls':189,'actual_usd':1.},
            'whole-bullet-equivalence-compatibility-v5-local-ids-v1':{'calls':189,'actual_usd':2.}},
            'deployment_none_proposal_plus_medium_confirmation_usd':4.}

    def test_reused_proposal_is_charged_in_new_input_pipeline(self):
        result=costs.helper_pipeline(self.phases(),{'actual_usage_derived_usd':3.})
        self.assertEqual(result['none_pipeline_usd'],3.)
        self.assertEqual(result['medium_pipeline_usd'],4.)
        self.assertAlmostEqual(result['medium_usd_per_cell'],4./189)
        self.assertEqual(result['none_pipeline_calls'],378)

    def test_confirmation_only_cannot_claim_deployment_cost(self):
        phases=self.phases();phases['deployment_none_proposal_plus_medium_confirmation_usd']=3.
        with self.assertRaisesRegex(ValueError,'include proposal'):
            costs.helper_pipeline(phases,{'actual_usage_derived_usd':3.})


if __name__=='__main__':unittest.main()
