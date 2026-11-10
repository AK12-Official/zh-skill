"""Provision missing setup/check dependencies. No changes during planning/dry-run."""

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

LINT_VERSION = "2.15.0"


def run(*argv, **kwargs):
    print("+", shlex.join(map(str, argv)), flush=True)
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def version(command, pattern):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            env=dict(os.environ, GOTOOLCHAIN="local"),
        )
        match = re.search(pattern, result.stdout + result.stderr)
        return tuple(map(int, match.group(1).split("."))) if match else ()
    except (OSError, subprocess.CalledProcessError):
        return ()


def package_manager():
    for folder in ("/opt/homebrew/bin", "/usr/local/bin"):
        if not shutil.which("brew") and Path(folder, "brew").is_file():
            os.environ["PATH"] = folder + os.pathsep + os.environ["PATH"]
    return next(
        (
            name
            for name in ("apt-get", "dnf", "yum", "apk", "pacman", "brew")
            if shutil.which(name)
        ),
        None,
    )


def install_packages(packages):
    manager = package_manager()
    if not manager and platform.system() == "Darwin":
        if os.geteuid() == 0:
            raise ValueError(
                "Homebrew bootstrap requires a normal macOS user account with administrator access"
            )
        with tempfile.TemporaryDirectory(prefix="set-up-homebrew-") as tmp:
            installer = Path(tmp) / "install.sh"
            fetch(
                "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh",
                installer,
            )
            install_env = dict(os.environ)
            if os.environ.get("SETUP_NONINTERACTIVE") == "1":
                install_env["NONINTERACTIVE"] = "1"
            run("/bin/bash", str(installer), env=install_env)
        manager = package_manager()
    if not manager:
        raise ValueError(
            "No supported package manager. Install required tools or Homebrew, then retry: "
            + ", ".join(packages)
        )
    prefix = []
    if manager != "brew" and os.geteuid() != 0:
        if not shutil.which("sudo"):
            raise ValueError(
                "Administrator privileges or sudo required for: " + ", ".join(packages)
            )
        prefix = ["sudo"] + (
            ["-n"] if os.environ.get("SETUP_NONINTERACTIVE") == "1" else []
        )
    if manager == "apt-get":
        run(*prefix, manager, "update")
        run(*prefix, manager, "install", "-y", *packages)
    elif manager in ("dnf", "yum"):
        run(*prefix, manager, "install", "-y", *packages)
    elif manager == "apk":
        run(*prefix, manager, "add", "--no-cache", *packages)
    elif manager == "pacman":
        run(*prefix, manager, "-S", "--needed", "--noconfirm", *packages)
    else:
        run(manager, "install", *packages)


