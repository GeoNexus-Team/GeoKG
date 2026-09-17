#!/usr/bin/env python
"""从 GeoNames 生成一级行政区（admin1）参考表。

## 为什么换源

原 ``reference_data.ADMIN1_REGIONS`` 自述来自 GADM，而 GADM 许可禁止再分发
（提交公开仓库即构成再分发），已移出仓库；``gazetteer.ADMIN1_EXTENDED`` 与
``admin1_global.ADMIN1_GLOBAL`` 则**没有任何出处**。两者合计 2,763 条实体的
来源都不可审计（见 docs/provenance-audit.md）。

本脚本改用 GeoNames：许可 **CC BY 4.0**（可商用、无 share-alike），
且能给出稳定的数字编码与 geonameid，可复现。

## 来源

    https://download.geonames.org/export/dump/admin1CodesASCII.txt
    https://download.geonames.org/export/dump/countryInfo.txt

格式（制表符分隔）::

    KE.01    Nairobi    Nairobi    184742

## 注意：curl 抓不到这个站点

本机 curl 与该站的 TLS 协商失败::

    error:06FFF089:digital envelope routines:CRYPTO_internal:bad key length

这是旧 TLS 栈的兼容问题，**不是网络不可达**。本脚本用 Python urllib，
可以正常下载。若换用 curl 会误判为"站点挂了"。

## 实体 id 用 geonameid，不用名称

名称在同一国内可能重复（admin2 实测有 6% 重名），用名称生成 id 会静默丢数据。
geonameid 由 GeoNames 保证唯一。

用法::

    python scripts/fetch_geonames_admin1.py [--check]
"""

from __future__ import annotations

import argparse
import ssl
import urllib.request
from pathlib import Path

BASE = "https://download.geonames.org/export/dump/"
UA = {"User-Agent": "GeoNexus-GeoKG/0.1 (+https://github.com/muyang/GeoKG)"}

OUT = Path(__file__).resolve().parent.parent / "src" / "geokg" / "data" / "geonames_admin1.tsv"

COLUMNS = ["iso3", "geonames_code", "name", "asciiname", "geonameid"]


def _ctx() -> ssl.SSLContext:
    """部分环境（含本机）需要放宽校验才能与 download.geonames.org 握手。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(name: str) -> str:
    req = urllib.request.Request(BASE + name, headers=UA)
    with urllib.request.urlopen(req, timeout=90, context=_ctx()) as r:
        return r.read().decode("utf-8", "replace")


def iso2_to_iso3(country_info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in country_info.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) > 1 and f[0] and f[1]:
            out[f[0]] = f[1]
    return out


def parse_admin1(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        f = line.split("\t")
        if len(f) < 4:
            continue
        code = f[0].strip()
        if "." not in code:
            continue
        iso2 = code.split(".")[0]
        rows.append([iso2, code, f[1].strip(), f[2].strip(), f[3].strip()])
    return rows


def render(rows: list[list[str]], *, skipped: dict[str, int]) -> str:
    header = (
        "# GeoNames 一级行政区（admin1）参考表\n"
        f"# 来源: {BASE}admin1CodesASCII.txt（配合 countryInfo.txt 做 ISO2→ISO3 映射）\n"
        "# 许可: Creative Commons Attribution 4.0 (CC BY 4.0)\n"
        "# 署名: GeoNames, https://www.geonames.org/\n"
        "# 生成: python scripts/fetch_geonames_admin1.py    —— 请勿手工编辑\n"
        "#\n"
        "# 每行 5 列，制表符分隔: " + "\t".join(COLUMNS) + "\n"
        "# geonames_code 形如 KE.01；geonameid 全局唯一，实体 id 以它为准\n"
    )
    if skipped:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(skipped.items()))
        header += f"# 未匹配到 UN M49 国家表而跳过的 ISO2: {detail}\n"
    body = "\n".join("\t".join(r) for r in rows)
    return header + body + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    print(f"  抓取 {BASE}countryInfo.txt")
    mapping = iso2_to_iso3(fetch("countryInfo.txt"))
    print(f"  抓取 {BASE}admin1CodesASCII.txt")
    raw = parse_admin1(fetch("admin1CodesASCII.txt"))
    print(f"  解析到 {len(raw)} 条 admin1")

    # 只保留能映射到 UN M49 国家表的条目
    m49_iso3 = _known_iso3()
    rows: list[list[str]] = []
    skipped: dict[str, int] = {}
    for iso2, code, name, ascii_name, gid in raw:
        iso3 = mapping.get(iso2)
        if not iso3 or iso3 not in m49_iso3:
            skipped[iso2] = skipped.get(iso2, 0) + 1
            continue
        rows.append([iso3, code, name, ascii_name, gid])
    rows.sort(key=lambda r: (r[0], r[2]))
    print(f"  保留 {len(rows)} 条；跳过 {sum(skipped.values())} 条"
          f"（{len(skipped)} 个 ISO2 不在国家表中）")

    text = render(rows, skipped=skipped)
    if args.check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            print("  ✅ 与磁盘上的数据文件一致")
            return 0
        print("  ⚠️ 与磁盘上的数据文件不一致（GeoNames 可能已更新）")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"  ✅ 已写入 {OUT.name} ({OUT.stat().st_size:,} bytes)")
    return 0


def _known_iso3() -> set[str]:
    """读入当前 UN M49 国家表，用于过滤。"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from geokg.reference_data import COUNTRIES_FULL

    return {c.iso3 for c in COUNTRIES_FULL}


if __name__ == "__main__":
    raise SystemExit(main())
