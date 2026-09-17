#!/usr/bin/env python
"""输出 GeoKG 的计数口径报告 —— 用于考核材料中"实体数"的可复现引用。

每个口径都在**同一份数据**上算出，因此报告里的任何数字都能被独立复现：

    python scripts/counting_basis.py            # 默认：含国家级监测
    python scripts/counting_basis.py --admin1   # 含次国家级监测任务空间
    python scripts/counting_basis.py --no-monitoring

退出码：0 正常；1 存在未标记来源的实体（说明计数不可信）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from geonexus.kg import KnowledgeGraph  # noqa: E402

from geokg.ingest import run_full_ingestion  # noqa: E402
from geokg.provenance import counting_basis, format_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--admin1", action="store_true",
                   help="含次国家级（一级行政区）监测任务空间")
    g.add_argument("--no-monitoring", action="store_true",
                   help="不计监测任务空间，只看策展 + 展开")
    args = ap.parse_args()

    if args.no_monitoring:
        levels: list[str] = []
        title = "GeoKG 计数口径报告（不含监测任务空间）"
    elif args.admin1:
        levels = ["country", "admin1"]
        title = "GeoKG 计数口径报告（含次国家级监测任务空间）"
    else:
        levels = ["country"]
        title = "GeoKG 计数口径报告（含国家级监测任务空间）"

    kg = KnowledgeGraph("geokg")
    run_full_ingestion(
        kg,
        monitor_levels=levels,
        include_monitoring=not args.no_monitoring,
    )

    basis = counting_basis(kg)
    print(format_report(basis, title=title))

    if basis["unclassified"]:
        print(f"  ❌ {len(basis['unclassified'])} 个实体缺少来源标记，计数不可信")
        return 1
    print("  ✅ 全部实体均已标记来源，口径可从数据复现")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
