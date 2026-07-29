#!/usr/bin/env sh
# Install skills from a public zh-skill GitHub repository without cloning it.
set -eu

repo="https://github.com/AK12-Official/zh-skill"
ref="main"
target="both"
force="0"
only=""
dest_root=""

usage() {
  cat <<'EOF'
Usage: install-skills.sh [options]

  --repo URL       zh-skill GitHub repository (default: AK12-Official/zh-skill)
  --ref REF        branch, tag, or commit (default: main)
  --target NAME    codex, claude, or both (default: both)
  --only ID        install only one ID; repeatable
  --dest-root DIR  override one installation root (single target only)
  --force          replace existing installed directories
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) repo=$2; shift 2 ;;
    --ref) ref=$2; shift 2 ;;
    --target) target=$2; shift 2 ;;
    --only) only="$only $2"; shift 2 ;;
    --dest-root) dest_root=$2; shift 2 ;;
    --force) force="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$target" in
  codex|claude|both) ;;
  *) echo "--target must be codex, claude, or both" >&2; exit 2 ;;
esac
if [ -n "$dest_root" ] && [ "$target" = "both" ]; then
  echo "--dest-root cannot be used with --target both" >&2
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

archive=$(mktemp "${TMPDIR:-/tmp}/zh-skill.XXXXXX.tar.gz")
work=$(mktemp -d "${TMPDIR:-/tmp}/zh-skill.XXXXXX")
cleanup() { rm -f "$archive"; rm -rf "$work"; }
trap cleanup EXIT HUP INT TERM

archive_url="https://codeload.github.com/$owner/$name/tar.gz/$ref"
curl -fsSL "$archive_url" -o "$archive"
tar -xzf "$archive" -C "$work"
library=$(find "$work" -mindepth 1 -maxdepth 1 -type d -print | head -n 1)
if [ -z "$library" ] || [ ! -d "$library/skills" ]; then
  echo "downloaded repository does not contain a skills directory" >&2
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
  mkdir -p "$root"
  if [ -e "$destination" ] || [ -L "$destination" ]; then
    if [ "$force" != "1" ]; then
      echo "already exists (use --force): $destination" >&2
      exit 1
    fi
    rm -rf "$destination"
  fi
  cp -R "$source_dir" "$destination"
  echo "[$platform] $id -> $destination"
}

found="0"
skill_list="$work/skills.list"
find "$library/skills" -type f -name SKILL.md -print > "$skill_list"
while IFS= read -r skill_file; do
  skill_dir=$(dirname "$skill_file")
  relative=${skill_dir#"$library/skills/"}
  id=$(printf '%s' "$relative" | tr '/' '-')
  selected "$id" || continue
  found="1"
  case "$target" in
    codex) install_one codex "$id" "$skill_dir" ;;
    claude) install_one claude "$id" "$skill_dir" ;;
    both)
      install_one codex "$id" "$skill_dir"
      install_one claude "$id" "$skill_dir"
      ;;
  esac
done < "$skill_list"

if [ "$found" = "0" ]; then
  if [ -n "$only" ]; then
    echo "no matching Skill ID found: $only" >&2
  else
    echo "no SKILL.md files found" >&2
  fi
  exit 1
fi

if [ -z "$dest_root" ]; then
  case "$target" in
    codex) ensure_gitignore_entry codex ;;
    claude) ensure_gitignore_entry claude ;;
    both)
      ensure_gitignore_entry codex
      ensure_gitignore_entry claude
      ;;
  esac
fi
