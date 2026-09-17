"""GeoKG 术语表 —— 逐类标注来源。

## 为什么不是"来源未核实"

审计发现原 ``CONCEPTS`` + ``EXTENDED_CONCEPTS``（371 条）没有任何来源标注。
但把它们一概说成"缺来源"并不准确——它们性质分三种，混在一起才是问题：

1. **外部数据集**：仪器名、EPSG 代码、标准编号——必须引用外部来源；
2. **本仓库自编术语表**：如"缓冲区分析""坐标参考系"——来源**就是我们**，
   ``geokg-authored`` 才是准确描述；
3. **已被其他层取代**：灾害术语（IRDR 已覆盖）、仪器名（OSCAR 已覆盖）——删除。

因此数据文件里**每条术语都带 ``source_id``**：

| source_id | 类别 | 分级 |
|-----------|------|------|
| ``iogp-epsg`` | CoordinateSystems | T1（EPSG 代码属 IOGP） |
| ``iso-ogc-standards`` | Standards | T1（标准编号属 ISO / OGC） |
| ``un-frameworks`` | PolicyFrameworks / SDGFramework | T2（联合国文件） |
| ``geokg-authored`` | 其余 9 类 | **本仓库自编术语表**（Apache-2.0） |

⚠️ ``geokg-authored`` 是**如实分类**，不是免除引用义务：凡是取自外部数据集
的内容都不在此列（仪器与灾害术语已分别改由 OSCAR 与 IRDR 提供）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
VOCABULARY_FILE = DATA_DIR / "vocabulary.tsv"

#: 本仓库自编术语表的来源 id
AUTHORED = "geokg-authored"


@dataclass(frozen=True)
class Term:
    """一条术语。"""

    source_id: str
    category: str
    term: str

    @property
    def entity_id(self) -> str:
        def _slug(t: str) -> str:
            return (t.lower().replace(" ", "-").replace(",", "").replace("/", "-")
                    .replace(":", "").replace(".", "").replace("(", "").replace(")", "")
                    .replace("+", "p").replace("_", "-"))
        return f"concept.{_slug(self.category)}.{_slug(self.term)}"


def load_vocabulary(path: str | Path | None = None) -> list[Term]:
    """加载术语表（制表符分隔，3 列，``#`` 行为注释）。"""
    src = Path(path) if path else VOCABULARY_FILE
    out: list[Term] = []
    seen: set[str] = set()
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 3:
            raise ValueError(f"{src.name}: 期望 3 列，实际 {len(f)} 列 -> {line[:60]!r}")
        t = Term(f[0], f[1], f[2])
        if t.entity_id in seen:
            raise ValueError(f"{src.name}: 实体 id 冲突 {t.entity_id!r}")
        seen.add(t.entity_id)
        out.append(t)
    if not out:
        raise ValueError(f"{src} 未加载到任何术语")
    return out


#: 全部术语
TERMS: list[Term] = load_vocabulary()

#: 本仓库自编部分
AUTHORED_TERMS: list[Term] = [t for t in TERMS if t.source_id == AUTHORED]

#: 有外部来源的部分
EXTERNAL_TERMS: list[Term] = [t for t in TERMS if t.source_id != AUTHORED]


def vocabulary_stats() -> dict[str, int]:
    by_source: dict[str, int] = {}
    for t in TERMS:
        by_source[t.source_id] = by_source.get(t.source_id, 0) + 1
    return {
        "terms_total": len(TERMS),
        "terms_authored": len(AUTHORED_TERMS),
        "terms_external": len(EXTERNAL_TERMS),
        "categories": len({t.category for t in TERMS}),
        **{f"src_{k}": v for k, v in sorted(by_source.items())},
    }
