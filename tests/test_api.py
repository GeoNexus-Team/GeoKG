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
