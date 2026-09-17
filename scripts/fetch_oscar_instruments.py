#!/usr/bin/env python
"""从 WMO OSCAR/Space 生成仪器目录。

## 为什么用它

原仪器目录（114 条手写 + 2,863 条星座展开）**没有任何出处**
（见 docs/provenance-audit.md）。OSCAR/Space 是 WMO（世界气象组织，
联合国专门机构）官方维护的对地观测卫星与仪器数据库，属 **T2 官方机构**。

它同时解决了两个问题：来源可追溯，且不必再用"按规则展开星座"凑数量——
真实在轨与规划中的卫星本来就有上千颗。

## 来源与许可

    API:   https://space.oscar.wmo.int/api/v1/instruments  （HAL 分页，30/页）
    文档:  https://space.oscar.wmo.int/apidoc/              （Swagger UI）
    免责:  https://space.oscar.wmo.int/pages/disclaimer

许可原文（引自免责声明页）::

    "All information available on these pages may be used and redistributed
     freely, however, any publication using this information should
     acknowledge WMO."

即**可自由使用与再分发，需致谢 WMO**；同时 WMO 不对数据准确性作任何担保。

署名: ``WMO OSCAR/Space, https://space.oscar.wmo.int/``

用法::

    python scripts/fetch_oscar_instruments.py            # 全量抓取
    python scripts/fetch_oscar_instruments.py --pages 3  # 只抓前 N 页（验证用）
    python scripts/fetch_oscar_instruments.py --check    # 只校验，不写入
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.request
from pathlib import Path

API = "https://space.oscar.wmo.int/api/v1/instruments"
UA = {"User-Agent": "GeoNexus-GeoKG/0.1 (+https://github.com/muyang/GeoKG)"}

OUT = Path(__file__).resolve().parent.parent / "src" / "geokg" / "data" / "oscar_instruments.tsv"

COLUMNS = ["oscar_id", "slug", "acronym", "fullname", "agency",
           "instrument_type", "classification", "wigos_subcomponent",
           "satellite_count", "variables"]

#: 署名要求（OSCAR 免责声明）
ATTRIBUTION = "WMO OSCAR/Space, https://space.oscar.wmo.int/"


def _ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_page(page: int, *, retries: int = 3) -> dict:
    url = f"{API}?page={page}"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60, context=_ctx()
            ) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as exc:  # 网络不稳，重试
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"抓取第 {page} 页失败: {last}")


def _clean(v: object) -> str:
    """制表符/换行会破坏 TSV，统一清洗为空串或去噪字符串。"""
    if v is None:
        return ""
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ").strip()


def collect(max_pages: int | None = None) -> tuple[list[list[str]], int]:
    first = fetch_page(1)
    last_page = int(first["_links"]["last"]["href"].rsplit("page=", 1)[1])
    if max_pages:
        last_page = min(last_page, max_pages)
    print(f"  共 {last_page} 页（每页 30 条）")

    rows: list[list[str]] = []
    seen: set[str] = set()
    for p in range(1, last_page + 1):
        payload = first if p == 1 else fetch_page(p)
        for s in payload.get("_embedded", {}).get("instruments", []):
            oid = _clean(s.get("id"))
            if not oid or oid in seen:
                continue
            seen.add(oid)
            sats = s.get("instrument-satellites") or []
            vars_ = s.get("variables") or []
            cl = s.get("classification")
            if isinstance(cl, list):
                cl = "|".join(str(x) for x in cl)
            if isinstance(vars_, list):
                vars_ = "|".join(str(x.get("name") if isinstance(x, dict) else x)
                                 for x in vars_)
            rows.append([
                oid,
                _clean(s.get("slug")),
                _clean(s.get("acronym")),
                _clean(s.get("fullname")),
                _clean(s.get("providing-agency")),
                _clean(s.get("instrumenttype")),
                _clean(cl),
                _clean(s.get("wigos-subcomponent")),
                str(len(sats) if isinstance(sats, list) else 0),
                _clean(vars_),
            ])
        if p % 5 == 0 or p == last_page:
            print(f"    第 {p}/{last_page} 页，累计 {len(rows)} 条")
    return rows, last_page


def render(rows: list[list[str]], *, pages: int) -> str:
    header = (
        "# WMO OSCAR/Space 对地观测仪器目录\n"
        f"# 来源: {API}（{pages} 页）\n"
        "# 文档: https://space.oscar.wmo.int/apidoc/\n"
        "# 许可: 可自由使用与再分发，须致谢 WMO；WMO 不对准确性作担保\n"
        "# 署名: " + ATTRIBUTION + "\n"
        "# 生成: python scripts/fetch_oscar_instruments.py   —— 请勿手工编辑\n"
        "#\n"
        "# 每行 10 列，制表符分隔: " + "\t".join(COLUMNS) + "\n"
    )
    return header + "\n".join("\t".join(r) for r in rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", type=int, default=None, help="只抓前 N 页（验证用）")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows, pages = collect(args.pages)
    print(f"  合计 {len(rows)} 台仪器")
    text = render(rows, pages=pages)

    if args.check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            print("  ✅ 与磁盘上的数据文件一致")
            return 0
        print("  ⚠️ 与磁盘上的数据文件不一致（OSCAR 可能已更新）")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"  ✅ 已写入 {OUT.name} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
