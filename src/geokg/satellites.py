"""对地观测卫星目录 —— WMO OSCAR/Space 来源。

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
SATELLITE_DATA_FILE = DATA_DIR / "oscar_satellites.tsv"

#: 署名要求（OSCAR 免责声明）
ATTRIBUTION = "WMO OSCAR/Space, https://space.oscar.wmo.int/"


@dataclass(frozen=True)
class Satellite:
    """一条 WMO OSCAR/Space 卫星记录。"""

    oscar_id: str
    slug: str
    acronym: str
    fullname: str
    space_agency: str
    status: str
    orbit: str
    launch_date: str
    eol: str
    altitude_km: str
    ect: str
    wigos_id: str
    instrument_count: int

    @property
    def entity_id(self) -> str:
        """实体 id —— 用 OSCAR 的 slug（由官方 id 派生、稳定且可读）。"""
        return f"satellite.{self.slug}"


def load_satellites(path: str | Path | None = None) -> list[Satellite]:
    """加载 OSCAR 卫星表（制表符分隔，13 列，``#`` 行为注释）。"""
    src = Path(path) if path else SATELLITE_DATA_FILE
    out: list[Satellite] = []
    seen: set[str] = set()
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 13:
            raise ValueError(f"{src.name}: 期望 13 列，实际 {len(f)} 列 -> {line[:60]!r}")
        if not f[1]:
            raise ValueError(f"{src.name}: slug 为空 -> {line[:60]!r}")
        if f[1] in seen:
            raise ValueError(f"{src.name}: slug 重复 {f[1]!r} —— 实体 id 将冲突")
        seen.add(f[1])
        try:
            n_inst = int(f[12] or 0)
        except ValueError:
            n_inst = 0
        out.append(Satellite(
            oscar_id=f[0], slug=f[1], acronym=f[2], fullname=f[3],
            space_agency=f[4], status=f[5], orbit=f[6], launch_date=f[7],
            eol=f[8], altitude_km=f[9], ect=f[10], wigos_id=f[11],
            instrument_count=n_inst,
        ))
    if not out:
        raise ValueError(f"{src} 未加载到任何卫星")
    return out


#: 全部卫星（WMO OSCAR/Space）
SATELLITES: list[Satellite] = load_satellites()


def satellite_stats() -> dict[str, int]:
    by_status: dict[str, int] = {}
    for s in SATELLITES:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    return {
        "satellites": len(SATELLITES),
        "agencies": len({s.space_agency for s in SATELLITES if s.space_agency}),
        "operational": by_status.get("Operational", 0),
        "planned": by_status.get("Planned", 0),
        "with_instruments": sum(1 for s in SATELLITES if s.instrument_count > 0),
    }
