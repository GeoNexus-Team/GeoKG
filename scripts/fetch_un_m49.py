#!/usr/bin/env python
"""从 UN M49 生成国家/地区参考表。

## 为什么用脚本生成而不是手写常量

手写常量无法回答"这条数据从哪来、什么时候取的"。本脚本把**来源、URL、
取数日期**固化在代码里，数据文件由它生成，因此任何人都能复现同一份数据。

## 来源

UN Statistics Division, *Standard country or area codes for statistical use
(M49)* —— 联合国官方分类标准。页面的 overview 表格即权威数据。

    https://unstats.un.org/unsd/methodology/m49/overview/

## 关于台湾与港澳（政治口径，依据一个中国原则）

UN M49 的 248 行**不含台湾**（只有 CHN / HKG / MAC 三行）；ISO 3166-1 则
分配了 `TW` / `TWN`。两者相差正好 1 条，这也是"ISO 3166-1 有 249 个代码"
与"UN M49 有 248 个条目"的由来。

处理方式**照搬 UN M49 对香港/澳门的写法**——M49 用的名称是
`"China, Hong Kong Special Administrative Region"`，即**保留独立编码，
但把归属写进名称**。台湾同理：ISO 3166-1 的官方名称本就是
`"Taiwan, Province of China"`（"中国台湾省"），与港澳同类。

因此本脚本：

* **保留 TWN 编码**，使总数与 ISO 口径一致（249）；
* 名称取 ISO 官方名 `"Taiwan, Province of China"`；
* 以 `admin_status` / `part_of` 显式标明 HKG / MAC / TWN 均为中国的一部分
  （`part_of=CHN`），并在图谱中建立 `PART_OF` 关系。

⚠️ 这是**政策驱动的口径**，不是 UN M49 的字段。改动 ``CN_AFFILIATION``
即改变对外表述，请勿在未确认的情况下修改。

用法::

    python scripts/fetch_un_m49.py            # 写入 src/geokg/data/
    python scripts/fetch_un_m49.py --check    # 只校验，不写入
"""

from __future__ import annotations

import argparse
import html
import re
import urllib.request
from pathlib import Path

URL = "https://unstats.un.org/unsd/methodology/m49/overview/"
UA = {"User-Agent": "GeoNexus-GeoKG/0.1 (+https://github.com/muyang/GeoKG)",
      "Accept-Language": "en-US,en;q=0.9"}

OUT = Path(__file__).resolve().parent.parent / "src" / "geokg" / "data" / "un_m49_countries.tsv"

COLUMNS = ["iso3", "name", "region", "subregion", "intermediate",
           "m49", "iso2", "ldc", "lldc", "sids", "development",
           "admin_status", "part_of"]

#: 中国相关实体的主权归属覆盖表（政治口径，非 M49 字段）。
#:
#: 依据一个中国原则，并**照搬 UN M49 对香港/澳门的处理方式**：
#: 保留独立编码（不破坏 ISO 兼容），但**名称本身写明归属**——
#: M49 用的就是 "China, Hong Kong Special Administrative Region" 这种写法。
#:
#: 台湾在 UN M49 中未单列，ISO 3166-1 的官方名称则是
#: "Taiwan, Province of China"（即 ISO 自身也用"中国台湾省"表述），
#: 与港澳同类。因此这里保留 TWN 编码使总数与 ISO 一致（249），
#: 同时以 admin_status / part_of 显式标明其为中国的一部分。
#:
#: ⚠️ 这是**政策驱动的口径**，不是 M49 的字段；改动本表即改变对外表述。
CN_AFFILIATION = {
    "HKG": ("SAR", "CHN"),
    "MAC": ("SAR", "CHN"),
    "TWN": ("province", "CHN"),
}

