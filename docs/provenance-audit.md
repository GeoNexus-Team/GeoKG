# GeoKG 数据来源审计

**日期**：2026-09-16
**范围**：`geokg` 包内全部策展/展开数据（不含派生的监测任务空间）
**触发**：决策"数据来源的可信度与精准性需要得到保证"

---

## 一、结论摘要

| 指标 | 数值 |
|------|------|
| 实体总数（口径②） | **7,590** |
| **来源已核实** | **703（9.3%）** |
| **来源未核实** | **6,887（90.7%）** |
| 缺少必需溯源字段 | **0**（强制机制已生效） |

**核心结论：目前 GeoKG 有 90.7% 的数据无法回答"这条数据凭什么可信"。**
它们不是错的数据，但**不可审计**——没有出处、版本、许可与检索日期，
因此不能出现在正式材料里，也无法在评审追问时自证。

此外，审计过程中发现一起**已发生的合规问题**：一级行政区数据自述来自 GADM，
而 GADM 许可禁止再分发。**已处置**（见 §三）。

---

## 二、逐来源清单

### 已核实（T1 规范源）——703 条

| 来源 id | 实体 | 条目 | 版本 | 许可 | 问题 |
|---------|------|-----:|------|------|------|
| `un-sdg-framework` | SDG_Goal / Target / Indicator | 442 | A/RES/71/313 | UN 公开文件 | ⚠️ 指标数 244 与原文档声明（231/256）不符，**待与官方清单核对** |
| `iso-3166-1` | Country / Region | 248 | ISO 3166-1:2020 | 代码表可自由使用 | ⚠️ 收录 221 条，ISO 官方分配 **249** 条，缺口 28 条待核实 |
| `geokg-authored` | Skill / ConceptCategory | 13 | v0.1.0 | Apache-2.0 | 本仓库自有，非外部引用 |

### 未核实（T5）——6,887 条

| 来源 id | 实体 | 条目 | 代码中的说明 | 缺失项 |
|---------|------|-----:|--------------|--------|
| `unverified-satellite-constellations` | Satellite / Band / Organization | 2,863 | 星座展开（`gazetteer.expand_satellite_constellations`） | 出处、版本、日期 |
| `unverified-extended-admin1` | AdminRegion | 2,763 | "按各国官方一级行政区名称整理" | **具体依据哪份官方名单** |
| `unverified-satellites` | Satellite / Band / Organization | 882 | "主要光学与 SAR 卫星" | 出处、版本、日期 |
| `unverified-extended-concepts` | Concept / ConceptCategory | 255 | 扩充词汇 | 出处 |
| `unverified-concepts` | Concept | 124 | "GeoNexus 领域本体" | 出处 |

**共同特征**：这些数据是**作者自行整理**的。它们未必不准确，但
"自行整理"不等于"可审计"——评审无法复核，我们也无法在版本升级时判断是否过期。

---

## 三、GADM 事件（已处置）

### 事实

`reference_data.py` 两处自述一级行政区来自 GADM：

```
- 行政区划：主要国家一级行政区（GADM level-1 结构）
# 主要国家一级行政区（GADM level-1 抽样，用于区域层级实体）
```

涉及 **775 条 / 28 国**。

### 为什么必须处置

