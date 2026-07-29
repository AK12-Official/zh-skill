#!/usr/bin/env python3
"""Install collected skills into Codex and/or Claude's user skill directory.

Local mode links to an existing zh-skill checkout by default, so updating that
checkout updates every project on the machine. Remote mode downloads a GitHub
tarball directly; it does not clone the collection repository.
"""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    print("需要 Python 3.11+（内置 tomllib）", file=sys.stderr)
    raise


HERE = Path(__file__).resolve().parents[1]


def safe_relative(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} 必须是安全的相对路径: {value}")
    return path


def load_sources(root: Path) -> list[dict]:
    manifest = root / "sources.toml"
    if not manifest.is_file():
        raise FileNotFoundError(f"找不到来源清单: {manifest}")
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    sources = data.get("sources", [])
    ids = [item.get("id") for item in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("sources.toml 中存在重复 id")
    return sources


def github_archive(repo: str, ref: str) -> str:
    parsed = urllib.parse.urlparse(repo)
    if parsed.netloc.lower() != "github.com":
        raise ValueError("免克隆模式目前只支持 GitHub 仓库")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise ValueError(f"无法解析 GitHub 仓库地址: {repo}")
    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    encoded_ref = urllib.parse.quote(ref, safe="/")
    return f"https://codeload.github.com/{owner}/{name}/tar.gz/{encoded_ref}"


def unpack_remote(repo: str, ref: str) -> tuple[tempfile.TemporaryDirectory, Path]:
    url = github_archive(repo, ref)
    request = urllib.request.Request(url, headers={"User-Agent": "zh-skill-installer"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    temp = tempfile.TemporaryDirectory(prefix="zh-skill-library-")
    root = Path(temp.name)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        safe_members = []
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"归档包含越界路径: {member.name}")
            if member.issym() or member.islnk():
                # Ignore links in unrelated parts of the collection. A Skill
                # that needs a link will fail the SKILL.md validation below.
                continue
            safe_members.append(member)
        archive.extractall(root, members=safe_members)
    children = [child for child in root.iterdir() if child.is_dir()]
    if len(children) != 1:
        temp.cleanup()
        raise ValueError("无法识别 GitHub 归档根目录")
    return temp, children[0]


def target_root(target: str, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    home = Path.home()
    if target == "codex":
        return home / ".codex" / "skills"
    if target == "claude":
        return home / ".claude" / "skills"
    raise ValueError(f"未知目标: {target}")


def remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def install_one(source: Path, target: Path, mode: str, force: bool) -> None:
    if not (source / "SKILL.md").is_file():
        raise ValueError(f"来源目录缺少 SKILL.md: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not force:
            raise FileExistsError(f"目标已存在（使用 --force 覆盖）: {target}")
        remove_existing(target)
    if mode == "link":
        target.symlink_to(source, target_is_directory=True)
        return
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        shutil.copytree(source, staging / target.name, symlinks=True)
        (staging / target.name).rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def selected_sources(sources: list[dict], only: list[str] | None) -> list[dict]:
    requested = set(only or [])
    known = {item.get("id") for item in sources}
    unknown = requested - known
    if unknown:
        raise ValueError(f"未知 Skill id: {', '.join(sorted(unknown))}")
    return [item for item in sources if not requested or item.get("id") in requested]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="免克隆模式的 GitHub 仓库 URL")
    parser.add_argument("--ref", default="main", help="远程仓库分支/tag/commit，默认 main")
    parser.add_argument("--target", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--only", action="append", help="只安装指定 id，可重复使用")
    parser.add_argument("--mode", choices=("link", "copy"), default="link")
    parser.add_argument("--dest-root", help="覆盖安装目录（仅适合一次安装一个 target）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 Skill 目录")
    args = parser.parse_args()

    temporary: tempfile.TemporaryDirectory | None = None
    try:
        if args.repo:
            temporary, library = unpack_remote(args.repo, args.ref)
            mode = "copy"  # 临时归档删除前不能创建链接
            print(f"已从 GitHub 归档下载 {args.repo}@{args.ref}（未克隆仓库）")
        else:
            library = HERE
            mode = args.mode
        sources = selected_sources(load_sources(library), args.only)
        if not sources:
            raise ValueError("来源清单为空")
        targets = ("codex", "claude") if args.target == "both" else (args.target,)
        for item in sources:
            item_id = item.get("id", "")
            if not item_id or Path(item_id).name != item_id:
                raise ValueError(f"id 必须是单层目录名: {item_id}")
            source = (library / safe_relative(item["dest"], "dest")).resolve()
            if library.resolve() not in source.parents:
                raise ValueError(f"来源 dest 越出了仓库根目录: {item['dest']}")
            for target in targets:
                destination = target_root(target, args.dest_root) / item_id
                install_one(source, destination, mode, args.force)
                print(f"[{target}] {item_id} -> {destination}")
    finally:
        if temporary is not None:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, FileExistsError, OSError, urllib.error.URLError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1)
