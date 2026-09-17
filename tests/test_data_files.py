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
from geokg import sdg as SDG

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


class TestCountryDataFile:
    def test_file_exists(self) -> None:
        assert RD.COUNTRY_DATA_FILE.exists(), "国家数据文件缺失"

    def test_row_count_and_columns(self) -> None:
        raw = [ln for ln in RD.COUNTRY_DATA_FILE.read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
        assert len(raw) == 249, f"UN M49(248) + ISO 补 TWN(1) 应为 249，实际 {len(raw)}"
        for ln in raw:
            assert len(ln.split("\t")) == 13, f"列数不对: {ln[:60]!r}"

    def test_iso3_unique(self) -> None:
        codes = [c.iso3 for c in RD.COUNTRIES_FULL]
        assert len(codes) == len(set(codes)), "iso3 有重复"

    def test_loads_expected_shape(self) -> None:
        assert len(RD.COUNTRIES) == len(RD.COUNTRIES_FULL)
        assert RD.COUNTRIES[0][0] == RD.COUNTRIES_FULL[0].iso3

    @pytest.mark.parametrize("iso3", ["CHN", "USA", "KEN", "TWN"])
    def test_key_countries_present(self, iso3: str) -> None:
        assert any(c.iso3 == iso3 for c in RD.COUNTRIES_FULL), f"{iso3} 缺失"

    def test_one_china_basis(self) -> None:
        """一个中国原则：HKG / MAC / TWN 均为中国的一部分。

        处理方式照搬 UN M49 对港澳的写法——保留独立编码，名称写明归属。
        UN M49 原文即 `"China, Hong Kong Special Administrative Region"`；
        ISO 3166-1 对 TW 的官方名是 `"Taiwan, Province of China"`。

        这是**政策口径**，必须有测试锁住，防止被无意改动。
        """
        by = {c.iso3: c for c in RD.COUNTRIES_FULL}
        assert by["CHN"].admin_status == "sovereign"
        assert by["CHN"].part_of == ""

        for iso3, status in (("HKG", "SAR"), ("MAC", "SAR"), ("TWN", "province")):
            c = by[iso3]
            assert c.part_of == "CHN", f"{iso3} 未标明归属中国"
            assert c.admin_status == status, f"{iso3} 状态应为 {status}"

    def test_taiwan_named_per_iso_official(self) -> None:
        """TWN 名称取 ISO 3166-1 官方名，与 M49 港澳写法同类。"""
        twn = next(c for c in RD.COUNTRIES_FULL if c.iso3 == "TWN")
        assert twn.name == "Taiwan, Province of China"
        assert twn.region == "Asia" and twn.subregion == "Eastern Asia"

    def test_hong_kong_named_per_un_m49(self) -> None:
        """港澳名称直接采用 UN M49 原文，不做改写。"""
        hkg = next(c for c in RD.COUNTRIES_FULL if c.iso3 == "HKG")
        mac = next(c for c in RD.COUNTRIES_FULL if c.iso3 == "MAC")
        assert hkg.name == "China, Hong Kong Special Administrative Region"
        assert mac.name == "China, Macao Special Administrative Region"

    def test_only_china_affiliated_entries_have_part_of(self) -> None:
        """当前只有中国相关条目带归属；其余均为主权实体。"""
        n = [c.iso3 for c in RD.COUNTRIES_FULL if c.part_of]
        assert sorted(n) == ["HKG", "MAC", "TWN"]
        assert all(c.admin_status == "sovereign"
                   for c in RD.COUNTRIES_FULL if not c.part_of)

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


class TestSdgFrameworkFile:
    """SDG 框架改用官方 API 后的数据完整性。

    核对期间发现旧实现有两个问题，这里都要锁住：
    1. 按"每目标有 N 个"用计数**伪造 id**，真实代码（1.a / 2.a / 17.18）全被错编号；
    2. 手写表少了 7 个指标，文档所称"231"亦为过时数字。
    """

    def test_counts(self) -> None:
        assert len(SDG.SDG_GOALS_LIST) == 17
        assert len(SDG.SDG_TARGETS_LIST) == 169
        assert len(SDG.SDG_INDICATORS_LIST) == 251

    def test_columns(self) -> None:
        raw = [ln for ln in SDG.SDG_DATA_FILE.read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
        assert len(raw) == 437
        for ln in raw:
            assert len(ln.split("\t")) == 7, f"列数不对: {ln[:60]!r}"

    def test_codes_unique_per_level(self) -> None:
        for level in ("goal", "target", "indicator"):
            codes = [e.code for e in SDG.SDG_ENTRIES if e.level == level]
            assert len(codes) == len(set(codes)), f"{level} code 重复"

    def test_real_codes_not_fabricated(self) -> None:
        """官方代码含字母后缀（1.a / 2.a / 5.c / 17.18 等），伪造的纯数字编号不会有。"""
        t = {e.code for e in SDG.SDG_TARGETS_LIST}
        for c in ("1.a", "1.b", "2.a", "5.c", "17.18", "17.19"):
            assert c in t, f"缺少真实具体目标代码 {c}"
        i = {e.code for e in SDG.SDG_INDICATORS_LIST}
        for c in ("1.a.1", "2.a.1", "17.18.1", "6.6.1"):
            assert c in i, f"缺少真实指标代码 {c}"

    def test_every_entry_has_title(self) -> None:
        for e in SDG.SDG_ENTRIES:
            assert e.title, f"{e.level} {e.code} 缺标题"

    def test_tiers_present(self) -> None:
        st = SDG.sdg_stats()
        assert st["indicators_tier1"] > 0 and st["indicators_tier2"] > 0
        assert st["indicators_tier1"] + st["indicators_tier2"] == st["indicators"]

    def test_entity_ids_use_official_codes(self) -> None:
        e = next(x for x in SDG.SDG_INDICATORS_LIST if x.code == "1.a.1")
        assert e.entity_id == "sdg.indicator.1.a.1"
        t = next(x for x in SDG.SDG_TARGETS_LIST if x.code == "1.a")
        assert t.entity_id == "sdg.target.1.a"
        assert t.parent == "1"

    def test_sdg_script_exists(self) -> None:
        f = SCRIPTS / "fetch_un_sdg.py"
        assert f.exists(), "SDG 数据将无法复现"
        assert "SDGAPI" in f.read_text(encoding="utf-8")


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
