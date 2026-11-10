#!/usr/bin/env python3
"""Compose personal project setup modules. Requires Python 3.11+."""

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET

import dependencies

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
VERSION = 3
MODULES = {"skills", "gitignore", "lint", "makefile", "ci"}
LANGUAGES = {"go", "python", "java"}
AGENTS = {"codex": ".codex", "antigravity": ".agents", "claude": ".claude"}
BEGIN, END = "# BEGIN project-setup", "# END project-setup"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def csv(value):
    result = list(dict.fromkeys(value.split(",")))
    if any(not item for item in result):
        raise ValueError("Empty item in selection: " + value)
    return result


def detect(root):
    result = []
    if (root / "go.mod").exists() or (root / "go.work").exists():
        result.append("go")
    if any(
        (root / f).exists()
        for f in (
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "uv.lock",
            "poetry.lock",
        )
    ):
        result.append("python")
    if any(
        (root / f).exists() for f in ("pom.xml", "build.gradle", "build.gradle.kts")
    ):
        result.append("java")
    return result


def json_text(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def project_versions(root, args, require_ci=True):
    versions = {}
    if "go" in args.languages:
        for name in ("go.work", "go.mod"):
            if (root / name).exists():
                match = re.search(r"^go\s+(\S+)", (root / name).read_text(), re.M)
                if match:
                    versions["go"] = match[1]
                    break
        versions["go"] = args.go_version or versions.get("go")
    if "python" in args.languages:
        path = root / ".python-version"
        versions["python"] = args.python_version or (
            path.read_text().strip() if path.exists() else None
        )
    if "java" in args.languages:
        path = root / ".java-version"
        versions["java"] = args.java_version or (
            path.read_text().strip() if path.exists() else None
        )
        pom = root / "pom.xml"
        if not versions["java"] and pom.exists():
            tree = ET.parse(pom)
            for key in (
                "maven.compiler.release",
                "maven.compiler.target",
                "java.version",
            ):
                node = tree.find(".//{*}" + key)
                if (
                    node is not None
                    and node.text
                    and re.fullmatch(r"\d+(?:\.\d+)*", node.text.strip())
                ):
                    versions["java"] = node.text.strip()
                    break
    for language, version in versions.items():
        if version and (
            not isinstance(version, str)
            or not re.fullmatch(r"\d+(?:\.\d+){0,2}", version)
        ):
            raise ValueError(f"Invalid {language} version: {version}")
        if require_ci and "ci" in args.modules and not version:
            raise ValueError(
                f"Cannot determine {language} version; supply --{language}-version"
            )
    if require_ci and "ci" in args.modules:
        if versions.get("python") and tuple(
            map(int, versions["python"].split(".")[:2])
        ) < (3, 11):
            raise ValueError("The shared runner requires Python >= 3.11")
        if versions.get("java") and int(versions["java"].split(".")[0]) < 17:
            raise ValueError(
                "Java format tools require JDK >= 17; select --java-version 17 or newer"
            )
    return versions


def workflow(language, version, args, root):
    lines = [
        "name: setup-" + language,
        "on: [push, pull_request]",
        "permissions:",
        "  contents: read",
        "jobs:",
        "  check:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v7",
    ]
    if language != "python":
        lines += [
            "      - uses: actions/setup-python@v7",
            "        with:",
            "          python-version: '3.12'",
        ]
    action = {
        "go": "setup-go@v7",
        "python": "setup-python@v7",
        "java": "setup-java@v6",
    }[language]
    lines += [
        "      - uses: actions/" + action,
        "        with:",
        f"          {language}-version: '{version}'",
    ]
    if language == "go":
        sums = sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("go.sum")
            if ".git" not in p.parts and ".setup" not in p.parts
        )
        if (root / "go.work.sum").exists():
            sums.append("go.work.sum")
        lines += ["          cache: " + ("true" if sums else "false")]
        if sums:
            lines += [
                "          cache-dependency-path: |",
                *["            " + p for p in sums],
            ]
        lines += [
            "      - uses: golangci/golangci-lint-action@v9",
            "        with:",
            "          version: v2.15.0",
            "          install-only: true",
        ]
    elif language == "java":
        patterns = (
            '"**/pom.xml"'
            if args.java_build == "maven"
            else '"**/*.gradle*\\n**/gradle-wrapper.properties"'
        )
        lines += [
            "          distribution: temurin",
            "          cache: " + args.java_build,
            "          cache-dependency-path: " + patterns,
            "      - run: python3 .setup/check.py tools",
        ]
    else:
        # pip cache includes all dependency descriptions, including custom command inputs.
        lines += [
            "      - uses: actions/cache@v4",
            "        with:",
            "          path: ~/.cache/pip",
            "          key: pip-${{ runner.os }}-"
            + version
            + "-${{ hashFiles('**/requirements*.txt', '**/pyproject.toml', '**/*.lock', '.setup/checks.json') }}",
            "      - run: python3 .setup/check.py deps",
        ]
    # The runner is deliberately used for CI-only installs and per-language jobs.
    command = "python3 .setup/check.py check --language " + language
    if "makefile" in args.modules:
        command = "make check SETUP_LANGUAGE=" + language
    lines += ["      - run: " + command]
    return "\n".join(lines) + "\n"


