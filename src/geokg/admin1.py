"""一级行政区（admin1）—— GeoNames 来源。

## 为什么单独一个模块

这里的数据来自**外部第三方**（GeoNames，CC BY 4.0），与 ``reference_data``
中由联合国标准生成的国家表性质不同：前者需要署名、需要标注取数日期，
且将来可能换源。单独成模块能让"这一层的来源"一目了然。

数据由 ``scripts/fetch_geonames_admin1.py`` 生成到
``data/geonames_admin1.tsv``，**不要手工编辑**。

## 来源与被替换掉的东西

先前的一级行政区来自两处，来源都不可审计，已全部移除：

* ``reference_data.ADMIN1_REGIONS``（775 条）—— 自述来自 **GADM**，而 GADM
  许可禁止再分发，已隔离到仓库之外；
* ``gazetteer.ADMIN1_EXTENDED``（1,327 条）+ ``admin1_global.ADMIN1_GLOBAL``
  （1,436 条）—— **没有任何出处**，已隔离。

本模块用 GeoNames 取代它们：许可干净（可商用、无 share-alike）、
有稳定数字编码与 geonameid、可脚本复现。

## 为什么实体 id 用 geonameid

名称在同一国内可能重复。admin2 层级实测有 6% 重名，若用名称生成 id 会
**静默丢数据**。geonameid 由 GeoNames 保证全局唯一。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
ADMIN1_DATA_FILE = DATA_DIR / "geonames_admin1.tsv"

#: 署名要求（CC BY 4.0）
ATTRIBUTION = "GeoNames, https://www.geonames.org/ (CC BY 4.0)"


@dataclass(frozen=True)
class Admin1Unit:
    """一条 GeoNames 一级行政区记录。"""

    iso3: str
    geonames_code: str  # 形如 KE.01
    name: str
    asciiname: str
    geonameid: str

    @property
    def entity_id(self) -> str:
        """实体 id —— 用 geonameid 而非名称，避免同国重名互相覆盖。"""
        return f"admin1.{self.iso3}.{self.geonameid}"


def load_admin1(path: str | Path | None = None) -> list[Admin1Unit]:
    """加载 GeoNames 一级行政区表（制表符分隔，5 列，``#`` 行为注释）。"""
    src = Path(path) if path else ADMIN1_DATA_FILE
    out: list[Admin1Unit] = []
    seen: set[str] = set()
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 5:
            raise ValueError(f"{src.name}: 期望 5 列，实际 {len(f)} 列 -> {line[:60]!r}")
        if not f[4]:
            raise ValueError(f"{src.name}: geonameid 为空 -> {line[:60]!r}")
        if f[4] in seen:
            raise ValueError(f"{src.name}: geonameid 重复 {f[4]!r} —— id 将冲突")
        seen.add(f[4])
        out.append(Admin1Unit(f[0], f[1], f[2], f[3], f[4]))
    if not out:
        raise ValueError(f"{src} 未加载到任何一级行政区")
    return out


#: 全部一级行政区（GeoNames）
ADMIN1_UNITS: list[Admin1Unit] = load_admin1()


def admin1_stats() -> dict[str, int]:
    return {
        "admin1_units": len(ADMIN1_UNITS),
        "admin1_countries": len({u.iso3 for u in ADMIN1_UNITS}),
    }
