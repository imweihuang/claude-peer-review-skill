from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_SCRIPT = REPO_ROOT / "peer-review" / "scripts" / "build_review_context.py"
RUNNER_SCRIPT = REPO_ROOT / "peer-review" / "scripts" / "run_peer_review.py"
CHATGPT_PRO_SKILL = REPO_ROOT / "chatgpt-pro-peer-review" / "SKILL.md"
CHATGPT_PRO_METADATA = REPO_ROOT / "chatgpt-pro-peer-review" / "agents" / "openai.yaml"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ContextBuilderTests(unittest.TestCase):
    def run_context(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(CONTEXT_SCRIPT), "--root", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    def init_repo(self, root: Path, files: dict[str, str]) -> None:
        subprocess.run(["git", "init"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    def test_total_limit_omission_is_visible_in_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root, {"a.txt": "a" * 50, "b.txt": "b" * 50})

            result = self.run_context(root, "--max-total-bytes", "20", "a.txt", "b.txt")

            self.assertEqual(result.returncode, 0)
            self.assertIn("CONTEXT OMITTED", result.stdout)

    def test_symlink_to_outside_root_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            outside = Path(tmp) / "outside-secret.txt"
            root.mkdir()
            outside.write_text("SECRET_TOKEN=abc123", encoding="utf-8")
            (root / "safe-link.md").symlink_to(outside)
            subprocess.run(["git", "init"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "safe-link.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            result = self.run_context(root, "safe-link.md")

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("SECRET_TOKEN", result.stdout)
            self.assertIn("skipped", result.stderr)

    def test_secret_like_content_blocks_context_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root, {"config.yaml": "api_key: sk-proj-" + "a" * 48})

            result = self.run_context(root, "config.yaml")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("possible secret", result.stderr)

    def test_non_git_root_fails_closed_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text("hello", encoding="utf-8")

            result = self.run_context(root, "notes.md")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("git ls-files unavailable", result.stderr)


class RunnerTests(unittest.TestCase):
    def test_gemini_command_skips_trust_for_headless_run(self) -> None:
        runner = load_module(RUNNER_SCRIPT, "run_peer_review")
        participant = runner.Participant(
            key="gemini",
            label="Gemini",
            cli="gemini",
            cli_path="/bin/gemini",
            cli_version="test",
            requested_model="gemini-test",
            requested_effort="not-cli-exposed",
            effort_status="test",
            status="ready",
        )

        cmd, stdin_text = runner.command_for(participant, "prompt", Path("/tmp"))

        self.assertIn("--skip-trust", cmd)
        self.assertEqual(stdin_text, "prompt")

    def test_gemini_cli_default_omits_unverified_model_flag(self) -> None:
        runner = load_module(RUNNER_SCRIPT, "run_peer_review")
        participant = runner.Participant(
            key="gemini",
            label="Gemini",
            cli="gemini",
            cli_path="/bin/gemini",
            cli_version="test",
            requested_model="cli-default",
            requested_effort="not-cli-exposed",
            effort_status="test",
            status="ready",
        )

        cmd, _ = runner.command_for(participant, "prompt", Path("/tmp"))

        self.assertNotIn("--model", cmd)

    def test_grok_command_allows_more_than_one_turn(self) -> None:
        runner = load_module(RUNNER_SCRIPT, "run_peer_review")
        with tempfile.TemporaryDirectory() as tmp:
            participant = runner.Participant(
                key="grok",
                label="Grok Build",
                cli="grok",
                cli_path="/bin/grok",
                cli_version="test",
                requested_model="grok-build",
                requested_effort="max; reasoning_effort=high",
                effort_status="test",
                status="ready",
            )

            cmd, _ = runner.command_for(participant, "prompt", Path(tmp))

        self.assertIn("--max-turns", cmd)
        turns = int(cmd[cmd.index("--max-turns") + 1])
        self.assertGreaterEqual(turns, 4)

    def test_run_exit_code_requires_all_reviewers_unless_partial_allowed(self) -> None:
        runner = load_module(RUNNER_SCRIPT, "run_peer_review")
        results = [
            runner.Participant("claude", "Claude", "claude", "/bin/claude", "test", "m", "e", "s", "ran"),
            runner.Participant("gemini", "Gemini", "gemini", "/bin/gemini", "test", "m", "e", "s", "error"),
        ]

        self.assertEqual(runner.run_exit_code(results, allow_partial=False), 1)
        self.assertEqual(runner.run_exit_code(results, allow_partial=True), 0)

    def test_ready_reviewers_run_concurrently_when_jobs_allows(self) -> None:
        runner = load_module(RUNNER_SCRIPT, "run_peer_review")
        participants = [
            runner.Participant("claude", "Claude", "claude", "/bin/claude", "test", "m", "e", "s", "ready"),
            runner.Participant("gemini", "Gemini", "gemini", "/bin/gemini", "test", "m", "e", "s", "ready"),
        ]
        active = 0
        max_active = 0
        lock = threading.Lock()

        def fake_runner(participant, review_input, output_dir, timeout_seconds):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.1)
            with lock:
                active -= 1
            participant.status = "ran"
            return participant

        results = runner.run_participants(participants, "prompt", Path("/tmp"), timeout_seconds=5, jobs=2, runner=fake_runner)

        self.assertEqual([item.key for item in results], ["claude", "gemini"])
        self.assertTrue(all(item.status == "ran" for item in results))
        self.assertEqual(max_active, 2)


class SkillDocumentationTests(unittest.TestCase):
    def test_chatgpt_pro_skill_is_discoverable_and_guarded(self) -> None:
        text = CHATGPT_PRO_SKILL.read_text(encoding="utf-8")

        self.assertIn("name: chatgpt-pro-peer-review", text)
        self.assertIn("Use when", text)
        self.assertIn("GPT-5.5 Pro", text)
        self.assertIn("Extended Pro", text)
        self.assertIn("Chrome", text)
        self.assertIn("Do not submit", text)
        self.assertIn("context helper", text)
        self.assertIn("manual browser", text)

    def test_chatgpt_pro_skill_has_ui_metadata(self) -> None:
        text = CHATGPT_PRO_METADATA.read_text(encoding="utf-8")

        self.assertIn("display_name: \"ChatGPT Pro Peer Review\"", text)
        self.assertIn("$chatgpt-pro-peer-review", text)


if __name__ == "__main__":
    unittest.main()
