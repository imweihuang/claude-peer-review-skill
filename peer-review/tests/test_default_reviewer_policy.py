#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_peer_review.py"
SKILL_PATH = Path(__file__).resolve().parents[1] / "SKILL.md"
SPEC = importlib.util.spec_from_file_location("run_peer_review", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class DefaultReviewerPolicyTest(unittest.TestCase):
    def test_default_constant_and_empty_selection_are_claude_only(self) -> None:
        self.assertEqual(RUNNER.DEFAULT_REVIEWERS, ("claude",))
        self.assertEqual(RUNNER.parse_reviewers(""), ["claude"])

    def test_default_alias_selects_only_claude(self) -> None:
        self.assertEqual(RUNNER.parse_reviewers("all"), ["claude"])

    def test_gemini_alias_does_not_implicitly_add_grok(self) -> None:
        self.assertEqual(RUNNER.parse_reviewers("all-with-gemini"), ["claude", "gemini"])

    def test_grok_remains_available_when_explicitly_requested(self) -> None:
        self.assertEqual(RUNNER.parse_reviewers("claude,grok"), ["claude", "grok"])

    def test_skill_documents_grok_as_opt_in(self) -> None:
        self.assertIn("Grok Build remains supported only as explicit opt-in", SKILL_PATH.read_text())
        self.assertIn("`all` is a legacy alias for the Claude default", SKILL_PATH.read_text())


if __name__ == "__main__":
    unittest.main()
