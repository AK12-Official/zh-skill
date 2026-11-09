#!/usr/bin/env sh
# Download the toolbox without cloning; invoke from the target project.
set -eu
repo=${SETUP_REPO:-AK12-Official/set-up}
ref=${SETUP_REF:-main}
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.11+ is required' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo 'Python 3.11+ is required' >&2
  exit 1
}
for setup_tool in curl tar; do
  command -v "$setup_tool" >/dev/null 2>&1 || { echo "Required tool missing: $setup_tool" >&2; exit 1; }
done
work=$(mktemp -d "${TMPDIR:-/tmp}/project-setup.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
curl -fL "https://codeload.github.com/$repo/tar.gz/$ref" -o "$work/repo.tar.gz"
tar -xzf "$work/repo.tar.gz" -C "$work"
library=$(find "$work" -mindepth 1 -maxdepth 1 -type d -print | head -n 1)
python3 "$library/scripts/setup.py" --repo "https://github.com/$repo" --ref "$ref" "$@"
