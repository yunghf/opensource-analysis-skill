#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loongwoong/OpenSource-X 仓库获取器 —— 不依赖 git 的源码读取通路。

用途：
    给出 GitHub / Gitee 仓库链接，通过 HTTP API + raw CDN 直接把源码树拉到本地，
    供深度项目分析的后续步骤（架构测绘 / 复杂度统计 / 依赖解析）使用。

为什么不用 git clone：
    - 仓库很大或只想看某个子目录时，全量克隆代价过高；
    - 目标环境可能没有 git、或不允许 clone（沙箱/CI）；
    - raw CDN 不计入 GitHub API 限流（API 只用于取元数据与文件树，通常 1~2 次调用）。

用法：
    python fetch_repo.py https://github.com/psf/requests
    python fetch_repo.py owner/repo --ref v2.31.0 --out ./repo
    python fetch_repo.py https://github.com/tiangolo/fastapi/tree/master/fastapi/routing
    python fetch_repo.py https://gitee.com/oschina/git-osc --meta-only
    python fetch_repo.py https://github.com/pandas-dev/pandas --max-files 200 --include "*.py,*.md,*.toml"

鉴权：
    设置环境变量 GITHUB_TOKEN（或 --token）可把 GitHub API 限额从 60/h 提到 5000/h。
    Gitee 同理支持 GITEE_TOKEN。

退出码：
    0 成功；1 参数/网络错误；2 部分文件失败（已下载的仍可用）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath

UA = "opensource-x-fetcher/1.1 (+workbuddy)"
RETRIES = 3          # 网络抖动重试次数（raw CDN 偶发 SSL UNEXPECTED_EOF，实测必须重试）
BACKOFF = 1.5        # 退避基数（秒）

HTTP_TIMEOUT = 30    # 由 --timeout 覆盖
HTTP_INSECURE = False  # 由 --insecure 覆盖

# ---------------------------------------------------------------- 跳过规则

SKIP_DIR_PARTS = {
    "node_modules", "vendor", "dist", "build", "out", "__pycache__", ".git",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "site-packages", "target", ".gradle", ".idea", ".vscode-test",
    "third_party", "bower_components", ".next", ".nuxt",
}

SKIP_EXT = {
    # 图片 / 字体 / 多媒体
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svgz",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".wav", ".mov", ".avi",
    # 二进制 / 归档 / 可执行
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".jar", ".war", ".so", ".dll", ".dylib",
    ".exe", ".bin", ".o", ".a", ".class", ".pyc", ".pyo", ".whl", ".egg", ".nupkg",
    # 设计 / 文档二进制
    ".psd", ".ai", ".sketch", ".fig", ".xcf", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # 凭据 / 密钥 / 证书
    ".pem", ".key", ".crt", ".csr", ".srl", ".p12", ".pfx", ".keystore", ".jks",
    # 数据库 / 数据快照
    ".db", ".sqlite", ".sqlite3", ".mdb", ".parquet", ".feather", ".pkl", ".pickle", ".npy", ".npz", ".pt", ".pth", ".onnx", ".h5", ".pb", ".ckpt", ".safetensors",
    # 锁文件（体积大、信息量低；依赖清单已覆盖）
    ".lock",
}

# 优先级：数字越小越先下载（用于 max-files 截断时保留最有价值的文件）
PRIORITY_RULES: list[tuple[int, re.Pattern]] = [
    (0, re.compile(r"(^|/)(README|readme)(\.[a-z]+)?$")),
    (1, re.compile(r"(^|/)(pyproject\.toml|package\.json|pom\.xml|build\.gradle(\.kts)?|Cargo\.toml|go\.mod|composer\.json|Gemfile|requirements[^/]*\.txt|setup\.py|setup\.cfg|environment\.ya?ml|Makefile|CMakeLists\.txt|Dockerfile[^/]*)$")),
    (2, re.compile(r"(^|/)(main|app|index|cli|server|manage|__init__|__main__)\.(py|js|ts|tsx|jsx|go|java|rs|c|cc|cpp|h|cs|rb|php|kt|swift)$")),
    (3, re.compile(r"(^|/)(ARCHITECTURE|DESIGN|docs?|CONTRIBUTING|CHANGELOG|HISTORY)[^/]*\.(md|rst|txt)$")),
    (4, re.compile(r"\.(py|js|ts|tsx|jsx|go|java|rs|c|cc|cpp|h|hpp|cs|rb|php|kt|swift|scala|sh|sql|proto)$")),
    (5, re.compile(r"\.(json|ya?ml|toml|ini|cfg|conf|properties|env\.example|tf|gradle)$")),
    (6, re.compile(r"\.(md|rst|txt|adoc)$")),
]
DEFAULT_PRIORITY = 7


