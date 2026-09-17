# GeoKG

GeoNexus 领域知识图谱**内容包** —— 只包含领域数据与内容专属 ETL，不包含图引擎。

本包是从 `GeoNexus-SDK` 中抽取出来的（2026 架构分层决策）：SDK 保持为可复用的
协议/契约工具集，领域内容独立版本化、独立发布。

## 分层边界

```
┌──────────────────────────────────────────────┐
│  GeoKG（本仓库）                              │
│    reference_data.py   SDG / 国家 / 卫星 / 概念 │
│    gazetteer.py        星座展开、扩充行政区划    │
│    admin1_global.py    86 国 / 1,436 个一级区划  │
│    ingest.py           内容专属 ETL            │
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
print(kg.stats())        # {'entities': 14736, 'relations': 21545, ...}
```

`monitor_levels` 决定派生任务空间的规模：

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
| ② ① + 系统性展开 | **7,382** | 0% |  GeoNames 行政区 + 扩展词汇（卫星已改由 OSCAR 提供） |
| ③ ② + 国家级监测任务空间 | **14,603** | 45.3% | 加「国家 × 指标」 |
| ④ ③ + 次国家级监测任务空间 | **126,485** | **93.2%** | 加「一级行政区 × 指标」 |

三个来源：

| origin | 含义 |
|--------|------|
| `curated` | 人工整理的参考表（SDG 框架、国家、卫星目录、概念） |
| `expanded` | 由策展表**系统性展开**（星座成员如 Sentinel-2A/2B/2C、扩展行政区、扩展词汇）——每行可追溯到策展表的一行，但不是逐条人工核定 |
| `derived` | 由交叉积/规则**派生**（`MonitoringUnit`、`DataRequirement`）——表达"某国需监测某指标"的任务空间，不含任何观测值 |

> ⚠️ **考核口径提示**：考核要求「GeoKG ≥2 万实体」。**只有口径 ④ 达标，而其中
> 92.8% 是交叉积派生**；口径 ③ 仅 14,736（目标的 74%），口径 ② 为 8,327（41%）。
> 因此当前**不存在既能达标又完全由策展内容支撑的口径**——要么取得考核方对
> 派生任务空间的认可，要么补充真实策展数据（见下）。

`run_full_ingestion` 的 `monitor_levels` 语义：

| 取值 | 效果 |
|------|------|
| `None`（默认） | `["country", "admin1"]` —— **最大配置** |
| `[]` | 不生成监测单元（等价 `include_monitoring=False`） |
| `["country"]` | 仅国家级 |
| `["country", "admin1"]` | 国家级 + 次国家级 |

> 旧版把 `monitor_levels or [...]` 写在默认值上，导致显式 `[]` 被静默替换为
> **最大**配置，使"纯策展"数字无法通过该参数取得。已修正并加回归测试。

## 数据规模

| 数据集 | 条目数 |
|--------|--------|
| SDG 目标 / 具体目标 / 指标 | 17 / 169 / 256 |
| 国家/地区（UN M49） | 249 |
| 卫星（WMO OSCAR/Space） | 1,044 |
| 仪器（WMO OSCAR/Space） | 1,244 |
| 一级行政区划（GeoNames） | 3,858 |
| 土地覆盖（ESA WorldCover） | 11 |
| 气候（Köppen-Geiger） | 35 |
| 灾害（IRDR） | 73 |
| 术语表 | 294（其中 218 条为 GeoKG 自编，76 条引外部来源） |
| 术语表（逐条标注来源） | 294 |

## 来源覆盖

**7,382 条实体全部带可追溯来源**（审计初期仅 9.3%）。
逐条可查：`python scripts/counting_basis.py` 会列出每个来源的条目数。

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

## 数据来源审计

**47.3% 的实体来源未核实**（P0 前为 90.7%）——详见 [`docs/provenance-audit.md`](docs/provenance-audit.md)。

从 2026-09 起，**每条实体强制带** `origin` / `source` / `license` / `retrieved`，
缺失即 CI 失败；未核实来源必须显式标 `UNVERIFIED`，不得静默混入策展数据。

```bash
python scripts/counting_basis.py     # 口径 + 溯源审计；字段缺失则退出码 1
```

## 测试

```bash
pytest tests -q     # 112 tests
```

## 相关仓库

- `GeoNexus-SDK` —— 协议、契约、图原语、CAFE、双 Agent、安全网关
- `GeoNexus-Platform` —— Web 前端、Java 管理面、互操作
