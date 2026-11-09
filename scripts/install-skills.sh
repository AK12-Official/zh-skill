#!/usr/bin/env sh
# Install registered skills from a public set-up GitHub repository without
# cloning it.  This script intentionally uses only POSIX sh, curl, tar, awk,
# and cp so it can be run directly from curl on machines without Python.
set -eu

repo="https://github.com/AK12-Official/set-up"
ref="main"
target="codex,antigravity"
force="0"
update="0"
installed_count="0"
only=""
dest_root=""
skip_openspec_cli="0"
manage_gitignore="1"
dry_run="0"
progress_total="6"

progress() {
  step=$1
  shift
  printf '[%s/%s] %s\n' "$step" "$progress_total" "$*"
}

usage() {
  cat <<'EOF'
Usage: install-skills.sh [options]

  --repo URL       set-up GitHub repository (default: AK12-Official/set-up)
  --ref REF        branch, tag, or commit (default: main)
  --target NAME    comma-separated codex, antigravity, claude (default: codex,antigravity)
                   both remains an alias for codex,claude
  --only ID        install only one registered Skill ID; repeatable
  --dest-root DIR  override one installation root (single target only)
  --dry-run        preview installation without writing project files
  --no-gitignore   let the setup entry point manage ignore rules
  --force          replace existing installed directories
  --update         update installed skills only; skip missing destinations
  --skip-openspec-cli
                   do not install the openspec CLI (by default it is installed
                   automatically when any openspec skill is selected)
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) repo=$2; shift 2 ;;
    --ref) ref=$2; shift 2 ;;
    --target) target=$2; shift 2 ;;
    --only) only="$only $2"; shift 2 ;;
    --dest-root) dest_root=$2; shift 2 ;;
    --dry-run) dry_run="1"; shift ;;
    --no-gitignore) manage_gitignore="0"; shift ;;
    --force) force="1"; shift ;;
    --update) update="1"; shift ;;
    --skip-openspec-cli) skip_openspec_cli="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[ "$target" != "both" ] || target="codex,claude"
case "$target" in
  ""|,*|*,|*,,*) echo "invalid --target list" >&2; exit 2 ;;
esac
targets=$(printf '%s' "$target" | tr ',' ' ')
for platform in $targets; do
  case "$platform" in
    codex|antigravity|claude) ;;
    *) echo "unknown target: $platform" >&2; exit 2 ;;
  esac
done
if [ -n "$dest_root" ] && [ "${target#*,}" != "$target" ]; then
  echo "--dest-root requires a single target" >&2
  exit 2
fi

project_root=$(pwd -P)

repo_path=${repo#https://github.com/}
repo_path=${repo_path#http://github.com/}
repo_path=${repo_path%.git}
owner=${repo_path%%/*}
name=${repo_path#*/}
if [ -z "$owner" ] || [ -z "$name" ] || [ "$owner" = "$repo_path" ]; then
  echo "--repo must be a GitHub repository URL" >&2
  exit 2
fi

archive=$(mktemp "${TMPDIR:-/tmp}/set-up.XXXXXX.tar.gz")
work=$(mktemp -d "${TMPDIR:-/tmp}/set-up.XXXXXX")
cleanup() { rm -f "$archive"; rm -rf "$work"; }
trap cleanup EXIT HUP INT TERM

archive_url="https://codeload.github.com/$owner/$name/tar.gz/$ref"
progress 1 "Downloading $owner/$name ($ref) ..."
curl -fL --progress-bar "$archive_url" -o "$archive"
progress 2 "Extracting repository archive ..."
tar -xzf "$archive" -C "$work"
library=$(find "$work" -mindepth 1 -maxdepth 1 -type d -print | head -n 1)
if [ -z "$library" ] || [ ! -f "$library/sources.toml" ]; then
  echo "downloaded repository does not contain sources.toml" >&2
  exit 1
fi

selected() {
  id=$1
  [ -z "$only" ] && return 0
  for wanted in $only; do
    [ "$wanted" = "$id" ] && return 0
  done
  return 1
}

install_root() {
  if [ -n "$dest_root" ]; then
    printf '%s\n' "$dest_root"
    return
  fi
  case "$1" in
    codex) printf '%s\n' "$project_root/.codex/skills" ;;
    antigravity) printf '%s\n' "$project_root/.agents/skills" ;;
    claude) printf '%s\n' "$project_root/.claude/skills" ;;
  esac
}

ensure_gitignore_entry() {
  directory=$1
  gitignore="$project_root/.gitignore"
  if [ -f "$gitignore" ] && grep -Eq "^/?[.]${directory}(/(\\*|\\*\\*)?)?/?$" "$gitignore"; then
    return
  fi
  if [ -s "$gitignore" ] && [ -n "$(tail -c 1 "$gitignore")" ]; then
    printf '\n' >> "$gitignore"
  fi
  printf '.%s/\n' "$directory" >> "$gitignore"
  echo "updated $gitignore: .$directory/"
}

