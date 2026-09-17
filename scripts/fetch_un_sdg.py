#!/usr/bin/env python
"""从 UN SDG 官方 API 生成可持续发展目标框架（目标 / 具体目标 / 指标）。

## 为什么要换源

原先 SDG 框架是**手写常量**：只有每目标的具体目标数与指标数（``SDG_TARGETS``
/ ``SDG_INDICATOR_COUNTS``），没有指标说明、没有层级（tier），
且核对后发现两处问题：

1. **文档声称"231 个唯一指标"是过时数字**。231 是 2017 年 A/RES/71/313
   原始框架的数；此后经多轮综合审议已扩充，官方 API 现返回 **251 个**。
2. **我们的表少了 7 个指标**（Goal 2 / 7 / 10 / 11 / 16 各有缺口）。

## 换成了什么

联合国统计司（UNSD）官方 SDG API —— **T1 规范源**：

    https://unstats.un.org/SDGAPI/v1/sdg/Goal/List
    https://unstats.un.org/SDGAPI/v1/sdg/Target/List
    https://unstats.un.org/SDGAPI/v1/sdg/Indicator/List

实测返回 17 目标 / 169 具体目标 / 251 指标，含 ``title`` / ``description`` /
``tier`` / ``uri``。不但修正了数字，还多出**指标说明与层级分类**——
这是 SDG 监测真正要用的字段。

用法::

    python scripts/fetch_un_sdg.py [--check]
"""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from pathlib import Path

BASE = "https://unstats.un.org/SDGAPI/v1/sdg"
UA = {"User-Agent": "GeoNexus-GeoKG/0.1 (+https://github.com/muyang/GeoKG)"}
OUT = Path(__file__).resolve().parent.parent / "src" / "geokg" / "data" / "un_sdg_framework.tsv"

COLUMNS = ["level", "code", "parent", "title", "description", "tier", "uri"]


def _ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


#: 网络不稳时可用 ``--raw-dir`` 指定本地保存的原始 API 响应目录，
#: 文件名形如 ``sdg_indicators.json``。原始响应即证据，因此这条路径同样可信。
RAW_FILES = {"Goal": "sdg_goals.json", "Target": "sdg_targets.json",
             "Indicator": "sdg_indicators.json"}


def fetch(path: str, raw_dir: Path | None = None) -> list[dict]:
    kind = path.strip("/").split("/")[0]
    if raw_dir is not None:
        f = raw_dir / RAW_FILES[kind]
        return json.loads(f.read_text(encoding="utf-8"))
    url = BASE + path
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=90, context=_ctx()
    ) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _clean(v: object) -> str:
    if v is None:
        return ""
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ").strip()


def build(raw_dir: Path | None = None) -> list[list[str]]:
    goals = fetch("/Goal/List", raw_dir)
    targets = fetch("/Target/List", raw_dir)
    indicators = fetch("/Indicator/List", raw_dir)
    print(f"  API: {len(goals)} 目标 / {len(targets)} 具体目标 / {len(indicators)} 指标")

    rows: list[list[str]] = []
    for g in goals:
        rows.append(["goal", _clean(g["code"]), "", _clean(g.get("title")),
                     _clean(g.get("description")), "", _clean(g.get("uri"))])
    for t in targets:
        rows.append(["target", _clean(t["code"]), _clean(t.get("goal")),
                     _clean(t.get("title")), _clean(t.get("description")),
                     "", _clean(t.get("uri"))])
    for i in indicators:
        rows.append(["indicator", _clean(i["code"]), _clean(i.get("target")),
                     _clean(i.get("description")), _clean(i.get("description")),
                     _clean(i.get("tier")), _clean(i.get("uri"))])
    return rows


def render(rows: list[list[str]]) -> str:
    n_g = sum(1 for r in rows if r[0] == "goal")
    n_t = sum(1 for r in rows if r[0] == "target")
    n_i = sum(1 for r in rows if r[0] == "indicator")
    header = (
        "# 联合国可持续发展目标框架（Goal / Target / Indicator）\n"
        f"# 来源: {BASE}/{{Goal,Target,Indicator}}/List\n"
        "# 许可: 联合国公开文件（引用 A/RES/71/313 及后续综合审议）\n"
        "# 生成: python scripts/fetch_un_sdg.py   —— 请勿手工编辑\n"
        "#\n"
        f"# 实测: {n_g} 目标 / {n_t} 具体目标 / {n_i} 指标\n"
        "#   注: '231 个唯一指标' 是 2017 年原始框架的数字，现已扩充至 "
        f"{n_i}；原手写表少 7 个且文档数字过时。\n"
        "# tier: 指标层级（1 = 概念明确且有成熟方法；2 = 方法/数据待完善）\n"
        "# 每行 7 列，制表符分隔: " + "\t".join(COLUMNS) + "\n"
    )
    return header + "\n".join("\t".join(r) for r in rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--raw-dir", type=Path, default=None,
                    help="从本地缓存的原始 API 响应构建（网络不稳时用）")
    args = ap.parse_args()

    rows = build(args.raw_dir)
    text = render(rows)

    if args.check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            print("  ✅ 与磁盘上的数据文件一致")
            return 0
        print("  ⚠️ 与磁盘上的数据文件不一致（UN 可能已更新框架）")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"  ✅ 已写入 {OUT.name} ({OUT.stat().st_size:,} bytes, {len(rows)} 行)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
