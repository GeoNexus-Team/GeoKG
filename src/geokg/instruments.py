"""对地观测仪器目录 —— WMO OSCAR/Space 来源。

## 为什么换源

原卫星目录由两部分组成，**来源都不可审计**：

* ``reference_data.SATELLITES``（114 条手写记录）—— 无出处、无版本、无日期；
* ``gazetteer.expand_satellite_constellations()``（2,863 条）—— 按规则"展开"
  星座成员，属于**合成数据**而非真实目录。

两者合计 2,977 条实体（见 docs/provenance-audit.md）。

## 换成了什么

**WMO OSCAR/Space** —— 世界气象组织（联合国专门机构）官方维护的对地观测
卫星与仪器数据库，分级 **T2 官方机构**。实测 1,044 颗卫星，且是真实记录
（406 在轨运行 / 381 已退役 / 131 规划中），不需要再用规则"凑数量"。

数据由 ``scripts/fetch_oscar_satellites.py`` 通过官方 REST API 抓取
（``https://space.oscar.wmo.int/api/v1/satellites``，HAL 分页）。

## 许可（引自 OSCAR 免责声明页）

    "All information available on these pages may be used and redistributed
     freely, however, any publication using this information should
     acknowledge WMO."

即可自由使用与再分发，**需致谢 WMO**；WMO 不对数据准确性作担保。
署名随实体写入 ``properties["attribution"]``。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
INSTRUMENT_DATA_FILE = DATA_DIR / "oscar_instruments.tsv"

#: 署名要求（OSCAR 免责声明）
ATTRIBUTION = "WMO OSCAR/Space, https://space.oscar.wmo.int/"


@dataclass(frozen=True)
class Instrument:
    """一条 WMO OSCAR/Space 仪器记录。"""

    oscar_id: str
    slug: str
    acronym: str
    fullname: str
    agency: str
    instrument_type: str
    classification: str
    wigos_subcomponent: str
    satellite_count: int
    variables: str

    @property
    def entity_id(self) -> str:
        """实体 id —— 用 OSCAR 的 slug（由官方 id 派生、稳定且可读）。"""
        return f"instrument.{self.slug}"


def load_instruments(path: str | Path | None = None) -> list[Instrument]:
    """加载 OSCAR 仪器表（制表符分隔，10 列，``#`` 行为注释）。"""
    src = Path(path) if path else INSTRUMENT_DATA_FILE
    out: list[Instrument] = []
    seen: set[str] = set()
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 10:
            raise ValueError(f"{src.name}: 期望 10 列，实际 {len(f)} 列 -> {line[:60]!r}")
        if not f[1]:
            raise ValueError(f"{src.name}: slug 为空 -> {line[:60]!r}")
        if f[1] in seen:
            raise ValueError(f"{src.name}: slug 重复 {f[1]!r} —— 实体 id 将冲突")
        seen.add(f[1])
        try:
            n_sat = int(f[8] or 0)
        except ValueError:
            n_sat = 0
        out.append(Instrument(
            oscar_id=f[0], slug=f[1], acronym=f[2], fullname=f[3],
            agency=f[4], instrument_type=f[5], classification=f[6],
            wigos_subcomponent=f[7], satellite_count=n_sat, variables=f[9],
        ))
    if not out:
        raise ValueError(f"{src} 未加载到任何仪器")
    return out


#: 全部仪器（WMO OSCAR/Space）
INSTRUMENTS: list[Instrument] = load_instruments()


def instrument_stats() -> dict[str, int]:
    return {
        "instruments": len(INSTRUMENTS),
        "agencies": len({i.agency for i in INSTRUMENTS if i.agency}),
        "types": len({i.instrument_type for i in INSTRUMENTS if i.instrument_type}),
        "on_satellites": sum(1 for i in INSTRUMENTS if i.satellite_count > 0),
    }