[GADM 许可](http://gadmaps.s3-website-us-west-1.amazonaws.com/license.html) 原文：

> "The data are freely available for **academic use and other non-commercial use**.
> **Redistribution or commercial use is not allowed without prior permission.**"

**提交进公开 GitHub 仓库即构成再分发**，与"允许学术使用"无关——学术使用许可的是
*使用*，不是*再分发*。

### 处置（决策 2c：先移出仓库待处理）

| 动作 | 结果 |
|------|------|
| 数据隔离到仓库之外 | `tmp/quarantine/reference_data_gadm_admin1.py`（11,899 bytes，775 条 / 28 国，内容完整保留） |
| 从 `reference_data.py` 移除 | 该模块由 568 行降至 442 行 |
| 从摄入管线移除 | 删除 `ingest_admin1()` 及其管线调用 |
| 从包导出移除 | `ADMIN1_REGIONS`、`ingest_admin1` 不再导出 |
| 加回归护栏 | `test_gadm_admin1_removed` 断言该数据不得回到包内 |
| 登记表护栏 | `test_no_redistribution_forbidden_source_registered` 防止 GADM 作为可用来源被登记 |

### 影响

| 指标 | 处置前 | 处置后 | 变化 |
|------|-------:|-------:|-----:|
| 口径② 策展+展开 | 8,327 | **7,590** | −737 |
| 口径④ 含次国家级监测 | 116,236 | **94,126** | −22,110 |
| AdminRegion 实体 | 3,500 | 2,763 | −737 |
| 与 2 万目标差距 | 11,673 | **12,410** | +737 |

> 口径④ 降幅远大于 737，因为监测任务空间是按行政单元**派生**的——
> 少 737 个一级行政区，就少了约 2.1 万个派生的监测单元。
> 这正是"派生数据不该计入实体数"的直观体现。

**待处理**（三选一，未决）：
- (a) 改由 **GeoNames admin1**（3,865 条，CC BY 4.0）重新获取并标注来源
- (b) 改由 **ISO 3166-2** 重新获取
- (c) 逐条核实后重写来源字段（成本最高，收益最低）

建议 **(a)**：来源许可最干净，且已在 admin2 调研中验证可下载。

---

## 三·补、P0 还债结果（已完成）

两项 P0 已执行完毕。

### 国家表改用 UN M49（T1）

| | 之前 | 之后 |
|---|---|---|
| 来源 | 无出处（文档称 ISO 3166-1，实收 221 条） | **UN M49**（联合国官方分类标准） |
| 条目 | 221 | **249** |
| 区域层级 | 2 级，且 Sub-region 与 Intermediate Region 混用 | **3 级**（Region → Sub-region → Intermediate Region） |
| 附加属性 | 无 | **LDC / LLDC / SIDS / 发达-发展中**（44 / 32 / 53） |

**为什么是 249 而不是 M49 的 248**：UN M49 的 248 行**不含台湾**
（只有 CHN / HKG / MAC），ISO 3166-1 则分配了 `TW` / `TWN`。本方案保留 TWN，
并在 `scripts/fetch_un_m49.py` 的 `ISO_ONLY` 中**显式记录**这一口径选择，
使总数与 ISO 口径一致。

⚠️ **这涉及政治敏感表述，请你确认**：如需与 UN M49 完全一致（248，不含 TWN），
删掉 `ISO_ONLY` 中那一行即可。

**顺带修正一处数据错误**：旧数据把 Kenya 直接挂在 "Eastern Africa"，
但按 UN M49，"Eastern Africa" 是 **Intermediate Region**，其 Sub-region
应为 "Sub-Saharan Africa"。现已按标准建成三级层级（29 个区域节点：5/17/7）。

### 一级行政区改用 GeoNames（T4，CC BY 4.0）

三个不可审计的来源**全部清除**：

| 来源 | 条目 | 处置 |
|------|-----:|------|
| `reference_data.ADMIN1_REGIONS`（GADM） | 775 | 已隔离（仓库之外） |
| `gazetteer.ADMIN1_EXTENDED`（无出处） | 1,327 | 已删除，隔离留存 |
| `admin1_global.py`（无出处） | 1,436 | 已删除，隔离留存 |
| **合计（去重后）** | **2,763** | → 由 GeoNames 取代 |

| | 之前 | 之后 |
|---|---|---|
| 来源 | 三者均不可审计 | **GeoNames**（CC BY 4.0，可商用、无 share-alike） |
| 条目 | 2,763 | **3,858** |
| 覆盖国家 | 174 | **227** |
| 实体 id | 名称 slug（同国重名会**静默丢失**） | **geonameid**（全局唯一，有测试护栏） |
| 可复现 | 否 | 是（`scripts/fetch_geonames_admin1.py`） |

### 效果（实测）

| 指标 | P0 前 | P0 后 |
|------|------:|------:|
| 实体总数（口径②） | 7,590 | **8,715** |
| **来源已核实** | 703（9.3%） | **4,591（52.7%）** |
| 来源未核实 | 6,887（90.7%） | **4,124（47.3%）** |
| 口径① 基础策展 | 1,709 | 1,739 |
| 口径③ +国家级监测 | 13,999 | 15,936 |
| 口径④ +次国家级监测 | 94,126 | 127,818 |

**已核实比例 9.3% → 52.7%**，达到 P0 的预期目标。

### 剩余未核实（4,124 条，P1）

| 来源 | 条目 | 计划 |
|------|-----:|------|
| 星座展开 | 2,863 | 追溯到 NASA/ESA/USGS 任务文档（T2） |
| 卫星目录 | 882 | 同上 |
| 扩充词汇 | 255 | 并入 L3 本体（土地覆盖/气候/灾害），逐项引用 |
| 概念表 | 124 | 同上 |

另：SDG 指标的 244 与官方清单（231）仍待核对。

---

## 四、已建立的强制机制（决策 4）

从本次起，**任何实体缺少 `source` / `license` / `retrieved` / `origin` 都会失败**：

```python
properties = {
    "origin":       "curated",              # 口径分层
    "source":       "un-sdg-framework",     # 稳定来源 id
    "source_tier":  "T1",                   # T1..T4；未核实为 T5
    "license":      "UN 公开文件",
    "retrieved":    "2026-09-16",
}
```

三层保障：

| 层 | 机制 | 失败行为 |
|----|------|----------|
| 摄入期 | `_ProvenanceKG` 包装每个 `add_entity`，自动盖来源戳 | 未登记的 source id → `KeyError` |
| 检查期 | `check_required_fields()` | 字段缺席即计入 `missing_fields` |
| CI 门禁 | `scripts/counting_basis.py` | `missing_fields` 非空 → **退出码 1** |

**关键设计：未核实必须显式写 `UNVERIFIED`，不允许留空。** 留空会被当作遗漏，
而 `UNVERIFIED` 是"已登记的债务"——它会被统计、被报告、被要求偿还，
但不会静默混进策展数据冒充已核实。

来源分级（`provenance.SOURCES`）：

| 级 | 含义 | 例子 |
|----|------|------|
| T1 | 规范/标准，定义即真理 | UN SDG 框架、ISO 3166、IOGP EPSG、OGC |
| T2 | 官方机构 | NASA/ESA/USGS、FAO、WMO |
| T3 | 同行评议共识 | Köppen-Geiger、WRB 土壤 |
| T4 | 聚合/社区 | GeoNames、OSM、Wikidata |
| T5 | **未核实，不得对外引用** | 当前 6,887 条 |

---

## 五、补齐计划（按性价比排序）

| 优先级 | 数据 | 动作 | 预计结果 |
|--------|------|------|----------|
| **P0** | AdminRegion 2,763 | 改用 GeoNames admin1（3,865 条，CC BY 4.0，T4）重建 | 2,763 → ~3,865，且**可审计** |
| **P0** | Country 221 → 249 | 补齐 ISO 3166-1 缺失的 28 条 | 248 → 276 |
| **P1** | SDG 指标 244 | 与 UN 官方清单核对，修正文档声明 | 消除数字不一致 |
| **P1** | 卫星 1,345 + 波段 3,156 | 逐条追溯到 NASA/ESA/USGS 任务文档（T2） | 全层转 T2 |
| **P2** | Concept 365 | 追溯或改为引用 FAO LCCS / GCMD / ENVO（T1/T2） | 见 L3 本体计划 |

**P0 优先的原因**：这两项规模最大、来源最明确（GeoNames/ISO 都是现成可下载的规范源），
且完成后就能把"策展口径"从 9.3% 已核实拉升到 **50%+**。

> 注意：这与"先审计、后扩容"的决策一致——**先还债，再扩张**。
> 在 90.7% 未核实的基础上继续加数据，只会扩大不可审计面。

---

## 六、本次未做 / 限制

* **未追溯存量数据的具体出处**：审计只做到"标记为未核实"，没有替作者
  回忆原始依据。卫星与概念表的真实来源需要人来确认。
* **未核实 SDG 指标的 244 vs 231 差异**：需与 UN 官方清单逐条比对，
  这是数据问题而非工程问题。
* **未处置隔离数据**：`tmp/quarantine/` 里的 775 条仍在磁盘上等待决策(三选一)。
* **ISO 3166-1 代码表的许可细节未最终确认**：代码表通常可自由使用，
  但 ISO 标准文本受版权保护，若要引用"标准"本身需购买。
* **未评估 P0 重建对派生口径的影响**：AdminRegion 换源后数量会变，
  口径③④ 会随之变化，需重建后重新测量。

---

## 七、复现命令

```bash
cd tmp/geokg-repo
python scripts/counting_basis.py                # 口径 + 溯源审计
python scripts/counting_basis.py --admin1       # 含次国家级监测
python scripts/counting_basis.py --no-monitoring

pytest tests -q                                  # 59 tests
```

退出码 0 表示**全部实体均带必需溯源字段**；非 0 表示存在字段缺失。
未核实比例会在报告中单独给出，作为偿还进度指标。
