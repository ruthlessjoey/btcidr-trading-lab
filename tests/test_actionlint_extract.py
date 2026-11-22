"""Offline adversarial tests for the bounded Actionlint archive reader."""
import gzip
import io
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from actionlint_extract import MAX_EXPANDED_BYTES, extract_actionlint


class ActionlintExtractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "release.tar.gz"
        self.binary = self.root / "actionlint"

    def make_archive(self, members):
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w") as tar:
            for name, kind, content in members:
                info = tarfile.TarInfo(name)
                if kind == "file":
                    info.size = len(content)
                    tar.addfile(info, io.BytesIO(content))
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = content.decode("utf-8")
                    tar.addfile(info)
                else:
                    raise AssertionError("unsupported synthetic member")
        with gzip.open(self.archive, "wb") as compressed:
            compressed.write(raw.getvalue())

    def test_extracts_one_valid_actionlint_member_to_fixed_destination(self):
        payload = b"synthetic actionlint executable"
        self.make_archive([("README.txt", "file", b"release notes"), ("actionlint", "file", payload)])
        extract_actionlint(self.archive, self.binary)
        self.assertEqual(self.binary.read_bytes(), payload)
        self.assertTrue(os.stat(self.binary).st_mode & 0o111)

    def test_rejects_duplicate_actionlint_members(self):
        self.make_archive([
            ("actionlint", "file", b"first"),
            ("actionlint", "file", b"second"),
        ])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            extract_actionlint(self.archive, self.binary)
        self.assertFalse(self.binary.exists())

    def test_rejects_symlink_named_actionlint(self):
        self.make_archive([("actionlint", "symlink", b"../../outside")])
        with self.assertRaisesRegex(ValueError, "regular file"):
            extract_actionlint(self.archive, self.binary)
        self.assertFalse(self.binary.exists())

    def test_rejects_more_than_configured_member_limit(self):
        self.make_archive([(f"ignored-{n}", "file", b"x") for n in range(4)])
        with self.assertRaisesRegex(ValueError, "too many members"):
            extract_actionlint(self.archive, self.binary, max_members=3)

    def test_rejects_decompressed_stream_over_configured_limit(self):
        self.make_archive([("actionlint", "file", b"x" * 2048)])
        with self.assertRaisesRegex(ValueError, "expansion limit"):
            extract_actionlint(self.archive, self.binary, max_expanded_bytes=1024)

    def test_expanded_limit_cannot_exceed_advertised_hard_cap(self):
        self.make_archive([("actionlint", "file", b"small")])
        for value in (MAX_EXPANDED_BYTES + 1, True, 1.5, 0, -1):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "expanded-byte limit is invalid"):
                    extract_actionlint(self.archive, self.binary, max_expanded_bytes=value)
        self.assertFalse(self.binary.exists())

    def test_rejects_oversized_binary_member(self):
        self.make_archive([("actionlint", "file", b"x" * 20)])
        with self.assertRaisesRegex(ValueError, "bounded regular file"):
            extract_actionlint(self.archive, self.binary, max_binary_bytes=16)

    def test_rejects_archive_with_no_actionlint_member(self):
        self.make_archive([("README.txt", "file", b"notes")])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            extract_actionlint(self.archive, self.binary)

    def test_rejects_existing_destination_without_overwriting(self):
        self.make_archive([("actionlint", "file", b"replacement")])
        self.binary.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            extract_actionlint(self.archive, self.binary)
        self.assertEqual(self.binary.read_bytes(), b"original")

    def test_rejects_symlink_archive(self):
        source = self.root / "real.tar.gz"
        self.make_archive([("actionlint", "file", b"x")])
        self.archive.rename(source)
        self.archive.symlink_to(source)
        with self.assertRaisesRegex(ValueError, "symlink"):
            extract_actionlint(self.archive, self.binary)


    def test_rejects_fifo_archive_without_blocking(self):
        fifo = self.root / "release.pipe"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "regular file"):
            extract_actionlint(fifo, self.binary)
        self.assertFalse(self.binary.exists())

    def test_rejects_symlinked_parent_of_archive(self):
        real_dir = self.root / "real-archive-dir"
        real_dir.mkdir()
        self.make_archive([("actionlint", "file", b"x")])
        nested = real_dir / "release.tar.gz"
        self.archive.rename(nested)
        alias = self.root / "archive-dir-alias"
        alias.symlink_to(real_dir, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked path component"):
            extract_actionlint(alias / nested.name, self.binary)
        self.assertFalse(self.binary.exists())

    def test_rejects_symlinked_parent_of_binary_destination(self):
        self.make_archive([("actionlint", "file", b"x")])
        real_dir = self.root / "real-binary-dir"
        real_dir.mkdir()
        alias = self.root / "binary-dir-alias"
        alias.symlink_to(real_dir, target_is_directory=True)
        destination = alias / "actionlint"
        with self.assertRaisesRegex(ValueError, "symlinked path component"):
            extract_actionlint(self.archive, destination)
        self.assertFalse((real_dir / "actionlint").exists())


if __name__ == "__main__":
    unittest.main()
