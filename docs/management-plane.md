# GeoKG 管理面设计

**决策**：CLI 先行，平台 Web 复用，统一设计管理面。
**状态**：CLI / 库 API / HTTP 管理面已实现并测试；平台页（阶段 4）为设计。

---

## 一、分层：为什么 CLI 之上能长出 Web

```
┌─────────────────────────────────────────────────────────┐
│  sources.py     数据：来源 / 上游 / 许可 / 陈旧度策略      │  ← 唯一真相
├─────────────────────────────────────────────────────────┤
│  admin.py       逻辑：返回纯 dict 的库 API                │  ← 零打印、零网络
├──────────────────┬──────────────────────────────────────┤
│  cli.py         表现：人类可读表格                        │
│  api.py         表现：HTTP/JSON                          │
└──────────────────┴──────────────────────────────────────┘
```

**关键约束**：`admin.py` 只返回**可 JSON 序列化**的数据结构，不打印、不写文件。
因此 Web 层只是把同一批函数挂到 HTTP 上，**业务逻辑零改动**。
`--json` 已经暴露了这个契约，可直接当接口样例用。

**这条约束是被测试钉住的**：`tests/test_api.py::TestReadOnly` 逐个把 HTTP 响应
与 `admin.*()` 的返回值做相等比较（剔除时间戳字段）。谁在路由里另写一套计算，
测试立刻失败。

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

## 六、HTTP 管理面（已实现）

### 6.1 启动

```bash
export GEOKG_API_KEYS='key-1,key-2'   # 不设则变更接口返回 503（见 6.3）
geokg-api --port 8788                 # 独立端口，默认只监听 127.0.0.1
```

**为什么独立端口**：GeoKG 是内容包而不是 SDK 的一部分（依赖单向
`geokg → geonexus`），管理面沿用同一原则——SDK 的 Web 服务不需要知道
GeoKG 存在。默认 `8788`，避开 SDK Web 的 `8787/8790`。

### 6.2 接口契约（14 条路由）

| 方法 | 路径 | 对应 | 性质 |
|------|------|------|------|
| GET | `/api/v1/geokg/health` | 存活探针（不读数据文件） | 免鉴权 |
| GET | `/api/v1/geokg/status` | `admin.status()` | 只读 |
| GET | `/api/v1/geokg/verify` | `admin.verify(drift=False)` | 只读 |
| GET | `/api/v1/geokg/licenses` | `admin.licenses()` | 只读 |
| GET | `/api/v1/geokg/counts?level=&level=` | `admin.counts()` | 只读（较重） |
| GET | `/api/v1/geokg/manifest` | `admin.manifest(write=False)` | 只读 |
| GET | `/api/v1/geokg/version` | 版本 + 指纹（精简） | 只读 |
| POST | `/api/v1/geokg/manifest` | `admin.manifest(write=True)` | **变更** |
| POST | `/api/v1/geokg/refresh` | `admin.refresh()` | **变更·长任务** |
| POST | `/api/v1/geokg/build` | `admin.build()` | **变更·长任务** |
| GET | `/api/v1/geokg/tasks` | 任务列表 | 鉴权 |
| GET | `/api/v1/geokg/tasks/{id}` | 任务状态 | 鉴权 |
| POST | `/api/v1/geokg/tasks/{id}/cancel` | 协作式取消 | 鉴权 |
| GET | `/api/v1/geokg/tasks/{id}/events` | 进度 SSE | 鉴权 |

变更接口返回 `202` + `{task_id, poll, events}`，客户端据此轮询或订阅。
OpenAPI 文档在 `/docs`。

**`drift` 刻意不上 HTTP**：漂移检查要联网、要跑生成脚本的 `--check`，属于运维
批处理（`geokg verify --drift` 或定时 CI），不该挂在 HTTP 请求上。

### 6.3 鉴权：只读放开，变更**失败关闭**

只读接口免鉴权——它们只回送随包分发的公开参考数据，不含机密。

变更接口复用 SDK 的 `APIKeyAuth`（`X-API-Key` 头），键从 `GEOKG_API_KEYS`
读取。⚠️ **这里有一处刻意偏离 SDK 默认**：

