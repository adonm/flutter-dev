#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

SCRIPT = pathlib.Path(__file__).with_name("flutter_sdk.py")
SPEC = importlib.util.spec_from_file_location("flutter_sdk", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
flutter_sdk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flutter_sdk)


class FlutterSdkArchiveTests(unittest.TestCase):
    def make_tree(self, root: pathlib.Path) -> pathlib.Path:
        sdk = root / "sdk"
        (sdk / "bin").mkdir(parents=True)
        executable = sdk / "bin/flutter"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o755)
        (sdk / "README").write_text("sdk\n")
        return sdk

    def test_archives_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            sdk = self.make_tree(root)
            first_tar = root / "first.tar.xz"
            second_tar = root / "second.tar.xz"
            flutter_sdk.write_tar_xz(sdk, first_tar)
            flutter_sdk.write_tar_xz(sdk, second_tar)
            self.assertEqual(first_tar.read_bytes(), second_tar.read_bytes())

            first_zip = root / "first.zip"
            second_zip = root / "second.zip"
            flutter_sdk.write_zip(sdk, first_zip)
            flutter_sdk.write_zip(sdk, second_zip)
            self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())
            with zipfile.ZipFile(first_zip) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["flutter/", "flutter/bin/", "flutter/README", "flutter/bin/flutter"],
                )

    @unittest.skipIf(not hasattr(pathlib.Path, "symlink_to"), "symlinks unavailable")
    def test_archive_rejects_escaping_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            sdk = self.make_tree(root)
            (sdk / "escape").symlink_to("../outside")
            with self.assertRaisesRegex(SystemExit, "escaping SDK symlink"):
                list(flutter_sdk.archive_paths(sdk))


class FlutterSdkManifestTests(unittest.TestCase):
    def test_combine_generates_mise_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            for platform_name in flutter_sdk.PLATFORMS:
                asset = flutter_sdk.expected_asset(platform_name)
                archive = root / asset
                archive.write_bytes(platform_name.encode())
                digest = flutter_sdk.sha256(archive)
                (root / f"{asset}.sha256").write_text(f"{digest}  {asset}\n")
                metadata = {
                    "schema": 1,
                    "platform": platform_name,
                    "archive": asset,
                    "archive_sha256": digest,
                    "archive_size": archive.stat().st_size,
                    "framework_version": flutter_sdk.FLUTTER_FRAMEWORK_VERSION,
                    "framework_revision": flutter_sdk.FLUTTER_SDK_REVISION,
                    "engine_revision": flutter_sdk.FLUTTER_ENGINE_REVISION,
                    "precache_engine_content_hash": flutter_sdk.PRECACHE_ENGINE_CONTENT_HASH,
                    "dart_sdk_version": flutter_sdk.DART_SDK_VERSION,
                    "flutter_version": {},
                    "gtk4_engine_sha256": (
                        flutter_sdk.GTK4_ENGINE_SHA256
                        if platform_name == "linux-x64"
                        else None
                    ),
                }
                (root / f"{platform_name}.json").write_text(json.dumps(metadata))

            flutter_sdk.combine(root)
            flutter_sdk.verify_release(root)
            generated = (root / "flutter-sdk.mise.toml").read_text()
            self.assertIn('[tools."http:flutter".platforms]', generated)
            for platform_name in flutter_sdk.PLATFORMS:
                self.assertIn(f"{platform_name} =", generated)


if __name__ == "__main__":
    unittest.main()
