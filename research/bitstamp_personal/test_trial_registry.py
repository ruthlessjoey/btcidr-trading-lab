import hashlib
import json
import unittest
from trial_registry import TrialRegistryError, verify_trial_registry


def encode(events):
    previous = "0" * 64
    lines = []
    for seq, event, payload in events:
        core = {"seq": seq, "event": event, "payload": payload, "previous_hash": previous}
        digest = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        lines.append(json.dumps({**core, "record_hash": digest}, sort_keys=True, separators=(",", ":")))
        previous = digest
    return ("\n".join(lines) + "\n").encode()


def start(trial_id, family="FAMILY"):
    return ("TRIAL_STARTED", {
        "trial_id": trial_id, "research_family": family,
        "strategy_id": "SMA", "config_sha256": "a" * 64,
    })


class TrialRegistryTests(unittest.TestCase):
    def test_counts_all_started_trials_including_failed_and_abandoned(self):
        events = [
            start("one"),
            ("TRIAL_FINISHED", {"trial_id": "one", "status": "FAILED", "result_sha256": None}),
            start("two"),
            ("TRIAL_FINISHED", {"trial_id": "two", "status": "ABANDONED", "result_sha256": None}),
            start("three"),
        ]
        raw = encode([(i + 1, *event) for i, event in enumerate(events)])
        result = verify_trial_registry(raw)
        self.assertEqual(result["trial_counts"], {"FAMILY": 3})
        self.assertEqual(result["registry_sha256"], hashlib.sha256(raw).hexdigest())

    def test_rejects_payload_tampering(self):
        raw = encode([(1, *start("one"))])
        with self.assertRaises(TrialRegistryError):
            verify_trial_registry(raw.replace(b'"strategy_id":"SMA"', b'"strategy_id":"RSI"'))

    def test_rejects_noncontiguous_sequence_and_duplicate_trial(self):
        with self.assertRaisesRegex(TrialRegistryError, "contiguous"):
            verify_trial_registry(encode([(2, *start("one"))]))
        event = start("one")
        with self.assertRaisesRegex(TrialRegistryError, "started once"):
            verify_trial_registry(encode([(1, *event), (2, *event)]))

    def test_rejects_finish_without_start_and_invalid_finish(self):
        finish = ("TRIAL_FINISHED", {"trial_id": "missing", "status": "FAILED", "result_sha256": None})
        with self.assertRaisesRegex(TrialRegistryError, "unknown trial"):
            verify_trial_registry(encode([(1, *finish)]))
        events = [start("one"), ("TRIAL_FINISHED", {
            "trial_id": "one", "status": "UNKNOWN", "result_sha256": None,
        })]
        with self.assertRaisesRegex(TrialRegistryError, "status"):
            verify_trial_registry(encode([(i + 1, *event) for i, event in enumerate(events)]))

    def test_rejects_duplicate_json_keys_and_missing_newline(self):
        with self.assertRaisesRegex(TrialRegistryError, "ending with newline"):
            verify_trial_registry(b"{}")
        raw = b'{"seq":1,"seq":1,"event":"TRIAL_STARTED","payload":{},"previous_hash":"' + b"0" * 64 + b'","record_hash":"' + b"0" * 64 + b'"}\n'
        with self.assertRaisesRegex(TrialRegistryError, "duplicate JSON"):
            verify_trial_registry(raw)


if __name__ == "__main__":
    unittest.main()
