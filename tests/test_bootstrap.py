"""Exercise the shell bootstrap on a minimal PATH with fake package/download services."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class BootstrapTest(unittest.TestCase):
    def test_missing_downloader_archive_tools_and_python_are_provisioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            repo = base / "repo"
            shutil.copytree(REPO / "scripts", repo / "scripts")
            shutil.copytree(REPO / "templates", repo / "templates")
            (repo / "skills/demo").mkdir(parents=True)
            (repo / "skills/demo/SKILL.md").write_text("fixture")
            (repo / "sources.toml").write_text(
                '[[sources]]\nid="demo"\ndest="skills/demo"\n'
            )
            archive = base / "repo.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                bundle.add(repo, arcname="repo")
            uv_dir = base / "uv-x86_64-unknown-linux-gnu"
            uv_dir.mkdir()
            uv = uv_dir / "uv"
            uv.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$LOG"\nif [ "$2" = find ]; then printf "%s\\n" "$REAL_PYTHON"; fi\n'
            )
            uv.chmod(0o755)
            uv_archive = base / "uv.tar.gz"
            with tarfile.open(uv_archive, "w:gz") as bundle:
                bundle.add(uv_dir, arcname=uv_dir.name)
            mock_curl = base / "curl"
            mock_curl.write_text(
                '#!/bin/sh\nsource_archive="$REPO_ARCHIVE"\nwhile [ "$#" -gt 0 ]; do\ncase "$1" in *astral-sh*) source_archive="$UV_ARCHIVE";; -o) cp "$source_archive" "$2"; exit;; esac\nshift\ndone\nexit 1\n'
            )
            mock_curl.chmod(0o755)
            # Provide POSIX base utilities only; deliberately omit curl/tar/gzip/Python.
            for tool in (
                "sh",
                "mkdir",
                "mktemp",
                "cp",
                "chmod",
                "rm",
                "mv",
                "awk",
                "grep",
                "tail",
                "tr",
                "find",
                "head",
            ):
                (bin_dir / tool).symlink_to(shutil.which(tool))
            (bin_dir / "id").write_text("#!/bin/sh\necho 0\n")
            (bin_dir / "uname").write_text(
                '#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo x86_64;; esac\n'
            )
            (bin_dir / "python3").write_text("#!/bin/sh\nexit 1\n")
            apt = bin_dir / "apt-get"
            apt.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$LOG"\nif [ "$1" = install ]; then\ncp "$MOCK_CURL" "$TEST_BIN/curl"\n"$REAL_LN" -s "$REAL_TAR" "$TEST_BIN/tar"\n"$REAL_LN" -s "$REAL_GZIP" "$TEST_BIN/gzip"\nfi\n'
            )
            for tool in ("id", "uname", "python3", "apt-get"):
                (bin_dir / tool).chmod(0o755)
            env = dict(
                os.environ,
                PATH=str(bin_dir),
                HOME=str(base / "home"),
                XDG_CACHE_HOME=str(base / "cache"),
                LOG=str(base / "calls"),
                REAL_PYTHON=sys.executable,
                REPO_ARCHIVE=str(archive),
                UV_ARCHIVE=str(uv_archive),
                MOCK_CURL=str(mock_curl),
                TEST_BIN=str(bin_dir),
                REAL_LN=shutil.which("ln"),
                REAL_TAR=shutil.which("tar"),
                REAL_GZIP=shutil.which("gzip"),
            )
            script = str(REPO / "scripts/setup.sh")
            preview = subprocess.run(
                ["/bin/sh", script, "--dry-run"],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertFalse((base / "calls").exists())
            self.assertFalse((base / "cache").exists())
            result = subprocess.run(
                [
                    "/bin/sh",
                    script,
                    "--mode",
                    "existing",
                    "--only",
                    "demo",
                    "--non-interactive",
                ],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            log = (base / "calls").read_text()
            self.assertIn("install -y curl tar gzip ca-certificates", log)
            self.assertIn("python install 3.12", log)
            self.assertTrue((project / ".agents/skills/demo/SKILL.md").exists())
            self.assertFalse((project / ".git").exists())
            self.assertFalse((project / ".setup/check.py").exists())
            # Retry uses the cached uv executable and package prerequisites.
            second = subprocess.run(
                [
                    "/bin/sh",
                    script,
                    "--mode",
                    "existing",
                    "--only",
                    "demo",
                    "--update",
                    "--non-interactive",
                ],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual((base / "calls").read_text().count("install -y"), 1)


if __name__ == "__main__":
    unittest.main()
