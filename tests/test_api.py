"""HTTP 管理面测试：只读契约 / 鉴权 / 长任务 / SSE。

锁住五件事：

1. **HTTP 不重复实现逻辑** —— 每个只读接口的返回必须与 ``admin.*`` 相等
   （时间戳字段除外）。这是"CLI 与 Web 共用同一逻辑层"的可验证形式：一旦
   有人在路由里另写一套计算，这个测试立刻失败；
2. **变更接口失败关闭** —— 没配 key 时必须 503 而不是放行。SDK 的
   ``APIKeyAuth`` 在空键集下放行，本服务刻意反着来，因此必须被测试钉住；
3. **同类变更不并发** —— 第二次提交返回 409，且任务结束后槽位必须释放
   （否则"刷新"会永久不可用）；
4. **取消是协作式的** —— 取消后任务要在下一个数据集边界停下并标记 cancelled，
   而不是把已经在跑的子进程当没发生；
5. **SSE 只推变化** —— 不重复发同样的帧，终态必达，progress 不回退。

长任务用假的 ``admin.refresh`` / ``admin.build`` 替身，因此**不联网、不写盘**。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from geokg import admin, api
from geokg.sources import DATASET_VERSION

KEYS = {"test-key-1", "test-key-2"}
HEAD = {"X-API-Key": "test-key-1"}
PREFIX = api.API_PREFIX

#: 逐次调用都会变的字段，比较接口与库 API 时须剔除
VOLATILE = ("generated_at", "inflight")


def _strip(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in VOLATILE}


# --------------------------------------------------------------------------- #
# 替身：可控速度的 refresh（不联网、不写文件）
# --------------------------------------------------------------------------- #
def _fake_refresh(dataset_id: str | None = None, *, all_: bool = False,
                  timeout: int = 1800, checkpoint: Any = None,
                  steps: int = 4, delay: float = 0.15,
                  gate: threading.Event | None = None) -> dict[str, Any]:
    """与 ``admin.refresh`` 同签名、同返回结构的替身，但按 ``steps`` 分步。"""
    results: list[dict[str, Any]] = []
    aborted = False
    for index in range(steps):
        if checkpoint is not None and not checkpoint({
            "dataset": f"fake-{index}", "index": index, "total": steps,
            "done": list(results), "ok": True,
        }):
            aborted = True
            break
        time.sleep(delay)
        results.append({"id": f"fake-{index}", "ok": True, "detail": "ok"})
    if gate is not None:
        gate.wait(timeout=10)
    return {"results": results, "ok": True, "aborted": aborted, "manifest": None}


def _patch_refresh(monkeypatch, **fake_kw: Any) -> None:
    """把 admin.refresh 换成替身；调用方传来的参数原样转发。"""
    monkeypatch.setattr(
        admin, "refresh",
        lambda *a, **kw: _fake_refresh(*a, **{**kw, **fake_kw}))


@pytest.fixture()
def client():
    """配了 key 的客户端（用 with 触发 lifespan，确保线程池被关闭）。"""
    with TestClient(api.create_app(set(KEYS))) as c:
        yield c


@pytest.fixture()
def open_client():
    """未配置 key 的客户端——验证只读照常、变更失败关闭。"""
    with TestClient(api.create_app(set())) as c:
        yield c


def _wait_for(tasks: Any, tid: str, statuses: tuple[str, ...],
              timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    state: dict[str, Any] = {}
    while time.time() < deadline:
        state = tasks.get(tid, include_result=False)
        if state["status"] in statuses:
            return state
        time.sleep(0.02)
    raise AssertionError(f"任务未在 {timeout}s 内进入 {statuses}，当前 {state}")


# --------------------------------------------------------------------------- #
# 只读契约
# --------------------------------------------------------------------------- #
class TestReadOnly:
    def test_status_equals_admin(self, client) -> None:
        got = client.get(f"{PREFIX}/status").json()
        # HTTP 层多一个 inflight 字段（客户端据此知道数据是否正被写入）
        assert got["inflight"] == {}
        assert _strip(got) == _strip(admin.status())

    def test_verify_equals_admin(self, client) -> None:
        assert client.get(f"{PREFIX}/verify").json() == admin.verify(drift=False)

    def test_licenses_equals_admin(self, client) -> None:
        assert client.get(f"{PREFIX}/licenses").json() == admin.licenses()

    def test_manifest_equals_admin(self, client) -> None:
        got = client.get(f"{PREFIX}/manifest").json()
        assert _strip(got) == _strip(admin.manifest(write=False))

    def test_counts_equals_admin(self, client) -> None:
        got = client.get(f"{PREFIX}/counts", params={"level": "country"}).json()
        assert got == admin.counts(monitor_levels=["country"])

    def test_counts_default_levels(self, client) -> None:
        """不给 level 时与 admin.counts(None) 一致（默认 country）。"""
        assert client.get(f"{PREFIX}/counts").json() == admin.counts(monitor_levels=None)

    def test_counts_rejects_unknown_level(self, client) -> None:
        r = client.get(f"{PREFIX}/counts", params={"level": "province"})
        assert r.status_code == 400
        assert "未知监测层级" in r.json()["detail"]

    def test_version_is_compact_and_consistent(self, client) -> None:
        v = client.get(f"{PREFIX}/version").json()
        mf = admin.manifest()
        assert v["dataset_version"] == DATASET_VERSION == mf["dataset_version"]
        assert v["fingerprint"] == mf["fingerprint"]
        assert v["manifest_generated_at"] == mf["stored_generated_at"]
        assert v["files"] == len(mf["files"])
        assert v["rows"] == sum(f["rows"] for f in mf["files"].values())

    def test_version_is_deterministic(self, client) -> None:
        """版本接口不得含"本次计算时间"——否则同一份数据每次都不同，无法缓存。"""
        first = client.get(f"{PREFIX}/version").json()
        time.sleep(1.1)  # 跨过 generated_at 的秒级分辨率
        assert client.get(f"{PREFIX}/version").json() == first

    def test_health_needs_no_key(self, open_client) -> None:
        h = open_client.get(f"{PREFIX}/health").json()
        assert h["status"] == "ok" and h["writable"] is False

    def test_drift_not_exposed_over_http(self, client) -> None:
        """漂移检查要联网跑脚本，刻意不挂 HTTP（属于运维批处理）。"""
        v = client.get(f"{PREFIX}/verify").json()
        assert v["drift_requested"] is False and v["drift"] == []


# --------------------------------------------------------------------------- #
# 鉴权
# --------------------------------------------------------------------------- #
class TestAuth:
    MUTATING = ("manifest", "refresh", "build")

    @pytest.mark.parametrize("path", MUTATING)
    def test_requires_key(self, client, path) -> None:
        assert client.post(f"{PREFIX}/{path}", json={}).status_code == 401

    @pytest.mark.parametrize("path", MUTATING)
    def test_rejects_wrong_key(self, client, path) -> None:
        r = client.post(f"{PREFIX}/{path}", json={}, headers={"X-API-Key": "nope"})
        assert r.status_code == 401

    @pytest.mark.parametrize("path", MUTATING)
    def test_fails_closed_without_configured_keys(self, open_client, path) -> None:
        """空键集必须 503——SDK 的 APIKeyAuth 此时放行，本服务刻意收紧。"""
        r = open_client.post(f"{PREFIX}/{path}", json={})
        assert r.status_code == 503
        assert "GEOKG_API_KEYS" in r.json()["detail"]

    def test_task_routes_also_gated(self, client) -> None:
        assert client.get(f"{PREFIX}/tasks").status_code == 401
        assert client.get(f"{PREFIX}/tasks/xyz").status_code == 401
        assert client.post(f"{PREFIX}/tasks/xyz/cancel").status_code == 401

    def test_readonly_open_without_keys(self, open_client) -> None:
        assert open_client.get(f"{PREFIX}/status").status_code == 200
        assert open_client.get(f"{PREFIX}/version").status_code == 200

    def test_every_post_route_is_gated(self, client) -> None:
        """新增 POST 路由时忘了挂 gate → 这条测试失败。"""
        posts = sorted({r.path for r in client.app.routes
                        if getattr(r, "methods", None) and "POST" in r.methods})
        assert posts, "没有找到任何 POST 路由，测试本身失效了"
        for path in posts:
            url = path.replace("{task_id}", "ghost")
            assert client.post(url, json={}).status_code == 401, f"{path} 未鉴权"

    def test_resolve_keys_precedence(self, monkeypatch) -> None:
        monkeypatch.setenv(api.ENV_KEYS, "env-a, env-b ,")
        assert api.resolve_keys() == {"env-a", "env-b"}
        # 显式参数优先于环境变量（空集合也是显式意图，不被环境变量覆盖）
        assert api.resolve_keys(set()) == set()
        monkeypatch.delenv(api.ENV_KEYS)
        assert api.resolve_keys() == set()


# --------------------------------------------------------------------------- #
# 参数校验
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("body,needle", [
        ({}, "需给出 dataset_id 或 all=true"),
        ({"dataset_id": "ghost"}, "未知数据集"),
        ({"dataset_id": "vocabulary", "all": True}, "不能同时给出"),
    ])
    def test_refresh_rejections(self, client, body, needle) -> None:
        r = client.post(f"{PREFIX}/refresh", json=body, headers=HEAD)
        assert r.status_code == 400, r.text
        assert needle in r.text

    def test_refresh_timeout_bounds_enforced(self, client) -> None:
        """timeout 越界由 pydantic 拦下（422），不会真的启动子进程。"""
        r = client.post(f"{PREFIX}/refresh",
                        json={"dataset_id": "vocabulary", "timeout": 5},
                        headers=HEAD)
        assert r.status_code == 422, r.text

    def test_build_rejects_unknown_level(self, client) -> None:
        r = client.post(f"{PREFIX}/build", json={"monitor_levels": ["bogus"]},
                        headers=HEAD)
        assert r.status_code == 400
        assert "未知监测层级" in r.json()["detail"]

    def test_unknown_task_404(self, client) -> None:
        assert client.get(f"{PREFIX}/tasks/ghost", headers=HEAD).status_code == 404
        assert client.post(f"{PREFIX}/tasks/ghost/cancel",
                           headers=HEAD).status_code == 404


# --------------------------------------------------------------------------- #
# 长任务
# --------------------------------------------------------------------------- #
class TestTasks:
    def test_refresh_task_runs_and_reports(self, client, monkeypatch) -> None:
        _patch_refresh(monkeypatch)
        r = client.post(f"{PREFIX}/refresh", json={"dataset_id": "vocabulary"},
                        headers=HEAD)
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["kind"] == "refresh:vocabulary"
        assert body["poll"].endswith(body["task_id"])

        state = client.app.state.tasks.wait(body["task_id"], timeout=10)
        assert state["status"] == "done", state
        assert state["progress"] == 1.0
        assert len(state["result"]["results"]) == 4
        assert state["result"]["aborted"] is False

    def test_duplicate_kind_conflicts_then_releases(self, client, monkeypatch) -> None:
        """同类并发 → 409；任务结束后槽位必须释放，否则刷新永久失效。"""
        gate = threading.Event()
        _patch_refresh(monkeypatch, gate=gate)
        first = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                            headers=HEAD)
        assert first.status_code == 202
        tid = first.json()["task_id"]
        tasks = client.app.state.tasks
        _wait_for(tasks, tid, ("running",))

        again = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                            headers=HEAD)
        assert again.status_code == 409
        assert client.get(f"{PREFIX}/status").json()["inflight"] == {
            "refresh:un-m49": tid}

        gate.set()
        tasks.wait(tid, timeout=10)
        second = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                             headers=HEAD)
        assert second.status_code == 202, second.text
        tasks.wait(second.json()["task_id"], timeout=10)
        assert client.get(f"{PREFIX}/status").json()["inflight"] == {}

    def test_aborting_worker_is_cooperative(self, client, monkeypatch) -> None:
        """取消：当前步骤跑完即停，不开启后续步骤，终态为 cancelled。"""
        _patch_refresh(monkeypatch, steps=6, delay=0.25)
        tid = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                          headers=HEAD).json()["task_id"]
        tasks = client.app.state.tasks
        _wait_for(tasks, tid, ("running",))

        assert client.post(f"{PREFIX}/tasks/{tid}/cancel",
                           headers=HEAD).status_code == 200
        state = tasks.wait(tid, timeout=10)
        assert state["status"] == "cancelled", state
        assert state["result"]["aborted"] is True
        assert len(state["result"]["results"]) < 6, "取消后仍在继续跑后续数据集"

    def test_cancel_finished_task_conflicts(self, client, monkeypatch) -> None:
        _patch_refresh(monkeypatch, steps=1, delay=0)
        tid = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                          headers=HEAD).json()["task_id"]
        client.app.state.tasks.wait(tid, timeout=10)
        assert client.post(f"{PREFIX}/tasks/{tid}/cancel",
                           headers=HEAD).status_code == 409

    def test_task_list(self, client, monkeypatch) -> None:
        _patch_refresh(monkeypatch, steps=1, delay=0)
        tid = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                          headers=HEAD).json()["task_id"]
        client.app.state.tasks.wait(tid, timeout=10)
        listed = client.get(f"{PREFIX}/tasks", headers=HEAD).json()
        assert tid in {t["id"] for t in listed["tasks"]}
        assert listed["inflight"] == {}

    def test_build_task(self, client, monkeypatch) -> None:
        monkeypatch.setattr(admin, "build",
                            lambda **kw: {"entities": 7, "relations": 3, **kw})
        r = client.post(f"{PREFIX}/build", json={"monitor_levels": ["country"]},
                        headers=HEAD)
        assert r.status_code == 202
        state = client.app.state.tasks.wait(r.json()["task_id"], timeout=10)
        assert state["status"] == "done"
        assert state["result"]["entities"] == 7

    def test_post_manifest_writes(self, client, monkeypatch) -> None:
        """POST /manifest 必须走 admin.manifest(write=True)。"""
        seen: list[bool] = []

        def fake_manifest(*, write: bool = False) -> dict[str, Any]:
            seen.append(write)
            return {"fingerprint": "f" * 64, "dataset_version": "x"}

        monkeypatch.setattr(admin, "manifest", fake_manifest)
        r = client.post(f"{PREFIX}/manifest", headers=HEAD)
        assert r.status_code == 200 and r.json()["fingerprint"] == "f" * 64
        assert seen == [True], f"写回接口必须传 write=True，实际 {seen}"


# --------------------------------------------------------------------------- #
# SSE
# --------------------------------------------------------------------------- #
class TestSse:
    def test_stream_yields_changes_and_terminates(self, client, monkeypatch) -> None:
        _patch_refresh(monkeypatch, steps=4, delay=0.12)
        tid = client.post(f"{PREFIX}/refresh", json={"dataset_id": "un-m49"},
                          headers=HEAD).json()["task_id"]

        frames: list[str] = []
        with client.stream("GET", f"{PREFIX}/tasks/{tid}/events",
                           headers=HEAD) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            for line in resp.iter_lines():
                if not line or line.startswith(":"):
                    continue
                frames.append(line)

        payloads = [json.loads(f[len("data: "):]) for f in frames]
        assert payloads, "SSE 没有推送任何帧"
        assert payloads[-1]["status"] in ("done", "failed", "cancelled")
        assert len(payloads) < 200, "疑似把无变化的状态也反复推送"
        progress = [p["progress"] for p in payloads]
        assert progress == sorted(progress), progress

    def test_stream_on_unknown_task_404(self, client) -> None:
        assert client.get(f"{PREFIX}/tasks/ghost/events",
                          headers=HEAD).status_code == 404


# --------------------------------------------------------------------------- #
# 检索与图谱视图
# --------------------------------------------------------------------------- #
class TestRetrieval:
    """`/search` `/entity` `/graph` `/types` —— 图谱视图的后端。

    这一组同时钉住"HTTP 不重复实现逻辑"：返回必须与 admin.* 相等。
    图是**数据文件的函数**，所以这些测试跑的是真实数据（无网络、无副作用）。
    """

    def test_search_equals_admin(self, client) -> None:
        got = client.get(f"{PREFIX}/search", params={"q": "brazil", "limit": 5}).json()
        assert got == admin.search("brazil", limit=5)

    def test_search_ranks_exact_name_above_substring(self, client) -> None:
        """只按 id 排会把 country.BRA 排到一堆 *brazil* 卫星后面。"""
        got = client.get(f"{PREFIX}/search", params={"q": "brazil"}).json()
        assert got["count"] >= 1
        assert got["results"][0]["id"] == "country.BRA"
        scores = [r["score"] for r in got["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_search_carries_provenance_on_every_hit(self, client) -> None:
        """检索结果必须能回答"这条凭什么可信"——否则界面只能显示一个名字。"""
        got = client.get(f"{PREFIX}/search", params={"q": "sentinel", "limit": 10}).json()
        assert got["results"]
        for hit in got["results"]:
            prov = hit["provenance"]
            assert prov.get("source"), hit["id"]
            assert prov.get("source_tier"), hit["id"]
            assert prov.get("license"), hit["id"]

    def test_search_type_filter(self, client) -> None:
        got = client.get(f"{PREFIX}/search",
                         params={"q": "", "type": "Satellite", "limit": 5}).json()
        assert got["results"] and all(r["type"] == "Satellite" for r in got["results"])

    def test_search_limit_and_truncation_flag(self, client) -> None:
        got = client.get(f"{PREFIX}/search", params={"q": "a", "limit": 3}).json()
        assert got["returned"] == 3
        assert got["truncated"] is True and got["count"] > 3

    def test_entity_equals_admin_and_is_bidirectional(self, client) -> None:
        got = client.get(f"{PREFIX}/entity/country.BRA").json()
        assert got == admin.entity("country.BRA")
        # 领域图里大量边指向宿主：只看 out 边国家节点几乎是孤立的
        assert len(got["in"]) > len(got["out"]), (len(got["in"]), len(got["out"]))
        assert got["entity"]["provenance"]["source"] == "un-m49"

    def test_entity_unknown_is_404(self, client) -> None:
        r = client.get(f"{PREFIX}/entity/ghost")
        assert r.status_code == 404 and "实体不存在" in r.json()["detail"]

    def test_graph_equals_admin(self, client) -> None:
        got = client.get(f"{PREFIX}/graph",
                         params={"focus": "country.BRA", "depth": 1}).json()
        assert got == admin.subgraph("country.BRA", depth=1)

    def test_graph_is_layered_and_connected(self, client) -> None:
        """按 BFS 层级返回，且不得出现悬空边（两端都必须落在 nodes 里）。"""
        got = client.get(f"{PREFIX}/graph",
                         params={"focus": "country.BRA", "depth": 2, "limit": 500}).json()
        ids = {n["id"] for n in got["nodes"]}
        assert got["nodes"][0]["id"] == "country.BRA"
        assert got["nodes"][0]["depth"] == 0
        assert {n["depth"] for n in got["nodes"]} == {0, 1, 2}
        assert all(e["source"] in ids and e["target"] in ids for e in got["edges"])
        assert got["by_type"]["Country"] >= 2   # 2 跳会走到邻国

    def test_graph_direction_changes_the_neighbourhood(self, client) -> None:
        """`neighbors()` 只走出边——这个接口必须能把两个方向分开。"""
        both = client.get(f"{PREFIX}/graph",
                          params={"focus": "country.BRA", "depth": 1,
                                  "direction": "both"}).json()
        out = client.get(f"{PREFIX}/graph",
                         params={"focus": "country.BRA", "depth": 1,
                                 "direction": "out"}).json()
        assert len(both["nodes"]) == 41      # 1 出 + 39 入
        assert len(out["nodes"]) == 2        # country.BRA + region.south-america
        assert len(both["nodes"]) > len(out["nodes"])

    def test_graph_unknown_focus_is_404(self, client) -> None:
        r = client.get(f"{PREFIX}/graph", params={"focus": "ghost"})
        assert r.status_code == 404, r.text
        assert "实体不存在" in r.json()["detail"]

    def test_graph_bad_direction_is_400(self, client) -> None:
        r = client.get(f"{PREFIX}/graph",
                       params={"focus": "country.BRA", "direction": "sideways"})
        assert r.status_code == 400 and "direction" in r.json()["detail"]

    def test_graph_truncates_at_limit(self, client) -> None:
        got = client.get(f"{PREFIX}/graph",
                         params={"focus": "country.BRA", "depth": 2, "limit": 5}).json()
        assert len(got["nodes"]) == 5 and got["truncated"] is True

    def test_types_equals_admin(self, client) -> None:
        got = client.get(f"{PREFIX}/types").json()
        assert got == admin.entity_types()
        assert {t["type"] for t in got["types"]} >= {
            "Country", "Satellite", "SDG_Indicator", "HazardType"}

    def test_dataset_identity_in_every_view(self, client) -> None:
        """每个视图都要能回答"这张图对应哪个数据集版本"。"""
        for path, params in (("/search", {"q": "brazil"}), ("/types", {}),
                             ("/graph", {"focus": "country.BRA", "depth": 1}),
                             ("/entity/country.BRA", {})):
            ds = client.get(f"{PREFIX}{path}", params=params).json()["dataset"]
            assert ds["dataset_version"] == DATASET_VERSION
            assert len(ds["fingerprint"]) == 64
            assert ds["entities"] > 0 and ds["relations"] > 0


class TestUiPage:
    """视图页本身：能打开、脚本能解析、**它调的接口都真实存在**。"""

    def test_root_redirects_to_ui(self, client) -> None:
        r = client.get("/", follow_redirects=False)
        assert r.status_code in (307, 308) and r.headers["location"] == "/ui"

    def test_ui_page_served(self, client) -> None:
        r = client.get("/ui")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        body = r.text
        assert "GeoKG" in body and "<svg" in body

    def test_ui_page_is_self_contained(self, client) -> None:
        """单文件、离线可用：不得引用任何外部资源。

        GeoKG 常部署在没有外网的机器上，页面一旦依赖 CDN 就是白屏。这里查的是
        "有没有外部引用"而不是子串——页面注释里就写着"零 CDN"，用 `"cdn" not in body`
        会被自己的注释绊倒。
        """
        import re

        body = client.get("/ui").text
        for pattern in (r"<script[^>]+src=", r"<link[^>]+href=", r"<img[^>]+src=",
                        r"@import"):
            assert not re.search(pattern, body), f"页面引用了外部资源: {pattern}"
        assert "http://" not in body and "https://" not in body

    def test_every_endpoint_the_page_calls_exists(self, client) -> None:
        """页面里的每个 fetch 路径都必须真实存在。

        防的是"页面写了个不存在的接口，只有人打开浏览器才发现"——我没有浏览器，
        所以让测试代替点一遍。
        """
        import re

        routes = {r.path for r in client.app.routes if getattr(r, "path", "").startswith(PREFIX)}
        page = client.get("/ui").text
        # 取到模板字符串的收尾反引号为止，否则 /entity/${encodeURIComponent(id)}
        # 会在括号处被截断
        calls = set(re.findall(r"\$\{API\}(/[^`\"'\s]*)", page))
        assert calls, "页面里没有解析到任何 API 调用，测试本身失效了"
        for call in calls:
            # 页面里的模板变量（如 /entity/${encodeURIComponent(id)}）→ 路由占位符
            normalized = PREFIX + re.sub(r"\$\{[^}]*\}", "{entity_id}", call).rstrip("/")
            assert normalized in routes, f"页面调用了不存在的接口: {call} → {normalized}"

    def test_page_field_contract(self, client) -> None:
        """页面读的每个字段都必须在响应里——否则打开就是空白或 NaN。

        我没有浏览器可以点一遍，所以把 JS 实际读取的字段在这里逐个断言。
        """
        v = client.get(f"{PREFIX}/version").json()
        assert {"dataset_version", "fingerprint", "rows"} <= set(v)

        t = client.get(f"{PREFIX}/types").json()
        assert {"types", "relations"} <= set(t)
        assert {"type", "entities", "example"} <= set(t["types"][0])

        s = client.get(f"{PREFIX}/search", params={"q": "brazil", "limit": 5}).json()
        assert {"count", "returned", "truncated", "results", "dataset"} <= set(s)
        hit = s["results"][0]
        assert {"id", "name", "type", "score", "provenance"} <= set(hit)

        g = client.get(f"{PREFIX}/graph", params={"focus": "country.BRA"}).json()
        assert {"found", "focus", "nodes", "edges", "by_type", "truncated",
                "limit", "dataset"} <= set(g)
        assert {"id", "name", "type", "depth"} <= set(g["nodes"][0])
        assert {"source", "target", "relation"} <= set(g["edges"][0])
        assert g["nodes"][0]["depth"] == 0

        e = client.get(f"{PREFIX}/entity/country.BRA").json()
        assert {"found", "entity", "in", "out", "dataset"} <= set(e)
        assert {"id", "name", "type", "provenance", "properties"} <= set(e["entity"])
        assert {"relation", "entity"} <= set(e["in"][0])
        assert {"id", "name", "type"} <= set(e["in"][0]["entity"])

    def test_page_dom_ids_all_exist(self, client) -> None:
        """JS 里 `$("foo")` 引用的每个 id 都必须在 HTML 里定义。

        手写页面最常见的坏法就是 id 打错 → `null.addEventListener` → 整页不响应，
        而且只有打开浏览器才看得到。这里用静态检查代替点击。
        """
        import re

        body = client.get("/ui").text
        js = re.search(r"<script>(.*?)</script>", body, re.S).group(1)
        defined = set(re.findall(r'id="([^"]+)"', body))
        used = set(re.findall(r'\$\("([^"]+)"\)', js))
        assert used, "没有解析到 $() 调用，测试本身失效了"
        assert not (used - defined), f"引用了不存在的 DOM id: {sorted(used - defined)}"
