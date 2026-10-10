import unittest
from olens_improve.sampling import sequence_metadata


class SamplingMetadataTests(unittest.TestCase):
    def test_padding_does_not_make_finished_rows_truncated(self):
        rows = [[11, 99, 99, 99], [11, 12, 13, 14]]
        metadata = sequence_metadata(rows, {99}, 99, 4)
        self.assertEqual(metadata["token_counts"], [2, 4])
        self.assertEqual(metadata["finish_reasons"], ["eos", "length"])
        self.assertEqual(metadata["truncated"], [False, True])
        self.assertEqual(metadata["generated_token_ids"][0], [11, 99])


if __name__ == "__main__":
    unittest.main()