def fetch(url, path, checksum=None):
    for attempt in range(3):
        print("Downloading:", url, flush=True)
        try:
            with (
                urllib.request.urlopen(url, timeout=120) as response,
                path.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream)
            if checksum:
                with path.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != checksum:
                    raise ValueError("SHA-256 mismatch: " + url)
            return
        except (OSError, ValueError) as error:
            path.unlink(missing_ok=True)
            if attempt == 2:
                raise
            print(f"Retrying download ({attempt + 2}/3): {error}", flush=True)


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if (
                    not (destination / member.filename)
                    .resolve()
                    .is_relative_to(destination.resolve())
                ):
                    raise ValueError("Unsafe archive member: " + member.filename)
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            # filter='data' is not available in every supported Python 3.11 patch.
            for member in bundle.getmembers():
                target = (destination / member.name).resolve()
                if (
                    not target.is_relative_to(destination.resolve())
                    or member.issym()
                    or member.islnk()
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("Unsafe archive member: " + member.name)
            if hasattr(tarfile, "data_filter"):
                bundle.extractall(destination, filter="data")
            else:
                bundle.extractall(destination)


def target():
    system = {"Linux": "linux", "Darwin": "darwin"}.get(platform.system())
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(platform.machine())
    if not system or not arch:
        raise ValueError("Automatic tool downloads support Linux/macOS amd64/arm64")
    return system, arch


def tool_cache():
    return (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "set-up/tools"
    )


def install_go(requested):
    system, arch = target()
    with urllib.request.urlopen(
        "https://go.dev/dl/?mode=json&include=all", timeout=120
    ) as response:
        releases = json.load(response)
    wanted = requested.removeprefix("go")
    # Major/minor selects the newest patch; a full version selects exactly.
    full_version = len(wanted.split(".")) == 3
    release = next(
        (
            item
            for item in releases
            if item["stable"]
            and (
                item["version"] == "go" + wanted
                or (
                    not full_version and item["version"].startswith("go" + wanted + ".")
                )
            )
        ),
        None,
    )
    if not release:
        raise ValueError("Go release not found: " + wanted)
    artifact = next(
        item
        for item in release["files"]
        if item["os"] == system and item["arch"] == arch and item["kind"] == "archive"
    )
    root = tool_cache() / release["version"] / (system + "-" + arch)
    binary = root / "go/bin/go"
    if not binary.exists():
        with tempfile.TemporaryDirectory(prefix="set-up-go-") as tmp:
            archive = Path(tmp) / artifact["filename"]
            fetch(
                "https://go.dev/dl/" + artifact["filename"], archive, artifact["sha256"]
            )
            extract(archive, root)
    return binary.parent


def install_lint():
    system, arch = target()
    root = tool_cache() / ("golangci-lint-" + LINT_VERSION) / (system + "-" + arch)
    folder = f"golangci-lint-{LINT_VERSION}-{system}-{arch}"
    binary = root / folder / "golangci-lint"
    if not binary.exists():
        with tempfile.TemporaryDirectory(prefix="set-up-lint-") as tmp:
            name = folder + ".tar.gz"
            base = f"https://github.com/golangci/golangci-lint/releases/download/v{LINT_VERSION}/"
            sums = Path(tmp) / "checksums.txt"
            fetch(base + f"golangci-lint-{LINT_VERSION}-checksums.txt", sums)
            checksum = next(
                (
                    line.split()[0]
                    for line in sums.read_text().splitlines()
                    if line.split()[-1].lstrip("*") == name
                ),
                None,
            )
            if not checksum:
                raise ValueError("Checksum entry missing for " + name)
            archive = Path(tmp) / name
            fetch(base + name, archive, checksum)
            extract(archive, root)
    return binary.parent


def install_python(requested):
    cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "set-up/bootstrap"
    )
    uv = cache / "uv"
    if not uv.exists() and not shutil.which("uv"):
        system, arch = target()
        machine = {"amd64": "x86_64", "arm64": "aarch64"}[arch]
        platform_name = (
            "apple-darwin"
            if system == "darwin"
            else (
                "unknown-linux-musl"
                if Path("/etc/alpine-release").exists()
                else "unknown-linux-gnu"
            )
        )
        folder = f"uv-{machine}-{platform_name}"
        with tempfile.TemporaryDirectory(prefix="set-up-python-") as tmp:
            archive = Path(tmp) / "uv.tar.gz"
            fetch(
                f"https://github.com/astral-sh/uv/releases/download/0.9.5/{folder}.tar.gz",
                archive,
            )
            extract(archive, Path(tmp) / "unpacked")
            cache.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(tmp) / "unpacked" / folder / "uv", uv)
    executable = str(uv) if uv.exists() else shutil.which("uv")
    env = dict(
        os.environ,
        UV_CACHE_DIR=str(cache / "cache"),
        UV_PYTHON_INSTALL_DIR=str(cache / "python"),
    )
    run(executable, "python", "install", requested, env=env)
    return subprocess.check_output(
        [executable, "python", "find", "--managed-python", requested],
        env=env,
        text=True,
    ).strip()


