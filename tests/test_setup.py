"""Offline behavior tests for setup and generated command dispatch."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SETUP = REPO / "scripts/setup.py"


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project with spaces"
        self.root.mkdir()
        self.env = dict(os.environ, HOME=self.tmp.name)

    def run_setup(self, *args, ok=True):
        result = subprocess.run(
            [
                sys.executable,
                str(SETUP),
                "--skip-deps",
                "--project",
                str(self.root),
                *args,
            ],
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_gitignore_repeat_and_preserve(self):
        path = self.root / ".gitignore"
        path.write_text("# custom\nprivate/\n")
        self.run_setup("--modules", "gitignore", "--language", "go")
        original = path.read_text()
        self.assertIn(".agents/", original)
        self.assertIn(".codex/", original)
        self.assertNotIn(".claude/", original)
        self.run_setup("--modules", "gitignore", "--language", "go")
        self.assertEqual(path.read_text(), original)
        path.write_text("# later\n" + original)
        self.run_setup("--update")
        self.assertTrue(path.read_text().startswith("# later\n# custom"))

    def test_preview_does_not_write(self):
        self.run_setup(
            "--modules",
            "gitignore,lint,makefile,ci",
            "--language",
            "go",
            "--go-version",
            "1.23",
            "--dry-run",
        )
        self.assertEqual(list(self.root.iterdir()), [])

    def test_conflict_all_or_nothing_and_backup(self):
        make = self.root / "Makefile"
        make.write_text("custom\n")
        self.run_setup("--modules", "gitignore,makefile", "--language", "go", ok=False)
        self.assertEqual(list(self.root.iterdir()), [make])
        self.run_setup("--modules", "gitignore,makefile", "--language", "go", "--force")
        backups = list((self.root / ".setup/backups").rglob("Makefile"))
        self.assertEqual(backups[0].read_text(), "custom\n")
        make.write_text("local changes\n")
        self.run_setup("--update", ok=False)
        self.assertEqual(make.read_text(), "local changes\n")

    def test_update_unchanged_managed_template(self):
        self.run_setup("--modules", "makefile", "--language", "go")
        path = self.root / "Makefile"
        state = self.root / ".setup/state.json"
        import hashlib

        path.write_text("old template\n")
        data = json.loads(state.read_text())
        data["files"]["Makefile"]["hash"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        state.write_text(json.dumps(data))
        self.run_setup("--modules", "makefile", "--language", "go", ok=False)
        self.run_setup("--update")
        self.assertIn("format-check", path.read_text())

    def test_managed_ignore_conflict(self):
        self.run_setup("--modules", "gitignore")
        path = self.root / ".gitignore"
        path.write_text(path.read_text().replace(".agents/", "mine/"))
        self.run_setup("--update", ok=False)
        self.assertIn("mine/", path.read_text())

    def test_preferences_cli_and_missing_versions(self):
        config = Path(self.tmp.name) / "prefs.json"
        config.write_text(
            json.dumps(
                {
                    "modules": ["gitignore"],
                    "languages": ["python"],
                    "agents": ["claude"],
                }
            )
        )
        self.run_setup("--config", str(config), "--agents", "codex")
        self.assertNotIn(".claude/", (self.root / ".gitignore").read_text())
        self.assertIn("__pycache__/", (self.root / ".gitignore").read_text())
        self.run_setup("--modules", "ci", "--language", "python", ok=False)
        self.assertFalse((self.root / ".github").exists())

    def test_existing_ruff_and_locked_project(self):
        (self.root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        self.run_setup("--modules", "lint")
        self.assertFalse((self.root / ".setup/ruff.toml").exists())
        (self.root / "uv.lock").touch()
        self.run_setup("--modules", "ci", "--python-version", "3.12", ok=False)
        self.run_setup(
            "--modules",
            "ci",
            "--python-version",
            "3.12",
            "--python-install",
            "uv sync --frozen",
            "--force",
        )
        data = json.loads((self.root / ".setup/checks.json").read_text())
        self.assertEqual(data["python_install"], [["uv", "sync", "--frozen"]])

    def test_symlink_and_malformed_ignore(self):
        external = Path(self.tmp.name) / "external"
        external.mkdir()
        (self.root / ".setup").symlink_to(external)
        self.run_setup("--modules", "gitignore", ok=False)
        self.assertEqual(list(external.iterdir()), [])
        (self.root / ".setup").unlink()
        (self.root / ".gitignore").write_text("# BEGIN project-setup\n")
        self.run_setup("--modules", "gitignore", ok=False)

    def test_each_language_and_ci_only(self):
        for language, extra in [
            ("go", ["--go-version", "1.23"]),
            ("python", ["--python-version", "3.12"]),
            ("java", ["--java-version", "17", "--java-build", "maven"]),
        ]:
            self.run_setup("--modules", "ci", "--language", language, *extra, "--force")
            workflow = (
                self.root / f".github/workflows/setup-{language}.yml"
            ).read_text()
            self.assertIn("contents: read", workflow)
            self.assertIn(
                "python3 .setup/check.py check --language " + language, workflow
            )
            self.assertNotIn("make check", workflow)
        self.assertFalse((self.root / "Makefile").exists())

    def test_skills_and_bootstrap(self):
        import shutil
        import tarfile

        fixture = Path(self.tmp.name) / "repo"
        (fixture / "skills/demo").mkdir(parents=True)
        (fixture / "skills/demo/SKILL.md").write_text("fixture skill")
        (fixture / "sources.toml").write_text(
            '[[sources]]\nid = "demo"\ndest = "skills/demo"\n'
        )
        shutil.copytree(REPO / "templates", fixture / "templates")
        shutil.copytree(REPO / "scripts", fixture / "scripts")
        archive = Path(self.tmp.name) / "fixture.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(fixture, arcname="fixture")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        curl = bin_dir / "curl"
        curl.write_text(
            '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
            'if [ "$1" = "-o" ]; then cp "$FIXTURE" "$2"; exit; fi\n'
            "shift\ndone\nexit 1\n"
        )
        curl.chmod(0o755)
        self.env.update(
            PATH=str(bin_dir) + ":" + os.environ["PATH"], FIXTURE=str(archive)
        )
        self.run_setup("--modules", "skills,gitignore", "--only", "demo")
        for destination in (".codex/skills/demo", ".agents/skills/demo"):
            self.assertEqual(
                (self.root / destination / "SKILL.md").read_text(), "fixture skill"
            )
        self.assertEqual((self.root / ".gitignore").read_text().count(".agents/"), 1)
        (self.root / ".agents/skills/demo/SKILL.md").write_text("old")
        self.run_setup("--update")
        self.assertEqual(
            (self.root / ".agents/skills/demo/SKILL.md").read_text(), "fixture skill"
        )
        result = subprocess.run(
            [
                "sh",
                str(REPO / "scripts/setup.sh"),
                "--modules",
                "gitignore",
                "--agents",
                "claude",
                "--skip-deps",
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(".claude/", (self.root / ".gitignore").read_text())
        piped_project = Path(self.tmp.name) / "piped-project"
        piped_project.mkdir()
        result = subprocess.run(
            [
                "sh",
                "-s",
                "--",
                "--mode",
                "new",
                "--language",
                "go",
                "--modules",
                "gitignore",
                "--dry-run",
            ],
            input=(REPO / "scripts/setup.sh").read_text(),
            cwd=piped_project,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("git init", result.stdout)
        self.assertEqual(list(piped_project.iterdir()), [])

        fresh = Path(self.tmp.name) / "brand-new"
        fresh.mkdir()
        self.run_setup(
            "--project",
            str(fresh),
            "--mode",
            "new",
            "--language",
            "python",
            "--only",
            "demo",
        )
        self.assertTrue((fresh / ".git").is_dir())
        self.assertTrue((fresh / "Makefile").exists())
        self.assertTrue((fresh / ".github/workflows/setup-python.yml").exists())
        self.assertTrue((fresh / ".agents/skills/demo/SKILL.md").exists())
        personal = Path(self.tmp.name) / "existing"
        personal.mkdir()
        (personal / "go.mod").write_text("module example.test/personal\n\ngo 1.23\n")
        self.run_setup(
            "--project", str(personal), "--mode", "existing", "--only", "demo"
        )
        self.assertFalse((personal / ".git").exists())
        self.assertFalse((personal / "Makefile").exists())
        self.assertFalse((personal / ".github").exists())
        self.assertFalse((personal / ".setup/check.py").exists())
        self.assertEqual(
            json.loads((personal / ".setup/state.json").read_text())["options"]["mode"],
            "existing",
        )

    def test_separate_modules_remain_updatable(self):
        self.run_setup(
            "--modules", "makefile,ci", "--language", "go", "--go-version", "1.23"
        )
        self.run_setup("--modules", "gitignore")
        state = json.loads((self.root / ".setup/state.json").read_text())
        self.assertEqual(
            set(state["options"]["modules"]), {"makefile", "ci", "gitignore"}
        )
        self.run_setup("--update")
        self.assertTrue((self.root / ".github/workflows/setup-go.yml").exists())

    def test_multilanguage_config_and_workflows(self):
        self.run_setup(
            "--modules",
            "makefile,ci",
            "--language",
            "go,python",
            "--go-version",
            "1.23",
            "--python-version",
            "3.12",
        )
        data = json.loads((self.root / ".setup/checks.json").read_text())
        self.assertEqual(data["languages"], ["go", "python"])
        for language in ("go", "python"):
            workflow = (
                self.root / f".github/workflows/setup-{language}.yml"
            ).read_text()
            self.assertIn("make check SETUP_LANGUAGE=" + language, workflow)

    def test_modes_and_interactive_new_preview(self):
        (self.root / "go.mod").write_text("module example.test/demo\n\ngo 1.23\n")
        (self.root / "Makefile").write_text("user makefile\n")
        before = {p.name: p.read_text() for p in self.root.iterdir()}
        self.run_setup("--mode", "existing", "--dry-run")
        self.assertEqual(before, {p.name: p.read_text() for p in self.root.iterdir()})
        self.run_setup("--mode", "existing", "--modules", "ci", ok=False)
        fresh = Path(self.tmp.name) / "new-project"
        fresh.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                str(SETUP),
                "--project",
                str(fresh),
                "--interactive",
                "--dry-run",
            ],
            env=self.env,
            input="1\n2\n\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("setup-python.yml", result.stdout)
        self.assertEqual(list(fresh.iterdir()), [])
        self.run_setup(
            "--project",
            str(fresh),
            "--mode",
            "new",
            "--non-interactive",
            "--dry-run",
            ok=False,
        )
        self.run_setup(
            "--project", str(fresh), "--mode", "new", "--language", "go", "--dry-run"
        )
        self.assertEqual(list(fresh.iterdir()), [])

    def test_missing_project_directory_is_never_created(self):
        missing = Path(self.tmp.name) / "missing"
        for mode in ("new", "existing"):
            for preview in ([], ["--dry-run"]):
                self.run_setup(
                    "--project",
                    str(missing),
                    "--mode",
                    mode,
                    "--language",
                    "go",
                    *preview,
                    ok=False,
                )
                self.assertFalse(missing.exists())

    def test_new_git_initialization_and_preservation(self):
        args = ["--mode", "new", "--modules", "gitignore", "--language", "go"]
        output = self.run_setup(*args, "--dry-run")
        self.assertIn("git init", output)
        self.assertFalse((self.root / ".git").exists())
        self.run_setup(*args)
        self.assertTrue((self.root / ".git").is_dir())
        config = self.root / ".git/config"
        config.write_text(config.read_text() + "\n[setup-test]\n\tkeep = true\n")
        before = config.read_bytes()
        output = self.run_setup(*args)
        self.assertNotIn("git init", output)
        self.assertEqual(config.read_bytes(), before)
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_real_go_commands(self):
        import shutil

        if not shutil.which("go") or not shutil.which("golangci-lint"):
            self.skipTest("Go or golangci-lint unavailable")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "go.mod").write_text("module example.test/demo\n\ngo 1.22\n")
        source = self.root / "main.go"
        source.write_text('package main\nfunc main(){println("ok")}\n')
        self.run_setup("--modules", "gitignore,lint,makefile,ci")
        env = dict(
            self.env,
            GOCACHE=str(Path(self.tmp.name) / "gocache"),
            GOTOOLCHAIN="local",
            GOLANGCI_LINT_CACHE=str(Path(self.tmp.name) / "lintcache"),
        )

        def run(action):
            return subprocess.run(
                [sys.executable, str(self.root / ".setup/check.py"), action],
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(run("format-check").returncode, 0)
        self.assertEqual(run("format").returncode, 0)
        before = source.read_text()
        result = subprocess.run(
            ["golangci-lint", "config", "verify", "--config", ".golangci.yml"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = run("check")
        self.assertIn("golangci-lint run", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, source.read_text())
        # An ignored error is not reported by go vet; prove the extra linter runs.
        source.write_text(
            "package main\n\nfunc mayFail() error { return nil }\n\nfunc main() { mayFail() }\n"
        )
        result = run("lint")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("errcheck", result.stdout + result.stderr)
        source.write_text(before)

        result = subprocess.run(
            ["make", "check"],
            cwd=self.root,
            env=dict(env, LANGUAGE="zh_CN:zh"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_golangci_config_protection(self):
        config = self.root / ".golangci.yml"
        config.write_text('version: "2"\nlinters:\n  default: all\n')
        original = config.read_text()
        self.run_setup("--modules", "lint", "--language", "go", ok=False)
        self.assertEqual(config.read_text(), original)
        config.rename(self.root / ".golangci.yaml")
        self.run_setup("--modules", "ci", "--language", "go", "--go-version", "1.25")
        self.assertFalse(config.exists())
        self.assertEqual((self.root / ".golangci.yaml").read_text(), original)
        data = json.loads((self.root / ".setup/checks.json").read_text())
        self.assertEqual(data["golangci_config"], ".golangci.yaml")
        workflow = (self.root / ".github/workflows/setup-go.yml").read_text()
        self.assertIn("install-only: true", workflow)
        self.assertIn("version: v2.15.0", workflow)

    def test_java_wrapper_dispatch(self):
        for tool, wrapper, test_args, build_args in [
            ("maven", "mvnw", "-B test", "-B -DskipTests package"),
            ("gradle", "gradlew", "--no-daemon test", "--no-daemon assemble"),
        ]:
            self.run_setup(
                "--modules",
                "lint",
                "--language",
                "java",
                "--java-build",
                tool,
                "--force",
            )
            path = self.root / wrapper
            path.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> calls.log\n')
            for action in ("test", "build"):
                result = subprocess.run(
                    [sys.executable, str(self.root / ".setup/check.py"), action],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (self.root / "calls.log").read_text().splitlines(),
                [test_args, build_args],
            )
            (self.root / "calls.log").unlink()
            path.unlink()


if __name__ == "__main__":
    unittest.main()
