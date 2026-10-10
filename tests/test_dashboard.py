"""Scientific disclosure and source-text safety checks for the local report."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("dashboard", Path(__file__).parents[1] / "scripts/build_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def test_readable_labels_keep_exact_condition_in_evidence(self):
        output = dashboard.metrics_table([{'family':'multihop_mt','condition':'pooled_greedy_swap-n32','endpoint':'Cell recovery','value':.25}])
        self.assertIn('Multi-hop facts', output)
        self.assertIn('Pool bullets from 32 samples', output)
        self.assertIn('title="pooled_greedy_swap-n32"', output)
        self.assertIn('25.0%', output)
        claims = dashboard.metrics_table([{'endpoint':'Unverifiable claims per produced output','value':2.5}])
        self.assertNotIn('250.0%', claims)

    def test_nested_test_record_requires_reveal(self):
        with self.assertRaisesRegex(ValueError, "reveal"):
            dashboard.build({"cohort": "development", "methods": {"sample_selection": {
                "metrics": [{"cohort": "test", "value": 0.5}]}}})

    def test_partial_grid_cannot_be_official(self):
        with self.assertRaisesRegex(ValueError, "full grids"):
            dashboard.build({"methods": {"sample_selection": {"metrics": [{
                "official_full_grid": True, "scope": "cell_pilot", "complete_grid": False}]}}})

    def test_source_text_and_missing_values_preserved_safely(self):
        output = dashboard.build({"methods": {"sample_selection": {"traces": [{
            "cell_id": "x", "baseline": "</script><script>alert(1)</script>",
            "selected": "- Alice trusts Bob.\n  She does not know his secret."}],
            "metrics": [{"family": "role", "value": None, "numerator": None,
                         "denominator": 12, "missing_count": 12}]}}})
        self.assertIn("She does not know his secret.", output)
        self.assertIn("&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;", output)
        self.assertNotIn("</script><script>alert(1)</script>", output)
        self.assertIn("Not measured", output)

    def test_cache_only_cost_cannot_silently_claim_full_inference(self):
        with self.assertRaisesRegex(ValueError, 'scope'):
            dashboard.build({'methods':{'sample_selection':{'cost_frontier':[{'label':'Incomplete cost','cost_unit':'GPU seconds','points':[{'cost':1,'value':.5}]}]}}})
    def test_sample_prefix_cannot_be_labeled_deployment_cost(self):
        with self.assertRaisesRegex(ValueError,'experimental_prefix'):
            dashboard.cost_chart([{'label':'Wrong scope','cost_unit':'samples','cost_scope':'deployment',
                                   'cost_definition':'Sample count','points':[]}])
    def test_component_interval_keeps_pair_identity_and_zero_reference(self):
        output=dashboard.ablation_charts([{'family':'multihop_mt','label':'multihop_mt: recovery change',
                'cohort':'synthetic','points':[{'condition':'pooled_greedy_swap-n32 vs best_n_exact-n32',
                'value':.1,'ci':[-.1,.2],'groups':2,'warning':'Tiny group count'}]}])
        self.assertIn('title="pooled_greedy_swap-n32 vs best_n_exact-n32"',output)
        self.assertIn('-10.0 pp',output)
        self.assertIn('20.0 pp',output)
        self.assertIn('Tiny group count',output)
    def test_measured_curve_can_draw_ci_and_handle_missing_ci(self):
        output = dashboard.build({"methods": {"sample_selection": {"scaling": [{
            "label": "Toy recovery fixture", "cohort": "synthetic", "points": [
                {"n": 1, "value": 0.4, "ci": [0.2, 0.6]},
                {"n": 2, "value": 0.5, "ci": None}]}], "cost_frontier": [{
                    "label": "Toy cost fixture", "cost_unit": "USD", "cost_scope":"deployment", "cost_definition":"Synthetic complete execution", "points": [
                        {"condition": "toy", "value": 0.4, "cost": 1, "ci": [0.2, 0.6]}]}]}}})
        self.assertIn('class="whisker"', output)
        self.assertIn("[0.2, 0.6]", output)
        self.assertIn("no fitted frontier is implied", output)


if __name__ == "__main__":
    unittest.main()
