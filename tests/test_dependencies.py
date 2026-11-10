"""Dependency planning and provisioning with controlled tools, never system installs."""

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "setup_dependencies", REPO / "scripts/dependencies.py"
)
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)


class DependenciesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def args(self, **overrides):
        return SimpleNamespace(
            **(
                dict(
                    mode="new",
                    update=False,
                    modules=["lint", "makefile", "ci"],
                    languages=["go"],
                    go_version="1.25",
                    python_version="3.12",
                    java_version="21",
                    java_build="maven",
                )
                | overrides
            )
        )

    def test_existing_mode_does_not_plan_language_dependencies(self):
        with (
            patch.object(deps.shutil, "which", return_value=None),
            patch.object(deps, "version") as version,
        ):
            self.assertEqual(
                deps.plan(self.args(mode="existing", modules=["skills"]), self.root),
                ["curl", "tar", "gzip"],
            )
            version.assert_not_called()

    def test_missing_tools_and_versions_are_detected(self):
        with (
            patch.object(deps.shutil, "which", return_value=None),
            patch.object(deps, "version", return_value=()),
            patch.object(deps, "usable", return_value=False),
        ):
            self.assertEqual(
                set(deps.plan(self.args(), self.root)),
                {"git", "make", "go", "golangci-lint"},
            )
            java = deps.plan(self.args(languages=["java"]), self.root)
            self.assertIn("jdk", java)
            self.assertIn("maven", java)
            (self.root / "mvnw").touch()
            self.assertNotIn(
                "maven", deps.plan(self.args(languages=["java"]), self.root)
            )

    def test_supported_package_manager_commands(self):
        expected = {
            "apt-get": [("apt-get", "update"), ("apt-get", "install", "-y", "git")],
            "dnf": [("dnf", "install", "-y", "git")],
            "yum": [("yum", "install", "-y", "git")],
            "apk": [("apk", "add", "--no-cache", "git")],
            "pacman": [("pacman", "-S", "--needed", "--noconfirm", "git")],
            "brew": [("brew", "install", "git")],
        }
        for manager, calls in expected.items():
            with (
                self.subTest(manager=manager),
                patch.object(deps, "package_manager", return_value=manager),
                patch.object(deps.os, "geteuid", return_value=0),
                patch.object(deps, "run") as run,
            ):
                deps.install_packages(["git"])
                self.assertEqual([c.args for c in run.call_args_list], calls)
        with (
            patch.object(deps, "package_manager", return_value="apt-get"),
            patch.object(deps.os, "geteuid", return_value=1000),
            patch.object(deps.shutil, "which", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "privileges"):
                deps.install_packages(["git"])

    def test_jdk_package_selection_for_supported_managers(self):
        jdk = self.root / "jdk-21"
        (jdk / "bin").mkdir(parents=True)
        (jdk / "bin/javac").touch()
        for manager, package in [
            ("apt-get", "openjdk-21-jdk"),
            ("dnf", "java-21-openjdk-devel"),
            ("yum", "java-21-openjdk-devel"),
            ("apk", "openjdk21-jdk"),
            ("pacman", "jdk21-openjdk"),
            ("brew", "openjdk@21"),
        ]:
            with (
                self.subTest(manager=manager),
                patch.object(deps, "package_manager", return_value=manager),
                patch.object(deps, "install_packages") as install,
                patch.object(deps.Path, "glob", return_value=iter([jdk])),
                patch.object(deps, "version", return_value=(21,)),
                patch.object(
                    deps.subprocess, "check_output", return_value="/brew/openjdk21"
                ),
            ):
                selected = deps.ensure_jdk("21")
                install.assert_called_once_with([package])
                self.assertEqual(
                    selected,
                    Path("/brew/openjdk21/libexec/openjdk.jdk/Contents/Home")
                    if manager == "brew"
                    else jdk,
                )

    def test_gradle_download_checksum_and_executable(self):
        import hashlib
        import zipfile

        archive = self.root / "fixture.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("gradle-8.12/bin/gradle", "#!/bin/sh\nexit 0\n")
        payload = archive.read_bytes()

        def fetch(url, path, checksum=None):
            if url.endswith(".sha256"):
                path.write_text(hashlib.sha256(payload).hexdigest())
            else:
                self.assertEqual(checksum, hashlib.sha256(payload).hexdigest())
                path.write_bytes(payload)

        with (
            patch.object(deps, "tool_cache", return_value=self.root / "tools"),
            patch.object(deps, "fetch", side_effect=fetch),
            patch.dict(os.environ),
        ):
            environment = deps.provision(
                self.args(languages=["java"], java_build="gradle"),
                self.root,
                ["gradle"],
            )
            program = Path(environment["paths"][0]) / "gradle"
            self.assertTrue(os.access(program, os.X_OK))
            with patch.object(deps, "fetch") as download:
                deps.provision(
                    self.args(languages=["java"], java_build="gradle"),
                    self.root,
                    ["gradle"],
                )
                download.assert_not_called()

    def test_provision_uses_cached_tools_and_local_environment(self):
        cache = self.root / "cached-go/bin"
        cache.mkdir(parents=True)
        (cache / "go").write_text("#!/bin/sh\necho fixture\n")
        with (
            patch.object(deps, "install_go", return_value=cache),
            patch.object(deps, "tool_cache", return_value=self.root),
            patch.dict(os.environ, GOROOT="/unrelated/sdk"),
        ):
            environment = deps.provision(self.args(), self.root, ["go"])
            (self.root / ".setup").mkdir()
            deps.project_environment(self.root, environment)
            self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], str(cache))
            self.assertEqual(os.environ["GOROOT"], str(cache.parent))
            self.assertTrue((self.root / ".setup/python").is_symlink())
            stored = json.loads((self.root / ".setup/environment.json").read_text())
            self.assertEqual(stored["paths"], [str(cache)])
            deps.project_environment(
                self.root, {"paths": [], "variables": {}, "python": sys.executable}
            )
            self.assertEqual(
                json.loads((self.root / ".setup/environment.json").read_text())[
                    "paths"
                ],
                [str(cache)],
            )
            # Shell activation preserves spaces and can be consumed independently.
            result = subprocess.run(
                ["sh", "-c", ". .setup/env.sh; command -v python3"],
                cwd=self.root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_download_checksum_is_enforced(self):
        import hashlib

        payload = b"controlled archive bytes"
        target = self.root / "download"
        expected = hashlib.sha256(payload).hexdigest()
        with patch.object(
            deps.urllib.request,
            "urlopen",
            side_effect=lambda *args, **kwargs: io.BytesIO(payload),
        ):
            deps.fetch("https://example.invalid/tool", target, expected)
        with patch.object(
            deps.urllib.request,
            "urlopen",
            side_effect=lambda *args, **kwargs: io.BytesIO(payload),
        ):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                deps.fetch("https://example.invalid/tool", target, "0" * 64)
        with patch.object(
            deps.urllib.request,
            "urlopen",
            side_effect=[io.BytesIO(b"truncated"), io.BytesIO(payload)],
        ) as download:
            deps.fetch("https://example.invalid/tool", target, expected)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(target.read_bytes(), payload)

    def test_go_version_selection_and_checksum_metadata(self):
        releases = []
        for version in ("1.25.2", "1.25.1"):
            releases.append(
                {
                    "version": "go" + version,
                    "stable": True,
                    "files": [
                        {
                            "filename": f"go{version}.linux-amd64.tar.gz",
                            "os": "linux",
                            "arch": "amd64",
                            "kind": "archive",
                            "sha256": "a" * 64,
                        }
                    ],
                }
            )

        def fetch(url, path, checksum):
            self.assertEqual(checksum, "a" * 64)
            with tarfile.open(path, "w:gz") as bundle:
                item = tarfile.TarInfo("go/bin/go")
                item.mode = 0o755
                data = b"#!/bin/sh\necho fixture\n"
                item.size = len(data)
                bundle.addfile(item, io.BytesIO(data))

        for request, expected in [("1.25", "go1.25.2"), ("1.25.1", "go1.25.1")]:
            with (
                patch.object(deps, "target", return_value=("linux", "amd64")),
                patch.object(deps, "tool_cache", return_value=self.root / "tools"),
                patch.object(
                    deps.urllib.request,
                    "urlopen",
                    return_value=io.BytesIO(json.dumps(releases).encode()),
                ),
                patch.object(deps, "fetch", side_effect=fetch),
            ):
                folder = deps.install_go(request)
                self.assertTrue((folder / "go").exists())
                self.assertIn(expected, str(folder))

    def test_archive_traversal_and_symlinks_are_rejected(self):
        for name, link in [("../escaped", False), ("link", True)]:
            archive = self.root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                member = tarfile.TarInfo(name)
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/etc/passwd"
                else:
                    member.size = 1
                bundle.addfile(member, None if link else io.BytesIO(b"x"))
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                deps.extract(archive, self.root / "extract")
        self.assertFalse((self.root / "escaped").exists())

    def test_dry_run_lists_missing_dependencies_without_installing(self):
        # Load the real orchestrator with dependency operations forbidden.
        sys.path.insert(0, str(REPO / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(REPO / "scripts")))
        setup_spec = importlib.util.spec_from_file_location(
            "dependency_setup_test", REPO / "scripts/setup.py"
        )
        setup = importlib.util.module_from_spec(setup_spec)
        setup_spec.loader.exec_module(setup)
        args = self.args(skip_deps=False, dry_run=True, force=False)
        with (
            patch.object(
                setup.dependencies, "plan", return_value=["go", "golangci-lint"]
            ),
            patch.object(setup.dependencies, "provision") as provision,
            patch.object(setup.dependencies, "finish") as finish,
        ):
            setup.apply(self.root, args, {".setup/checks.json": '{"versions": {}}\n'})
            provision.assert_not_called()
            finish.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
