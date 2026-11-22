"""Validate a trusted GitHub workflow_run event before starting Q0.8 review.

This helper is used only by the trusted default-branch workflow. It validates the
unprivileged offline test run and confirms that the candidate branch still carries
the exact approved offline workflow definition. It never executes candidate code.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable

REPOSITORY = "ruthlessjoey/btcidr-trading-lab"
WORKFLOW_ID = 421573668
WORKFLOW_NAME = "Q0.8 offline security regression tests (sparse unprotected scope)"
WORKFLOW_PATH = ".github/workflows/q08-offline-tests.yml"
SPECIALIST_WORKFLOW_PATH = "q08-specialist-review.yml"
OFFLINE_WORKFLOW_BLOB = "4821963a7b752a1e5bbc52e1d97c93ea296ff7f4"
BRANCH = "security/q0-provider-sanitization-2026-11-18"
MAX_RESPONSE_BYTES = 524_288
MAX_RUN_PAGES = 20
RUNS_PER_PAGE = 100
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class GateError(RuntimeError):
    """The upstream workflow event is not the one trusted for Q0.8."""


def github_json(url: str, token: str) -> dict:
    if not isinstance(token, str) or len(token) < 20:
        raise GateError("GitHub read token is unavailable")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "q08-trusted-workflow-run-gate",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError):
        raise GateError("GitHub workflow definition lookup failed") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise GateError("GitHub workflow definition response exceeded the fixed limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GateError("GitHub workflow definition response was not valid JSON") from None
    if type(value) is not dict:
        raise GateError("GitHub workflow definition response has an invalid shape")
    return value



def select_resume_run(
    head_sha: str,
    token: str,
    current_run_id: str,
    fetch_json: Callable[[str, str], dict] = github_json,
) -> str:
    """Deduplicate same-head reviews and reuse only an exact-head prior checkpoint."""
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        raise GateError("Review head SHA is invalid for idempotency lookup")
    if not isinstance(token, str) or len(token) < 20:
        raise GateError("GitHub read token is unavailable for idempotency lookup")
    if not isinstance(current_run_id, str) or not current_run_id.isascii() or not current_run_id.isdigit():
        raise GateError("Current GitHub run ID is invalid")

    workflow_url = (
        "https://api.github.com/repos/" + REPOSITORY
        + "/actions/workflows/" + SPECIALIST_WORKFLOW_PATH
    )
    workflow = fetch_json(workflow_url, token)
    workflow_id = workflow.get("id") if type(workflow) is dict else None
    if type(workflow_id) is not int or workflow_id <= 0:
        raise GateError("Trusted specialist workflow metadata is invalid")

    marker = "Q0.8 specialist review " + head_sha
    matching_runs = []
    total_count = None
    for page in range(1, MAX_RUN_PAGES + 1):
        url = (
            "https://api.github.com/repos/" + REPOSITORY
            + "/actions/workflows/" + str(workflow_id) + "/runs"
            + "?event=workflow_run&per_page=" + str(RUNS_PER_PAGE)
            + "&page=" + str(page)
        )
        payload = fetch_json(url, token)
        if type(payload) is not dict:
            raise GateError("Specialist workflow run list has an invalid shape")
        page_total = payload.get("total_count")
        page_runs = payload.get("workflow_runs")
        if type(page_total) is not int or page_total < 0 or type(page_runs) is not list:
            raise GateError("Specialist workflow run list metadata is invalid")
        if total_count is None:
            total_count = page_total
            if total_count > MAX_RUN_PAGES * RUNS_PER_PAGE:
                raise GateError("Specialist workflow history exceeds the bounded deduplication scan")
        elif page_total != total_count:
            raise GateError("Specialist workflow run list changed during the deduplication scan")
        expected_page_size = min(RUNS_PER_PAGE, max(0, total_count - ((page - 1) * RUNS_PER_PAGE)))
        if len(page_runs) != expected_page_size:
            raise GateError("Specialist workflow run list page is incomplete")
        for prior in page_runs:
            if type(prior) is not dict:
                raise GateError("Specialist workflow run entry is malformed")
            if prior.get("id") == int(current_run_id):
                continue
            if prior.get("display_title") == marker:
                matching_runs.append(prior)
        if page * RUNS_PER_PAGE >= total_count:
            break
    else:
        if total_count and total_count > MAX_RUN_PAGES * RUNS_PER_PAGE:
            raise GateError("Specialist workflow history scan reached its fixed page limit")

    if any(
        prior.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"}
        for prior in matching_runs
    ):
        raise GateError("A Q0.8 specialist review for this exact SHA is already queued or running")
    if any(prior.get("conclusion") == "success" for prior in matching_runs):
        raise GateError("A Q0.8 specialist review for this exact SHA already completed successfully")

    # Resume the newest failed/cancelled attempt only when its own checkpoint artifact exists.
    for prior in matching_runs:
        if prior.get("status") != "completed" or prior.get("conclusion") not in {
            "failure", "cancelled", "timed_out", "action_required", "startup_failure"
        }:
            continue
        prior_id = prior.get("id")
        if type(prior_id) is not int or prior_id <= 0:
            raise GateError("Prior specialist workflow run has an invalid identifier")
        artifacts_url = (
            "https://api.github.com/repos/" + REPOSITORY
            + "/actions/runs/" + str(prior_id) + "/artifacts?per_page=100"
        )
        artifacts_payload = fetch_json(artifacts_url, token)
        artifacts = artifacts_payload.get("artifacts") if type(artifacts_payload) is dict else None
        if type(artifacts) is not list:
            raise GateError("Prior specialist workflow artifacts response is malformed")
        expected_name = "q08-review-checkpoint-" + str(prior_id)
        for artifact in artifacts:
            if type(artifact) is not dict:
                raise GateError("Prior specialist workflow artifact entry is malformed")
            if (
                artifact.get("name") == expected_name
                and artifact.get("expired") is False
                and type(artifact.get("size_in_bytes")) is int
                and artifact["size_in_bytes"] > 0
            ):
                return str(prior_id)
    return ""


def validate_event(
    event: dict,
    token: str,
    fetch_json: Callable[[str, str], dict] = github_json,
) -> str:
    """Return the exact reviewed commit SHA only for the approved successful run."""
    if type(token) is not str or len(token) < 20:
        raise GateError("GitHub read token is unavailable")
    if type(event) is not dict:
        raise GateError("GitHub event payload must be an object")
    run = event.get("workflow_run")
    workflow = event.get("workflow")
    repository = event.get("repository")
    if not all(type(value) is dict for value in (run, workflow, repository)):
        raise GateError("GitHub workflow_run event is missing required objects")

    checks = (
        workflow.get("id") == WORKFLOW_ID and type(workflow.get("id")) is int,
        workflow.get("path") == WORKFLOW_PATH,
        repository.get("full_name") == REPOSITORY,
        run.get("name") == WORKFLOW_NAME,
        run.get("event") == "push",
        run.get("conclusion") == "success",
        run.get("head_branch") == BRANCH,
        (run.get("head_repository") or {}).get("full_name") == REPOSITORY,
        type(run.get("id")) is int and run.get("id") > 0,
        isinstance(run.get("head_sha"), str) and bool(SHA_RE.fullmatch(run["head_sha"])),
    )
    if not all(checks):
        raise GateError("Upstream workflow identity, repository, branch, SHA, or conclusion mismatch")

    head_sha = run["head_sha"]
    url = (
        "https://api.github.com/repos/" + REPOSITORY
        + "/contents/" + WORKFLOW_PATH + "?ref=" + head_sha
    )
    workflow_blob = fetch_json(url, token)
    if type(workflow_blob) is not dict or workflow_blob.get("sha") != OFFLINE_WORKFLOW_BLOB:
        raise GateError("Candidate branch offline workflow is not the approved immutable blob")
    return head_sha


def main() -> int:
    try:
        event_path = os.environ["GITHUB_EVENT_PATH"]
        with open(event_path, "r", encoding="utf-8") as stream:
            event = json.load(stream)
        if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
            raise GateError("Trusted review workflow ran in an unexpected repository")
        token = os.environ.get("GITHUB_TOKEN", "")
        head_sha = validate_event(event, token)
        resume_from_run_id = select_resume_run(
            head_sha, token, os.environ.get("GITHUB_RUN_ID", "")
        )
        output_path = os.environ.get("GITHUB_OUTPUT", "")
        if not output_path:
            raise GateError("GitHub output path is unavailable")
        with open(output_path, "a", encoding="utf-8") as output:
            output.write("resume_from_run_id=" + resume_from_run_id + "\\n")
    except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, GateError) as exc:
        message = str(exc) if isinstance(exc, GateError) else "event payload could not be read"
        print("::error::Q0.8 upstream workflow validation failed: " + message)
        return 1
    print("Trusted Q0.8 workflow_run event validated for exact head " + head_sha)
    if resume_from_run_id:
        print("A checkpoint from the exact same review head will be resumed.")
    else:
        print("No previous same-head review requires deduplication or checkpoint restore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
