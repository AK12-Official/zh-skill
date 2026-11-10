"""Run generated lint configurations against readable and violating code."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SETUP = REPO / "scripts/setup.py"


class GeneratedLintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="set-up-lint-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(
            os.environ,
            HOME=str(self.root),
            GOCACHE=str(self.root / "gocache"),
            GOLANGCI_LINT_CACHE=str(self.root / "lintcache"),
            GOTOOLCHAIN="local",
        )

    def setup_language(self, language):
        command = [
            sys.executable,
            str(SETUP),
            "--project",
            str(self.root),
            "--mode",
            "new",
            "--language",
            language,
            "--modules",
            "lint",
            "--skip-deps",
            "--non-interactive",
        ]
        if language == "java":
            command += ["--java-build", "maven"]
        result = subprocess.run(command, capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def run_command(self, *command):
        return subprocess.run(
            command, cwd=self.root, env=self.env, capture_output=True, text=True
        )

    def test_go_quality_rules_reject_real_violations(self):
        if not shutil.which("go") or not shutil.which("golangci-lint"):
            self.skipTest("Go and golangci-lint required")
        self.setup_language("go")
        (self.root / "go.mod").write_text("module example.test/quality\n\ngo 1.22\n")
        verified = self.run_command(
            "golangci-lint", "config", "verify", "--config", ".golangci.yml"
        )
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        file = self.root / "quality.go"
        check = [sys.executable, str(self.root / ".setup/check.py"), "lint"]
        file.write_text("package quality\n\nfunc Add(a, b int) int { return a + b }\n")
        accepted = self.run_command(*check)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        lines = "\n".join(f"    {i}," for i in range(65))
        cases = [
            (
                "long-line",
                "// " + "readable words " * 12 + "\nfunc Short() {}\n",
                ["lll"],
            ),
            (
                "long-function",
                "func ManyLines() int {\n values := []int{\n"
                + lines
                + "\n }\n return len(values)\n}\n",
                ["funlen"],
            ),
            (
                "many-statements",
                "func ManyStatements(n int) int {\n" + "n++\n" * 45 + "return n\n}\n",
                ["funlen"],
            ),
            (
                "branches",
                "func Branches(n int) int {\n"
                + "\n".join(f"if n == {i} {{ n++ }}" for i in range(20))
                + "\nreturn n\n}\n",
                ["gocyclo"],
            ),
            (
                "nested",
                "func Nested(n int) int {\n"
                + "".join(f"if n > {i} {{\n" for i in range(7))
                + "return n + 1\n"
                + "}\n" * 7
                + "return n\n}\n",
                ["gocognit", "nestif"],
            ),
            (
                "naked-return",
                "func Naked() (result int) {\n values := []int{\n"
                + "\n".join(f"{i}," for i in range(32))
                + "\n}\nresult = len(values)\nreturn\n}\n",
                ["nakedret"],
            ),
            (
                "unexplained-nolint",
                'func LongText() string {\nreturn "'
                + "words " * 25
                + '" //nolint:lll\n}\n',
                ["nolintlint"],
            ),
        ]
        for name, code, expected in cases:
            with self.subTest(case=name):
                file.write_text("package quality\n\n" + code)
                formatted = self.run_command("gofmt", "-w", str(file))
                self.assertEqual(formatted.returncode, 0, formatted.stderr)
                result = self.run_command(*check)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                for linter in expected:
                    self.assertIn("(" + linter + ")", result.stdout + result.stderr)
        file.write_text(
            'package quality\n\nfunc LongText() string {\nreturn "'
            + "words " * 25
            + '" //nolint:lll // External protocol text must stay on one line.\n}\n'
        )
        accepted = self.run_command(*check)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

    def test_python_length_and_complexity_rules(self):
        ruff = os.environ.get("SETUP_TEST_RUFF") or shutil.which("ruff")
        if not ruff:
            self.skipTest("Ruff required; set SETUP_TEST_RUFF to its executable")
        self.setup_language("python")
        file = self.root / "quality.py"
        command = [ruff, "check", "--config", ".setup/ruff.toml", str(file)]
        file.write_text("def add(a, b):\n    return a + b\n")
        self.assertEqual(self.run_command(*command).returncode, 0)
        cases = [
            ("line", "# " + "readable words " * 10 + "\n", "E501"),
            (
                "statements",
                "def long_function(n):\n" + "    n += 1\n" * 55 + "    return n\n",
                "PLR0915",
            ),
            (
                "branches",
                "def branches(n):\n"
                + "".join(f"    if n == {i}:\n        n += 1\n" for i in range(15))
                + "    return n\n",
                "PLR0912",
            ),
            (
                "complexity",
                "def complexity(n):\n"
                + "".join(f"    if n == {i}:\n        n += 1\n" for i in range(11))
                + "    return n\n",
                "C901",
            ),
        ]
        for name, code, expected in cases:
            with self.subTest(case=name):
                file.write_text(code)
                result = self.run_command(*command)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def test_java_length_and_complexity_rules(self):
        jar = os.environ.get("SETUP_TEST_CHECKSTYLE_JAR")
        if not jar or not Path(jar).is_file() or not shutil.which("java"):
            self.skipTest("Java and SETUP_TEST_CHECKSTYLE_JAR required")
        self.setup_language("java")
        file = self.root / "Quality.java"
        command = ["java", "-jar", jar, "-c", ".setup/checkstyle.xml", str(file)]
        file.write_text(
            "class Quality {\n  int add(int a, int b) {\n    return a + b;\n  }\n}\n"
        )
        accepted = self.run_command(*command)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        cases = [
            ("line", "// " + "readable words " * 10 + "\n", "LineLength"),
            (
                "method",
                "  int longMethod(int n) {\n"
                + "    n++;\n" * 151
                + "    return n;\n  }\n",
                "MethodLength",
            ),
            (
                "complexity",
                "  int branches(int n) {\n"
                + "".join(
                    f"    if (n == {i}) {{\n      n++;\n    }}\n" for i in range(11)
                )
                + "    return n;\n  }\n",
                "CyclomaticComplexity",
            ),
            (
                "nesting",
                "  int nested(int n) {\n"
                + "".join(f"    if (n > {i}) {{\n" for i in range(6))
                + "      n++;\n"
                + "    }\n" * 6
                + "    return n;\n  }\n",
                "NestedIfDepth",
            ),
        ]
        for name, code, expected in cases:
            with self.subTest(case=name):
                file.write_text("class Quality {\n" + code + "}\n")
                result = self.run_command(*command)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
