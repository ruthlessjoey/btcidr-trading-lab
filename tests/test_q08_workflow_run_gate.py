"""Offline adversarial tests for the trusted Q0.8 workflow_run gate."""
import unittest
from unittest.mock import Mock

from tools.q08_workflow_run_gate import (
    BRANCH,
    OFFLINE_WORKFLOW_BLOB,
    REPOSITORY,
    WORKFLOW_ID,
    WORKFLOW_NAME,
    WORKFLOW_PATH,
    GateError,
    select_resume_run,
    validate_event,
)


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
        self.assertIn("/actions/runs?workflow_id=999", reader.call_args_list[1].args[0])

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
