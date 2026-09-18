"""管理面测试：来源登记表 / 库 API / CLI。

锁住四件事：

1. **登记表是唯一真相** —— 每个数据文件都必须登记，且登记的上游/许可与其
   它在别处的声明一致（否则"真相"又会被拆回多处）；
2. **只读 API 无副作用、可 JSON 序列化** —— 因为它要供未来的 Web 管理面复用，
   一旦返回值不可序列化或偷偷写盘，复用就会出问题；
3. **陈旧度策略按源设置** —— 静态数据集（WorldCover/Köppen/IRDR）不得被误报过期，
   高频源（GeoNames）必须能触发告警；
4. **CLI 退出码可用于 CI** —— verify 失败、status --strict 遇陈旧都应非零。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

import pytest

from geokg import admin
from geokg import sources as S


class TestRegistry:
    def test_every_data_file_is_registered(self) -> None:
        """磁盘上的每个 .tsv 都必须在登记表里——否则管理面看不见它。"""
        on_disk = {p.name for p in S.DATA_DIR.glob("*.tsv")}
        registered = set(S.files())
        assert on_disk == registered, f"未登记: {on_disk - registered}"

    def test_ids_unique(self) -> None:
        ids = [d.id for d in S.DATASETS]
        assert len(ids) == len(set(ids))

    def test_generators_exist(self) -> None:
        for d in S.DATASETS:
            assert d.generator_path.exists(), f"{d.id} 的生成脚本缺失: {d.generator}"

    def test_required_metadata_present(self) -> None:
        for d in S.DATASETS:
            assert d.upstream, f"{d.id} 缺上游"
            assert d.license, f"{d.id} 缺许可"
            assert d.attribution, f"{d.id} 缺署名"
            assert d.tier, f"{d.id} 缺分级"
            assert d.sources, f"{d.id} 未关联 provenance 来源"

    def test_registry_matches_provenance(self) -> None:
        """登记表与 provenance.SOURCES 必须对得上——这是防止"真相再次分裂"的关键。"""
        from geokg.provenance import SOURCES

        declared = set(S.SOURCE_IDS)
        missing = declared - set(SOURCES)
        assert not missing, f"登记表引用了 provenance 中不存在的来源: {missing}"

    def test_staleness_policy_is_sensible(self) -> None:
        """高频源必须有阈值；静态源必须为 None（否则会被误报过期）。"""
        by_id = S.BY_ID
        assert by_id["geonames-admin1"].staleness_days == 30   # 每日更新
        assert by_id["wmo-oscar-satellites"].staleness_days == 90
        for static in ("esa-worldcover", "koppen-geiger", "irdr-hazards"):
            assert by_id[static].staleness_days is None, f"{static} 是静态源，不应有阈值"

    def test_get_unknown_raises_with_hint(self) -> None:
        with pytest.raises(KeyError, match="未知数据集"):
            S.get("nope")

    def test_network_flag_matches_reality(self) -> None:
        """转录型生成器不应被标为需要联网。"""
        for d in S.DATASETS:
            if d.generator in ("build_l3_ontology.py", "build_vocabulary.py"):
                assert d.requires_network is False, f"{d.id} 是离线转录"


class TestReadOnlyApi:
    def test_status_is_json_serializable(self) -> None:
        st = admin.status()
        json.dumps(st)  # 不可序列化即失败
        assert st["counts"]["datasets"] == len(S.DATASETS)

    def test_status_reports_all_datasets(self) -> None:
        st = admin.status()
        assert {d["id"] for d in st["datasets"]} == set(S.BY_ID)

    def test_status_has_manifest(self) -> None:
        st = admin.status()
        assert st["manifest_present"], "清单缺失——请运行 geokg manifest --write"

    def test_verify_passes_offline(self) -> None:
        v = admin.verify(drift=False)
        assert v["ok"], [c for c in v["checks"] if not c["ok"]]

    def test_verify_is_json_serializable(self) -> None:
        json.dumps(admin.verify(drift=False))

    def test_verify_offline_does_not_touch_network(self) -> None:
        """离线校验不得触发联网（CI 与无网环境都要能跑）。"""
        v = admin.verify(drift=False)
        assert v["drift"] == [] and v["drift_requested"] is False

    def test_licenses_aggregates(self) -> None:
        lic = admin.licenses()
        json.dumps(lic)
        assert len(lic["groups"]) >= 5
        assert any("WMO" in a for a in lic["requires_attribution"])

    def test_manifest_fingerprint_stable(self) -> None:
        """同一批数据两次生成的指纹必须一致（这是引用版本号的基础）。"""
        assert admin.manifest()["fingerprint"] == admin.manifest()["fingerprint"]

    def test_manifest_rows_exclude_header(self) -> None:
        """L3 数据文件带列头行，行数不得把它算进去。"""
        mf = admin.manifest()["files"]
        assert mf["esa-worldcover"]["rows"] == 11
        assert mf["koppen-geiger"]["rows"] == 35
        assert mf["irdr-hazards"]["rows"] == 73


class TestStaleness:
    def test_age_parsing(self) -> None:
        assert admin._age_days(date.today().isoformat()) == 0
        old = (date.today() - timedelta(days=40)).isoformat()
        assert admin._age_days(old) == 40
        assert admin._age_days("") is None
        assert admin._age_days("bogus") is None

    def test_stale_detection_for_fast_source(self) -> None:
        ds = S.BY_ID["geonames-admin1"]
        old = (date.today() - timedelta(days=ds.staleness_days + 5)).isoformat()
        st = admin.dataset_status(ds, {"files": {"geonames-admin1": {"retrieved": old}}})
        assert st["stale"] is True
        assert st["age_days"] > ds.staleness_days

    def test_static_source_never_stale(self) -> None:
        """静态数据集即使取数日期很老也不得报陈旧。"""
        for sid in ("esa-worldcover", "koppen-geiger", "irdr-hazards"):
            ds = S.BY_ID[sid]
            old = (date.today() - timedelta(days=3650)).isoformat()
            st = admin.dataset_status(ds, {"files": {sid: {"retrieved": old}}})
            assert st["stale"] is False, f"{sid} 是静态源却被判陈旧"

    def test_fingerprint_mismatch_detected(self) -> None:
        """数据改了但清单没重算 → 必须告警。"""
        ds = S.BY_ID["un-m49"]
        st = admin.dataset_status(ds, {"files": {"un-m49": {"sha256": "deadbeef"}}})
        assert st["fingerprint_match"] is False


class TestCli:
    def test_version(self, capsys) -> None:
        from geokg.cli import main

        assert main(["version"]) == 0
        assert S.DATASET_VERSION in capsys.readouterr().out

    def test_status_ok(self, capsys) -> None:
        from geokg.cli import main

        assert main(["status"]) == 0
        assert "数据集状态" in capsys.readouterr().out

    def test_status_strict_clean(self) -> None:
        from geokg.cli import main

        assert main(["status", "--strict"]) == 0

    def test_verify_ok(self, capsys) -> None:
        from geokg.cli import main

        assert main(["verify"]) == 0
        assert "全部通过" in capsys.readouterr().out

    def test_json_output_is_parseable(self, capsys) -> None:
        """--json 是给 Web/脚本消费的接口契约，必须能解析。"""
        from geokg.cli import main

        assert main(["--json", "status"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "datasets" in payload and "counts" in payload

    def test_licenses_ok(self, capsys) -> None:
        from geokg.cli import main

        assert main(["licenses"]) == 0
        assert "署名" in capsys.readouterr().out

    def test_manifest_without_write_does_not_persist(self, capsys) -> None:
        """不加 --write 不得写盘——只读命令要保持无副作用。"""
        from geokg.cli import main

        before = admin.MANIFEST_FILE.read_bytes()
        assert main(["manifest"]) == 0
        assert admin.MANIFEST_FILE.read_bytes() == before

    def test_refresh_requires_target(self) -> None:
        from geokg.cli import main

        assert main(["refresh"]) == 2  # 未指定 id 也未 --all

    def test_cli_subcommands_cover_the_documented_set(self) -> None:
        """CLI 的子命令集合必须与文档一致——防止加了命令没更新说明。"""
        from geokg.cli import build_parser

        parser = build_parser()
        subs = {
            a.dest for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
            for a in [a]
        }
        choices = set()
        for a in parser._actions:
            if isinstance(a, argparse._SubParsersAction):
                choices |= set(a.choices)
        assert choices == {
            "status", "verify", "licenses", "counts",
            "manifest", "refresh", "build", "version",
        }, f"子命令与文档不符: {choices}"
        assert subs  # 确认上面的遍历确实取到了 subparsers
