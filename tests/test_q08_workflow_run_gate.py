"""Offline adversarial tests for the trusted Q0.8 workflow_run gate."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.q08_workflow_run_gate import (
    BRANCH,
    OFFLINE_WORKFLOW_BLOB,
    REPOSITORY,
    WORKFLOW_ID,
    WORKFLOW_NAME,
    WORKFLOW_PATH,
    GateError,
    select_resume_run,
    validate_bootstrap_event,
    validate_event,
)
import tools.q08_workflow_run_gate as gate


def valid_event():
    return {
        "repository": {"full_name": REPOSITORY},
        "workflow": {"id": WORKFLOW_ID, "path": WORKFLOW_PATH},
        "workflow_run": {
            "id": 45052517363,
            "name": WORKFLOW_NAME,
            "event": "push",
            "conclusion": "success",
            "head_branch": BRANCH,
            "head_sha": "a68b759b75adde426402eb39ef9c360f60e5bc27",
            "head_repository": {"full_name": REPOSITORY},
        },
    }


class WorkflowRunGateTests(unittest.TestCase):
    def valid_bootstrap_event(self):
        return {
            "repository": {"full_name": REPOSITORY},
            "ref": "refs/heads/main",
            "after": "f" * 40,
        }

    def valid_pr60(self):
        return {
            "number": 60,
            "state": "open",
            "head": {
                "ref": BRANCH,
                "sha": "e8674dbfe3efd2339ddb028484362f9466f7b058",
                "repo": {"full_name": REPOSITORY},
            },
            "base": {
                "ref": "feature/m6-risk-engine",
                "repo": {"full_name": REPOSITORY},
            },
        }

    def valid_offline_run(self):
        return {
            "id": 45055081357,
            "workflow_id": WORKFLOW_ID,
            "name": WORKFLOW_NAME,
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "head_branch": BRANCH,
            "head_sha": "e8674dbfe3efd2339ddb028484362f9466f7b058",
            "head_repository": {"full_name": REPOSITORY},
            "repository": {"full_name": REPOSITORY},
        }

    def bootstrap_reader(self, *, pr=None, branch_sha=None, workflow_sha=None, runs=None):
        run_payload = runs if runs is not None else {
            "total_count": 1,
            "workflow_runs": [self.valid_offline_run()],
        }
        return Mock(side_effect=[
            self.valid_pr60() if pr is None else pr,
            {"commit": {"sha": self.valid_pr60()["head"]["sha"] if branch_sha is None else branch_sha}},
            {"sha": OFFLINE_WORKFLOW_BLOB if workflow_sha is None else workflow_sha},
            run_payload,
        ])

    def test_main_push_bootstrap_selects_exact_successful_pr60_head(self):
        event = self.valid_bootstrap_event()
        with tempfile.TemporaryDirectory() as temp:
            event_path = Path(temp) / "event.json"
            output_path = Path(temp) / "output.txt"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            env = {
                "GITHUB_EVENT_PATH": str(event_path),
                "GITHUB_REPOSITORY": REPOSITORY,
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_TOKEN": "x" * 32,
                "GITHUB_RUN_ID": "900",
                "GITHUB_OUTPUT": str(output_path),
            }
            with patch.dict(os.environ, env, clear=False), \
                    patch.object(gate, "validate_bootstrap_event", return_value="e8674dbfe3efd2339ddb028484362f9466f7b058"), \
                    patch.object(gate, "select_resume_run", return_value="700"):
                self.assertEqual(gate.main(), 0)
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "review_head_sha=e8674dbfe3efd2339ddb028484362f9466f7b058\n"
                "resume_from_run_id=700\n",
            )

    def test_bootstrap_accepts_only_open_exact_pr60_head_with_successful_offline_run(self):
        reader = self.bootstrap_reader()
        selected = validate_bootstrap_event(self.valid_bootstrap_event(), "x" * 32, reader)
        self.assertEqual(selected, "e8674dbfe3efd2339ddb028484362f9466f7b058")
        self.assertEqual(reader.call_count, 4)
        self.assertIn("/pulls/60", reader.call_args_list[0].args[0])
        self.assertIn("/branches/" + BRANCH, reader.call_args_list[1].args[0])
        self.assertIn("actions/workflows/421573668/runs", reader.call_args_list[3].args[0])
        self.assertIn("status=completed", reader.call_args_list[3].args[0])

    def test_bootstrap_rejects_non_main_or_wrong_repository_event_before_api(self):
        cases = []
        event = self.valid_bootstrap_event()
        event["ref"] = "refs/heads/attacker"
        cases.append(event)
        event = self.valid_bootstrap_event()
        event["repository"] = {"full_name": "attacker/fork"}
        cases.append(event)
        event = self.valid_bootstrap_event()
        event["after"] = "not-a-sha"
        cases.append(event)
        for candidate in cases:
            reader = Mock()
            with self.subTest(event=candidate), self.assertRaises(GateError):
                validate_bootstrap_event(candidate, "x" * 32, reader)
            reader.assert_not_called()

    def test_bootstrap_rejects_closed_fork_wrong_branch_or_wrong_base_pr(self):
        mutations = (
            lambda pr: pr.update(state="closed"),
            lambda pr: pr["head"].update(ref="attacker-branch"),
            lambda pr: pr["head"].update(repo={"full_name": "attacker/fork"}),
            lambda pr: pr["base"].update(ref="main"),
            lambda pr: pr["base"].update(repo={"full_name": "attacker/fork"}),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                pr = self.valid_pr60()
                mutate(pr)
                reader = Mock(return_value=pr)
                with self.assertRaises(GateError):
                    validate_bootstrap_event(self.valid_bootstrap_event(), "x" * 32, reader)
                self.assertEqual(reader.call_count, 1)

    def test_bootstrap_rejects_pr_head_branch_ref_mismatch(self):
        reader = self.bootstrap_reader(branch_sha="0" * 40)
        with self.assertRaisesRegex(GateError, "branch ref do not match"):
            validate_bootstrap_event(self.valid_bootstrap_event(), "x" * 32, reader)
        self.assertEqual(reader.call_count, 2)

    def test_bootstrap_rejects_unapproved_offline_workflow_blob(self):
        reader = self.bootstrap_reader(workflow_sha="0" * 40)
        with self.assertRaisesRegex(GateError, "immutable blob"):
            validate_bootstrap_event(self.valid_bootstrap_event(), "x" * 32, reader)
        self.assertEqual(reader.call_count, 3)

    def test_bootstrap_requires_successful_run_for_exact_current_sha(self):
        invalid_runs = (
            dict(self.valid_offline_run(), conclusion="failure"),
            dict(self.valid_offline_run(), head_sha="b" * 40),
            dict(self.valid_offline_run(), workflow_id=WORKFLOW_ID + 1),
            dict(self.valid_offline_run(), head_repository={"full_name": "attacker/fork"}),
        )
        for run in invalid_runs:
            reader = self.bootstrap_reader(runs={"total_count": 1, "workflow_runs": [run]})
            with self.subTest(run=run), self.assertRaisesRegex(GateError, "no successful exact-head"):
                validate_bootstrap_event(self.valid_bootstrap_event(), "x" * 32, reader)

    def test_bootstrap_fails_closed_on_incomplete_offline_run_page(self):
        reader = self.bootstrap_reader(runs={"total_count": 101, "workflow_runs": [self.valid_offline_run()]})
        with self.assertRaisesRegex(GateError, "page is incomplete"):
            validate_bootstrap_event(self.valid_bootstrap_event(), "x" * 32, reader)

    def test_trusted_workflow_restores_gate_selected_same_head_checkpoint(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "q08-specialist-review.yml"
        ).read_text(encoding="utf-8")
        gate_position = workflow.index("id: validate-gate")
        restore_position = workflow.index("name: Restore checkpoint from an earlier run")
        review_position = workflow.index("name: Run immutable branch review")
        self.assertLess(gate_position, restore_position)
        self.assertLess(restore_position, review_position)
        self.assertIn("run: python3 runner/tools/q08_workflow_run_gate.py", workflow)
        self.assertIn(
            "github.event_name == 'workflow_run' && steps.validate-gate.outputs.resume_from_run_id != ''",
            workflow,
        )
        resume_expression = (
            "(github.event_name == 'workflow_run' || github.event_name == 'push') "
            "&& steps.validate-gate.outputs.resume_from_run_id || inputs.resume_from_run_id"
        )
        self.assertEqual(workflow.count(resume_expression), 3)
        self.assertIn(
            "Q08_RESUME_FROM_RUN_ID: ${{ " + resume_expression + " || '' }}",
            workflow,
        )
        self.assertEqual(workflow.count("\\n  workflow_run:\\n"), 1)
        self.assertIn(
            "  push:\\n    branches: [main]\\n    paths:\\n      - \\\".github/workflows/q08-specialist-review.yml\\\"",
            workflow,
        )
        self.assertIn("GITHUB_EVENT_NAME: ${{ github.event_name }}", workflow)
        self.assertIn(
            "github.event_name == 'push' && steps.validate-gate.outputs.review_head_sha",
            workflow,
        )
        self.assertIn(
            "github.event_name == 'push' && steps.validate-gate.outputs.resume_from_run_id",
            workflow,
        )
        self.assertIn(
            "github.event_name == 'workflow_run' || github.event_name == 'push'",
            workflow,
        )

    def setUp(self):
        self.fetch_json = Mock(return_value={"sha": OFFLINE_WORKFLOW_BLOB})

    def test_approved_exact_workflow_run_returns_immutable_head(self):
        result = validate_event(valid_event(), "x" * 32, self.fetch_json)
        self.assertEqual(result, "a68b759b75adde426402eb39ef9c360f60e5bc27")
        self.fetch_json.assert_called_once_with(
            "https://api.github.com/repos/" + REPOSITORY
            + "/contents/" + WORKFLOW_PATH
            + "?ref=a68b759b75adde426402eb39ef9c360f60e5bc27",
            "x" * 32,
        )

    def test_wrong_event_identity_fields_fail_closed_before_api_lookup(self):
        mutations = (
            ("repository", lambda event: event["repository"].update(full_name="attacker/fork")),
            ("workflow_id", lambda event: event["workflow"].update(id=WORKFLOW_ID + 1)),
            ("workflow_path", lambda event: event["workflow"].update(path=".github/workflows/evil.yml")),
            ("workflow_name", lambda event: event["workflow_run"].update(name="Other workflow")),
            ("event", lambda event: event["workflow_run"].update(event="workflow_dispatch")),
            ("conclusion", lambda event: event["workflow_run"].update(conclusion="failure")),
            ("branch", lambda event: event["workflow_run"].update(head_branch="attacker-branch")),
            ("head_repository", lambda event: event["workflow_run"].update(
                head_repository={"full_name": "attacker/fork"})),
            ("invalid_sha", lambda event: event["workflow_run"].update(head_sha="../secrets")),
            ("boolean_run_id", lambda event: event["workflow_run"].update(id=True)),
            ("string_run_id", lambda event: event["workflow_run"].update(id="45052517363")),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                self.fetch_json.reset_mock()
                event = valid_event()
                mutate(event)
                with self.assertRaises(GateError):
                    validate_event(event, "x" * 32, self.fetch_json)
                self.fetch_json.assert_not_called()

    def test_missing_event_objects_fail_closed(self):
        cases = (
            {},
            {"repository": {}, "workflow": {}, "workflow_run": None},
            {"repository": [], "workflow": {}, "workflow_run": {}},
        )
        for event in cases:
            with self.subTest(event=event), self.assertRaises(GateError):
                validate_event(event, "x" * 32, self.fetch_json)
        self.fetch_json.assert_not_called()

    def test_unapproved_offline_workflow_blob_is_rejected(self):
        self.fetch_json.return_value = {"sha": "0" * 40}
        with self.assertRaisesRegex(GateError, "immutable blob"):
            validate_event(valid_event(), "x" * 32, self.fetch_json)

    def test_malformed_workflow_metadata_response_is_rejected(self):
        self.fetch_json.return_value = []
        with self.assertRaisesRegex(GateError, "immutable blob"):
            validate_event(valid_event(), "x" * 32, self.fetch_json)

    def test_github_fetch_failure_fails_closed(self):
        self.fetch_json.side_effect = GateError("synthetic API failure")
        with self.assertRaisesRegex(GateError, "synthetic API failure"):
            validate_event(valid_event(), "x" * 32, self.fetch_json)

    def test_missing_token_fails_before_lookup(self):
        with self.assertRaisesRegex(GateError, "token is unavailable"):
            validate_event(valid_event(), "", self.fetch_json)
        self.fetch_json.assert_not_called()

    def test_no_prior_same_head_review_starts_one_review(self):
        workflow_id = {"id": 999}
        no_runs = {"total_count": 0, "workflow_runs": []}
        reader = Mock(side_effect=[workflow_id, no_runs])
        resume = select_resume_run(
            "a68b759b75adde426402eb39ef9c360f60e5bc27", "x" * 32, "900",
            reader,
        )
        self.assertEqual(resume, "")
        self.assertEqual(reader.call_count, 2)
        self.assertTrue(
            reader.call_args_list[0].args[0].endswith("/actions/workflows/q08-specialist-review.yml")
        )
        self.assertEqual(
            reader.call_args_list[1].args[0],
            "https://api.github.com/repos/" + REPOSITORY
            + "/actions/workflows/999/runs?event=workflow_run&per_page=100&page=1",
        )

    def test_same_head_running_review_blocks_duplicate(self):
        same_head = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        run = {
            "id": 700, "display_title": "Q0.8 specialist review " + same_head,
            "status": "in_progress",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [run]},
        ])
        with self.assertRaisesRegex(GateError, "already queued or running"):
            select_resume_run(same_head, "x" * 32, "900", reader)

    def test_same_head_successful_review_blocks_duplicate(self):
        same_head = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        run = {
            "id": 700, "display_title": "Q0.8 specialist review " + same_head,
            "status": "completed", "conclusion": "success",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [run]},
        ])
        with self.assertRaisesRegex(GateError, "already completed successfully"):
            select_resume_run(same_head, "x" * 32, "900", reader)

    def test_failed_same_head_review_resumes_only_its_checkpoint(self):
        same_head = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        prior = {
            "id": 700, "display_title": "Q0.8 specialist review " + same_head,
            "status": "completed", "conclusion": "failure",
        }
        artifacts = {
            "artifacts": [{
                "name": "q08-review-checkpoint-700",
                "expired": False,
                "size_in_bytes": 380,
            }]
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [prior]},
            artifacts,
        ])
        resume = select_resume_run(same_head, "x" * 32, "900", reader)
        self.assertEqual(resume, "700")
        self.assertIn("/actions/runs/700/artifacts", reader.call_args_list[2].args[0])

    def test_failed_same_head_without_checkpoint_starts_cleanly(self):
        same_head = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        prior = {
            "id": 700, "display_title": "Q0.8 specialist review " + same_head,
            "status": "completed", "conclusion": "failure",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [prior]},
            {"artifacts": []},
        ])
        resume = select_resume_run(same_head, "x" * 32, "900", reader)
        self.assertEqual(resume, "")

    def test_different_head_review_does_not_block(self):
        current = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        prior = {
            "id": 700, "display_title": "Q0.8 specialist review " + "b" * 40,
            "status": "in_progress",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [prior]},
        ])
        self.assertEqual(select_resume_run(current, "x" * 32, "900", reader), "")

    def test_current_review_run_is_excluded_from_its_own_deduplication(self):
        current = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        current_run = {
            "id": 900, "display_title": "Q0.8 specialist review " + current,
            "status": "in_progress",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [current_run]},
        ])
        self.assertEqual(select_resume_run(current, "x" * 32, "900", reader), "")

    def test_run_list_pagination_cannot_hide_duplicate(self):
        current = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        first = [{"id": index + 1000, "display_title": "Other review", "status": "completed"}
                 for index in range(100)]
        duplicate = {
            "id": 700, "display_title": "Q0.8 specialist review " + current,
            "status": "in_progress",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 101, "workflow_runs": first},
            {"total_count": 101, "workflow_runs": [duplicate]},
        ])
        with self.assertRaisesRegex(GateError, "already queued or running"):
            select_resume_run(current, "x" * 32, "900", reader)
        self.assertEqual(reader.call_count, 3)

    def test_oversized_review_history_fails_closed(self):
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 2001, "workflow_runs": []},
        ])
        with self.assertRaisesRegex(GateError, "exceeds the bounded deduplication scan"):
            select_resume_run("a" * 40, "x" * 32, "900", reader)
        self.assertEqual(reader.call_count, 2)

    def test_incomplete_run_list_page_fails_closed(self):
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 101, "workflow_runs": [{"id": 1000}]},
        ])
        with self.assertRaisesRegex(GateError, "page is incomplete"):
            select_resume_run("a68b759b75adde426402eb39ef9c360f60e5bc27", "x" * 32, "900", reader)

    def test_malformed_artifact_response_fails_closed(self):
        same_head = "a68b759b75adde426402eb39ef9c360f60e5bc27"
        prior = {
            "id": 700, "display_title": "Q0.8 specialist review " + same_head,
            "status": "completed", "conclusion": "failure",
        }
        reader = Mock(side_effect=[
            {"id": 999},
            {"total_count": 1, "workflow_runs": [prior]},
            [],
        ])
        with self.assertRaisesRegex(GateError, "artifacts response is malformed"):
            select_resume_run(same_head, "x" * 32, "900", reader)


if __name__ == "__main__":
    unittest.main()