def ensure_jdk(major):
    manager = package_manager()
    if manager == "apt-get":
        packages = [f"openjdk-{major}-jdk"]
    elif manager in ("dnf", "yum"):
        packages = [f"java-{major}-openjdk-devel"]
    elif manager == "apk":
        packages = [f"openjdk{major}-jdk"]
    elif manager == "pacman":
        packages = [f"jdk{major}-openjdk"]
    elif manager == "brew":
        packages = [f"openjdk@{major}"]
    else:
        raise ValueError("A package manager is required to install JDK " + major)
    install_packages(packages)
    if manager == "brew":
        prefix = subprocess.check_output(
            ["brew", "--prefix", f"openjdk@{major}"], text=True
        ).strip()
        return Path(prefix) / "libexec/openjdk.jdk/Contents/Home"
    for path in (Path("/usr/lib/jvm")).glob("*"):
        if (path / "bin/javac").exists() and version(
            [str(path / "bin/javac"), "-version"], r"javac (\d+(?:\.\d+)*)"
        ) >= (int(major),):
            return path
    raise ValueError("JDK installed but javac not found; set JAVA_HOME and retry")


def usable(command):
    try:
        return (
            subprocess.run([command, "--version"], capture_output=True).returncode == 0
        )
    except OSError:
        return False


def plan(args, root):
    checks = bool(set(args.modules) & {"lint", "makefile", "ci"})
    result = []
    for command in ("curl", "tar", "gzip") if "skills" in args.modules else ():
        if not shutil.which(command):
            result.append(command)
    if args.mode == "new" and not usable("git"):
        result.append("git")
    if checks:
        if "makefile" in args.modules and not usable("make"):
            result.append("make")
        if "go" in args.languages:
            desired = tuple(map(int, (args.go_version or "1.25").split(".")))
            if version(
                ["go", "version"], r"go(\d+(?:\.\d+)*)"
            ) < desired or not shutil.which("gofmt"):
                result.append("go")
            lint_version = version(
                ["golangci-lint", "--version"], r"version (\d+(?:\.\d+)*)"
            )
            if lint_version[:1] != (2,) or lint_version < tuple(
                map(int, LINT_VERSION.split("."))
            ):
                result.append("golangci-lint")
        if "python" in args.languages:
            desired = tuple(
                map(
                    int,
                    (
                        args.python_version
                        or f"{sys.version_info.major}.{sys.version_info.minor}"
                    ).split("."),
                )
            )
            python = root / ".setup/python"
            actual = version(
                [str(python) if python.exists() else sys.executable, "--version"],
                r"Python (\d+(?:\.\d+)*)",
            )
            if actual[: len(desired)] != desired:
                result.append("python-runtime")
            result.append("python-check-environment")
        if "java" in args.languages:
            major = max(17, int((args.java_version or "21").split(".")[0]))
            if version(["javac", "-version"], r"javac (\d+(?:\.\d+)*)") < (major,):
                result.append("jdk")
            build = args.java_build
            if not (
                root / ("mvnw" if build == "maven" else "gradlew")
            ).exists() and not shutil.which("mvn" if build == "maven" else "gradle"):
                result.append(build)
            result.append("java-check-jars")
    return list(dict.fromkeys(result))


def provision(args, root, missing):
    environment = {"paths": [], "variables": {}, "python": sys.executable}
    if "python-runtime" in missing:
        environment["python"] = install_python(args.python_version)
    elif (root / ".setup/python").exists():
        environment["python"] = str((root / ".setup/python").resolve())
    packages = [
        item
        for item in missing
        if item in {"curl", "tar", "gzip", "git", "make", "maven"}
    ]
    if packages:
        install_packages(packages)
    if "go" in missing:
        environment["paths"].append(str(install_go(args.go_version or "1.25")))
    if "golangci-lint" in missing:
        environment["paths"].append(str(install_lint()))
    if "jdk" in missing:
        java_home = ensure_jdk(
            str(max(17, int((args.java_version or "21").split(".")[0])))
        )
        environment["variables"]["JAVA_HOME"] = str(java_home)
        environment["paths"].append(str(java_home / "bin"))
    if "gradle" in missing:
        # Use a known JDK-compatible distribution instead of obsolete OS packages.
        root_cache = tool_cache() / "gradle-8.12"
        if not (root_cache / "gradle-8.12/bin/gradle").exists():
            with tempfile.TemporaryDirectory(prefix="set-up-gradle-") as tmp:
                archive = Path(tmp) / "gradle.zip"
                base = "https://services.gradle.org/distributions/gradle-8.12-bin.zip"
                sha = Path(tmp) / "sha256"
                fetch(base + ".sha256", sha)
                fetch(base, archive, sha.read_text().strip())
                extract(archive, root_cache)
            (root_cache / "gradle-8.12/bin/gradle").chmod(0o755)
        environment["paths"].append(str(root_cache / "gradle-8.12/bin"))
    if "go" in args.languages and set(args.modules) & {"lint", "makefile", "ci"}:
        # A caller's GOROOT must not mix the OS SDK with a downloaded SDK.
        candidates = [Path(path) / "go" for path in environment["paths"]]
        selected = next((path for path in candidates if path.exists()), None)
        if selected is None and shutil.which("go"):
            selected = Path(shutil.which("go")).resolve()
        if selected and selected.is_relative_to(tool_cache().resolve()):
            environment["variables"]["GOROOT"] = str(selected.parent.parent)
    os.environ.update(environment["variables"])
    if environment["paths"]:
        os.environ["PATH"] = (
            os.pathsep.join(environment["paths"]) + os.pathsep + os.environ["PATH"]
        )
    return environment