def generate(root, args):
    # Shared runner/config support every previously installed language, so
    # adding one module cannot break an existing workflow for another.
    state_path = safe_path(root, ".setup/state.json")
    if state_path.exists():
        installed = json.loads(state_path.read_text()).get("options", {})
        installed_languages = installed.get("languages", [])
        if not isinstance(installed_languages, list) or any(
            language not in LANGUAGES for language in installed_languages
        ):
            raise ValueError("Invalid installed languages in state")
        args.languages = list(dict.fromkeys(installed_languages + args.languages))
        for key in (
            "go_version",
            "python_version",
            "java_version",
            "java_build",
            "python_install",
        ):
            if getattr(args, key) is None:
                setattr(args, key, installed.get(key))
    files = {}
    if "gitignore" in args.modules:
        rules = (TEMPLATES / "gitignore/common.txt").read_text().splitlines()
        for language in args.languages:
            rules += (TEMPLATES / f"gitignore/{language}.txt").read_text().splitlines()
        rules += [AGENTS[agent] + "/" for agent in args.agents]
        files[".gitignore"] = (
            BEGIN + "\n" + "\n".join(dict.fromkeys(rules)) + "\n" + END + "\n"
        )
    checks = bool(set(args.modules) & {"lint", "makefile", "ci"})
    if checks:
        if not args.languages:
            raise ValueError(
                "Language modules require --language go,python,java or recognizable project files"
            )
        if "java" in args.languages:
            maven = (root / "pom.xml").exists()
            gradle = any(
                (root / f).exists() for f in ("build.gradle", "build.gradle.kts")
            )
            if not args.java_build:
                if maven == gradle:
                    raise ValueError("Specify --java-build maven or gradle")
                args.java_build = "maven" if maven else "gradle"
        versions = project_versions(root, args)
        installs = args.python_install
        if "python" in args.languages and installs is None:
            if any(
                (root / f).exists() for f in ("uv.lock", "poetry.lock", "Pipfile.lock")
            ):
                raise ValueError(
                    "Locked Python project: supply --python-install commands or python_install in config to preserve your dependency workflow"
                )
            if (root / "requirements.txt").exists():
                installs = [
                    ["python3", "-m", "pip", "install", "-r", "requirements.txt"]
                ]
            elif (root / "pyproject.toml").exists():
                data = tomllib.loads((root / "pyproject.toml").read_text())
                installs = (
                    [["python3", "-m", "pip", "install", "."]]
                    if "project" in data or "build-system" in data
                    else []
                )
            elif (root / "setup.py").exists():
                installs = [["python3", "-m", "pip", "install", "."]]
        ruff_config = ".setup/ruff.toml"
        files[".setup/check.py"] = (TEMPLATES / "check.py").read_text()
        files[".setup/checks.json"] = json_text(
            {
                "languages": args.languages,
                "java_build": args.java_build,
                "python_install": installs or [],
                "versions": versions,
            }
        )
        if "go" in args.languages:
            config_names = (
                ".golangci.yml",
                ".golangci.yaml",
                ".golangci.toml",
                ".golangci.json",
            )
            golangci_config = next(
                (name for name in config_names if (root / name).exists()),
                ".golangci.yml",
            )
            if golangci_config == ".golangci.yml":
                files[".golangci.yml"] = (TEMPLATES / "lint/golangci.yml").read_text()
            checks_data = json.loads(files[".setup/checks.json"])
            checks_data["golangci_config"] = golangci_config
            files[".setup/checks.json"] = json_text(checks_data)
        if "python" in args.languages:
            existing_ruff = any(
                (root / f).exists() for f in ("ruff.toml", ".ruff.toml")
            )
            if (root / "pyproject.toml").exists():
                existing_ruff |= "ruff" in tomllib.loads(
                    (root / "pyproject.toml").read_text()
                ).get("tool", {})
            if existing_ruff:
                ruff_config = None
            if not existing_ruff:
                files[".setup/ruff.toml"] = (TEMPLATES / "lint/ruff.toml").read_text()
        checks_data = json.loads(files[".setup/checks.json"])
        checks_data["ruff_config"] = ruff_config
        files[".setup/checks.json"] = json_text(checks_data)
        if "java" in args.languages:
            files[".setup/checkstyle.xml"] = (
                TEMPLATES / "lint/checkstyle.xml"
            ).read_text()
        if "makefile" in args.modules:
            targets = ["format", "format-check", "lint", "test", "build", "check"]
            files["Makefile"] = (
                "# Generated by project setup\nPYTHON ?= $(if $(wildcard .setup/python),.setup/python,python3)\n"
                "SETUP_LANGUAGE ?=\n.DEFAULT_GOAL := help\n.PHONY: help "
                + " ".join(targets)
                + "\n\n"
                'help:\n\t@echo "Targets: '
                + " ".join(targets)
                + ' (optional SETUP_LANGUAGE=go|python|java)"\n\n'
                + "".join(
                    f"{target}:\n\t$(PYTHON) .setup/check.py {target} $(if $(SETUP_LANGUAGE),--language $(SETUP_LANGUAGE))\n\n"
                    for target in targets
                )
            )
        if "ci" in args.modules:
            for language in args.languages:
                files[f".github/workflows/setup-{language}.yml"] = workflow(
                    language, versions[language], args, root
                )
    return files


