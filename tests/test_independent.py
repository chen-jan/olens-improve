"""Source-span checks for independent diagnostics; no real-model claims."""

import unittest
from olens_improve.independent import candidate_mentions


class MentionTests(unittest.TestCase):
    def test_mentions_retain_exact_spans_and_numeric_qualifiers(self):
        text = "- Alice Smith does not trust Bob; the value is -12.5, not 13."
        rows = candidate_mentions(text)
        self.assertTrue(all(text[row["start"]:row["end"]] == row["text"] for row in rows))
        self.assertEqual([row["text"] for row in rows if row["kind"] == "number"], ["-12.5", "13"])
        self.assertEqual([row["text"] for row in rows if row["kind"] == "capitalized_span"], ["Alice Smith", "Bob"])

    def test_no_entity_is_invented_from_lowercase_description(self):
        self.assertEqual(candidate_mentions("the performer humiliates the heckler"), [])


if __name__ == "__main__":
    unittest.main()
