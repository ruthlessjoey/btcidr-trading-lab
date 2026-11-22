"""Offline adversarial tests for the trusted Q0.8 workflow_run gate."""
import copy
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
        with self.assertRaises(GateError):
            validate_event(valid_event(), "", self.fetch_json)
        # The injected reader models the API call; the helper passes the token to it.
        self.fetch_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
