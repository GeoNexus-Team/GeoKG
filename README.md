# GeoKG

GeoNexus 领域知识图谱**内容包** —— 只包含领域数据与内容专属 ETL，不包含图引擎。

本包是从 `GeoNexus-SDK` 中抽取出来的（2026 架构分层决策）：SDK 保持为可复用的
协议/契约工具集，领域内容独立版本化、独立发布。

## 分层边界

```
┌──────────────────────────────────────────────┐
│  GeoKG（本仓库）                              │
│    sources.py          9 个数据源的声明式登记表 │
│    reference_data.py   SDG / 国家 / 卫星 / 概念 │
│    gazetteer.py        星座展开、扩充行政区划    │
│    admin1.py           GeoNames 一级行政区划     │
│    ingest.py           内容专属 ETL            │
│    admin.py / cli.py / api.py   管理面三层      │
└───────────────────┬──────────────────────────┘
                    │ 单向依赖
                    ▼
┌──────────────────────────────────────────────┐
│  geonexus-sdk                                 │
│    geonexus.kg          KnowledgeGraph 图原语  │
│    geonexus.kg.storage  gzip / NDJSON / 增量追加│
│    geonexus.kg.neo4j_store  Neo4j 后端         │
│    geonexus.adapters.osm    OSM 适配器（可选）  │
└──────────────────────────────────────────────┘
```

**反向依赖为零**：SDK 不导入本包。这样领域数据更新不会导致 SDK 版本变更，
SDK 也可以在没有本包的情况下独立安装。

## 安装

```bash
pip install -e .            # 需要先安装 geonexus-sdk
pip install -e ".[osm]"     # 含 OSM 摄入路径（ingest_from_osm）
```

> **Python 版本**：本包声明 `>=3.10`（与 SDK 一致）。若需在 3.9 环境安装
> （例如本地主开发环境），用
> `pip install -e . --ignore-requires-python --no-deps`。

## 用法

```python
from geonexus.kg import KnowledgeGraph
from geokg.ingest import run_full_ingestion

kg = KnowledgeGraph()
report = run_full_ingestion(kg, monitor_levels=["country"])
print(kg.stats())        # {'entities': 14603, 'relations': 20893, ...}
```

`monitor_levels` 决定派生任务空间的规模：

| 取值 | 效果 |
|------|------|
| `None`（默认） | `["country", "admin1"]` —— **最大配置** |
| `[]` | 不生成监测单元（等价 `include_monitoring=False`） |
| `["country"]` | 仅国家级 |
| `["country", "admin1"]` | 国家级 + 次国家级 |

> 旧版把 `monitor_levels or [...]` 写在默认值上，导致显式 `[]` 被静默替换为
> **最大**配置，使"纯策展"数字无法通过该参数取得。已修正并加回归测试。

## 计数口径

实体来源**写在实体本身**（`properties["origin"]`），因此任何口径都能从数据复现，
不靠文档解释：

```bash
python scripts/counting_basis.py              # 含国家级监测
python scripts/counting_basis.py --admin1     # 含次国家级监测
python scripts/counting_basis.py --no-monitoring
```

| 口径 | 实体数 | 派生占比 | 说明 |
|------|--------|----------|------|
| ① 基础策展参考数据 | **3,524** | 0% | 人工整理的参考表 |
| ② ① + 系统性展开 | **7,382** | 0% | GeoNames 行政区（3,858）+ 扩展词汇（卫星已改由 OSCAR 提供） |
| ③ ② + 国家级监测任务空间 | **14,603** | 49.4% | 加「国家 × 指标」 |
| ④ ③ + 次国家级监测任务空间 | **126,485** | **94.2%** | 加「一级行政区 × 指标」 |

三个来源：

| origin | 含义 |
|--------|------|
| `curated` | 人工整理的参考表（SDG 框架、国家、卫星目录、概念） |
| `expanded` | 由策展表**系统性展开**（扩展行政区、扩展词汇）——每行可追溯到策展表的一行，但不是逐条人工核定 |
| `derived` | 由交叉积/规则**派生**（`MonitoringUnit`、`DataRequirement`）——表达"某国需监测某指标"的任务空间，不含任何观测值 |

> ⚠️ **考核口径提示**：考核要求「GeoKG ≥2 万实体」。**只有口径 ④ 达标，而其中
> 94.2% 是交叉积派生**；口径 ③ 为 14,603（目标的 73%），口径 ② 为 7,382（37%）。
> 因此当前**不存在既能达标又完全由策展内容支撑的口径**——要么取得考核方对
> 派生任务空间的认可，要么补充真实策展数据。

## 数据规模

9 个数据文件，**7,245 行**（`geokg manifest` 可逐项复核）：

| 数据集 | 条目数 | 分级 |
|--------|-------:|------|
| UN M49 国家/地区 | 249 | T1 |
| UN SDG 目标 / 具体目标 / 指标 | 17 / 169 / 251 | T1 |
| 卫星（WMO OSCAR/Space） | 1,044 | T2 |
| 仪器（WMO OSCAR/Space） | 1,244 | T2 |
| 一级行政区划（GeoNames） | 3,858 | T4 |
| 土地覆盖（ESA WorldCover） | 11 | T2 |
| 气候（Köppen-Geiger） | 35 | T3 |
| 灾害（IRDR） | 73 | T3 |
| 术语表 | 294（218 条 GeoKG 自编 + 76 条引外部来源） | 混合 |