def safe_path(root, relative):
    path = root / relative
    if path.is_symlink() or any(
        p.is_symlink() for p in path.parents if p != root and root in p.parents
    ):
        raise ValueError("Refusing symlink: " + str(path))
    if not path.resolve().is_relative_to(root):
        raise ValueError("Path escapes project: " + str(path))
    return path


def apply(root, args, files):
    state_path = safe_path(root, ".setup/state.json")
    state = (
        json.loads(state_path.read_text())
        if state_path.exists()
        else {"schema": 1, "files": {}}
    )
    if (
        not isinstance(state, dict)
        or state.get("schema") != 1
        or not isinstance(state.get("files"), dict)
    ):
        raise ValueError("Unsupported setup state file")
    save_state = bool(files) or (
        "skills" in args.modules and (not args.update or state_path.exists())
    )
    temporary_state = safe_path(root, ".setup/state.json.setup-tmp")
    if save_state and temporary_state.exists():
        raise ValueError("Temporary state file already exists: " + str(temporary_state))
    plan = []
    conflicts = []
    for relative, template in files.items():
        path = safe_path(root, relative)
        current = path.read_text() if path.exists() else None
        previous = state["files"].get(relative)
        content = template
        if relative == ".gitignore":
            if current is not None:
                if (
                    current.count(BEGIN) != current.count(END)
                    or current.count(BEGIN) > 1
                ):
                    raise ValueError("Malformed managed block in .gitignore")
                if BEGIN in current:
                    start, end = current.index(BEGIN), current.index(END) + len(END)
                    if end < start:
                        raise ValueError("Malformed managed block in .gitignore")
                    old_block = current[start:end] + "\n"
                    if (
                        (not previous or digest(old_block) != previous["hash"])
                        and template != old_block
                        and not args.force
                    ):
                        conflicts.append(relative)
                    content = current[:start] + template.rstrip("\n") + current[end:]
                else:
                    content = (
                        current
                        + ("" if not current or current.endswith("\n") else "\n")
                        + template
                    )
        elif current is not None and current != template:
            permitted = args.force or (
                args.update and previous and digest(current) == previous["hash"]
            )
            if not permitted:
                conflicts.append(relative)
        temporary = path.with_name(path.name + ".setup-tmp")
        if current != content and (temporary.exists() or temporary.is_symlink()):
            raise ValueError("Temporary path already exists: " + str(temporary))
        status = (
            "unchanged"
            if current == content
            else ("create" if current is None else "modify")
        )
        print(f"{status}: {relative}")
        if current is not None and current != content:
            print(
                "".join(
                    difflib.unified_diff(
                        current.splitlines(True),
                        content.splitlines(True),
                        fromfile=relative,
                        tofile=relative + " (generated)",
                    )
                ),
                end="",
            )
        plan.append((relative, path, current, content, template))
    if conflicts:
        raise ValueError(
            "Conflicts (preserved, no files written): "
            + ", ".join(conflicts)
            + ". Review diff; use --update for unchanged managed files or --force for backed-up replacement."
        )
    checks = bool(set(args.modules) & {"lint", "makefile", "ci"})
    if checks and not args.skip_deps:
        for local_file in (".setup/environment.json", ".setup/env.sh", ".setup/venv"):
            safe_path(root, local_file)
        local_venv = root / ".setup/venv"
        if (
            local_venv.is_dir()
            and any(local_venv.iterdir())
            and not (local_venv / ".set-up-managed").exists()
        ):
            raise ValueError(
                "Existing .setup/venv is not owned by set-up; preserve it before provisioning"
            )
        python_link = root / ".setup/python"
        if python_link.exists() and not python_link.is_symlink():
            raise ValueError("Unmanaged local Python launcher: " + str(python_link))
        dependencies.activate(root)
    if ".setup/checks.json" in files:
        runtime_versions = json.loads(files[".setup/checks.json"])["versions"]
        for language, runtime_version in runtime_versions.items():
            if getattr(args, language + "_version") is None:
                setattr(args, language + "_version", runtime_version)
    dependency_plan = dependencies.plan(args, root) if not args.skip_deps else []
    if not args.skip_deps:
        print(
            "Dependencies to check/install: "
            + (", ".join(dependency_plan) or "available")
        )
    initialize_git = (
        args.mode == "new" and not args.update and not (root / ".git").exists()
    )
    if initialize_git:
        if not shutil.which("git") and args.skip_deps:
            raise ValueError("New project setup requires Git on PATH")
        print("create: .git (git init)")
    if args.dry_run:
        return
    if args.non_interactive:
        os.environ["SETUP_NONINTERACTIVE"] = "1"
    environment = (
        dependencies.provision(args, root, dependency_plan)
        if not args.skip_deps
        else None
    )
    if initialize_git:
        subprocess.run(["git", "init", str(root)], cwd=root, check=True)
    # Preflight all configuration conflicts before invoking the Skill installer.
    if "skills" in args.modules:
        safe_path(root, ".gitignore")
        for agent in args.agents:
            safe_path(root, AGENTS[agent] + "/skills")
        command = [
            "sh",
            str(REPO / "scripts/install-skills.sh"),
            "--target",
            ",".join(args.agents),
            "--skip-openspec-cli",
        ]
        if "gitignore" in args.modules:
            command += ["--no-gitignore"]
        if args.update:
            command += ["--update"]
        if args.force:
            command += ["--force"]
        for skill in args.only:
            command += ["--only", skill]
        command += ["--repo", args.repo, "--ref", args.ref]
        subprocess.run(command, cwd=root, check=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for relative, path, current, content, template in plan:
        if current != content:
            if current is not None:
                backup = safe_path(root, ".setup/backups/" + stamp + "/" + relative)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".setup-tmp")
            if temporary.exists() or temporary.is_symlink():
                raise ValueError("Temporary path already exists: " + str(temporary))
            temporary.write_text(content)
            temporary.replace(path)
        state["files"][relative] = {
            "hash": digest(template if relative == ".gitignore" else content),
            "template_version": VERSION,
        }
    if save_state:
        old_options = state.get("options", {})
        options = {
            name: getattr(args, name)
            for name in (
                "mode",
                "modules",
                "languages",
                "agents",
                "java_build",
                "go_version",
                "python_version",
                "java_version",
                "python_install",
            )
        }
        options["modules"] = list(
            dict.fromkeys(old_options.get("modules", []) + args.modules)
        )
        options["languages"] = list(
            dict.fromkeys(old_options.get("languages", []) + args.languages)
        )
        for key in (
            "go_version",
            "python_version",
            "java_version",
            "java_build",
            "python_install",
        ):
            if options[key] is None:
                options[key] = old_options.get(key)
        state["options"] = options
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_state = safe_path(root, ".setup/state.json.setup-tmp")
        with temporary_state.open("x") as stream:
            stream.write(json_text(state))
        temporary_state.replace(state_path)
    if checks and environment is not None:
        dependencies.project_environment(root, environment)
        dependencies.finish(args, root)
        print(
            "Local tools are ready. To use downloaded tools directly: . .setup/env.sh"
        )