> SDK 的 `APIKeyAuth` 在键集为空时**放行**（SDK 里真正的门是 JWT，API key 只是
> 转发给节点的凭据）。但 GeoKG 的变更接口会**执行子进程、覆写数据文件**，
> 放行等于把写权限敞开给整个网段。因此键集为空时本服务**拒绝**变更请求（503），
> 并在提示里告诉运维怎么配置。

宁可运维看到"变更不可用"，也不要静默地"变更人人可用"。
`tests/test_api.py::TestAuth::test_fails_closed_without_configured_keys` 钉住这一点。

### 6.4 长任务：复用 SDK，不另造轮子

`refresh` 实测耗时：OSCAR 仪器 42 页 × ~5.6s ≈ **4 分钟**，卫星 35 页 ≈ **3.5 分钟**。
**绝不能用阻塞式请求**。因此复用 `geonexus.web.TaskManager`：

- `POST /refresh` → 线程池，立即返回 `task_id`
- `GET /tasks/{id}` → 轮询状态
- `GET /tasks/{id}/events` → SSE，**仅状态变化时发帧**，空闲 15s 发心跳注释
  （用 `asyncio.sleep` 而非 `time.sleep`——后者会卡住事件循环，一个订阅者就能
  拖垮整个服务）

**两道防重**：

1. **同类不并发**：同一 kind（如 `refresh:geonames-admin1`）已有任务在跑时，
   第二次提交返回 `409`。任务结束必须释放槽位，否则"刷新"会永久失效——
   这一条也被测试覆盖。
2. **写操作串行**：`refresh` 与 `build` 共用一把锁。两个刷新同时写同一个 TSV，
   或刷新中途建图读到半截文件，都会产生难以复现的坏数据。

**取消是协作式的**：`refresh` 只在**数据集之间**检查是否取消（生成脚本是子进程，
杀不掉），所以取消的语义是"当前这个刷完就停，不再开下一个"。为此
`admin.refresh` 增加了可选的 `checkpoint` 回调（CLI 不传，HTTP 用它同时做进度
上报与取消检查）；**中止时不写回清单**——只刷了一半就落指纹，会把没刷的部分
一并登记成"当前版本"，返回的指纹还会与磁盘不符。因此中止与失败时
`result.manifest` 一律为 `null`（= 清单未变）。

**任务状态只存内存**：进程重启后线程池已死，把旧记录读回来标"running"只会误导。

### 6.5 只用 HTTP 就拿得到的治理视图

`GET /status` 在 `admin.status()` 之上**附加**一个 `inflight` 字段（HTTP 层字段，
不进库 API 契约），客户端据此判断此刻读到的只读数据是否正被写入，避免把中间
状态当成结论。

`GET /status` 的 `ok_strict` 是**严格门禁的唯一判据**，CLI `--strict` 与 HTTP
共用它。此前 CLI 靠 `"未更新" in message` 这样的中文子串匹配来推断门禁——
改一次文案门禁就静默失效。现在每条告警带结构化的 `reason`
（`missing` / `stale` / `drift`）与 `gate` 布尔值：数据缺失和陈旧参与门禁，
**指纹漂移不参与**（它是"忘了重算清单"，不是数据不健康）。

### 6.6 与平台（Java 管理面）的衔接

管算分离下 Java 是管理面，但 Java 不应重写 GeoKG 逻辑，三种接法：

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | GeoKG 提供独立 FastAPI 服务（`:8788`），Java 管理面通过 HTTP 调用，`portal.html` 增加"数据治理"页 | 逻辑单一实现；与执行面架构一致 |
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
| **3** | **HTTP 管理面**（FastAPI 薄路由 + 长任务复用 TaskManager/SSE + 鉴权） | ✅ **已完成** |
| **4** | 平台 `portal.html` 增加数据治理页（消费阶段 3 的接口） | ⬜ 待做 |
| **5** | CI 定时巡检：`geokg status --strict` 检出陈旧数据 | ✅ **已完成**（每周一 02:00 UTC） |

阶段 1–3、5 已完成并测试（阶段 3 零逻辑改动地复用了 `admin.py`）。阶段 4 只是
前端页面 + 调用上面那批接口。

阶段 5 的意义在于**不依赖任何人推送**：上游更新、数据变旧，定时任务就会失败并
通知。判据是现成的 `ok_strict`，因此定时任务与 push/PR 门禁不可能给出不同结论。
