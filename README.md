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

| 配置 | 实体数 | 说明 |
|------|--------|------|
| `[]` | 8,327 | **纯策展参考数据** |
| `["country"]` | 14,736 | 加国家级监测单元 |
| `["country", "admin1"]` | 116,236 | 加次国家级监测任务空间 |

> ⚠️ **计数口径**：8,327 是策展数据；14,736 / 116,236 中包含由
> `MonitoringUnit` / `DataRequirement` **系统性派生**的实体，它们不是人工
> 策展内容。对外报数时请注明口径，不要不加限定地引用 116,236。

## 数据规模

| 数据集 | 条目数 |
|--------|--------|
| SDG 目标 / 具体目标 / 指标 | 17 / 169 / 256 |
| 国家 | 221 |
| 卫星 / 波段 | 114 / 781 |
| 一级行政区划（参考 + 扩充） | 775 + gazetteer 扩展 |
| 概念 | 117 + 扩展 |

## 测试

```bash
pytest tests -q     # 34 tests
```

## 相关仓库

- `GeoNexus-SDK` —— 协议、契约、图原语、CAFE、双 Agent、安全网关
- `GeoNexus-Platform` —— Web 前端、Java 管理面、互操作
