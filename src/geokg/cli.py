"""``geokg`` 命令行 —— GeoKG 的管理工具。

## 定位

只做**表现**：把 :mod:`geokg.admin` 返回的 dict 渲染成人看的表格。
所有逻辑都在 ``admin`` 里，因此未来的平台 Web 管理面可以直接复用同一批
函数，不需要重写业务逻辑。

加 ``--json`` 可输出原始结构（供脚本/CI/Web 消费，也是接口契约的直观形态）。

## 子命令

只读（零网络、零副作用）::

    geokg status                 整体状态 + 陈旧度告警
    geokg verify [--drift]        数据完整性 + 溯源门禁（--drift 才联网）
    geokg licenses                许可与署名汇总
    geokg counts [--admin1]        计数口径 + 溯源审计
    geokg version                 数据集版本与指纹

有副作用::

    geokg manifest --write        重算数据清单
    geokg refresh <id>|--all      重新生成数据（联网）
    geokg build [--admin1]        构建知识图谱并报告统计
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import admin
from .sources import DATASET_VERSION, DATASETS

# --------------------------------------------------------------------------- #
# 渲染工具
# --------------------------------------------------------------------------- #
_STALE = "⚠️"
_OK = "✅"
_FAIL = "❌"


def _table(headers: list[str], rows: list[list[str]], *, widths: list[int] | None = None) -> str:
    if not rows:
        return "  （无）"
    w = widths or [
        max(len(str(headers[i])), max(len(str(r[i])) for r in rows))
        for i in range(len(headers))
    ]
    out = ["  " + "  ".join(str(h).ljust(w[i]) for i, h in enumerate(headers))]
    out.append("  " + "  ".join("-" * w[i] for i in range(len(headers))))
    for r in rows:
        out.append("  " + "  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))
    return "\n".join(out)


def _emit(args: argparse.Namespace, payload: dict[str, Any], render) -> int:
    """统一的输出与退出码处理。"""
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        render(payload)
    return 0 if payload.get("ok", True) else 1


# --------------------------------------------------------------------------- #
# 各子命令
# --------------------------------------------------------------------------- #
def cmd_status(args: argparse.Namespace) -> int:
    st = admin.status()

    def render(s: dict[str, Any]) -> None:
        print("=" * 78)
        mf = "有" if s["manifest_present"] else "缺"
        print(f" GeoKG 数据集状态    version={s['dataset_version']}    manifest={mf}")
        print("=" * 78)
        print()
        rows = []
        for d in s["datasets"]:
            if not d["exists"]:
                flag = _FAIL
            elif d["stale"]:
                flag = _STALE
            else:
                flag = _OK
            age = f"{d['age_days']}d" if d["age_days"] is not None else "—"
            thr = f"{d['staleness_days']}d" if d["staleness_days"] else "静态"
            rows.append([flag, d["id"], d["tier"], f"{d['rows']:,}",
                         str(d["size_bytes"] // 1024) + "K", age, thr])
        print(_table(["", "数据集", "分级", "行数", "体积", "已过", "阈值"], rows))
        print()
        c = s["counts"]
        print(f"  合计: {c['datasets']} 个数据集 / {c['present']} 个已就位 / "
              f"{c['rows_total']:,} 行")
        print()
        if s["warnings"]:
            print("  告警:")
            for w in s["warnings"]:
                mark = _FAIL if w["level"] == "error" else _STALE
                print(f"    {mark} [{w['dataset']}] {w['message']}")
        else:
            print(f"  {_OK} 无告警")
        print()

    if args.strict:
        # 定时 CI 用：数据缺失或陈旧即失败（指纹漂移不算，它是"忘了重算清单"）。
        # 判据由 admin.status() 以结构化字段给出，与 HTTP 门禁同源。
        st["ok"] = st["ok_strict"]
    return _emit(args, st, render)


def cmd_verify(args: argparse.Namespace) -> int:
    v = admin.verify(drift=args.drift)

    def render(v: dict[str, Any]) -> None:
        print("=" * 78)
        print(" GeoKG 校验" + ("（含上游漂移检查）" if v["drift_requested"] else "（离线）"))
        print("=" * 78)
        print()
        for c in v["checks"]:
            print(f"  {_OK if c['ok'] else _FAIL} {c['name']}")
            if c.get("detail"):
                print(f"      {c['detail']}")
        if v["drift"]:
            print()
            print("  上游漂移:")
            for d in v["drift"]:
                mark = {"clean": _OK, "drift": _STALE, "skip": "—",
                        "timeout": _FAIL}.get(d["status"], "?")
                print(f"    {mark} {d['id']:<24} {d['status']:<8} {d['detail']}")
        print()
        print(f"  结论: {'全部通过' if v['ok'] else '存在失败项'}")
        print()

    return _emit(args, v, render)


def cmd_licenses(args: argparse.Namespace) -> int:
    lic = admin.licenses()

    def render(lic_data: dict[str, Any]) -> None:
        print("=" * 78)
        print(" GeoKG 许可与署名汇总")
        print("=" * 78)
        print()
        for g in lic_data["groups"]:
            print(f"  【{g['license']}】")
            print(f"    数据集: {', '.join(g['datasets'])}")
            for a in g["attributions"]:
                print(f"    署名  : {a}")
            print()
        print("  必须署名的来源:")
        for a in lic_data["requires_attribution"]:
            print(f"    · {a}")
        if lic_data["authored_note"]:
            print()
            print(f"  说明: {lic_data['authored_note']}")
        print()

    return _emit(args, lic, render)


def cmd_counts(args: argparse.Namespace) -> int:
    from .provenance import format_provenance_report, format_report

    levels = [] if args.no_monitoring else (["country", "admin1"] if args.admin1 else ["country"])
    r = admin.counts(levels)

    def render(r: dict[str, Any]) -> None:
        title = "GeoKG 计数口径报告"
        if not r["monitor_levels"]:
            title += "（不含监测任务空间）"
        print(format_report(r["basis"], title=title))
        print(format_provenance_report(r["provenance"]))

    return _emit(args, {"ok": True, **r}, render)


def cmd_manifest(args: argparse.Namespace) -> int:
    mf = admin.manifest(write=args.write)

    def render(m: dict[str, Any]) -> None:
        print("=" * 78)
        print(f" GeoKG 数据清单   version={m['dataset_version']}")
        print("=" * 78)
        print()
        rows = [[d["file"], f"{d['rows']:,}", (d["sha256"] or "—")[:12], d["retrieved"]]
                for d in m["files"].values()]
        print(_table(["文件", "行数", "sha256", "取数日期"], rows))
        print()
        print(f"  数据集指纹: {m['fingerprint']}")
        print(f"  生成时间  : {m['generated_at']}")
        if args.write:
            print(f"  {_OK} 已写入 {admin.MANIFEST_FILE}")
        else:
            print("  （未写入；加 --write 才会落盘）")
        print()

    return _emit(args, mf, render)


def cmd_refresh(args: argparse.Namespace) -> int:
    if not args.all and not args.dataset:
        print(f"{_FAIL} 需指定数据集 id 或 --all", file=sys.stderr)
        print(f"     可用: {', '.join(d.id for d in DATASETS)}", file=sys.stderr)
        return 2
    r = admin.refresh(args.dataset, all_=args.all, timeout=args.timeout)

    def render(r: dict[str, Any]) -> None:
        print("=" * 78)
        print(" GeoKG 数据刷新")
        print("=" * 78)
        print()
        for x in r["results"]:
            sec = f"{x.get('seconds', '')}s" if x.get("seconds") else ""
            print(f"  {_OK if x['ok'] else _FAIL} {x['id']:<24} {sec:<8} {x.get('detail', '')}")
        print()
        if r["manifest"]:
            print(f"  清单已重算: {r['manifest']['fingerprint'][:16]}…")
        else:
            print(f"  {_STALE} 有失败项，清单未重算")
        print()

    return _emit(args, {**r, "ok": r["ok"]}, render)


def cmd_build(args: argparse.Namespace) -> int:
    levels = None if args.admin1 else ["country"]
    b = admin.build(monitor_levels=levels)

    def render(b: dict[str, Any]) -> None:
        print("=" * 78)
        print(" GeoKG 建图")
        print("=" * 78)
        print()
        print(f"  实体: {b['entities']:,}   关系: {b['relations']:,}   "
              f"耗时: {b['seconds']}s")
        print(f"  监测层级: {b['monitor_levels'] or '（无）'}")
        p = b["provenance"]
        print(f"  溯源: {p['verified']:,}/{p['total']:,} ({p['ratio']:.1%})")
        print()
        print("  按类型:")
        for t, n in sorted(b["by_type"].items(), key=lambda kv: -kv[1]):
            print(f"    {t:<22}{n:>9,}")
        print()

    return _emit(args, {"ok": True, **b}, render)


def cmd_version(args: argparse.Namespace) -> int:
    mf = admin.manifest()

    def render(m: dict[str, Any]) -> None:
        print(f"geokg {DATASET_VERSION}")
        print(f"  数据集指纹: {m['fingerprint']}")
        rows = sum(d["rows"] for d in m["files"].values())
        print(f"  数据文件  : {len(m['files'])} 个 / {rows:,} 行")
        # 用磁盘清单的时间，而不是 m['generated_at']（那永远是"刚刚"）
        print(f"  清单生成于: {m['stored_generated_at'] or '（尚无清单文件）'}")

    return _emit(args, mf, render)


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="geokg",
        description="GeoKG 管理工具：状态 / 校验 / 许可 / 口径 / 刷新 / 建图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--json", action="store_true", help="输出 JSON（供脚本/CI/Web 消费）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="整体状态与陈旧度告警")
    p.add_argument("--strict", action="store_true",
                   help="有陈旧/缺失数据时以非零码退出（供定时 CI 用）")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("verify", help="数据完整性 + 溯源门禁")
    p.add_argument("--drift", action="store_true",
                   help="额外检测上游漂移（联网，较慢）")
    p.set_defaults(func=cmd_verify)

    sub.add_parser("licenses", help="许可与署名汇总").set_defaults(func=cmd_licenses)

    p = sub.add_parser("counts", help="计数口径与溯源审计")
    p.add_argument("--admin1", action="store_true", help="含次国家级监测任务空间")
    p.add_argument("--no-monitoring", action="store_true", help="不含监测任务空间")
    p.set_defaults(func=cmd_counts)

    p = sub.add_parser("manifest", help="查看/重算数据清单")
    p.add_argument("--write", action="store_true", help="写回 data/manifest.json")
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("refresh", help="重新生成数据（联网）")
    p.add_argument("dataset", nargs="?", help="数据集 id")
    p.add_argument("--all", action="store_true", help="刷新全部")
    p.add_argument("--timeout", type=int, default=1800, help="单个数据集超时（秒）")
    p.set_defaults(func=cmd_refresh)

    p = sub.add_parser("build", help="构建知识图谱并报告统计")
    p.add_argument("--admin1", action="store_true", help="含次国家级监测任务空间")
    p.set_defaults(func=cmd_build)

    sub.add_parser("version", help="数据集版本与指纹").set_defaults(func=cmd_version)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
