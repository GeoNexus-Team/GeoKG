# GeoKG 管理面设计

**决策**：CLI 先行，平台 Web 复用，统一设计管理面。
**状态**：CLI 与库 API 已实现并测试；Web 层为设计（未实现）。

---

## 一、分层：为什么 CLI 之上能长出 Web

```
┌─────────────────────────────────────────────────────────┐
│  sources.py     数据：来源 / 上游 / 许可 / 陈旧度策略      │  ← 唯一真相
├─────────────────────────────────────────────────────────┤
│  admin.py       逻辑：返回纯 dict 的库 API                │  ← 零打印、零网络
├──────────────────┬──────────────────────────────────────┤
│  cli.py         表现：人类可读表格                        │
│  （未来）api.py 表现：HTTP/JSON                          │
└──────────────────┴──────────────────────────────────────┘
```

**关键约束**：`admin.py` 只返回**可 JSON 序列化**的数据结构，不打印、不写文件。
因此未来的 Web 层只是把同一批函数挂到 HTTP 上，**业务逻辑零改动**。
`--json` 已经暴露了这个契约，可直接当接口样例用。

## 二、唯一真相：`sources.py`

此前"GeoKG 依赖哪些上游"分散在**三处**（8 个脚本的 URL 常量、
`provenance.SOURCES`、各脚本 `OUT` 与打包配置），彼此可能不一致。
现已合并为声明式登记表，CLI / 清单 / 许可汇总 / CI 门禁**全部从这里读**：

```python
Dataset(
    id="geonames-admin1",
    file="geonames_admin1.tsv",
    generator="fetch_geonames_admin1.py",
    upstream="https://download.geonames.org/export/dump/",
    license="Creative Commons Attribution 4.0 (CC BY 4.0)",
    attribution="GeoNames, https://www.geonames.org/",
    tier="T4",
    requires_network=True,
    staleness_days=30,          # GeoNames 每日更新
    sources=("geonames-admin1",),
    produces=("AdminRegion",),
)
```

**新增数据源只需加一条**，CLI/清单/许可/CI 全部自动覆盖。

## 三、CLI 能力（已实现）

```bash
geokg status [--strict]      # 整体状态 + 陈旧度告警
geokg verify [--drift]       # 数据完整性 + 溯源门禁（--drift 才联网）
geokg licenses               # 许可与署名汇总
geokg counts [--admin1]      # 计数口径 + 溯源审计
geokg manifest [--write]     # 查看/重算数据清单
geokg refresh <id>|--all     # 重新生成数据（联网）
geokg build [--admin1]       # 构建图谱并报告统计
geokg version                # 数据集版本与指纹
```

**只读命令刻意零网络、零副作用**——本机网络不稳，CI 也应能离线跑门禁。

实测输出（`geokg status`）：

```
    数据集                    分级  行数     体积    已过  阈值
  ✅  un-m49                 T1  249    20K   0d   180d
  ✅  geonames-admin1        T4  3,858  163K  0d   30d
  ✅  wmo-oscar-instruments  T2  1,244  508K  0d   90d
  ✅  esa-worldcover         T2  11     1K    0d   静态
  ...
  告警:
    ⚠️ [geonames-admin1] 数据已 90 天未更新（阈值 30 天，上游 https://...）
```

## 四、陈旧度策略

各上游更新频率差异极大，**统一阈值没有意义**，因此按源设置：

| 类型 | 数据集 | 阈值 | 理由 |
|------|--------|-----:|------|
| 高频联网 | GeoNames | **30 天** | 每日更新 |
| 中频联网 | WMO OSCAR（卫星/仪器） | **90 天** | 持续更新 |
| 慢变标准 | UN M49 | **180 天** | 偶发调整 |
| 年度框架 | UN SDG | **365 天** | 年度审议 |
| **静态** | WorldCover / Köppen / IRDR | **None** | 发布即定格，**永不陈旧** |

`None` 很重要：把 2014 年的 IRDR 报告按"天数"判过期是错的——它没有"新版本"。

## 五、数据集版本

两级标识，兼顾"好引用"与"可复现"：

| | 形式 | 用途 |
|---|---|---|
| **版本号** | `2026.09.1`（`sources.DATASET_VERSION`，人工递增） | 论文/方案里写"使用 GeoKG 数据集 2026.09.1" |
| **指纹** | `9cc336f4…`（9 个文件 sha256 排序后再哈希） | 精确复现：任何文件变动都会改变指纹 |

