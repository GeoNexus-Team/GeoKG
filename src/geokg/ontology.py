"""L3 地球系统本体 —— 土地覆盖 / 气候 / 灾害。

## 这一层解决什么

GeoKG 的回答能力此前停在"**叫什么、在哪**"（行政区划、地名）。本层补上
"**这是什么**"：

| 层 | 内容 | 回答 |
|----|------|------|
| 已有 | 国家、行政区划 | 在哪 |
| 已有 | 卫星、波段 | 用什么观测 |
| **L3** | 土地覆盖 / 气候 / 灾害 | **这是什么地物或现象** |

## 三个来源（均为可引用文献，非自行整理）

| 领域 | 来源 | 分级 | 条目 |
|------|------|------|-----:|
| 土地覆盖 | ESA WorldCover（FAO LCCS 方案） | T2 官方机构 | 11 |
| 气候 | Köppen-Geiger（Beck et al. 2018, *Sci Data*） | T3 同行评议 | 35 |
| 灾害 | IRDR Peril Classification (2014) | T3 技术报告 | 73 |

## 关于"转录"

这三个分类只以论文/技术报告形式发布，**没有官方机器可读清单**，
因此数据是**转录**而非下载——见 ``scripts/build_l3_ontology.py``。
校验方式是把它与引用文献逐条比对，而不是比对文件哈希。

## 关于灾害层级的如实处理

IRDR 明确指出 peril 与 main event **不是一对一关系**，因此本模块
**不为 peril 指定 main event 父级**。family → main_event 的层级有文献支持，
照实建立；peril 保持为独立层，避免编造关系。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

LANDCOVER_FILE = DATA_DIR / "worldcover_landcover.tsv"
CLIMATE_FILE = DATA_DIR / "koppen_geiger_climate.tsv"
HAZARD_FILE = DATA_DIR / "irdr_hazards.tsv"

#: ESA WorldCover 署名要求（CC BY 4.0）
LANDCOVER_ATTRIBUTION = (
    "© ESA WorldCover project / Contains modified Copernicus Sentinel data "
    "(2020/2021) processed by ESA WorldCover consortium"
)


@dataclass(frozen=True)
class OntologyTerm:
    """一条本体条目。``level`` 与 ``parent`` 用于建立层级关系。"""

    source_id: str
    level: str
    code: str
    name: str
    parent: str
    description: str


def load_terms(path: str | Path) -> list[OntologyTerm]:
    """加载本体数据文件（制表符分隔，6 列，``#`` 行为注释）。"""
    src = Path(path)
    out: list[OntologyTerm] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if f[0] == "source_id":  # 表头行
            continue
        if len(f) != 6:
            raise ValueError(f"{src.name}: 期望 6 列，实际 {len(f)} 列 -> {line[:60]!r}")
        out.append(OntologyTerm(f[0], f[1], f[2], f[3], f[4], f[5]))
    if not out:
        raise ValueError(f"{src} 未加载到任何条目")
    return out


LANDCOVER_TERMS: list[OntologyTerm] = load_terms(LANDCOVER_FILE)
CLIMATE_TERMS: list[OntologyTerm] = load_terms(CLIMATE_FILE)
HAZARD_TERMS: list[OntologyTerm] = load_terms(HAZARD_FILE)

ALL_TERMS: list[OntologyTerm] = LANDCOVER_TERMS + CLIMATE_TERMS + HAZARD_TERMS


def ontology_stats() -> dict[str, int]:
    return {
        "landcover_classes": sum(1 for t in LANDCOVER_TERMS if t.level == "class"),
        "climate_groups": sum(1 for t in CLIMATE_TERMS if t.level == "group"),
        "climate_classes": sum(1 for t in CLIMATE_TERMS if t.level == "class"),
        "hazard_families": sum(1 for t in HAZARD_TERMS if t.level == "family"),
        "hazard_main_events": sum(1 for t in HAZARD_TERMS if t.level == "main_event"),
        "hazard_perils": sum(1 for t in HAZARD_TERMS if t.level == "peril"),
        "total": len(ALL_TERMS),
    }
