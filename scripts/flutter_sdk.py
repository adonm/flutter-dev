#!/usr/bin/env python3
"""Build and verify immutable, Mise-compatible Flutter SDK archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.parse
import urllib.request
import zipfile
from typing import Any, Iterable

FLUTTER_REPOSITORY = "https://github.com/adonm/flutter.git"
FLUTTER_SDK_REVISION = "328b829d35a3a5d7a00e0c2f0e97eb8cc0d97188"
FLUTTER_VERSION_BASE_TAG = "3.47.0-0.1.pre"
FLUTTER_VERSION_MERGE_BASE = "6cbdfac0e7adb0e4c3c9627c54fc294a67592ff9"
FLUTTER_FRAMEWORK_VERSION = "3.47.0-1.0.pre-160"
FLUTTER_ENGINE_REVISION = "fc1ad955f16467c959e3cd8079b760d5af0984aa"
DART_SDK_VERSION = "3.14.0 (build 3.14.0-28.0.dev)"
ENGINE_BUILD_CONTENT_HASH = "4b9d582709c5336c84a698251b542d65ed790a9d"
PRECACHE_ENGINE_CONTENT_HASH = "469f2b34de41cab5f677ba84d6e9099c0e682d1e"
DART_REVISION = "d402ff7c9c8442d64aa8148609480aa0e04a24fd"
GTK4_ENGINE_SHA256 = "61cafba174d24e2c4f73e416cb98c0b33a0ca751b99bf0d9c42cf2c4f1f44add"
ENGINE_RELEASE_TAG = f"flutter-engine-gtk4-{FLUTTER_SDK_REVISION}"
SDK_RELEASE_TAG = f"flutter-sdk-{FLUTTER_SDK_REVISION}"
RELEASE_BASE_URL = (
    "https://github.com/adonm/flutter-dev/releases/download/" + SDK_RELEASE_TAG
)
ENGINE_BASE_URL = (
    "https://github.com/adonm/flutter-dev/releases/download/" + ENGINE_RELEASE_TAG
)
MAX_ENGINE_DOWNLOAD = 100 * 1024 * 1024

PLATFORMS: dict[str, dict[str, object]] = {
    "linux-x64": {
        "systems": ("linux",),
        "machines": ("x86_64", "amd64"),
        "config": ("--enable-linux-desktop",),
        "precache": ("--android", "--linux", "--web"),
        "extension": "tar.xz",
    },
    "macos-x64": {
        "systems": ("darwin",),
        "machines": ("x86_64", "amd64"),
        "config": ("--enable-ios", "--enable-macos-desktop"),
        "precache": ("--ios", "--macos"),
        "extension": "zip",
    },
    "macos-arm64": {
        "systems": ("darwin",),
        "machines": ("arm64", "aarch64"),
        "config": ("--enable-ios", "--enable-macos-desktop"),
        "precache": ("--ios", "--macos"),
        "extension": "zip",
    },
    "windows-x64": {
        "systems": ("windows",),
        "machines": ("amd64", "x86_64"),
        "config": ("--enable-windows-desktop",),
        "precache": ("--windows",),
        "extension": "zip",
    },
}
PUBLISHED_SHA256 = {
    "linux-x64": "b6e95c97348bebd1f129db1f1cbfb7a4a8f6481839ebe80d3eb746e102336bb9",
    "macos-arm64": "7752c1f52abebeaccd4d3c3d8201cd7b0208282636ae58ef5f1a958ca610358a",
    "macos-x64": "85b9ffaa0316cf84852bd1055514759270e97939a618a79bac3d6037182f0adf",
    "windows-x64": "581f30161c555a5eab288de2b218dec501ac5e71f316b2d36fbb53f5322599ce",
}


def run(
    *args: str,
    capture: bool = False,
    environment: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
) -> str:
    result = subprocess.run(
        args,
        check=True,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def expected_asset(platform_name: str) -> str:
    extension = PLATFORMS[platform_name]["extension"]
    return f"flutter-{platform_name}-{FLUTTER_SDK_REVISION}.{extension}"


def host_system() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    if os.name == "nt":
        return "windows"
    return sys.platform


def validate_host(platform_name: str) -> None:
    contract = PLATFORMS[platform_name]
    system = host_system()
    machine = platform.machine().lower()
    if system not in contract["systems"] or machine not in contract["machines"]:
        raise SystemExit(
            f"{platform_name} SDK must be built on its native host, got {system}-{machine}"
        )


def flutter_command(sdk: pathlib.Path, *args: str) -> tuple[str, ...]:
    executable = sdk / "bin" / ("flutter.bat" if os.name == "nt" else "flutter")
    if not executable.is_file():
        raise SystemExit(f"Flutter executable is missing: {executable}")
    return (str(executable), *args)


def sdk_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["CI"] = "true"
    environment["FLUTTER_PREBUILT_ENGINE_VERSION"] = PRECACHE_ENGINE_CONTENT_HASH
    environment["FLUTTER_SUPPRESS_ANALYTICS"] = "true"
    return environment


def clone_sdk(destination: pathlib.Path) -> None:
    if destination.exists():
        raise SystemExit(f"Flutter SDK destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    run("git", "init", str(destination))
    run("git", "-C", str(destination), "config", "core.longpaths", "true")
    run("git", "-C", str(destination), "remote", "add", "origin", FLUTTER_REPOSITORY)
    run(
        "git",
        "-C",
        str(destination),
        "fetch",
        "--depth=512",
        "--no-tags",
        "origin",
        FLUTTER_SDK_REVISION,
    )
    run(
        "git",
        "-C",
        str(destination),
        "fetch",
        "--depth=512",
        "--no-tags",
        "origin",
        f"refs/tags/{FLUTTER_VERSION_BASE_TAG}:refs/tags/{FLUTTER_VERSION_BASE_TAG}",
    )
    run("git", "-C", str(destination), "checkout", "--detach", FLUTTER_SDK_REVISION)
    merge_base = run(
        "git",
        "-C",
        str(destination),
        "merge-base",
        FLUTTER_VERSION_BASE_TAG,
        "HEAD",
        capture=True,
    )
    if merge_base != FLUTTER_VERSION_MERGE_BASE:
        raise SystemExit(
            f"Flutter version merge base mismatch: expected "
            f"{FLUTTER_VERSION_MERGE_BASE}, got {merge_base}"
        )
    revision = run("git", "-C", str(destination), "rev-parse", "HEAD", capture=True)
    if revision != FLUTTER_SDK_REVISION:
        raise SystemExit(f"Flutter checkout mismatch: {revision}")


def download(name: str, destination: pathlib.Path) -> None:
    url = f"{ENGINE_BASE_URL}/{name}"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise SystemExit(f"refusing unexpected engine URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "flutter-dev-sdk-builder"})
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_ENGINE_DOWNLOAD:
                raise SystemExit(f"engine asset exceeds {MAX_ENGINE_DOWNLOAD} bytes")
            output.write(chunk)


def validate_gtk4_engine(library: pathlib.Path) -> None:
    actual = sha256(library)
    if actual != GTK4_ENGINE_SHA256:
        raise SystemExit(
            f"GTK4 engine SHA-256 mismatch: expected {GTK4_ENGINE_SHA256}, got {actual}"
        )
    if shutil.which("readelf") is None:
        raise SystemExit("readelf is required to validate the Linux GTK4 engine")
    dynamic = run("readelf", "--dynamic", "--wide", str(library), capture=True)
    if "Shared library: [libgtk-4.so.1]" not in dynamic:
        raise SystemExit("GTK4 engine does not directly link libgtk-4.so.1")
    if "Shared library: [libgtk-3.so.0]" in dynamic:
        raise SystemExit("GTK4 engine directly links libgtk-3.so.0")
    sections = run("readelf", "--sections", "--wide", str(library), capture=True)
    if ".debug_info" in sections or ".debug_line" in sections:
        raise SystemExit("GTK4 engine contains debug sections")


def install_gtk4_engine(sdk: pathlib.Path) -> None:
    cache = sdk / "bin/cache/artifacts/engine/linux-x64-release"
    if not (cache / "gen_snapshot").is_file():
        raise SystemExit(f"Flutter Linux release cache is incomplete: {cache}")
    with tempfile.TemporaryDirectory(prefix="flutter-gtk4-") as temporary:
        root = pathlib.Path(temporary)
        library = root / "libflutter_linux_gtk4.so"
        sidecar = root / "libflutter_linux_gtk4.so.sha256"
        metadata_file = root / "engine-metadata.json"
        download(library.name, library)
        download(sidecar.name, sidecar)
        download(metadata_file.name, metadata_file)
        if sidecar.read_text().split() != [GTK4_ENGINE_SHA256, library.name]:
            raise SystemExit("invalid GTK4 engine checksum sidecar")
        metadata = json.loads(metadata_file.read_text())
        expected = {
            "schema": 1,
            "platform": "linux-x64-release",
            "library": library.name,
            "library_sha256": GTK4_ENGINE_SHA256,
            "library_size": library.stat().st_size,
            "flutter_sdk_revision": FLUTTER_SDK_REVISION,
            "engine_content_hash": ENGINE_BUILD_CONTENT_HASH,
            "dart_revision": DART_REVISION,
            "runtime_mode": "release",
            "tests": 620,
        }
        actual = {key: metadata.get(key) for key in expected}
        if actual != expected:
            raise SystemExit(f"GTK4 engine metadata mismatch: {actual}")
        validate_gtk4_engine(library)
        installed = cache / library.name
        shutil.copyfile(library, installed)
        installed.chmod(0o644)
        validate_gtk4_engine(installed)


def version_metadata(sdk: pathlib.Path) -> dict[str, object]:
    machine = json.loads(
        run(
            *flutter_command(sdk, "--version", "--machine"),
            capture=True,
            environment=sdk_environment(),
        )
    )
    expected = {
        "frameworkVersion": FLUTTER_FRAMEWORK_VERSION,
        "frameworkRevision": FLUTTER_SDK_REVISION,
        "engineRevision": FLUTTER_ENGINE_REVISION,
        "dartSdkVersion": DART_SDK_VERSION,
    }
    actual = {key: machine.get(key) for key in expected}
    if actual != expected:
        raise SystemExit(f"Flutter version mismatch: expected {expected}, got {actual}")
    stamp = (sdk / "bin/cache/engine.stamp").read_text().strip()
    if stamp != PRECACHE_ENGINE_CONTENT_HASH:
        raise SystemExit(
            f"Flutter cache mismatch: expected {PRECACHE_ENGINE_CONTENT_HASH}, got {stamp}"
        )
    revision = run("git", "-C", str(sdk), "rev-parse", "HEAD", capture=True)
    if revision != FLUTTER_SDK_REVISION:
        raise SystemExit(f"Flutter Git revision mismatch: {revision}")
    if subprocess.run(
        ["git", "-C", str(sdk), "diff", "--quiet", "HEAD", "--"], check=False
    ).returncode != 0:
        raise SystemExit(f"Flutter SDK contains tracked changes: {sdk}")
    return machine


def prepare_sdk(destination: pathlib.Path, platform_name: str) -> None:
    validate_host(platform_name)
    clone_sdk(destination)
    contract = PLATFORMS[platform_name]
    environment = sdk_environment()
    run(
        *flutter_command(
            destination,
            "--suppress-analytics",
            "config",
            *contract["config"],
        ),
        environment=environment,
    )
    run(
        *flutter_command(
            destination,
            "--suppress-analytics",
            "precache",
            *contract["precache"],
        ),
        environment=environment,
    )
    if platform_name == "linux-x64":
        install_gtk4_engine(destination)
    version_metadata(destination)
    shutil.rmtree(destination / "bin/cache/downloads", ignore_errors=True)
    run("git", "-C", str(destination), "gc", "--prune=now")
    print(f"prepared {platform_name} Flutter SDK at {destination}")


def safe_link(root: pathlib.Path, path: pathlib.Path) -> None:
    target = os.readlink(path)
    if os.path.isabs(target):
        raise SystemExit(f"absolute SDK symlink is not allowed: {path} -> {target}")
    resolved = (path.parent / target).resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise SystemExit(f"escaping SDK symlink is not allowed: {path} -> {target}") from error


def archive_paths(root: pathlib.Path) -> Iterable[pathlib.Path]:
    yield root
    for directory, names, files in os.walk(root, followlinks=False):
        names.sort()
        files.sort()
        base = pathlib.Path(directory)
        for name in names:
            path = base / name
            yield path
            if path.is_symlink():
                safe_link(root, path)
        for name in files:
            path = base / name
            yield path
            if path.is_symlink():
                safe_link(root, path)


def normalized_mode(path: pathlib.Path) -> int:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        return 0o777
    if stat.S_ISDIR(mode):
        return 0o755
    return 0o755 if mode & 0o111 else 0o644


def write_tar_xz(sdk: pathlib.Path, output: pathlib.Path) -> None:
    with tarfile.open(output, "w:xz", preset=6) as archive:
        for path in archive_paths(sdk):
            relative = path.relative_to(sdk)
            name = pathlib.PurePosixPath("flutter", *relative.parts).as_posix()
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = normalized_mode(path)
            if info.isfile():
                with path.open("rb") as source:
                    archive.addfile(info, source)
            else:
                archive.addfile(info)


def zip_info(name: str, mode: int, *, directory: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name + ("/" if directory and not name.endswith("/") else ""))
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.create_system = 3
    file_type = stat.S_IFDIR if directory else stat.S_IFREG
    info.external_attr = (file_type | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def write_zip(sdk: pathlib.Path, output: pathlib.Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in archive_paths(sdk):
            relative = path.relative_to(sdk)
            name = pathlib.PurePosixPath("flutter", *relative.parts).as_posix()
            mode = normalized_mode(path)
            if path.is_symlink():
                info = zip_info(name, mode)
                info.external_attr = (stat.S_IFLNK | mode) << 16
                archive.writestr(info, os.readlink(path).encode())
            elif path.is_dir():
                archive.writestr(zip_info(name, mode, directory=True), b"")
            else:
                info = zip_info(name, mode)
                with path.open("rb") as source, archive.open(info, "w") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)


def package_sdk(sdk: pathlib.Path, platform_name: str, output_dir: pathlib.Path) -> None:
    validate_host(platform_name)
    machine = version_metadata(sdk)
    if platform_name == "linux-x64":
        validate_gtk4_engine(
            sdk
            / "bin/cache/artifacts/engine/linux-x64-release/libflutter_linux_gtk4.so"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    asset = expected_asset(platform_name)
    output = output_dir / asset
    if output.exists():
        raise SystemExit(f"SDK archive already exists: {output}")
    if PLATFORMS[platform_name]["extension"] == "tar.xz":
        write_tar_xz(sdk, output)
    else:
        write_zip(sdk, output)
    digest = sha256(output)
    (output_dir / f"{asset}.sha256").write_text(f"{digest}  {asset}\n")
    metadata = {
        "schema": 1,
        "platform": platform_name,
        "archive": asset,
        "archive_sha256": digest,
        "archive_size": output.stat().st_size,
        "framework_version": FLUTTER_FRAMEWORK_VERSION,
        "framework_revision": FLUTTER_SDK_REVISION,
        "engine_revision": FLUTTER_ENGINE_REVISION,
        "precache_engine_content_hash": PRECACHE_ENGINE_CONTENT_HASH,
        "dart_sdk_version": DART_SDK_VERSION,
        "flutter_version": machine,
        "gtk4_engine_sha256": GTK4_ENGINE_SHA256 if platform_name == "linux-x64" else None,
    }
    (output_dir / f"{platform_name}.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )
    print(f"packaged {output} ({output.stat().st_size} bytes, sha256:{digest})")


def expected_host_metadata(platform_name: str, root: pathlib.Path) -> dict[str, object]:
    path = root / f"{platform_name}.json"
    if not path.is_file():
        raise SystemExit(f"missing SDK host metadata: {path}")
    metadata = json.loads(path.read_text())
    asset = expected_asset(platform_name)
    archive = root / asset
    sidecar = root / f"{asset}.sha256"
    if not archive.is_file() or not sidecar.is_file():
        raise SystemExit(f"missing SDK archive or checksum for {platform_name}")
    digest = sha256(archive)
    expected = {
        "schema": 1,
        "platform": platform_name,
        "archive": asset,
        "archive_sha256": digest,
        "archive_size": archive.stat().st_size,
        "framework_version": FLUTTER_FRAMEWORK_VERSION,
        "framework_revision": FLUTTER_SDK_REVISION,
        "engine_revision": FLUTTER_ENGINE_REVISION,
        "precache_engine_content_hash": PRECACHE_ENGINE_CONTENT_HASH,
        "dart_sdk_version": DART_SDK_VERSION,
        "gtk4_engine_sha256": GTK4_ENGINE_SHA256 if platform_name == "linux-x64" else None,
    }
    actual = {key: metadata.get(key) for key in expected}
    if actual != expected:
        raise SystemExit(f"SDK metadata mismatch for {platform_name}: {actual}")
    if sidecar.read_text().split() != [digest, asset]:
        raise SystemExit(f"invalid SDK checksum sidecar: {sidecar}")
    return metadata


def mise_toml(hosts: dict[str, dict[str, object]]) -> str:
    lines = [
        "# Generated by flutter-dev; do not edit by hand.",
        '[tools."http:flutter"]',
        f'version = "{FLUTTER_FRAMEWORK_VERSION}"',
        "",
        '[tools."http:flutter".platforms]',
    ]
    for platform_name in sorted(hosts):
        metadata = hosts[platform_name]
        lines.append(
            f'{platform_name} = {{ url = "{RELEASE_BASE_URL}/{metadata["archive"]}", '
            f'checksum = "sha256:{metadata["archive_sha256"]}" }}'
        )
    return "\n".join(lines) + "\n"


def combine(root: pathlib.Path) -> None:
    hosts = {
        platform_name: expected_host_metadata(platform_name, root)
        for platform_name in PLATFORMS
    }
    manifest = {
        "schema": 1,
        "release_tag": SDK_RELEASE_TAG,
        "framework_version": FLUTTER_FRAMEWORK_VERSION,
        "framework_revision": FLUTTER_SDK_REVISION,
        "engine_revision": FLUTTER_ENGINE_REVISION,
        "precache_engine_content_hash": PRECACHE_ENGINE_CONTENT_HASH,
        "dart_sdk_version": DART_SDK_VERSION,
        "platforms": hosts,
    }
    (root / "flutter-sdk-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (root / "flutter-sdk.mise.toml").write_text(mise_toml(hosts))
    verify_release(root)
    print(f"combined {len(hosts)} Flutter SDK archives in {root}")


def verify_release(root: pathlib.Path) -> None:
    manifest_path = root / "flutter-sdk-manifest.json"
    mise_path = root / "flutter-sdk.mise.toml"
    if not manifest_path.is_file() or not mise_path.is_file():
        raise SystemExit("SDK release manifest or Mise configuration is missing")
    hosts = {
        platform_name: expected_host_metadata(platform_name, root)
        for platform_name in PLATFORMS
    }
    manifest = json.loads(manifest_path.read_text())
    expected = {
        "schema": 1,
        "release_tag": SDK_RELEASE_TAG,
        "framework_version": FLUTTER_FRAMEWORK_VERSION,
        "framework_revision": FLUTTER_SDK_REVISION,
        "engine_revision": FLUTTER_ENGINE_REVISION,
        "precache_engine_content_hash": PRECACHE_ENGINE_CONTENT_HASH,
        "dart_sdk_version": DART_SDK_VERSION,
        "platforms": hosts,
    }
    if manifest != expected:
        raise SystemExit("combined Flutter SDK manifest does not match host metadata")
    parsed = tomllib.loads(mise_path.read_text())
    flutter = parsed.get("tools", {}).get("http:flutter", {})
    if flutter.get("version") != FLUTTER_FRAMEWORK_VERSION:
        raise SystemExit("generated Mise Flutter version is invalid")
    platforms = flutter.get("platforms")
    expected_platforms = {
        name: {
            "url": f"{RELEASE_BASE_URL}/{metadata['archive']}",
            "checksum": f"sha256:{metadata['archive_sha256']}",
        }
        for name, metadata in hosts.items()
    }
    if platforms != expected_platforms:
        raise SystemExit("generated Mise Flutter platforms are invalid")


def check_config(root: pathlib.Path) -> None:
    manifest = json.loads((root / "submodules.json").read_text())
    flutter = next(
        (item for item in manifest["submodules"] if item["path"] == "sdk/flutter"),
        None,
    )
    if flutter is None or flutter.get("commit") != FLUTTER_SDK_REVISION:
        raise SystemExit("Flutter SDK artifact revision does not match submodules.json")
    if (root / "sdk/flutter").exists():
        revision = run(
            "git", "-C", str(root / "sdk/flutter"), "rev-parse", "HEAD", capture=True
        )
        if revision != FLUTTER_SDK_REVISION:
            raise SystemExit("checked-out Flutter SDK does not match artifact revision")
    with (root / "mise.toml").open("rb") as source:
        mise = tomllib.load(source)
    flutter_tool = mise.get("tools", {}).get("http:flutter", {})
    expected_mise = {
        platform_name: {
            "url": f"{RELEASE_BASE_URL}/{expected_asset(platform_name)}",
            "checksum": f"sha256:{PUBLISHED_SHA256[platform_name]}",
        }
        for platform_name in PLATFORMS
    }
    if (
        flutter_tool.get("version") != FLUTTER_FRAMEWORK_VERSION
        or flutter_tool.get("platforms") != expected_mise
    ):
        raise SystemExit("parent Mise configuration does not match published SDK bytes")
    if mise.get("env", {}).get("FLUTTER_PREBUILT_ENGINE_VERSION") != (
        PRECACHE_ENGINE_CONTENT_HASH
    ):
        raise SystemExit("parent Mise configuration does not select the SDK cache hash")
    print(f"Flutter SDK artifact contract: {FLUTTER_SDK_REVISION}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("platform", choices=PLATFORMS)
    prepare.add_argument("destination", type=pathlib.Path)
    package = subcommands.add_parser("package")
    package.add_argument("platform", choices=PLATFORMS)
    package.add_argument("sdk", type=pathlib.Path)
    package.add_argument("output", type=pathlib.Path)
    combine_parser = subcommands.add_parser("combine")
    combine_parser.add_argument("directory", type=pathlib.Path)
    verify = subcommands.add_parser("verify-release")
    verify.add_argument("directory", type=pathlib.Path)
    config = subcommands.add_parser("check-config")
    config.add_argument("root", nargs="?", type=pathlib.Path, default=pathlib.Path.cwd())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare_sdk(args.destination.resolve(), args.platform)
    elif args.command == "package":
        package_sdk(args.sdk.resolve(), args.platform, args.output.resolve())
    elif args.command == "combine":
        combine(args.directory.resolve())
    elif args.command == "verify-release":
        verify_release(args.directory.resolve())
    elif args.command == "check-config":
        check_config(args.root.resolve())


if __name__ == "__main__":
    main()
