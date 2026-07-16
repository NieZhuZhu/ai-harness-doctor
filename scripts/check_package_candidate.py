#!/usr/bin/env python3
"""Pack, install, and self-test the exact local npm package candidate."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

PACKAGE_NAME = "ai-harness-doctor"
COMMAND_TIMEOUT_SECONDS = 120
PUBLIC_READMES = {
    "README.md",
    "README.zh-CN.md",
    "README.ja.md",
    "README.es.md",
    "README.ko.md",
    "README.pt-BR.md",
    "README.fr.md",
}
MAINTENANCE_SCRIPTS = {
    "scripts/check_package_candidate.py",
    "scripts/check_readme_sync.py",
    "scripts/gen_adapters.py",
}
REQUIRED_DOCTOR_CHECKS = {
    "node",
    "python",
    "script:scan",
    "script:explain",
    "script:plan",
    "script:draft",
    "script:validate",
    "script:stubs",
    "script:drift",
    "script:review",
    "script:eval",
    "mcp-server",
}


class PackageCandidateError(Exception):
    """A concise, expected candidate-verification failure."""


def _relative_files(root, directory):
    base = root / directory
    return {
        path.relative_to(root).as_posix()
        for path in base.rglob("*")
        if path.is_file()
    }


def expected_package_files(root):
    """Return the checkout-derived public file inventory required in the tarball."""
    root = Path(root)
    expected = {
        "package.json",
        "LICENSE",
        "SKILL.md",
        *PUBLIC_READMES,
    }
    expected.update(
        path.relative_to(root).as_posix()
        for path in (root / "bin").glob("*.js")
        if path.is_file() and not path.name.endswith(".test.js")
    )
    expected.update(
        path.relative_to(root).as_posix()
        for path in (root / "scripts").glob("*.py")
        if path.is_file()
        and path.relative_to(root).as_posix() not in MAINTENANCE_SCRIPTS
    )
    for directory in ("commands", "adapters", "references", "assets"):
        expected.update(_relative_files(root, directory))
    return expected


def parse_pack_output(stdout):
    try:
        payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PackageCandidateError("npm pack returned invalid JSON") from exc
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise PackageCandidateError("npm pack must return exactly one package record")
    return payload[0]


def _safe_member_path(value):
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return None
    return path.as_posix()


def validate_pack_record(
    root,
    record,
    pack_root,
    *,
    expected_version,
    require_tarball=True,
):
    """Validate one npm pack record and return its contained tarball path."""
    root = Path(root)
    pack_root = Path(pack_root).resolve()
    if record.get("name") != PACKAGE_NAME:
        raise PackageCandidateError("packed package name mismatch")
    if record.get("version") != expected_version:
        raise PackageCandidateError("packed package version mismatch")

    entries = record.get("files")
    if not isinstance(entries, list):
        raise PackageCandidateError("npm pack record is missing its file inventory")
    packaged = set()
    for entry in entries:
        member = _safe_member_path(entry.get("path") if isinstance(entry, dict) else None)
        if member is None:
            raise PackageCandidateError("npm pack record contains an unsafe member path")
        if member in packaged:
            raise PackageCandidateError(
                f"npm pack record contains a duplicate member path: {member}"
            )
        packaged.add(member)

    missing = sorted(expected_package_files(root) - packaged)
    if missing:
        raise PackageCandidateError(
            "missing required package files: " + ", ".join(missing)
        )
    forbidden = sorted(
        path
        for path in packaged
        if path in MAINTENANCE_SCRIPTS
        or path.startswith("tests/")
        or (path.startswith("bin/") and path.endswith(".test.js"))
    )
    if forbidden:
        raise PackageCandidateError(
            "forbidden package files: " + ", ".join(forbidden)
        )

    filename = record.get("filename")
    if not isinstance(filename, str) or not filename:
        raise PackageCandidateError("npm pack record is missing its tarball filename")
    tarball = (pack_root / filename).resolve()
    try:
        tarball.relative_to(pack_root)
    except ValueError as exc:
        raise PackageCandidateError("npm pack tarball path escapes the pack root") from exc
    if require_tarball and not tarball.is_file():
        raise PackageCandidateError("npm pack tarball was not created")
    return tarball


def validate_doctor_report(stdout, *, expected_version):
    try:
        report = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PackageCandidateError(
            "installed doctor self-test returned invalid JSON"
        ) from exc
    if not isinstance(report, dict):
        raise PackageCandidateError("installed doctor self-test returned a non-object")
    if report.get("version") != expected_version:
        raise PackageCandidateError("installed doctor version mismatch")
    checks = report.get("checks")
    if not isinstance(checks, list):
        raise PackageCandidateError("installed doctor report is missing checks")
    by_name = {
        item.get("name"): item
        for item in checks
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    missing = sorted(REQUIRED_DOCTOR_CHECKS - set(by_name))
    unhealthy = sorted(
        name
        for name in REQUIRED_DOCTOR_CHECKS
        if name in by_name and by_name[name].get("ok") is not True
    )
    if missing:
        raise PackageCandidateError(
            "installed doctor is missing checks: " + ", ".join(missing)
        )
    if unhealthy or report.get("ok") is not True:
        names = unhealthy or ["top-level doctor status"]
        raise PackageCandidateError("unhealthy checks: " + ", ".join(names))
    return report


def _command(argv, *, cwd, env, stage):
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PackageCandidateError(f"{stage} could not execute") from exc
    if result.returncode != 0:
        detail = " ".join((result.stderr or result.stdout).split())
        if len(detail) > 300:
            detail = detail[-300:]
        suffix = f": {detail}" if detail else ""
        raise PackageCandidateError(f"{stage} failed{suffix}")
    return result


def verify_candidate(root):
    root = Path(root).resolve()
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    expected_version = package.get("version")
    if not isinstance(expected_version, str) or not expected_version:
        raise PackageCandidateError("package.json has no version")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node is None or npm is None:
        raise PackageCandidateError("Node.js and npm are required")

    with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-package-") as td:
        temporary = Path(td)
        pack_root = temporary / "pack"
        install_root = temporary / "install"
        home = temporary / "home"
        cache = temporary / "npm-cache"
        for path in (pack_root, install_root, home, cache):
            path.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "AI_HARNESS_DOCTOR_NO_UPDATE_CHECK": "1",
                "HOME": str(home),
                "USERPROFILE": str(home),
                "npm_config_cache": str(cache),
                "npm_config_update_notifier": "false",
            }
        )

        packed = _command(
            [
                npm,
                "pack",
                "--ignore-scripts",
                "--json",
                "--pack-destination",
                str(pack_root),
            ],
            cwd=root,
            env=env,
            stage="npm pack",
        )
        record = parse_pack_output(packed.stdout)
        tarball = validate_pack_record(
            root,
            record,
            pack_root,
            expected_version=expected_version,
        )
        _command(
            [
                npm,
                "install",
                "--prefix",
                str(install_root),
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                "--offline",
                str(tarball),
            ],
            cwd=temporary,
            env=env,
            stage="local tarball install",
        )

        package_root = (
            install_root / "node_modules" / PACKAGE_NAME
        ).resolve()
        try:
            package_root.relative_to(install_root.resolve())
        except ValueError as exc:
            raise PackageCandidateError(
                "installed package escaped the install prefix"
            ) from exc
        cli = package_root / "bin" / "cli.js"
        if not cli.is_file():
            raise PackageCandidateError("installed package is missing bin/cli.js")
        doctor = _command(
            [node, str(cli), "doctor", "--self-test", "--json"],
            cwd=temporary,
            env=env,
            stage="installed doctor self-test",
        )
        validate_doctor_report(
            doctor.stdout,
            expected_version=expected_version,
        )
    return expected_version


def main():
    root = Path(__file__).resolve().parent.parent
    try:
        version = verify_candidate(root)
    except PackageCandidateError as exc:
        print(f"package candidate error: {exc}", file=sys.stderr)
        return 1
    print(f"package candidate OK: {PACKAGE_NAME}@{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
