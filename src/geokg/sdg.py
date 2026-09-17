"""联合国可持续发展目标框架 —— 官方 API 来源。

## 为什么换源

原先 SDG 框架是**手写常量**，只有每目标的具体目标数与指标数，没有说明、
没有层级（tier），且核对后发现两处问题：

1. 文档声称"231 个唯一指标"——那是 2017 年 A/RES/71/313 原始框架的数字，
   此后经多轮综合审议已扩充。官方 API 现返回 **251** 个。
2. 手写表**少了 7 个指标**（Goal 2 / 7 / 10 / 11 / 16 各有缺口）。

## 换成了什么

联合国统计司（UNSD）官方 SDG API（**T1 规范源**）：
``https://unstats.un.org/SDGAPI/v1/sdg/{Goal,Target,Indicator}/List``

实测 17 目标 / 169 具体目标 / 251 指标，含 ``title`` / ``description`` /
``tier``。不但修正了数字，还补上了**指标说明与层级分类**——
SDG 监测真正要用的字段。

数据由 ``scripts/fetch_un_sdg.py`` 生成（支持 ``--raw-dir`` 用本地缓存的
原始响应离线构建）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SDG_DATA_FILE = DATA_DIR / "un_sdg_framework.tsv"

GOAL = "goal"
TARGET = "target"
INDICATOR = "indicator"


@dataclass(frozen=True)
class SdgEntry:
    """一条 SDG 框架条目（目标 / 具体目标 / 指标）。"""

    level: str
    code: str
    parent: str
    title: str
    description: str
    tier: str
    uri: str

    @property
    def entity_id(self) -> str:
        if self.level == GOAL:
            return f"sdg.goal.{self.code}"
        if self.level == TARGET:
            return f"sdg.target.{self.code}"
        return f"sdg.indicator.{self.code}"


def load_sdg(path: str | Path | None = None) -> list[SdgEntry]:
    """加载 SDG 框架表（制表符分隔，7 列，``#`` 行为注释）。"""
    src = Path(path) if path else SDG_DATA_FILE
    out: list[SdgEntry] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 7:
            raise ValueError(f"{src.name}: 期望 7 列，实际 {len(f)} 列 -> {line[:60]!r}")
        if f[0] not in (GOAL, TARGET, INDICATOR):
            raise ValueError(f"{src.name}: 未知层级 {f[0]!r}")
        out.append(SdgEntry(*f))
    if not out:
        raise ValueError(f"{src} 未加载到任何条目")
    return out


#: 全部 SDG 框架条目
SDG_ENTRIES: list[SdgEntry] = load_sdg()

SDG_GOALS_LIST: list[SdgEntry] = [e for e in SDG_ENTRIES if e.level == GOAL]
SDG_TARGETS_LIST: list[SdgEntry] = [e for e in SDG_ENTRIES if e.level == TARGET]
SDG_INDICATORS_LIST: list[SdgEntry] = [e for e in SDG_ENTRIES if e.level == INDICATOR]


def sdg_stats() -> dict[str, int]:
    t1 = sum(1 for e in SDG_INDICATORS_LIST if e.tier == "1")
    t2 = sum(1 for e in SDG_INDICATORS_LIST if e.tier == "2")
    return {
        "goals": len(SDG_GOALS_LIST),
        "targets": len(SDG_TARGETS_LIST),
        "indicators": len(SDG_INDICATORS_LIST),
        "indicators_tier1": t1,
        "indicators_tier2": t2,
    }
