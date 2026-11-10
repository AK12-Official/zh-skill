#!/usr/bin/env sh
# Bootstrap the runtime, download the toolbox, and configure the current project.
set -eu
repo=${SETUP_REPO:-AK12-Official/set-up}
ref=${SETUP_REF:-main}
setup_install=1
setup_preview=0
setup_non_interactive=0
setup_target=.
setup_expect_project=0
for setup_argument in "$@"; do
  if [ "$setup_expect_project" = 1 ]; then setup_target=$setup_argument; setup_expect_project=0; continue; fi
  case "$setup_argument" in
    --project) setup_expect_project=1 ;;
    --project=*) setup_target=${setup_argument#--project=} ;;
  esac
done
[ "$setup_expect_project" = 0 ] && [ -d "$setup_target" ] || {
  echo "Project directory must already exist: $setup_target" >&2
  exit 1
}
for setup_argument in "$@"; do
  case "$setup_argument" in
    --non-interactive) setup_non_interactive=1 ;;
    --skip-deps) setup_install=0 ;;
    --dry-run) setup_install=0; setup_preview=1 ;;
    --help|-h) setup_install=0 ;;
  esac
done

setup_privileged() {
  if [ "$(id -u)" = 0 ]; then "$@"
  elif command -v sudo >/dev/null 2>&1; then
    if [ "$setup_non_interactive" = 1 ]; then sudo -n "$@"; else sudo "$@"; fi
  else echo "Cannot install $*: run with an administrator account or install sudo." >&2; exit 1
  fi
}

setup_packages() {
  echo "Installing bootstrap packages: $*"
  if command -v apt-get >/dev/null 2>&1; then
    setup_privileged apt-get update
    setup_privileged apt-get install -y "$@"
  elif command -v dnf >/dev/null 2>&1; then setup_privileged dnf install -y "$@"
  elif command -v yum >/dev/null 2>&1; then setup_privileged yum install -y "$@"
  elif command -v apk >/dev/null 2>&1; then setup_privileged apk add --no-cache "$@"
  elif command -v pacman >/dev/null 2>&1; then setup_privileged pacman -S --needed --noconfirm "$@"
  elif command -v brew >/dev/null 2>&1; then brew install "$@"
  else
    echo "No supported package manager. Install curl, tar, gzip and CA certificates, then retry." >&2
    exit 1
  fi
}

setup_missing=""
for setup_tool in curl tar gzip; do
  command -v "$setup_tool" >/dev/null 2>&1 || setup_missing="$setup_missing $setup_tool"
done
if [ "$(uname -s)" = Linux ] && [ ! -s /etc/ssl/certs/ca-certificates.crt ] && [ ! -s /etc/pki/tls/certs/ca-bundle.crt ] && [ ! -s /etc/ssl/cert.pem ]; then
  setup_missing="$setup_missing ca-certificates"
fi
setup_python="python3"
setup_python_ok=0
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  setup_python_ok=1
fi
if [ "$setup_install" = 0 ] && { [ -n "$setup_missing" ] || [ "$setup_python_ok" = 0 ]; }; then
  echo "Bootstrap dependencies required:$setup_missing; Python 3.11+ is also needed if missing or outdated."
  if [ "$setup_preview" = 1 ]; then
    echo "Dry-run: no packages installed. Full configuration preview requires the bootstrap dependencies."
    exit 0
  fi
  echo "Retry without --skip-deps to provision missing bootstrap dependencies." >&2
  exit 1
fi
if [ -n "$setup_missing" ]; then
  # Package names are common to the supported Linux managers; macOS has these tools.
  case " $setup_missing " in
    *' ca-certificates '*) setup_packages $setup_missing ;;
    *) setup_packages $setup_missing ca-certificates ;;
  esac
fi

work=$(mktemp -d "${TMPDIR:-/tmp}/project-setup.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
if [ "$setup_python_ok" = 0 ]; then
  # uv supplies managed CPython without replacing the OS interpreter.
  setup_cache=${XDG_CACHE_HOME:-$HOME/.cache}/set-up/bootstrap
  mkdir -p "$setup_cache"
  setup_uv="$setup_cache/uv"
  if [ ! -x "$setup_uv" ]; then
    case "$(uname -s)" in
      Linux) setup_platform=unknown-linux-gnu; [ ! -f /etc/alpine-release ] || setup_platform=unknown-linux-musl ;;
      Darwin) setup_platform=apple-darwin ;;
      *) echo "Automatic bootstrap supports Linux and macOS." >&2; exit 1 ;;
    esac
    case "$(uname -m)" in
      x86_64|amd64) setup_arch=x86_64 ;;
      aarch64|arm64) setup_arch=aarch64 ;;
      *) echo "Unsupported architecture for managed Python." >&2; exit 1 ;;
    esac
    setup_uv_archive="uv-$setup_arch-$setup_platform"
    curl -fL --retry 3 --connect-timeout 20 "https://github.com/astral-sh/uv/releases/download/0.9.5/$setup_uv_archive.tar.gz" -o "$work/uv.tar.gz"
    tar -xzf "$work/uv.tar.gz" -C "$work"
    cp "$work/$setup_uv_archive/uv" "$setup_uv"
    chmod +x "$setup_uv"
  fi
  UV_CACHE_DIR="$setup_cache/cache" UV_PYTHON_INSTALL_DIR="$setup_cache/python" "$setup_uv" python install 3.12
  setup_python=$(UV_CACHE_DIR="$setup_cache/cache" UV_PYTHON_INSTALL_DIR="$setup_cache/python" "$setup_uv" python find --managed-python 3.12)
fi
"$setup_python" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
curl -fL --retry 3 --connect-timeout 20 "https://codeload.github.com/$repo/tar.gz/$ref" -o "$work/repo.tar.gz"
tar -xzf "$work/repo.tar.gz" -C "$work"
library=""
for setup_entry in "$work"/*; do
  if [ -f "$setup_entry/scripts/setup.py" ]; then library=$setup_entry; break; fi
done
[ -n "$library" ] || { echo 'Downloaded archive has no setup entry point' >&2; exit 1; }
"$setup_python" "$library/scripts/setup.py" --repo "https://github.com/$repo" --ref "$ref" "$@"