def priority_of(path: str) -> int:
    for score, pat in PRIORITY_RULES:
        if pat.search(path):
            return score
    return DEFAULT_PRIORITY


def should_skip(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(p in SKIP_DIR_PARTS for p in parts[:-1]):
        return True
    suf = PurePosixPath(path).suffix.lower()
    if suf in SKIP_EXT:
        return True
    # 无扩展名的常见二进制/证书目录
    if any(p in {"certs", "certificates", "keys"} for p in parts[:-1]) and suf in {"", ".pem", ".key"}:
        return True
    return False


# ---------------------------------------------------------------- URL 解析

def parse_target(raw: str) -> dict:
    """把各种写法统一成 {host, owner, repo, ref, subpath}。"""
    s = raw.strip().strip("'\"")
    s = re.sub(r"^git\+", "", s)
    s = re.sub(r"\.git$", "", s)

    # git@host:owner/repo
    m = re.match(r"^git@(?P<host>[^:]+):(?P<rest>.+)$", s)
    if m:
        s = f"https://{m.group('host')}/{m.group('rest')}"

    if not s.startswith("http"):
        # owner/repo 简写
        parts = s.split("/")
        if len(parts) >= 2:
            s = f"https://github.com/{parts[0]}/{parts[1]}" + ("/" + "/".join(parts[2:]) if len(parts) > 2 else "")
        else:
            raise ValueError(f"无法识别的仓库标识: {raw}")

    m = re.match(r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/?#]+)(?P<rest>/.*)?$", s)
    if not m:
        raise ValueError(f"无法解析的仓库 URL: {raw}")

    host = m.group("host").lower()
    owner, repo = m.group("owner"), m.group("repo")
    rest = (m.group("rest") or "").strip("/")

    if host in {"github.com", "www.github.com"}:
        host_key = "github"
    elif host in {"gitee.com", "www.gitee.com"}:
        host_key = "gitee"
    else:
        raise ValueError(f"暂不支持的托管平台: {host}（当前支持 github.com / gitee.com）")

    ref, subpath = None, ""
    if rest:
        parts = rest.split("/")
        # 只有 tree / blob 是 GitHub 的路径前缀关键字。注意：不要把 src 当关键字
        # （很多仓库的真实目录就叫 src/，误判会导致 ref 被解析错 → 树请求 404）
        if parts[0] in {"tree", "blob"} and len(parts) >= 2:
            ref = parts[1]
            subpath = "/".join(parts[2:])
        else:
            subpath = rest

    return {"host": host_key, "owner": owner, "repo": repo, "ref": ref, "subpath": subpath}


# ---------------------------------------------------------------- HTTP

def http_get(url: str, token: str | None = None, timeout: int | None = None, as_json: bool = False,
             insecure: bool | None = None, retries: int | None = None):
    """带退避重试的 GET。

    为什么要重试：raw.githubusercontent.com 在本机偶发 `SSL: UNEXPECTED_EOF_WHILE_READING`
    （并发下载时更明显），单次失败不代表文件不可得。对 5xx / 403 / 429 与网络异常一律退避重试。
    """
    timeout = HTTP_TIMEOUT if timeout is None else timeout
    insecure = HTTP_INSECURE if insecure is None else insecure
    retries = RETRIES if retries is None else retries
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json" if as_json else "*/*"}
    if token:
        headers["Authorization"] = f"token {token}" if "gitee.com" in url else f"Bearer {token}"

    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                body = r.read()
            return json.loads(body.decode("utf-8", "replace")) if as_json else body
        except urllib.error.HTTPError as e:
            last = e
            # 4xx（非限流）是确定性失败，重试无意义
            if e.code not in (403, 408, 429) and e.code < 500:
                raise
            if attempt < retries:
                time.sleep(BACKOFF * attempt)
                continue
            raise
        except Exception as e:                      # URLError / SSLError / timeout / ConnectionReset
            last = e
            if attempt < retries:
                time.sleep(BACKOFF * attempt)
                continue
            raise
    raise last  # pragma: no cover


def api_base(host: str) -> str:
    return "https://api.github.com" if host == "github" else "https://gitee.com/api/v5"


def repo_meta(host: str, owner: str, repo: str, token: str | None) -> dict:
    url = f"{api_base(host)}/repos/{owner}/{repo}"
    if host == "gitee" and token:
        url += f"?access_token={token}"
    return http_get(url, token, as_json=True)


def resolve_ref(host: str, owner: str, repo: str, meta: dict, ref: str | None, token: str | None) -> str:
    if ref:
        return ref
    return meta.get("default_branch") or "main"


def fetch_tree(host: str, owner: str, repo: str, ref: str, token: str | None) -> tuple[list[dict], bool]:
    """返回 (entries, truncated)。entries 只含 blob。"""
    if host == "github":
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
        data = http_get(url, token, as_json=True)
        entries = [e for e in data.get("tree", []) if e.get("type") == "blob"]
        return entries, bool(data.get("truncated"))

    # Gitee：先取分支 SHA，再递归取树
    q = f"?access_token={token}" if token else ""
    branch = http_get(f"https://gitee.com/api/v5/repos/{owner}/{repo}/branches/{ref}{q}", token, as_json=True)
    sha = (branch.get("commit") or {}).get("sha") or branch.get("sha")
    data = http_get(f"https://gitee.com/api/v5/repos/{owner}/{repo}/git/trees/{sha}?recursive=1{q}", token, as_json=True)
    entries = [e for e in data.get("tree", []) if e.get("type") == "blob"]
    return entries, bool(data.get("truncated"))


def raw_url(host: str, owner: str, repo: str, ref: str, path: str) -> str:
    """兼容旧调用：返回首选原始内容 URL。"""
    return raw_urls(host, owner, repo, ref, path)[0][1]


# 原始内容多源候选。实测（2026-09-18 本机，两轮独立探测）——**稳定性随时间波动**，
# 所以不要依赖单一镜像，靠下面的多源轮询 + 自适应偏好兜住：
#   github.com/<o>/<r>/raw/<ref>/<path>     4/4 · 4/4   平均 0.87s   ← 最稳，优先
#   raw.githubusercontent.com/...           1/3 · 4/4   平均 0.55s   ← 最快但历史上有 1/3 崩率
#   raw.githack.com/<o>/<r>/<ref>/<path>    4/4 · 4/4   平均 0.89s
#   cdn.statically.io/gh/<o>/<r>/<ref>/<p>  4/4 · 1/4   平均 24.25s  ← 慢且不稳，仅兜底
#   cdn.jsdelivr.net/gh/...                 0~2/4                  ← 本机不可用，不纳入
RAW_MIRRORS: dict[str, list[str]] = {
    "github": [
        "https://github.com/{owner}/{repo}/raw/{ref}/{path}",
        "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}",
        "https://raw.githack.com/{owner}/{repo}/{ref}/{path}",
        "https://cdn.statically.io/gh/{owner}/{repo}/{ref}/{path}",
    ],
    "gitee": [
        "https://gitee.com/{owner}/{repo}/raw/{ref}/{path}",
    ],
}

# 每个 host 记住上次成功的镜像下标，下次优先命中（自适应，减少无效往返）
_preferred: dict[str, int] = {"github": 0, "gitee": 0}


def raw_urls(host: str, owner: str, repo: str, ref: str, path: str) -> list[tuple[int, str]]:
    """按「上次成功者优先」的顺序返回 [(镜像下标, url), ...]。"""
    tpls = RAW_MIRRORS[host]
    start = _preferred.get(host, 0) % len(tpls)
    out: list[tuple[int, str]] = []
    for i in range(len(tpls)):
        idx = (start + i) % len(tpls)
        out.append((idx, tpls[idx].format(owner=owner, repo=repo, ref=ref, path=path)))
    return out


# ---------------------------------------------------------------- 过滤

def select_files(entries: list[dict], args) -> tuple[list[dict], list[dict]]:
    include = [p.strip() for p in (args.include or "").split(",") if p.strip()]
    exclude = [p.strip() for p in (args.exclude or "").split(",") if p.strip()]

    kept, dropped = [], []
    for e in entries:
        path = e["path"]
        if args.subpath and not path.startswith(args.subpath.rstrip("/") + "/") and path != args.subpath:
            dropped.append({**e, "reason": "subpath"})
            continue
        if include and not any(PurePosixPath(path).match(p) for p in include):
            dropped.append({**e, "reason": "include-filter"})
            continue
        if exclude and any(PurePosixPath(path).match(p) for p in exclude):
            dropped.append({**e, "reason": "exclude-filter"})
            continue
        if should_skip(path):
            dropped.append({**e, "reason": "binary-or-vendored"})
            continue
        size = e.get("size") or 0
        if args.max_file_size and size > args.max_file_size:
            dropped.append({**e, "reason": f"size>{args.max_file_size}"})
            continue
        kept.append(e)

    kept.sort(key=lambda e: (priority_of(e["path"]), -int(e.get("size") or 0)))
    if args.max_files and len(kept) > args.max_files:
        for e in kept[args.max_files:]:
            dropped.append({**e, "reason": "max-files"})
        kept = kept[: args.max_files]
    return kept, dropped


# ---------------------------------------------------------------- 主流程

def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024.0
    return f"{n:.1f}TB"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="通过 URL 读取 GitHub/Gitee 源码（无需 git clone）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("target", help="仓库 URL 或 owner/repo")
    ap.add_argument("--ref", help="分支 / tag / commit（默认仓库默认分支）")
    ap.add_argument("--out", help="输出目录（默认 ./<repo>）")
    ap.add_argument("--include", help="只下载匹配的文件，逗号分隔，如 '*.py,*.md'")
    ap.add_argument("--exclude", help="排除匹配的文件，逗号分隔")
    ap.add_argument("--max-files", type=int, default=300, help="最多下载文件数（按优先级截断，默认 300）")
    ap.add_argument("--max-file-size", type=int, default=400_000, help="单文件大小上限（字节，默认 400KB）")
    ap.add_argument("--workers", type=int, default=8, help="并发下载线程数（默认 6；过高会加剧 TLS 抖动）")
    ap.add_argument("--timeout", type=int, default=30, help="单次请求超时秒数（默认 30）")
    ap.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验（仅在证书链异常时使用）")
    ap.add_argument("--token", help="API token（也可用 GITHUB_TOKEN / GITEE_TOKEN 环境变量）")
    ap.add_argument("--meta-only", action="store_true", help="只取元数据与文件树，不下载文件内容")
    args = ap.parse_args()

    global HTTP_TIMEOUT, HTTP_INSECURE
    HTTP_TIMEOUT, HTTP_INSECURE = args.timeout, args.insecure

    t0 = time.time()
    try:
        tgt = parse_target(args.target)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    host, owner, repo = tgt["host"], tgt["owner"], tgt["repo"]
    args.subpath = tgt["subpath"]
    ref_opt = args.ref or tgt["ref"]
    token = args.token or os.environ.get("GITHUB_TOKEN" if host == "github" else "GITEE_TOKEN")
    slug = f"{owner}/{repo}"
    print(f"🔎 目标: {slug}  [{host}]" + (f"  ref={ref_opt}" if ref_opt else "") + (f"  subpath={args.subpath}" if args.subpath else ""))

    out_dir = Path(args.out or repo).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = out_dir / "_fetch"
    meta_dir.mkdir(exist_ok=True)

    # 1) 元数据
    try:
        meta = repo_meta(host, owner, repo, token)
    except urllib.error.HTTPError as e:
        msg = {401: "未授权（私有仓库需 --token）", 403: "被限流（设置 GITHUB_TOKEN 可提到 5000/h）", 404: "仓库不存在或为私有"}.get(e.code, f"HTTP {e.code}")
        print(f"❌ 获取仓库元数据失败: {msg}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ 获取仓库元数据失败: {type(e).__name__} {e}", file=sys.stderr)
        return 1

    ref = resolve_ref(host, owner, repo, meta, ref_opt, token)
    lic = (meta.get("license") or {}) or {}
    print(f"   ref={ref} | ⭐{meta.get('stargazers_count', 0)} | license={lic.get('spdx_id') or lic.get('name') or 'unknown'} | 最后推送={meta.get('pushed_at', '?')[:10]}")

    # 2) 文件树
    try:
        entries, truncated = fetch_tree(host, owner, repo, ref, token)
    except Exception as e:
        print(f"❌ 获取文件树失败: {type(e).__name__} {e}", file=sys.stderr)
        return 1
    print(f"   文件树: {len(entries)} 个 blob" + ("  ⚠️ API 标记 truncated（仓库过大，树可能不完整）" if truncated else ""))

    kept, dropped = select_files(entries, args)
    total_bytes = sum(int(e.get("size") or 0) for e in kept)
    print(f"   选中 {len(kept)} 个文件 ({human(total_bytes)})，跳过 {len(dropped)} 个")

    # 3) 下载
    failures: list[dict] = []
    ok = 0
    if not args.meta_only:
        def one(e: dict):
            path = e["path"]
            dest = out_dir / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            last: Exception | None = None
            # 多源轮询：单镜像失败自动换下一个（本机 raw.githubusercontent.com 实测仅约 1/3 成功率）
            for idx, url in raw_urls(host, owner, repo, ref, path):
                try:
                    body = http_get(url, token, retries=2)
                    dest.write_bytes(body)
                    if _preferred.get(host) != idx:
                        _preferred[host] = idx          # 记住可用镜像，后续文件优先命中
                    return path, len(body)
                except urllib.error.HTTPError as ex:
                    last = ex
                    if ex.code == 404 and host == "github":
                        continue                        # 该镜像没有此文件（如仅存在于 git 对象），换源
                    continue
                except Exception as ex:
                    last = ex
                    continue
            raise last if last else RuntimeError(f"无可用原始内容源: {path}")

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = {pool.submit(one, e): e for e in kept}
            for i, fut in enumerate(as_completed(futs), 1):
                e = futs[fut]
                try:
                    fut.result(); ok += 1
                except Exception as ex:
                    failures.append({"path": e["path"], "error": f"{type(ex).__name__}: {ex}"})
                if i % 25 == 0 or i == len(kept):
                    print(f"   下载进度 {i}/{len(kept)}")

    # 4) 落盘产物
    (meta_dir / "tree.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    (meta_dir / "meta.json").write_text(json.dumps({
        "host": host, "owner": owner, "repo": repo, "ref": ref, "slug": slug,
        "stars": meta.get("stargazers_count"), "forks": meta.get("forks_count"),
        "open_issues": meta.get("open_issues_count"), "license": lic.get("spdx_id") or lic.get("name"),
        "description": meta.get("description"), "topics": meta.get("topics") or [],
        "created_at": meta.get("created_at"), "pushed_at": meta.get("pushed_at"),
        "archived": meta.get("archived"), "language": meta.get("language"),
        "default_branch": meta.get("default_branch"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "api_truncated": truncated, "downloaded": ok, "failed": len(failures),
        "source_url": f"https://{ 'github.com' if host=='github' else 'gitee.com' }/{slug}",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 语言构成（按体积估算，供技术栈拆解用）
    ext_bytes: dict[str, int] = {}
    for e in kept:
        suf = PurePosixPath(e["path"]).suffix.lower() or "(no-ext)"
        ext_bytes[suf] = ext_bytes.get(suf, 0) + int(e.get("size") or 0)
    top_ext = sorted(ext_bytes.items(), key=lambda kv: -kv[1])[:15]

    dropped_summary: dict[str, int] = {}
    for d in dropped:
        dropped_summary[d["reason"]] = dropped_summary.get(d["reason"], 0) + 1

    summary = [
        f"# 仓库获取报告 · {slug}",
        "",
        f"- 来源：{ 'github.com' if host=='github' else 'gitee.com' }/{slug}  （ref: `{ref}`）",
        f"- 采集时间：{time.strftime('%Y-%m-%d %H:%M:%S')}    耗时：{time.time()-t0:.1f}s",
        f"- 元数据：⭐{meta.get('stargazers_count')} · fork {meta.get('forks_count')} · open issues {meta.get('open_issues_count')} · 许可证 {lic.get('spdx_id') or lic.get('name') or 'unknown'} · 主语言 {meta.get('language')}",
        f"- 仓库状态：{'⚠️ 已归档（archived）' if meta.get('archived') else '活跃'} · 最后推送 {meta.get('pushed_at','?')[:10]} · 创建于 {meta.get('created_at','?')[:10]}",
        f"- 描述：{meta.get('description') or '（无）'}",
        "",
        f"## 文件树规模",
        f"",
        f"- blob 总数：**{len(entries)}**" + ("（⚠️ API 标记 truncated，树不完整，建议改用 git 浅克隆补齐）" if truncated else ""),
        f"- 本次下载：**{ok}** 个文件，共 {human(sum(int(e.get('size') or 0) for e in kept if e['path'] not in {f['path'] for f in failures}))}"
        + (f"；失败 {len(failures)} 个" if failures else ""),
        f"- 按体积估算的语言构成（Top 15）：",
        "",
        "| 扩展名 | 体积 | 占比 |",
        "|---|---|---|",
    ]
    tot = sum(v for _, v in top_ext) or 1
    for ext, b in top_ext:
        summary.append(f"| `{ext}` | {human(b)} | {b*100.0/tot:.1f}% |")
    summary += ["", "## 跳过明细（按原因）", "", "| 原因 | 数量 |", "|---|---|"]
    for r, c in sorted(dropped_summary.items(), key=lambda kv: -kv[1]):
        summary.append(f"| {r} | {c} |")
    if failures:
        summary += ["", "## 下载失败", "", "| 文件 | 错误 |", "|---|---|"]
        for f in failures[:50]:
            summary.append(f"| `{f['path']}` | {f['error']} |")
    summary += [
        "",
        "## 后续步骤",
        "",
        "1. 用 `_fetch/tree.json` 做目录测绘与分层判断（无需再请求 API）。",
        "2. 用 `_fetch/meta.json` 填充报告开头的「分析对象」与「数据来源」字段。",
        "3. 进入深度项目分析主流程 Step 1 起（架构 → 演化 → 第一性原理 → 巧思 → 质量 → 技术栈）。",
        "4. 演化分析需要 git 历史：本通路不含提交记录，若需角度二请改用 `git clone --filter=blob:none`。",
        "",
    ]
    (meta_dir / "summary.md").write_text("\n".join(summary), encoding="utf-8")

    print(f"\n✅ 完成：{ok} 个文件 → {out_dir}")
    print(f"   元数据与报告：{meta_dir}\\meta.json | tree.json | summary.md")
    if failures:
        print(f"   ⚠️ {len(failures)} 个文件失败（详见 summary.md）")
    if args.meta_only:
        print("   （--meta-only：仅元数据与文件树，未下载内容）")
    print(f"   耗时 {time.time()-t0:.1f}s")
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
