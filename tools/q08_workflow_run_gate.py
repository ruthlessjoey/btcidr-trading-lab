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
OFFLINE_WORKFLOW_BLOB = "4821963a7b752a1e5bbc52e1d97c93ea296ff7f4"
BRANCH = "security/q0-provider-sanitization-2026-11-18"
MAX_RESPONSE_BYTES = 65_536
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


def validate_event(
    event: dict,
    token: str,
    fetch_json: Callable[[str, str], dict] = github_json,
) -> str:
    """Return the exact reviewed commit SHA only for the approved successful run."""
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
    if workflow_blob.get("sha") != OFFLINE_WORKFLOW_BLOB:
        raise GateError("Candidate branch offline workflow is not the approved immutable blob")
    return head_sha


def main() -> int:
    try:
        event_path = os.environ["GITHUB_EVENT_PATH"]
        with open(event_path, "r", encoding="utf-8") as stream:
            event = json.load(stream)
        if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
            raise GateError("Trusted review workflow ran in an unexpected repository")
        head_sha = validate_event(event, os.environ.get("GITHUB_TOKEN", ""))
    except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, GateError) as exc:
        message = str(exc) if isinstance(exc, GateError) else "event payload could not be read"
        print("::error::Q0.8 upstream workflow validation failed: " + message)
        return 1
    print("Trusted Q0.8 workflow_run event validated for exact head " + head_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