def prompt_stream(args):
    if args.non_interactive:
        return None
    if args.interactive or sys.stdin.isatty():
        return sys.stdin
    try:
        return open("/dev/tty")
    except OSError:
        return None


def ask(stream, message, default=None):
    suffix = f" [{default}]" if default else ""
    print(message + suffix + ": ", end="", flush=True)
    answer = stream.readline()
    if not answer:
        raise ValueError("Input ended; supply explicit options or --non-interactive")
    return answer.strip() or default or ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["new", "existing"],
        help="new: full setup; existing: AI skills only",
    )
    interaction = parser.add_mutually_exclusive_group()
    interaction.add_argument(
        "--interactive", action="store_true", help="ask mode/language via stdin"
    )
    interaction.add_argument(
        "--non-interactive",
        action="store_true",
        help="never ask; default to existing mode",
    )
    parser.add_argument("--project", default=".")
    parser.add_argument(
        "--config", help="JSON preferences; explicit CLI options take precedence"
    )
    parser.add_argument(
        "--modules", help="comma-separated skills,gitignore,lint,makefile,ci"
    )
    parser.add_argument(
        "--language", dest="languages", help="comma-separated go,python,java"
    )
    parser.add_argument("--agents", help="comma-separated codex,antigravity,claude")
    parser.add_argument("--java-build", choices=["maven", "gradle"])
    for language in ("go", "python", "java"):
        parser.add_argument("--" + language + "-version")
    parser.add_argument(
        "--python-install",
        action="append",
        help="dependency install argv as a shell-quoted string; repeatable, no shell execution",
    )
    parser.add_argument(
        "--only", action="append", default=[], help="Skill ID; repeatable"
    )
    parser.add_argument("--repo", default="https://github.com/AK12-Official/set-up")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="generate configuration only; do not install dependencies",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="update unchanged managed templates and installed skills",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace conflicting templates with backups; skills use existing force semantics",
    )
    args = parser.parse_args()
    root = Path(args.project).resolve()
    preferences = (
        Path(args.config).expanduser()
        if args.config
        else Path.home() / ".config/project-setup/config.json"
    )
    defaults = json.loads(preferences.read_text()) if preferences.exists() else {}
    if not isinstance(defaults, dict):
        raise ValueError("Config must be a JSON object")
    if args.config and not preferences.exists():
        raise ValueError("Config not found: " + str(preferences))
    state_path = safe_path(root, ".setup/state.json")
    if (
        args.update
        and not state_path.exists()
        and args.modules is None
        and "modules" not in defaults
    ):
        args.modules = "skills"
    if args.update and state_path.exists():
        defaults = {**json.loads(state_path.read_text()).get("options", {}), **defaults}
    allowed = {
        "mode",
        "modules",
        "languages",
        "agents",
        "java_build",
        "go_version",
        "python_version",
        "java_version",
        "python_install",
    }
    if not isinstance(defaults, dict):
        raise ValueError("Config must be a JSON object")
    if set(defaults) - allowed:
        raise ValueError("Unknown config keys: " + ",".join(set(defaults) - allowed))
    requested_mode = args.mode or defaults.get("mode")
    for key, value in defaults.items():
        if key == "modules" and requested_mode == "existing" and args.modules is None:
            continue
        if getattr(args, key) is None:
            setattr(args, key, value)
    stream = prompt_stream(args)
    guided_new = args.mode == "new"
    if args.mode is None:
        if args.modules is not None:
            selected = (
                csv(args.modules) if isinstance(args.modules, str) else args.modules
            )
            args.mode = "new" if set(selected) - {"skills"} else "existing"
        elif stream is not None and not args.update:
            choice = ask(stream, "选择 setup 模式：1. 创建新项目  2. 加入已有项目", "2")
            if choice not in {"1", "2", "new", "existing"}:
                raise ValueError("请选择 1/new 或 2/existing")
            args.mode = "new" if choice in {"1", "new"} else "existing"
            guided_new = args.mode == "new"
        else:
            args.mode = "existing"
    if args.mode not in {"new", "existing"}:
        raise ValueError("Invalid mode")
    if root.exists() and not root.is_dir():
        raise ValueError("Target is not a directory: " + str(root))
    if not root.is_dir():
        raise ValueError(
            "Project directory must already exist; create it and run setup inside it: "
            + str(root)
        )
    if guided_new and args.languages is None:
        if stream is not None:
            answer = ask(
                stream, "选择项目语言：1. Go  2. Python  3. Java（可用逗号组合）"
            )
            mapping = {"1": "go", "2": "python", "3": "java"}
            args.languages = ",".join(
                mapping.get(item, item) for item in answer.split(",")
            )
        elif not detect(root):
            raise ValueError(
                "New project requires --language go,python,java in non-interactive mode"
            )
    for key, valid, fallback in [
        ("languages", LANGUAGES, detect(root)),
        ("modules", MODULES, None),
        ("agents", set(AGENTS), ["codex", "antigravity"]),
    ]:
        value = getattr(args, key)
        value = csv(value) if isinstance(value, str) else value
        if value is None:
            value = fallback
        if key == "modules" and value is None:
            value = (
                ["skills", "gitignore", "lint", "makefile", "ci"]
                if args.mode == "new"
                else ["skills"]
            )
        if (
            not isinstance(value, list)
            or not value
            and key != "languages"
            or any(not isinstance(item, str) or item not in valid for item in value)
        ):
            raise ValueError("Invalid " + key)
        setattr(args, key, list(dict.fromkeys(value)))
    if args.mode == "existing" and set(args.modules) - {"skills"}:
        raise ValueError(
            "Existing mode only installs AI skills; use --mode new for project configuration modules"
        )
    if guided_new:
        detected_versions = project_versions(root, args, require_ci=False)
        baselines = {"go": "1.25", "python": "3.12", "java": "21"}
        for language in args.languages:
            key = language + "_version"
            if getattr(args, key) is None and not detected_versions.get(language):
                value = (
                    ask(stream, f"{language} CI 运行版本", baselines[language])
                    if stream
                    else baselines[language]
                )
                setattr(args, key, value)
        if (
            "java" in args.languages
            and not args.java_build
            and not any(
                (root / name).exists()
                for name in ("pom.xml", "build.gradle", "build.gradle.kts")
            )
        ):
            value = (
                ask(stream, "Java 构建工具：1. Maven  2. Gradle", "1")
                if stream
                else "1"
            )
            args.java_build = {"1": "maven", "2": "gradle"}.get(value, value)
    if stream is not None and stream is not sys.stdin:
        stream.close()
    if args.python_install is not None:
        args.python_install = [
            shlex.split(item) if isinstance(item, str) else item
            for item in args.python_install
        ]
        if any(
            not isinstance(command, list)
            or not command
            or any(not isinstance(arg, str) for arg in command)
            for command in args.python_install
        ):
            raise ValueError(
                "python_install must be a list of nonempty argv lists or command strings"
            )
    if args.java_build is not None and args.java_build not in {"maven", "gradle"}:
        raise ValueError("Invalid java_build")
    print(
        "Mode:",
        args.mode,
        "| modules:",
        ",".join(args.modules),
        "| languages:",
        ",".join(args.languages) or "(none)",
        "| agents:",
        ",".join(args.agents),
    )
    files = generate(root, args)
    if args.dry_run and "skills" in args.modules:
        print(
            "Skill preview: targets="
            + ",".join(args.agents)
            + "; IDs="
            + (",".join(args.only) or "all registered")
            + "; mode="
            + ("update installed only" if args.update else "install")
            + "; no download or writes"
        )
    apply(root, args, files)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, ET.ParseError) as error:
        print("setup: " + str(error), file=sys.stderr)
        sys.exit(1)
