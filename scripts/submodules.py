#!/usr/bin/env python3
"""Validate and update flutter-dev's pinned submodules."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "submodules.json"
GITMODULES_PATH = ROOT / ".gitmodules"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_FIELDS = {"path", "kind", "origin", "upstream", "branch", "commit", "purpose"}


class ValidationError(Exception):
    pass


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    check: bool = True,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )


def indexed_text(relative: str, working_path: Path) -> str:
    working = working_path.read_text()
    indexed = run(["git", "show", f":{relative}"], check=False)
    if indexed.returncode != 0:
        raise ValidationError(f"{relative} is not staged in the parent index")
    if working != indexed.stdout:
        raise ValidationError(f"{relative} has unstaged changes; stage it before validation")
    return working


def load_manifest() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        data = json.loads(indexed_text("submodules.json", MANIFEST_PATH))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read {MANIFEST_PATH.name}: {error}") from error

    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValidationError("submodules.json must be an object with schema 1")
    entries = data.get("submodules")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("submodules.json must contain a non-empty submodules array")

    seen: set[str] = set()
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValidationError(f"submodule entry {number} must be an object")
        missing = REQUIRED_FIELDS - entry.keys()
        extra = entry.keys() - REQUIRED_FIELDS
        if missing or extra:
            raise ValidationError(
                f"submodule entry {number} has missing={sorted(missing)} extra={sorted(extra)}"
            )
        path = entry["path"]
        if not isinstance(path, str) or not path:
            raise ValidationError(f"submodule entry {number} has an invalid path")
        pure_path = PurePosixPath(path)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise ValidationError(f"submodule path escapes the repository: {path}")
        if path in seen:
            raise ValidationError(f"duplicate submodule path: {path}")
        seen.add(path)
        if not isinstance(entry["origin"], str) or not entry["origin"].startswith("https://"):
            raise ValidationError(f"{path}: origin must be an HTTPS URL")
        upstream = entry["upstream"]
        if upstream is not None and (
            not isinstance(upstream, str) or not upstream.startswith("https://")
        ):
            raise ValidationError(f"{path}: upstream must be null or an HTTPS URL")
        if not isinstance(entry["branch"], str) or not entry["branch"]:
            raise ValidationError(f"{path}: branch must be a non-empty string")
        if not isinstance(entry["commit"], str) or not SHA_RE.fullmatch(entry["commit"]):
            raise ValidationError(f"{path}: commit must be a lowercase 40-character SHA")

    return data, entries


def load_gitmodules() -> dict[str, dict[str, str]]:
    parser = configparser.RawConfigParser()
    try:
        parser.read_string(indexed_text(".gitmodules", GITMODULES_PATH))
    except (OSError, configparser.Error) as error:
        raise ValidationError(f"cannot read .gitmodules: {error}") from error

    modules: dict[str, dict[str, str]] = {}
    for section in parser.sections():
        if not section.startswith('submodule "') or not section.endswith('"'):
            raise ValidationError(f"unexpected .gitmodules section: {section}")
        values = dict(parser.items(section))
        path = values.get("path")
        if not path:
            raise ValidationError(f"{section}: missing path")
        if path in modules:
            raise ValidationError(f"duplicate .gitmodules path: {path}")
        modules[path] = values
    return modules


def load_index_gitlinks() -> dict[str, str]:
    result = run(["git", "ls-files", "--stage", "-z"])
    links: dict[str, str] = {}
    for raw_record in result.stdout.split("\0"):
        if not raw_record:
            continue
        metadata, path = raw_record.split("\t", 1)
        mode, commit, stage = metadata.split(" ")
        if mode != "160000":
            continue
        if stage != "0":
            raise ValidationError(f"unmerged submodule gitlink: {path}")
        links[path] = commit
    return links


def local_branch_contains(path: Path, branch: str, commit: str) -> str | None:
    reference = f"refs/remotes/origin/{branch}"
    exists = run(
        ["git", "show-ref", "--verify", "--quiet", reference],
        cwd=path,
        check=False,
    )
    if exists.returncode != 0:
        return f"missing local {reference}; fetch the configured branch"
    ancestor = run(
        ["git", "merge-base", "--is-ancestor", commit, reference],
        cwd=path,
        check=False,
    )
    if ancestor.returncode != 0:
        return f"pin {commit[:12]} is not reachable from origin/{branch}"
    return None


def anonymous_git_environment() -> tuple[dict[str, str], Path]:
    directory = ROOT / ".tmp" / "anonymous-git"
    directory.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith(("GIT_CONFIG_", "GIT_ASKPASS", "SSH_ASKPASS", "GCM_")):
            environment.pop(key)
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        environment.pop(key, None)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CEILING_DIRECTORIES": str(ROOT),
            "HOME": str(directory),
            "XDG_CONFIG_HOME": str(directory),
        }
    )
    return environment, directory


def remote_branch_error(origin: str, branch: str, commit: str) -> str | None:
    environment, directory = anonymous_git_environment()
    result = run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "http.extraHeader=",
            "ls-remote",
            "--exit-code",
            "--heads",
            origin,
            f"refs/heads/{branch}",
        ],
        cwd=directory,
        check=False,
        environment=environment,
    )
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or "branch was not advertised"
        return f"cannot resolve public branch {branch} at {origin}: {detail}"
    remote_commit = result.stdout.split()[0]
    if remote_commit != commit:
        return (
            f"public branch {branch} points to {remote_commit}, expected exact pin {commit}"
        )
    return None


def check_workspace(*, remote: bool) -> None:
    _, entries = load_manifest()
    modules = load_gitmodules()
    links = load_index_gitlinks()
    expected_paths = {entry["path"] for entry in entries}
    errors: list[str] = []

    for label, actual_paths in ((".gitmodules", set(modules)), ("index", set(links))):
        missing = expected_paths - actual_paths
        extra = actual_paths - expected_paths
        if missing:
            errors.append(f"{label}: missing submodules: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{label}: unexpected submodules: {', '.join(sorted(extra))}")

    for entry in entries:
        error_count = len(errors)
        relative = entry["path"]
        path = ROOT / relative
        module = modules.get(relative, {})
        commit = entry["commit"]

        for key, expected in (("url", entry["origin"]), ("branch", entry["branch"])):
            actual = module.get(key)
            if actual != expected:
                errors.append(f"{relative}: .gitmodules {key}={actual!r}, expected {expected!r}")

        indexed = links.get(relative)
        if indexed != commit:
            errors.append(f"{relative}: index pin={indexed!r}, expected {commit}")

        if not path.exists():
            errors.append(f"{relative}: worktree is missing; run just bootstrap")
            continue

        repository = run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=path, check=False
        )
        if repository.returncode != 0 or repository.stdout.strip() != "true":
            errors.append(f"{relative}: path is not an initialized Git worktree")
            continue

        head = run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()
        if head != commit:
            errors.append(f"{relative}: checkout={head}, expected {commit}")

        origin = run(["git", "config", "--get", "remote.origin.url"], cwd=path, check=False)
        if origin.returncode != 0:
            errors.append(f"{relative}: origin remote is missing")
        elif origin.stdout.strip() != entry["origin"]:
            errors.append(
                f"{relative}: origin={origin.stdout.strip()!r}, expected {entry['origin']!r}"
            )

        dirty = run(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=path
        ).stdout.strip()
        if dirty:
            errors.append(f"{relative}: worktree is dirty:\n{dirty}")

        commit_exists = run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=path, check=False
        )
        if commit_exists.returncode != 0:
            errors.append(f"{relative}: commit object is missing: {commit}")
        else:
            branch_error = local_branch_contains(path, entry["branch"], commit)
            if branch_error:
                errors.append(f"{relative}: {branch_error}")

        if remote:
            branch_error = remote_branch_error(entry["origin"], entry["branch"], commit)
            if branch_error:
                errors.append(f"{relative}: {branch_error}")

        marker = "ok " if len(errors) == error_count else "err"
        print(f"{marker} {relative:<32} {commit[:12]}  {entry['branch']}")

    if errors:
        print("\nSubmodule validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)

    scope = "local pins and public branches" if remote else "local pins"
    print(f"\nValidated {len(entries)} submodules ({scope}).")


def update_pin(relative: str) -> None:
    data, entries = load_manifest()
    matches = [entry for entry in entries if entry["path"] == relative]
    if not matches:
        raise ValidationError(f"unknown submodule path: {relative}")
    entry = matches[0]
    path = ROOT / relative
    if not path.exists():
        raise ValidationError(f"{relative}: worktree is missing; run just bootstrap")

    dirty = run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=path
    ).stdout.strip()
    if dirty:
        raise ValidationError(f"{relative}: refusing to pin a dirty worktree:\n{dirty}")

    origin = run(["git", "config", "--get", "remote.origin.url"], cwd=path).stdout.strip()
    if origin != entry["origin"]:
        raise ValidationError(f"{relative}: origin={origin!r}, expected {entry['origin']!r}")

    commit = run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()
    branch_error = local_branch_contains(path, entry["branch"], commit)
    if branch_error:
        raise ValidationError(f"{relative}: {branch_error}")

    previous = entry["commit"]
    entry["commit"] = commit
    MANIFEST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Updated {relative}: {previous[:12]} -> {commit[:12]}")


def verify_clone(url: str, reference: str, relative_destination: str) -> None:
    source = url
    if "://" not in url and not re.match(r"^[^/]+@[^:]+:", url):
        source = str((ROOT / url).resolve())

    destination = (ROOT / relative_destination).resolve()
    temporary_root = (ROOT / ".tmp").resolve()
    if temporary_root not in destination.parents:
        raise ValidationError("clone destination must be below .tmp/")
    if destination.exists():
        raise ValidationError(f"clone destination already exists: {destination}")

    environment, directory = anonymous_git_environment()
    clone = run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "http.extraHeader=",
            "clone",
            "--no-checkout",
            source,
            str(destination),
        ],
        cwd=directory,
        check=False,
        environment=environment,
    )
    if clone.returncode != 0:
        raise ValidationError(f"parent clone failed: {clone.stderr.strip()}")

    checkout = run(
        ["git", "checkout", "--detach", reference],
        cwd=destination,
        check=False,
        environment=environment,
    )
    if checkout.returncode != 0:
        raise ValidationError(f"cannot check out {reference}: {checkout.stderr.strip()}")

    submodules = run(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=destination,
        check=False,
        environment=environment,
    )
    if submodules.returncode != 0:
        raise ValidationError(f"recursive submodule clone failed: {submodules.stderr.strip()}")

    validation = run(
        [sys.executable, "scripts/submodules.py", "check"],
        cwd=destination,
        check=False,
    )
    if validation.returncode != 0:
        raise ValidationError(
            f"cloned workspace validation failed:\n{validation.stdout}{validation.stderr}"
        )
    print(validation.stdout, end="")
    print(f"Verified recursive clone of {reference} at {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="validate all pinned submodules")
    check_parser.add_argument(
        "--remote",
        action="store_true",
        help="also verify each configured branch is advertised by its public origin",
    )
    pin_parser = subparsers.add_parser("pin", help="record one clean checkout's HEAD")
    pin_parser.add_argument("path", help="exact submodule path from submodules.json")
    clone_parser = subparsers.add_parser("clone", help="verify an isolated recursive clone")
    clone_parser.add_argument("url", help="public parent repository URL")
    clone_parser.add_argument("reference", help="exact parent commit or advertised ref")
    clone_parser.add_argument("destination", help="new destination below .tmp/")
    arguments = parser.parse_args()

    try:
        if arguments.command == "check":
            check_workspace(remote=arguments.remote)
        elif arguments.command == "pin":
            update_pin(arguments.path)
        else:
            verify_clone(arguments.url, arguments.reference, arguments.destination)
    except ValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