def activate(root):
    path = root / ".setup/environment.json"
    if path.exists():
        environment = json.loads(path.read_text())
        os.environ.update(environment["variables"])
        os.environ["PATH"] = os.pathsep.join(
            environment["paths"] + [os.environ["PATH"]]
        )


def project_environment(root, environment):
    path = root / ".setup/environment.json"
    previous = (
        json.loads(path.read_text())
        if path.exists()
        else {"paths": [], "variables": {}}
    )
    environment["paths"] = list(dict.fromkeys(environment["paths"] + previous["paths"]))
    environment["variables"] = {**previous["variables"], **environment["variables"]}
    path.write_text(json.dumps(environment, indent=2) + "\n")
    python = root / ".setup/python"
    if python.is_symlink():
        python.unlink()
    elif python.exists():
        raise ValueError("Refusing to replace unmanaged .setup/python")
    python.symlink_to(environment["python"])
    lines = ["# Generated local tool environment; use: . .setup/env.sh"]
    lines += [
        f"export {key}={shlex.quote(value)}"
        for key, value in environment["variables"].items()
    ]
    if environment["paths"]:
        lines += [
            "export PATH="
            + shlex.quote(os.pathsep.join(environment["paths"]))
            + ':"$PATH"'
        ]
    (root / ".setup/env.sh").write_text("\n".join(lines) + "\n")


def finish(args, root):
    if "python" in args.languages and set(args.modules) & {"lint", "makefile", "ci"}:
        interpreter = root / ".setup/venv/bin/python"
        base_python = str((root / ".setup/python").resolve())
        venv = root / ".setup/venv"
        marker = venv / ".set-up-managed"
        if venv.exists() and any(venv.iterdir()) and not marker.exists():
            raise ValueError(
                "Existing .setup/venv is not owned by set-up; preserve or move it before provisioning"
            )
        expected = version([base_python, "--version"], r"Python (\d+(?:\.\d+)*)")[:2]
        actual = version([str(interpreter), "--version"], r"Python (\d+(?:\.\d+)*)")[:2]
        pip_check = (
            subprocess.run(
                [str(interpreter), "-m", "pip", "--version"], capture_output=True
            )
            if interpreter.exists()
            else None
        )
        if pip_check is None or pip_check.returncode or expected != actual:
            check = subprocess.run(
                [base_python, "-c", "import ensurepip"], capture_output=True
            )
            if check.returncode:
                base_python = install_python(
                    args.python_version
                    or f"{sys.version_info.major}.{sys.version_info.minor}"
                )
                environment = json.loads((root / ".setup/environment.json").read_text())
                environment["python"] = base_python
                project_environment(root, environment)
            venv.mkdir(parents=True, exist_ok=True)
            marker.touch()
            try:
                run(base_python, "-m", "venv", "--clear", str(venv))
            finally:
                marker.touch()
        run(str(interpreter), str(root / ".setup/check.py"), "deps")
    if "java" in args.languages and set(args.modules) & {"lint", "makefile", "ci"}:
        run(sys.executable, str(root / ".setup/check.py"), "tools")
