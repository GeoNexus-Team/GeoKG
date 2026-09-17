"""数据文件完整性测试。

锁住两件事：

1. **数据文件本身可用**——列数、唯一性、关键条目（防止脚本改坏或文件被截断）；
2. **可复现**——数据文件由 ``scripts/fetch_*.py`` 生成，脚本存在且声明了来源与许可。

这些断言值来自实测；若上游数据更新导致数字变化，测试会失败并提示重新生成，
这正是想要的：**数据变化必须是有意识的动作**，不能悄悄漂移。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from geokg import admin1 as A1
from geokg import reference_data as RD

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


class TestCountryDataFile:
    def test_file_exists(self) -> None:
        assert RD.COUNTRY_DATA_FILE.exists(), "国家数据文件缺失"

    def test_row_count_and_columns(self) -> None:
        raw = [ln for ln in RD.COUNTRY_DATA_FILE.read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
        assert len(raw) == 249, f"UN M49(248) + ISO 补 TWN(1) 应为 249，实际 {len(raw)}"
        for ln in raw:
            assert len(ln.split("\t")) == 11, f"列数不对: {ln[:60]!r}"

    def test_iso3_unique(self) -> None:
        codes = [c.iso3 for c in RD.COUNTRIES_FULL]
        assert len(codes) == len(set(codes)), "iso3 有重复"

    def test_loads_expected_shape(self) -> None:
        assert len(RD.COUNTRIES) == len(RD.COUNTRIES_FULL)
        assert RD.COUNTRIES[0][0] == RD.COUNTRIES_FULL[0].iso3

    @pytest.mark.parametrize("iso3", ["CHN", "USA", "KEN", "TWN"])
    def test_key_countries_present(self, iso3: str) -> None:
        assert any(c.iso3 == iso3 for c in RD.COUNTRIES_FULL), f"{iso3} 缺失"

    def test_taiwan_retained_explicitly(self) -> None:
        """TWN 不在 UN M49 中（M49 只列 CHN/HKG/MAC），由 ISO 3166-1 补充。

        这是一项**显式记录的口径选择**，不是静默处理——所以要有测试盯着它。
        """
        twn = next(c for c in RD.COUNTRIES_FULL if c.iso3 == "TWN")
        assert twn.region == "Asia" and twn.subregion == "Eastern Asia"

    def test_antarctica_has_no_region(self) -> None:
        """ATA 在 UN M49 中没有区域——摄入时必须容错，不能造出空名区域实体。"""
        ata = next(c for c in RD.COUNTRIES_FULL if c.iso3 == "ATA")
        assert ata.region == "" and ata.subregion == ""

    def test_sdg_grouping_flags(self) -> None:
        by = {c.iso3: c for c in RD.COUNTRIES_FULL}
        assert by["AFG"].ldc is True          # 最不发达国家
        assert by["CHE"].ldc is False
        assert by["NPL"].lldc is True         # 内陆发展中国家
        assert by["MUS"].sids is True         # 小岛屿发展中国家

    def test_flag_counts_match_un_m49(self) -> None:
        assert sum(1 for c in RD.COUNTRIES_FULL if c.ldc) == 44
        assert sum(1 for c in RD.COUNTRIES_FULL if c.lldc) == 32
        assert sum(1 for c in RD.COUNTRIES_FULL if c.sids) == 53


class TestAdmin1DataFile:
    def test_file_exists(self) -> None:
        assert A1.ADMIN1_DATA_FILE.exists(), "admin1 数据文件缺失"

    def test_row_count_and_columns(self) -> None:
        raw = [ln for ln in A1.ADMIN1_DATA_FILE.read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
        assert len(raw) == 3858, f"GeoNames admin1 实测 3,858，实际 {len(raw)}"
        for ln in raw:
            assert len(ln.split("\t")) == 5, f"列数不对: {ln[:60]!r}"

    def test_geonameid_unique_and_used_as_id(self) -> None:
        ids = [u.geonameid for u in A1.ADMIN1_UNITS]
        assert len(ids) == len(set(ids)), "geonameid 重复会导致实体 id 冲突"
        assert A1.ADMIN1_UNITS[0].entity_id.startswith("admin1.")

    def test_entity_id_uses_geonameid_not_name(self) -> None:
        """名称在同国内可能重复，用名称生成 id 会静默丢数据。"""
        u = A1.ADMIN1_UNITS[0]
        assert u.geonameid in u.entity_id
        assert u.name.lower().replace(" ", "-") not in u.entity_id

    def test_coverage(self) -> None:
        assert len({u.iso3 for u in A1.ADMIN1_UNITS}) >= 200, "覆盖国家数异常偏低"

    def test_no_duplicate_entity_ids(self) -> None:
        eids = [u.entity_id for u in A1.ADMIN1_UNITS]
        assert len(eids) == len(set(eids))


class TestRegenerationScripts:
    """数据文件必须由脚本生成，脚本必须声明来源与许可。"""

    @pytest.mark.parametrize("name,needle", [
        ("fetch_un_m49.py", "unstats.un.org"),
        ("fetch_geonames_admin1.py", "download.geonames.org"),
    ])
    def test_script_exists_and_cites_source(self, name: str, needle: str) -> None:
        f = SCRIPTS / name
        assert f.exists(), f"{name} 缺失——数据将无法复现"
        assert needle in f.read_text(encoding="utf-8"), f"{name} 未声明来源"

    def test_geonames_script_mentions_licence(self) -> None:
        t = (SCRIPTS / "fetch_geonames_admin1.py").read_text(encoding="utf-8")
        assert "CC BY 4.0" in t, "必须声明 GeoNames 的许可"

    def test_geonames_script_documents_tls_quirk(self) -> None:
        """curl 抓不到该站点（TLS bad key length），脚本文档要写明，否则会被误判为站点故障。"""
        t = (SCRIPTS / "fetch_geonames_admin1.py").read_text(encoding="utf-8")
        assert "bad key length" in t