`manifest.json` 记录每个文件的 sha256 / 行数 / 取数日期 / 许可 / 上游，
随 wheel 一起分发，因此**安装后也能回答"这是什么版本、数据多旧"**。

⚠️ 清单的 `retrieved` **只在文件真正变化时更新**——否则每次重算都把日期刷成今天，
陈旧度告警就永远不会触发。

## 六、Web 管理面设计（未实现）

### 6.1 接口契约

因为 `admin.py` 返回纯 dict，HTTP 层只是薄路由：

| 方法 | 路径 | 对应 | 性质 |
|------|------|------|------|
| GET | `/api/v1/geokg/status` | `admin.status()` | 只读 |
| GET | `/api/v1/geokg/verify?drift=` | `admin.verify()` | 只读 |
| GET | `/api/v1/geokg/licenses` | `admin.licenses()` | 只读 |
| GET | `/api/v1/geokg/counts?levels=` | `admin.counts()` | 只读 |
| GET | `/api/v1/geokg/manifest` | `admin.manifest()` | 只读 |
| GET | `/api/v1/geokg/version` | 版本 + 指纹 | 只读 |
| POST | `/api/v1/geokg/manifest` | `admin.manifest(write=True)` | **变更** |
| POST | `/api/v1/geokg/refresh/{id}` | `admin.refresh(id)` | **变更·长任务** |
| POST | `/api/v1/geokg/build` | `admin.build()` | **变更·长任务** |

### 6.2 长任务必须异步

`refresh` 实测耗时：OSCAR 仪器 42 页 × ~5.6s ≈ **4 分钟**，卫星 35 页 ≈ **3.5 分钟**。
**绝不能用阻塞式请求**。

✅ **复用 SDK 已有能力**，不另造轮子：

- `geonexus.web.TaskManager` —— 后台任务 + 状态查询（本会话刚修过它的持久化竞态）
- SSE 事件推送 —— 实时进度

因此 `POST /refresh/{id}` 应立即返回 `task_id`，前端轮询或订阅 SSE。

### 6.3 鉴权

- **只读接口**：可匿名（数据本身就是公开的）
- **变更接口**（refresh / manifest / build）：必须鉴权
  - 复用 SDK 的 `APIKeyAuth` / `SecurityGateway`，不新造机制
  - `refresh` 会联网抓取并改写数据文件，风险最高，建议单独授权

### 6.4 与平台（Java 管理面）的衔接

管算分离下 Java 是管理面，但 Java 不应重写 GeoKG 逻辑，两种接法：

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | GeoKG 提供 FastAPI 服务（与执行面同构，`:8787`），Java 管理面通过 HTTP 调用，`portal.html` 增加"数据治理"页 | 逻辑单一实现；与执行面架构一致 |
| B | Java 内嵌 Python 进程 | 部署复杂、跨语言调试痛苦 |
| C | Java 重新实现一遍 | **不可接受**——两套逻辑必然漂移 |

**明确不建议**：把 GeoKG 管理功能做进 SDK CLI。SDK 不依赖 GeoKG 是我们已确立的
架构边界；若确需统一入口，应通过 entry-point 插件机制挂载，而非硬依赖。

## 七、明确不做

**不做实体编辑功能**（增删改 Entity）。GeoKG 是**生成物**，不是人工维护的库——
手动改一条就绕过了 `origin`/`source`/`license` 强制机制，整个溯源体系会被架空。
管理面是**"重新生成 + 校验"**导向，不是"编辑"导向。

需要人工干预时，正确做法是**改上游映射或生成脚本，然后 refresh**，
而不是直接改实体。

## 八、分阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| **1** | `sources.py` 登记表 + `admin.py` 库 API + `cli.py` | ✅ **已完成** |
| **2** | `manifest.json` 版本化 + 陈旧度告警 | ✅ **已完成** |
| **3** | **Web API**（FastAPI 薄路由 + 长任务复用 TaskManager/SSE + 鉴权） | ⬜ 待做 |
| **4** | 平台 `portal.html` 增加数据治理页（消费阶段 3 的接口） | ⬜ 待做 |
| **5** | CI 定时任务：`geokg status --strict` 检出陈旧数据 | ⬜ 待做 |

阶段 1–2 已完成并测试（142 项测试通过），阶段 3 可零逻辑改动地复用它们。
