#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_module.py — 模块下载 CLI（纯标准库，离线友好）。

从 GitHub Releases 拉取某个模块的打包产物，或列出现有可下载模块。

约定：
  每个 Release 标签 <tag> 附带资产 <module_id>.tar.gz，
  其下载地址为：
    https://github.com/<owner>/<repo>/releases/download/<tag>/<module_id>.tar.gz
  catalog.json 中每个模块的 download_url 指向该 Release 标签页。

子命令：
  list                             读取 catalog.json 并打印可下载模块
  get   --module <id> [--tag T]   下载并解包到 ./modules/

也可使用 --from-local <path> 直接从本地归档解包（无需联网），
便于 CI 或内网环境复用已发布模块。
"""
import argparse
import json
import os
import sys
import tarfile
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER = "vickywu97"
REPO = "verified-chinese-law-kb"
DEFAULT_BASE = f"https://github.com/{OWNER}/{REPO}/releases/download"


def load_catalog():
    path = os.path.join(REPO_ROOT, "catalog.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_list(_args):
    cat = load_catalog()
    print(f"仓库: {OWNER}/{REPO}  (catalog v{cat.get('version')})\n")
    print(f"{'id':6s} {'名称':14s} {'状态':9s} {'已核验':8s} 下载地址")
    for m in cat.get("modules", []):
        print(f"{m['id']:6s} {m['name']:14s} {m.get('status',''):9s} "
              f"{m.get('verified_articles',0):<8d} {m.get('download_url','')}")
    return 0


def _derive_tag(cat, module_id):
    for m in cat.get("modules", []):
        if m["id"] == module_id:
            # download_url 形如 .../releases/tag/v1.0.0-M1
            return os.path.basename(m.get("download_url", "")) or f"v1.0.0-{module_id}"
    return f"v1.0.0-{module_id}"


def cmd_get(args):
    cat = load_catalog()
    tag = args.tag or _derive_tag(cat, args.module)
    asset = f"{args.module}.tar.gz"
    url = f"{args.base}/{tag}/{asset}"

    if args.from_local:
        archive = args.from_local
    else:
        archive = os.path.join(REPO_ROOT, "archive", asset)
        os.makedirs(os.path.dirname(archive), exist_ok=True)
        print(f"下载 {url}")
        try:
            urllib.request.urlretrieve(url, archive)
        except Exception as e:  # noqa: BLE001
            print(f"下载失败: {e}", file=sys.stderr)
            return 2

    dest = os.path.join(REPO_ROOT, "modules", args.module)
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest)
    print(f"已解包到 {dest}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="下载知识库模块")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("list")
    p = sub.add_parser("get")
    p.add_argument("--module", required=True, help="模块 id，如 M1")
    p.add_argument("--tag", default=None, help="Release 标签，缺省从 catalog 推导")
    p.add_argument("--base", default=DEFAULT_BASE, help="Release 资产基址")
    p.add_argument("--from-local", default=None, help="本地归档路径（离线模式）")
    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "get":
        return cmd_get(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