> SDG 采用联合国官方框架（17 目标 / 169 具体目标 / 251 指标）。
> 此前记为 256 是重复计数所致；`geokg verify` 现在会与官方数量对账。

## 来源覆盖

**100% 的实体带可追溯来源，未核实为 0 条**——每条实体强制带
`origin` / `source` / `source_tier` / `license` / `retrieved`，缺失即 CI 失败。
逐项可查：

```bash
python scripts/counting_basis.py     # 按来源与分级列出条目数
```

## 卫星与仪器目录（WMO OSCAR/Space）

1,044 颗卫星，来自 WMO 官方数据库（T2 官方机构）：
406 在轨运行 / 131 规划中 / 148 个机构，
1,018 颗带仪器记录。

此前是 114 条无出处的手写记录 + 2,863 条按规则合成的"星座展开"——**已全部删除**。
改用真实目录后实体数净减少，这是正确的方向。

许可（OSCAR 免责声明）：可自由使用与再分发，**须致谢 WMO**。

## L3 地球系统本体

补上"**这是什么**"这一层——此前图谱只能回答"叫什么、在哪"。

| 领域 | 来源 | 分级 | 条目 |
|------|------|------|-----:|
| 土地覆盖 | ESA WorldCover（FAO LCCS 方案） | T2 官方机构 | 11 |
| 气候 | Köppen-Geiger（Beck et al. 2018） | T3 同行评议 | 35 |
| 灾害 | IRDR Peril Classification (2014) | T3 技术报告 | 73 |

这三个分类只以论文/报告形式发布，无官方机器可读清单，因此由
`scripts/build_l3_ontology.py` **转录**并标注引用，署名随实体分发。

## 管理工具

安装后可用 `geokg` 命令（也可 `python -m geokg.cli`）：

```bash
geokg status [--strict]     # 整体状态 + 陈旧度告警
geokg verify [--drift]      # 数据完整性 + 溯源门禁（--drift 才联网）
geokg licenses              # 许可与署名汇总
geokg counts [--admin1]     # 计数口径 + 溯源审计
geokg manifest [--write]    # 查看/重算数据清单
geokg refresh <id>|--all    # 重新生成数据（联网）
geokg build [--admin1]      # 构建图谱并报告统计
geokg version               # 数据集版本与指纹
```

只读命令**零网络、零副作用**，可离线与 CI 中使用；加 `--json` 输出结构化结果。

数据集版本 `2026.09.1`，指纹见 `geokg version`。陈旧度按源设置阈值
（GeoNames 30 天 / OSCAR 90 天 / 静态数据集永不陈旧）。

### HTTP 管理面

平台 Web 不需要依赖本包的 Python 代码，起一个独立端口的只读/变更服务即可：

```bash
export GEOKG_API_KEYS='key-1,key-2'   # 不设则变更接口 503（失败关闭）
geokg-api --port 8788                 # 默认只监听 127.0.0.1；/docs 有 OpenAPI
```

只读接口（`/api/v1/geokg/{status,verify,licenses,counts,manifest,version}`）免鉴权，
与 CLI 读**同一批** `admin.py` 函数——不存在两套逻辑。变更接口
（`POST manifest|refresh|build`）需 `X-API-Key`，长任务返回 `task_id`，
可轮询 `GET /tasks/{id}` 或订阅 SSE `GET /tasks/{id}/events`。

架构、鉴权与长任务设计见 [`docs/management-plane.md`](docs/management-plane.md)。

### 快速自检

```bash
pytest tests -q                              # 190 项测试
python -m geokg.cli verify                   # 数据完整性 + 溯源门禁（离线）
python -m geokg.cli status --strict          # CI 门禁：有陈旧/缺失数据即非零退出
curl -s localhost:8788/api/v1/geokg/version  # 数据集版本与指纹
```

> 测试与脚本的参考数据路径是相对 `src/geokg/data/` 的，请在**仓库根目录**运行。

## 数据来源审计

**未核实来源 0 条（100% 可追溯）**，审计起点为 90.7% 未核实。
完整过程与判定标准见 [`docs/provenance-audit.md`](docs/provenance-audit.md)。

从 2026-09 起，**每条实体强制带** `origin` / `source` / `license` / `retrieved`，
缺失即 CI 失败；未核实来源必须显式标 `UNVERIFIED`，不得静默混入策展数据。

```bash
python scripts/counting_basis.py     # 口径 + 溯源审计；字段缺失则退出码 1
```

## 测试

```bash
pytest tests -q     # 190 tests
```

CI（`.github/workflows/ci.yml`）跑三件事：测试、`ruff check`、以及管理门禁
（`geokg verify` + `geokg status --strict`，全部离线）。另外每周一 02:00 UTC
定时跑一次 `status --strict`，这样**上游数据变旧不需要有人推送也能被发现**。

HTTP 管理面另有一条冒烟测试：真起一个 uvicorn 进程、真实端口绑定，断言无 key
的变更请求返回 401——这三件事 `TestClient` 都覆盖不到。

## 相关仓库

- `GeoNexus-SDK` —— 协议、契约、图原语、CAFE、双 Agent、安全网关、Web BFF
- `GeoNexus-Platform` —— Node 门户、Java 管理面、Python 执行面、互操作

三个仓库可拼成一个本地可测的栈（执行面 `:8787`、GeoKG `:8788`、Registry
`:8790`、SDK Web `:8900`、Java `:8080`、Node 门户 `:3100`）。GeoKG 与它们
**只有单向依赖**，因此也可以单独使用：所有管理面能力只依赖本仓库 + `geonexus.kg`。
