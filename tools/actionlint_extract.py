"""Bounded, non-extracting reader for the pinned Actionlint release archive."""
from __future__ import annotations

import gzip
import os
import stat
import sys
import tarfile
from pathlib import Path

MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_BINARY_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 64
CHUNK_SIZE = 1024 * 1024


class LimitedReader:
    """Cap the decompressed byte stream before tarfile parses it."""

    def __init__(self, raw, limit: int):
        if type(limit) is not int or limit <= 0:
            raise ValueError("expanded-byte limit must be a positive integer")
        self.raw = raw
        self.limit = limit
        self.total = 0

    def read(self, size: int = -1) -> bytes:
        remaining = self.limit - self.total
        if remaining < 0:
            raise ValueError("archive expansion limit exceeded")
        if size is None or size < 0 or size > remaining + 1:
            size = remaining + 1
        data = self.raw.read(size)
        self.total += len(data)
        if self.total > self.limit:
            raise ValueError("archive expansion limit exceeded")
        return data


def _open_regular_archive(path: Path):
    if path.is_symlink():
        raise ValueError("archive must not be a symlink")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    raw = os.fdopen(descriptor, "rb")
    try:
        metadata = os.fstat(raw.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("archive must be a regular file")
        if not 0 < metadata.st_size <= MAX_ARCHIVE_BYTES:
            raise ValueError("archive size is outside the configured limit")
        return raw
    except Exception:
        raw.close()
        raise


def extract_actionlint(
    archive_path: str | os.PathLike[str],
    binary_path: str | os.PathLike[str],
    *,
    max_expanded_bytes: int = MAX_EXPANDED_BYTES,
    max_binary_bytes: int = MAX_BINARY_BYTES,
    max_members: int = MAX_MEMBERS,
) -> None:
    """Copy one bounded regular tar member named actionlint; never extract paths."""
    archive = Path(archive_path)
    binary = Path(binary_path)
    if type(max_expanded_bytes) is not int or not 0 < max_expanded_bytes <= MAX_EXPANDED_BYTES:
        raise ValueError("expanded-byte limit is invalid")
    if type(max_binary_bytes) is not int or not 0 < max_binary_bytes <= MAX_BINARY_BYTES:
        raise ValueError("binary-size limit is invalid")
    if type(max_members) is not int or not 0 < max_members <= MAX_MEMBERS:
        raise ValueError("archive-member limit is invalid")
    if binary.name != "actionlint" or binary.parent.is_symlink() or not binary.parent.is_dir():
        raise ValueError("binary destination must be a fixed file in a real directory")
    if binary.exists() or binary.is_symlink():
        raise FileExistsError("binary destination already exists")

    member_count = 0
    match_count = 0
    binary_data = None
    with _open_regular_archive(archive) as compressed:
        with gzip.GzipFile(fileobj=compressed, mode="rb") as expanded:
            limited = LimitedReader(expanded, max_expanded_bytes)
            with tarfile.open(fileobj=limited, mode="r|") as tar:
                for member in tar:
                    member_count += 1
                    if member_count > max_members:
                        raise ValueError("archive contains too many members")
                    if member.name != "actionlint":
                        continue
                    match_count += 1
                    if match_count != 1:
                        raise ValueError("archive contains duplicate actionlint members")
                    if not member.isfile() or not 0 < member.size <= max_binary_bytes:
                        raise ValueError("actionlint member is not a bounded regular file")
                    source = tar.extractfile(member)
                    if source is None:
                        raise ValueError("unable to read actionlint member")
                    chunks = []
                    remaining = member.size
                    with source:
                        while remaining:
                            chunk = source.read(min(CHUNK_SIZE, remaining))
                            if not chunk:
                                raise ValueError("truncated actionlint member")
                            chunks.append(chunk)
                            remaining -= len(chunk)
                        if source.read(1):
                            raise ValueError("actionlint member exceeds its declared size")
                    binary_data = b"".join(chunks)

            # Drain the decompressed stream to validate the gzip trailer and ensure
            # trailing data is also covered by the expansion limit.
            while limited.read(CHUNK_SIZE):
                pass

    if match_count != 1 or binary_data is None:
        raise ValueError("archive must contain exactly one actionlint member")

    descriptor = os.open(binary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
    with os.fdopen(descriptor, "wb") as output:
        output.write(binary_data)
        output.flush()
        os.fsync(output.fileno())
        os.fchmod(output.fileno(), 0o755)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: actionlint_extract.py ARCHIVE BINARY")
    extract_actionlint(args[0], args[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
