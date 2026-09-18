"""GeoKG 数据源登记表 —— 管理面的**唯一真相**。

## 为什么需要它

在此之前，"GeoKG 依赖哪些上游"这件事分散在**三处**，彼此可能不一致：

1. 8 个生成脚本里各自的 ``API`` / ``BASE`` / ``URL`` 常量；
2. ``provenance.SOURCES`` 里的许可 / 分级 / 取数日期；
3. 各脚本的 ``OUT`` 常量与 ``pyproject.toml`` 的打包配置。

本模块把它们合并成一处声明式登记表。CLI、数据清单、许可汇总、CI 门禁
**全部从这里读**，因此新增一个数据源只需在这里加一条。

## 分层（管理面设计）

::

    sources.py      数据：来源、上游、许可、陈旧度策略   ← 本模块
        ↓
    admin.py        逻辑：返回纯 dict 的库 API（可 JSON 序列化）
        ↓
    cli.py          表现：人类可读输出
        ↓
    （未来）HTTP    表现：平台 Web 复用 admin.py 的同一批 dict

**关键约束**：``admin.py`` 只返回可 JSON 序列化的数据结构，不做打印、不写文件。
因此未来的 Web 管理面可以零改动地复用同一批函数——这正是"CLI 先行、Web 复用"
的实现方式。

## 陈旧度策略

各上游更新频率差异极大：GeoNames 每日更新，WorldCover / Köppen / IRDR 是静态
数据集。因此按源设阈值，``None`` 表示**永不陈旧**：

* 联网抓取型（GeoNames 30 天 / OSCAR 90 天）——需要定期刷新；
* 静态发布型（WorldCover / Köppen / IRDR）——发布即定格，不存在"过期"；
* 标准/框架型（UN M49 180 天 / SDG 365 天）——变更缓慢，容忍度高。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: 数据文件所在目录
DATA_DIR = Path(__file__).resolve().parent / "data"

#: 生成脚本所在目录（相对包根：src/geokg → ../../scripts）
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"

#: 数据集版本（人工递增，用于论文/方案中精确引用"用的是哪一版"）
#: 命名规则 YYYY.MM[.patch]；实际内容指纹由 manifest 的 sha256 给出。
DATASET_VERSION = "2026.09.1"


@dataclass(frozen=True)
class Dataset:
    """一个由脚本生成的数据文件，及其全部溯源元信息。"""

    id: str
    file: str
    generator: str
    upstream: str
    license: str
    attribution: str
    tier: str
    #: True = 生成需要联网；False = 离线可复现
    requires_network: bool
    #: 超过多少天算陈旧；None = 静态源，永不陈旧
    staleness_days: int | None
    #: 本文件在 provenance.SOURCES 中占用的来源 id（可能多个）
    sources: tuple[str, ...]
    #: 该数据文件产出的实体类型（供 status 展示）
    produces: tuple[str, ...] = field(default=())

    @property
    def path(self) -> Path:
        return DATA_DIR / self.file

    @property
    def generator_path(self) -> Path:
        return SCRIPTS_DIR / self.generator


#: 全部数据源。新增数据源只需在此加一条。
DATASETS: tuple[Dataset, ...] = (
    Dataset(
        id="un-m49",
        file="un_m49_countries.tsv",
        generator="fetch_un_m49.py",
        upstream="https://unstats.un.org/unsd/methodology/m49/overview/",
        license="联合国公开数据",
        attribution="UN Statistics Division, Standard country or area codes (M49)",
        tier="T1",
        requires_network=True,
        staleness_days=180,
        sources=("un-m49", "iso-3166-1"),
        produces=("Country", "Region"),
    ),
    Dataset(
        id="un-sdg-framework",
        file="un_sdg_framework.tsv",
        generator="fetch_un_sdg.py",
        upstream="https://unstats.un.org/SDGAPI/v1/sdg",
        license="联合国公开文件（A/RES/71/313 及后续综合审议）",
        attribution="United Nations Statistics Division, SDG indicator framework",
        tier="T1",
        requires_network=True,
        staleness_days=365,
        sources=("un-sdg-framework",),
        produces=("SDG_Goal", "SDG_Target", "SDG_Indicator"),
    ),
    Dataset(
        id="geonames-admin1",
        file="geonames_admin1.tsv",
        generator="fetch_geonames_admin1.py",
        upstream="https://download.geonames.org/export/dump/",
        license="Creative Commons Attribution 4.0 (CC BY 4.0)",
        attribution="GeoNames, https://www.geonames.org/",
        tier="T4",
        requires_network=True,
        staleness_days=30,  # GeoNames 每日更新
        sources=("geonames-admin1",),
        produces=("AdminRegion",),
    ),
    Dataset(
        id="wmo-oscar-satellites",
        file="oscar_satellites.tsv",
        generator="fetch_oscar_satellites.py",
        upstream="https://space.oscar.wmo.int/api/v1/satellites",
        license="可自由使用与再分发，须致谢 WMO；WMO 不对准确性作担保",
        attribution="WMO OSCAR/Space, https://space.oscar.wmo.int/",
        tier="T2",
        requires_network=True,
        staleness_days=90,
        sources=("wmo-oscar-satellites",),
        produces=("Satellite", "Organization"),
    ),
    Dataset(
        id="wmo-oscar-instruments",
        file="oscar_instruments.tsv",
        generator="fetch_oscar_instruments.py",
        upstream="https://space.oscar.wmo.int/api/v1/instruments",
        license="可自由使用与再分发，须致谢 WMO；WMO 不对准确性作担保",
        attribution="WMO OSCAR/Space, https://space.oscar.wmo.int/",
        tier="T2",
        requires_network=True,
        staleness_days=90,
        sources=("wmo-oscar-instruments",),
        produces=("Instrument",),
    ),
    Dataset(
        id="esa-worldcover",
        file="worldcover_landcover.tsv",
        generator="build_l3_ontology.py",
        upstream="https://docs.planet.com/data/public-data/other-datasets/esa-worldcover/",
        license="Creative Commons Attribution 4.0 (CC BY 4.0)",
        attribution="© ESA WorldCover project / Contains modified Copernicus Sentinel "
                    "data (2020/2021) processed by ESA WorldCover consortium",
        tier="T2",
        requires_network=False,  # 转录，离线可复现
        staleness_days=None,    # 静态产品（2020/2021）
        sources=("esa-worldcover",),
        produces=("LandCoverClass",),
    ),
    Dataset(
        id="koppen-geiger",
        file="koppen_geiger_climate.tsv",
        generator="build_l3_ontology.py",
        upstream="https://doi.org/10.1038/sdata.2018.214",
        license="Creative Commons Attribution 4.0 (CC BY 4.0)",
        attribution="Beck, H. et al. (2018) Scientific Data 5:180214",
        tier="T3",
        requires_network=False,
        staleness_days=None,  # 已发表分类，不随时间变化
        sources=("koppen-geiger-beck2018",),
        produces=("ClimateClass",),
    ),
    Dataset(
        id="irdr-hazards",
        file="irdr_hazards.tsv",
        generator="build_l3_ontology.py",
        upstream="https://www.irdrinternational.org/pdf/uploads/files/sc11/"
                 "IRDR_DATA-Project-Report-No.-1.pdf",
        license="IRDR 公开技术报告（引用 IRDR DATA Publication No. 1）",
        attribution="IRDR (2014) Peril Classification and Hazard Glossary",
        tier="T3",
        requires_network=False,
        staleness_days=None,  # 2014 年技术报告，静态
        sources=("irdr-peril-classification-2014",),
        produces=("HazardType",),
    ),
    Dataset(
        id="vocabulary",
        file="vocabulary.tsv",
        generator="build_vocabulary.py",
        upstream="（逐类标注：IOGP EPSG / ISO·OGC / 联合国 / 本仓库自编）",
        license="混合：EOF 见下（含 Apache-2.0 自编内容）",
        attribution="geokg-authored（Apache-2.0）+ IOGP EPSG + ISO/OGC + UN",
        tier="混合",
        requires_network=False,
        staleness_days=None,
        sources=("iogp-epsg", "iso-ogc-standards", "un-frameworks", "geokg-authored"),
        produces=("Concept", "ConceptCategory"),
    ),
)

#: 按 id 索引
BY_ID: dict[str, Dataset] = {d.id: d for d in DATASETS}

#: 全部来源 id（含 vocabulary 的多个来源）
SOURCE_IDS: tuple[str, ...] = tuple(s for d in DATASETS for s in d.sources)


def get(dataset_id: str) -> Dataset:
    """按 id 取数据集；不存在则抛 KeyError 并给出可用列表。"""
    try:
        return BY_ID[dataset_id]
    except KeyError:
        raise KeyError(
            f"未知数据集 {dataset_id!r}；可用: {', '.join(BY_ID)}"
        ) from None


def files() -> tuple[str, ...]:
    """全部数据文件名。"""
    return tuple(d.file for d in DATASETS)
