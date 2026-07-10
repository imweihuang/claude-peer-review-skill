#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_peer_review.py"
SKILL_PATH = Path(__file__).resolve().parents[1] / "SKILL.md"
CANON_PATH = Path.home() / ".claude" / "skills" / "shared" / "hard-stops.md"
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

    @unittest.skipUnless(CANON_PATH.exists(), "shared machine canon is not installed")
    def test_skill_and_shared_canon_document_grok_as_opt_in(self) -> None:
        self.assertIn("Grok Build remains supported only as explicit opt-in", SKILL_PATH.read_text())
        self.assertIn("`all` is a legacy alias for the Claude default", SKILL_PATH.read_text())
        self.assertIn("Grok review is explicit opt-in", CANON_PATH.read_text())

    def test_planning_fable_uses_matching_high_opus_fallback(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PEER_REVIEW_CLAUDE_MODEL": RUNNER.DEFAULT_CLAUDE_MODEL,
                "PEER_REVIEW_CLAUDE_FALLBACK_MODEL": "",
                "PEER_REVIEW_CLAUDE_FALLBACK_EFFORT": "",
            },
            clear=True,
        ):
            participant = RUNNER.preflight_participant(
                "claude", RUNNER.resolve_review_intensity("planning")
            )

        self.assertEqual(participant.requested_effort, "high")
        self.assertEqual(participant.fallback_model, "opus")
        self.assertEqual(participant.fallback_effort, "high")
        self.assertIn("Opus 4.8 fallback uses --effort high", participant.effort_status)

    def test_fable_alias_ignores_lower_effort_and_keeps_mandatory_fallback(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PEER_REVIEW_CLAUDE_MODEL": "claude-fable-5-20260709",
                "PEER_REVIEW_CLAUDE_EFFORT": "medium",
                "PEER_REVIEW_CLAUDE_FALLBACK_MODEL": "",
                "PEER_REVIEW_CLAUDE_FALLBACK_EFFORT": "",
            },
            clear=True,
        ):
            participant = RUNNER.preflight_participant(
                "claude", RUNNER.resolve_review_intensity("planning")
            )

        self.assertEqual(participant.requested_effort, "high")
        self.assertEqual(participant.fallback_model, "opus")
        self.assertEqual(participant.fallback_effort, "high")
        self.assertIn("ignored effort override medium", participant.effort_status)

    def test_fable_alias_honors_xhigh_override_for_primary_and_fallback(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PEER_REVIEW_CLAUDE_MODEL": "claude-fable-5-20260709",
                "PEER_REVIEW_CLAUDE_EFFORT": "xhigh",
            },
            clear=True,
        ):
            participant = RUNNER.preflight_participant(
                "claude", RUNNER.resolve_review_intensity("planning")
            )

        self.assertEqual(participant.requested_effort, "xhigh")
        self.assertEqual(participant.fallback_effort, "xhigh")

    def test_invalid_effort_override_is_disclosed_and_uses_planning_floor(self) -> None:
        with patch.dict(
            "os.environ",
            {"PEER_REVIEW_CLAUDE_EFFORT": "banana"},
            clear=True,
        ):
            participant = RUNNER.preflight_participant(
                "claude", RUNNER.resolve_review_intensity("planning")
            )

        self.assertEqual(participant.requested_effort, "high")
        self.assertEqual(participant.fallback_effort, "high")
        self.assertIn("ignored effort override banana", participant.effort_status)

    def test_rate_limit_and_quota_errors_trigger_fallback(self) -> None:
        self.assertTrue(RUNNER.should_use_claude_fallback("HTTP 429 rate limit exceeded"))
        self.assertTrue(RUNNER.should_use_claude_fallback("quota exhausted for this model"))

    def test_planning_fable_timeout_runs_matching_high_opus_fallback(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            participant = RUNNER.preflight_participant(
                "claude", RUNNER.resolve_review_intensity("planning")
            )
        participant.status = "ready"
        participant.cli_path = "/fake/claude"
        primary_timeout = RUNNER.subprocess.TimeoutExpired(
            cmd=["/fake/claude"], timeout=5, output="", stderr="primary timed out"
        )
        fallback_success = RUNNER.subprocess.CompletedProcess(
            args=["/fake/claude"], returncode=0, stdout="review complete", stderr=""
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch.object(
                RUNNER.subprocess, "run", side_effect=[primary_timeout, fallback_success]
            ) as run_mock:
                result = RUNNER.run_participant(
                    participant, "review input", Path(output_dir), timeout_seconds=10
                )

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.status, "ran")
        self.assertEqual(result.completed_model, "opus")
        self.assertEqual(result.completed_effort, "high")
        self.assertEqual(run_mock.call_count, 2)

    def test_fallback_timeout_still_records_matching_effort(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            participant = RUNNER.preflight_participant(
                "claude", RUNNER.resolve_review_intensity("planning")
            )
        participant.status = "ready"
        participant.cli_path = "/fake/claude"
        primary_timeout = RUNNER.subprocess.TimeoutExpired(
            cmd=["/fake/claude"], timeout=5, output="", stderr="primary timed out"
        )
        fallback_timeout = RUNNER.subprocess.TimeoutExpired(
            cmd=["/fake/claude"], timeout=5, output="", stderr="fallback timed out"
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch.object(
                RUNNER.subprocess, "run", side_effect=[primary_timeout, fallback_timeout]
            ):
                result = RUNNER.run_participant(
                    participant, "review input", Path(output_dir), timeout_seconds=10
                )

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.status, "timeout")
        self.assertIn("used fallback opus/high", result.notes or "")
        self.assertIn("timed out", result.notes or "")


if __name__ == "__main__":
    unittest.main()
