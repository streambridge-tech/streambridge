"""Compare pyproject.toml's version with existing v* git tags.

A pull request must raise the version above the latest tag. A release fails
when v<version> already exists.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_version(value: str) -> tuple[int, ...]:
    text = value.strip()
    if text.lower().startswith("v"):
        text = text[1:]
    parts = text.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"Not a numeric version: {value}")
    return tuple(int(part) for part in parts)


def project_version(root: Path = ROOT) -> str:
    in_project = False
    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project or not stripped.startswith("version"):
            continue
        _, _, raw = stripped.partition("=")
        version = raw.strip().strip('"').strip("'")
        parse_version(version)
        return version
    raise ValueError("project.version is missing from pyproject.toml")


def latest_tag(tags: list[str]) -> str | None:
    parsed: list[tuple[tuple[int, ...], str]] = []
    for tag in tags:
        try:
            parsed.append((parse_version(tag), tag))
        except ValueError:
            continue
    if not parsed:
        return None
    return max(parsed)[1]


def version_is_newer(current: str, latest: str | None) -> bool:
    if not latest:
        return True
    return parse_version(current) > parse_version(latest)


def git_tags(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list", "v*"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_pull_request(root: Path = ROOT) -> str:
    current = project_version(root)
    latest = latest_tag(git_tags(root))
    if not version_is_newer(current, latest):
        raise SystemExit(
            f"Version {current} is not newer than {latest}. "
            "Bump version in pyproject.toml."
        )
    if latest:
        return f"Version {current} is newer than {latest}."
    return f"No release tag yet. Version {current} is ok."


def release_tag(root: Path = ROOT) -> str:
    current = project_version(root)
    tag = f"v{current}"
    if tag in git_tags(root):
        raise SystemExit(
            f"Tag {tag} already exists. Bump version in pyproject.toml."
        )
    return tag


def main(argv: list[str] | None = None) -> int:
    command = (argv or sys.argv[1:])[:1]
    if command == ["check-pr"]:
        print(check_pull_request())
        return 0
    if command == ["release-tag"]:
        print(release_tag())
        return 0
    print("usage: release_version.py check-pr|release-tag", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