install_one() {
  platform=$1
  id=$2
  source_dir=$3
  root=$(install_root "$platform")
  destination="$root/$id"
  if [ "$update" = "1" ] && [ ! -e "$destination" ] && [ ! -L "$destination" ]; then
    echo "[$platform] skipped (not installed): $id"
    return 0
  fi
  if [ ! -f "$source_dir/SKILL.md" ]; then
    echo "registered Skill is missing SKILL.md: $source_dir" >&2
    exit 1
  fi
  if [ -e "$destination" ] || [ -L "$destination" ]; then
    if [ "$force" != "1" ] && [ "$update" != "1" ]; then
      echo "already exists (use --force): $destination" >&2
      exit 1
    fi
  fi
  if [ "$dry_run" = "1" ]; then
    echo "[$platform] would install/update: $destination"
    return 0
  fi
  mkdir -p "$root"
  # Stage the complete skill before replacing the previous installation.
  staged=$(mktemp -d "$root/.set-up.XXXXXX")
  if ! cp -R "$source_dir/." "$staged/"; then
    rm -rf "$staged"
    echo "failed to copy Skill: $id; existing installation preserved" >&2
    exit 1
  fi
  rm -rf "$destination"
  mv "$staged" "$destination"
  installed_count=$((installed_count + 1))
  case "$id" in
    *openspec*) openspec_selected="1" ;;
  esac
  echo "[$platform] $id -> $destination"
}

install_openspec_cli() {
  if command -v openspec >/dev/null 2>&1; then
    echo "openspec CLI already installed: $(command -v openspec)"
    return 0
  fi

  pm=""
  if command -v npm >/dev/null 2>&1; then
    pm="npm"
  elif command -v pnpm >/dev/null 2>&1; then
    pm="pnpm"
  elif command -v bun >/dev/null 2>&1; then
    pm="bun"
  elif command -v yarn >/dev/null 2>&1; then
    pm="yarn"
  fi

  if [ -z "$pm" ]; then
    echo "openspec CLI requires npm, pnpm, bun, or yarn; none found" >&2
    echo "install it manually: npm install -g @fission-ai/openspec@latest" >&2
    return 1
  fi

  echo "installing openspec CLI with $pm ..."
  case "$pm" in
    npm)  npm install -g @fission-ai/openspec@latest ;;
    pnpm) pnpm add -g @fission-ai/openspec@latest ;;
    bun)  bun add -g @fission-ai/openspec@latest ;;
    yarn) yarn global add @fission-ai/openspec@latest ;;
  esac

  if command -v openspec >/dev/null 2>&1; then
    echo "openspec CLI installed: $(openspec --version 2>/dev/null || true)"
  else
    echo "openspec CLI install finished, but 'openspec' is not on PATH" >&2
    echo "add your package manager's global bin directory to PATH and re-check" >&2
  fi
}

openspec_selected="0"
# Sources are deliberately read from the manifest rather than discovered with
# find: this keeps the installation ID and set of installable skills identical
# to the Python installer.  The collection's manifest values are quoted,
# single-line TOML strings.
skill_list="$work/skills.list"
progress 3 "Reading registered Skill manifest ..."
awk '
  /^\[\[sources\]\]/ { emit=1; id=""; dest=""; next }
  emit && $0 ~ /^[[:space:]]*id[[:space:]]*=/ {
    value=$0
    sub(/^[^=]*=[[:space:]]*"/, "", value)
    sub(/"[[:space:]]*$/, "", value)
    id=value
  }
  emit && $0 ~ /^[[:space:]]*dest[[:space:]]*=/ {
    value=$0
    sub(/^[^=]*=[[:space:]]*"/, "", value)
    sub(/"[[:space:]]*$/, "", value)
    dest=value
  }
  emit && id != "" && dest != "" { print id "\t" dest; emit=0 }
' "$library/sources.toml" > "$skill_list"

selected_count="0"
while IFS="$(printf '\t')" read -r id relative; do
  if selected "$id"; then
    selected_count=$((selected_count + 1))
  fi
done < "$skill_list"

if [ "$selected_count" = "0" ]; then
  if [ -n "$only" ]; then
    echo "no matching Skill ID found: $only" >&2
  else
    echo "no SKILL.md files found" >&2
  fi
  exit 1
fi

action="Installing"
[ "$update" = "0" ] || action="Updating installed"
progress 4 "$action Skill(s) from $selected_count selected for target: $target ..."
current_skill="0"

while IFS="$(printf '\t')" read -r id relative; do
  case "$id" in
    ""|*/*|*'..'*|*[!a-z0-9-]*)
      echo "invalid Skill ID in sources.toml: $id" >&2
      exit 1
      ;;
  esac
  case "$relative" in
    ""|/*|../*|*/../*|*'/..')
      echo "unsafe Skill destination in sources.toml: $relative" >&2
      exit 1
      ;;
  esac
  selected "$id" || continue
  current_skill=$((current_skill + 1))
  printf '  (%s/%s) %s\n' "$current_skill" "$selected_count" "$id"
  skill_dir="$library/$relative"
  for platform in $targets; do
    install_one "$platform" "$id" "$skill_dir"
  done
done < "$skill_list"

progress 5 "Updating project configuration ..."
if [ -z "$dest_root" ] && [ "$update" = "0" ] && [ "$manage_gitignore" = "1" ] && [ "$dry_run" = "0" ]; then
  for platform in $targets; do
    case "$platform" in
      antigravity) ensure_gitignore_entry agents ;;
      *) ensure_gitignore_entry "$platform" ;;
    esac
  done
fi

progress 6 "Checking optional dependencies ..."
if [ "$openspec_selected" = "1" ]; then
  if [ "$skip_openspec_cli" = "1" ]; then
    if ! command -v openspec >/dev/null 2>&1; then
      echo "note: the installed openspec skills require the openspec CLI, which is not on PATH" >&2
      echo "run: npm install -g @fission-ai/openspec@latest" >&2
    fi
  else
    install_openspec_cli
  fi
fi

if [ "$update" = "1" ]; then
  echo "Update complete: $installed_count installation(s) updated for $target."
else
  echo "Installation complete: $installed_count installation(s) installed for $target."
fi