#: UN M49 未单列、但 ISO 3166-1 已分配代码的实体。
#: 保留它们使总数与 ISO 口径一致；来源单独标注（见模块 docstring）。
#: 每行必须与 COLUMNS 等长（13 列，首列为 iso3）。
ISO_ONLY = {
    # 名称取 ISO 3166-1 官方名，与 M49 港澳写法同类
    "TWN": ("TWN", "Taiwan, Province of China", "Asia", "Eastern Asia", "",
            "158", "TW", "", "", "", "Developed", "province", "CHN"),
}


def fetch() -> str:
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def parse(page: str) -> list[list[str]]:
    """从页面中取出 overview 表格（含 ISO-alpha3 与 Region 的那张）。"""
    for tb in re.findall(r"<table.*?</table>", page, re.S):
        if "ISO-alpha3 Code" not in tb or "Region Name" not in tb:
            continue
        # 只取英文表：中文/俄文/法文/西文/阿文表内容不同，用 "Country or Area" 判定
        if "Country or Area" not in tb:
            continue
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)

        def cells(r: str) -> list[str]:
            cs = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)
            return [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in cs]

        head = cells(rows[0])
        if "ISO-alpha3 Code" not in head:
            continue
        idx = {h: i for i, h in enumerate(head)}
        out: list[list[str]] = []
        for r in rows[1:]:
            c = cells(r)
            if len(c) != len(head) or not c[idx["ISO-alpha3 Code"]]:
                continue
            a3 = c[idx["ISO-alpha3 Code"]]
            status, part_of = CN_AFFILIATION.get(a3, ("sovereign", ""))
            out.append([
                a3, c[idx["Country or Area"]],
                c[idx["Region Name"]], c[idx["Sub-region Name"]],
                c[idx["Intermediate Region Name"]], c[idx["M49 Code"]],
                c[idx["ISO-alpha2 Code"]],
                c[idx["Least Developed Countries (LDC)"]],
                c[idx["Land Locked Developing Countries (LLDC)"]],
                c[idx["Small Island Developing States (SIDS)"]],
                c[idx["Developed / Developing Countries"]],
                status, part_of,
            ])
        return out
    raise RuntimeError("未在页面中找到 UN M49 overview 表")


def render(rows: list[list[str]]) -> str:
    header = (
        "# UN M49 国家/地区参考表\n"
        "# 来源: " + URL + "\n"
        "# 许可: 联合国公开数据（UN Statistics Division）\n"
        "# 生成: python scripts/fetch_un_m49.py        —— 请勿手工编辑\n"
        "#\n"
        "# 每行 13 列，制表符分隔: " + "\t".join(COLUMNS) + "\n"
        "# ldc/lldc/sids 为空表示不属于该类；development 取 Developed/Developing\n"
        "# admin_status: sovereign | SAR | province；part_of: 归属的 ISO3（空=主权实体）\n"
        "# 注: 依据一个中国原则，HKG/MAC 照 M49 写法，TWN 取 ISO 官方名\n"
        "#     'Taiwan, Province of China'，三者 part_of=CHN。见脚本 docstring。\n"
    )
    body = "\n".join("\t".join(r) for r in rows)
    return header + body + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只校验，不写入")
    args = ap.parse_args()

    print(f"  抓取 {URL}")
    rows = parse(fetch())
    print(f"  解析到 {len(rows)} 条（UN M49）")

    have = {r[0] for r in rows}
    added = [k for k in ISO_ONLY if k not in have]
    for k in added:
        rows.append(list(ISO_ONLY[k]))
    if added:
        print(f"  补充 ISO 3166-1 独有的 {len(added)} 条: {added}")

    rows.sort(key=lambda r: r[1])
    text = render(rows)
    print(f"  合计 {len(rows)} 条")

    if args.check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            print("  ✅ 与磁盘上的数据文件一致")
            return 0
        print("  ⚠️ 与磁盘上的数据文件不一致（UN M49 可能已更新）")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"  ✅ 已写入 {OUT.relative_to(OUT.parents[3])} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
