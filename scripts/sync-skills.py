#!/usr/bin/env python3
"""Synchronize skills declared in sources.toml.

The script intentionally uses only Python's standard library. It replaces each
managed destination atomically, then records the resolved upstream revision in
sources.lock.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    print("需要 Python 3.11+（内置 tomllib）", file=sys.stderr)
    raise


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sources.toml"
LOCKFILE = ROOT / "sources.lock.json"


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def safe_repo_path(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} 必须是相对且不包含 .. 的路径: {value}")
    return path


def destination(value: str) -> Path:
    relative = safe_repo_path(value, "dest")
    target = (ROOT / relative).resolve()
    if ROOT not in target.parents:
        raise ValueError(f"dest 越出了仓库根目录: {value}")
    return target


def copy_source(source: Path, dest: Path, dry_run: bool) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"来源目录不存在: {source}")
    if dry_run:
        print(f"  would replace {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{dest.name}.", dir=dest.parent))
    try:
        shutil.copytree(source, staging / dest.name, symlinks=True)
        backup = dest.with_name(f".{dest.name}.old")
        if backup.exists():
            shutil.rmtree(backup)
        if dest.exists():
            dest.rename(backup)
        (staging / dest.name).rename(dest)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def sync_git(item: dict, dest: Path, dry_run: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="zh-skill-git-") as tmp:
        checkout = Path(tmp) / "repo"
        run("git", "clone", "--filter=blob:none", "--no-checkout", item["repo"], str(checkout))
        run("git", "fetch", "--depth=1", "origin", item.get("ref", "HEAD"), cwd=checkout)
        revision = run("git", "rev-parse", "FETCH_HEAD", cwd=checkout)
        run("git", "checkout", "--detach", revision, cwd=checkout)
        source = checkout / safe_repo_path(item["path"], "path")
        copy_source(source, dest, dry_run)
    return {"kind": "git", "repo": item["repo"], "ref": item.get("ref", "HEAD"), "commit": revision}


def sync_zip(item: dict, dest: Path, dry_run: bool) -> dict:
    expected = item.get("sha256", "").lower()
    if len(expected) != 64:
        raise ValueError(f"ZIP 来源 {item['id']} 必须提供 64 位 sha256")
    with tempfile.TemporaryDirectory(prefix="zh-skill-zip-") as tmp:
        archive = Path(tmp) / "source.zip"
        urllib.request.urlretrieve(item["url"], archive)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"{item['id']} SHA-256 不匹配: 期望 {expected}，实际 {actual}")
        extracted = Path(tmp) / "extracted"
        extracted.mkdir()
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                member_path = (extracted / member.filename).resolve()
                if extracted not in member_path.parents and member_path != extracted:
                    raise ValueError(f"ZIP 包含越界路径: {member.filename}")
            zf.extractall(extracted)
        source = extracted / safe_repo_path(item["path"], "path")
        copy_source(source, dest, dry_run)
    return {"kind": "zip", "url": item["url"], "sha256": actual}


def load_manifest() -> list[dict]:
    data = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    items = data.get("sources", [])
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("sources.toml 中存在重复 id")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="只同步指定 id，可重复使用")
    parser.add_argument("--dry-run", action="store_true", help="只显示将要执行的操作")
    args = parser.parse_args()

    items = load_manifest()
    selected = set(args.only or [])
    if selected:
        known = {item["id"] for item in items}
        unknown = selected - known
        if unknown:
            raise ValueError(f"未知来源 id: {', '.join(sorted(unknown))}")
        items = [item for item in items if item["id"] in selected]

    lock = json.loads(LOCKFILE.read_text(encoding="utf-8")) if LOCKFILE.exists() else {"sources": {}}
    lock.setdefault("sources", {})
    # Remove records for sources that no longer exist in the manifest. This
    # keeps the generated lock file aligned when a source id is renamed.
    manifest_ids = {item["id"] for item in load_manifest()}
    for source_id in list(lock["sources"]):
        if source_id not in manifest_ids:
            del lock["sources"][source_id]
    for item in items:
        for required in ("id", "kind", "path", "dest"):
            if not item.get(required):
                raise ValueError(f"来源缺少字段 {required}: {item}")
        dest = destination(item["dest"])
        print(f"[{item['id']}] {item['kind']}")
        if item["kind"] == "git":
            record = sync_git(item, dest, args.dry_run)
        elif item["kind"] == "zip":
            record = sync_zip(item, dest, args.dry_run)
        else:
            raise ValueError(f"不支持的来源类型: {item['kind']}")
        record["dest"] = item["dest"]
        if item.get("license"):
            record["license"] = item["license"]
        lock["sources"][item["id"]] = record

    if not args.dry_run:
        LOCKFILE.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("完成" if not args.dry_run else "dry-run 完成")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1)
