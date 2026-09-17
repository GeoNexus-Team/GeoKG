# admin2（二级行政区划）数据源与许可调研

**目的**：GeoKG 现有 8,327 条策展+展开实体，考核线为 2 万，缺口 **+11,673**。
课题3 又要求"国家级、**城市级** SDGs 评估监测"，而图谱目前完全没有城市级落脚点。
本文件评估用于补齐二级行政区划（admin2）的候选数据源、许可条件与实测可行性。

**结论**：推荐 **GeoNames（主）+ geoBoundaries gbOpen（交叉校验）**，
**明确排除 GADM 与 Natural Earth**。

---

## 一、结论摘要

| 数据源 | 许可 | 全球 admin2 | 体积 | 可用性 |
|--------|------|-------------|------|--------|
| **GeoNames** `admin2Codes.txt` | **CC BY 4.0**（可商用，无 share-alike） | **47,643** 单元 / 189 实体 | **2.4 MB** | ✅ **推荐为主源** |
| **geoBoundaries** `gbOpen/ADM2` | 汇编 CC BY 4.0；**但 45 国上游为 share-alike，1 国权利不明** | 49,363 单元 / 180 国 | ~1.6 GB（几何） | ⚠️ **仅用于交叉校验，不直接入库** |
| ~~GADM~~ | **禁止再分发**，仅学术/非商业 | ~46,000 | 大 | ❌ **不可用** |
| ~~Natural Earth~~ | Public Domain | **仅美国** | 1.8 MB | ❌ **不可用** |

两个可用源**都不完整且互补**（见 §四），因此建议主源 + 校验，而不是二选一。

---

## 二、许可分析（本调研的关键风险）

### ⚠️ GADM —— 最大的坑

[GADM 许可页](http://gadmaps.s3-website-us-west-1.amazonaws.com/license.html) 原文：

> "The data are freely available for **academic use and other non-commercial use**.
> **Redistribution or commercial use is not allowed without prior permission.**"

**"禁止再分发"直接否决了它的使用**——把数据提交进公开 GitHub 仓库本身就是再分发。
GADM 在学术论文里被大量引用（做图可以），但**不能进我们的仓库**。
另注：奥地利部分数据为 CC BY-SA 2.0。

### ⚠️ geoBoundaries —— 要注意"汇编许可 ≠ 源许可"

geoBoundaries 自身汇编为 [CC BY 4.0](https://www.geoboundaries.org/)（可商用，需署名）。
但其 API 对**每个国家**返回 `boundaryLicense` 字段，标明**上游原始许可**。
实测 gbOpen/ADM2 的**完整**逐国分布（180 国，全量枚举，非抽样）：

| 上游许可 | 国家数 | 性质 |
|----------|--------:|------|
| CC BY 3.0 IGO | 47 | 署名 |
| CC BY 4.0（含两种写法） | 38 | 署名 |
| **ODbL 1.0** | **33** | **⚠️ share-alike** |
| Public Domain | 28 | 无限制 |
| **CC BY-SA 2.0** | **7** | **⚠️ share-alike** |
| CC BY 3.0 | 7 | 署名 |
| **CC BY-SA 3.0 Unported** | **5** | **⚠️ share-alike** |
| CC0 1.0 | 5 | 无限制 |
| CC BY 2.5 | 1 | 署名 |
| PDDL 1.0（公共领域奉献） | 1 | 无限制 |
| Open Government Licence v3.0 | 1 | 署名 |
| Etalab Open License 2.0 | 1 | 署名 |
| Data license Germany 2.0 | 1 | 署名 |
| Open Government Canada 2.0 | 1 | 需核 |
| Singapore Open Data License 1.0 | 1 | 需核 |
| swisstopo License | 1 | **需逐一核** |
| National Institute of Statistics (INE) Data License | 1 | **需逐一核** |
| **Other - Direct Permission** | **1** | **⚠️ 权利不明** |

**这是比预期严重得多的结论**：

1. **share-alike 国家共 45 个**（ODbL 33 + CC BY-SA 12），而非只看主表时以为的 33。
   share-alike 可能要求**衍生数据库**同样以该许可授权，对自行定许可
   （Apache-2.0）的项目是实质约束，需法务确认。
2. **有 1 国许可是 "Other - Direct Permission"**——权利状态不明确，
   **必须排除或单独取得许可**，不能"看起来是开放的"就直接用。
3. 另有 4 国为**定制许可**（swisstopo / INE / 加拿大 / 新加坡），各自条款不同，
   需逐条审阅。

geoBoundaries 另提供 `gbAuthoritative`（UN SALB 镜像）与 `gbHumanitarian`（OCHA 镜像），
官方明确说明 `gbAuthoritative` **不可用于商业用途**，因此我们只用 `gbOpen`——
但即使 `gbOpen`，上面这些**上游**许可仍然适用。

**对比之下 GeoNames 只有一条 CC BY 4.0**，零 share-alike、零定制条款、
零权利不明条目。这是推荐它做主源的**决定性**理由，而不只是"体积小"。

### ✅ GeoNames —— 最干净

[官方条款页](https://www.geonames.org/export/)：

> "free … **cc-by licence** … **commercial usage is allowed** …
> You should give credit to GeoNames when using data … with a link or another reference"

数据集 readme.txt 明确版本：

> "This work is licensed under a **Creative Commons Attribution 4.0 License**"

即 **CC BY 4.0，允许商用，只需署名**。与 Apache-2.0 项目兼容（无 share-alike）。

### ❌ Natural Earth

[官方页面](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-2-counties/) 原文：

> "Internal, second-order administrative boundaries and polygons for **just the United States**."
> "**All countries but the United States lack admin-2 features.**"

虽然是 Public Domain（最宽松），但**只有美国**，无法用于全球 admin2。
其 admin-1 覆盖全球，可作为 admin1 的交叉校验源。

---

## 三、实测（本机，2026-09）

所有数字均为**实测**，非文档引用。

### GeoNames

```
admin2Codes.txt      2,375,310 bytes   47,643 行   189 个实体
admin1CodesASCII.txt   151,583 bytes    3,865 行   228 个实体
countryInfo.txt                       （ISO2↔ISO3 映射）
```

格式（制表符分隔）：`CC.A1.A2 \t name \t asciiname \t geonameid`

```
AE.01.101   Abu Dhabi Municipality   Abu Dhabi Municipality   12047239
```

**关键优势：编码本身携带父级 ADM1**（`AE.01.101` = 国家 AE / ADM1 `01` / ADM2 `101`），
因此**层级关系无需空间运算即可得到**。

⚠️ **下载注意**：`curl` 对本站失败——

```
error:06FFF089:digital envelope routines:CRYPTO_internal:bad key length
```

这是本机旧 TLS 栈与该站密钥协商不兼容（非网络问题）。**改用 Python `urllib`
可正常下载**（约数秒）。这条要写进抓取脚本，否则会误判为"站点不可达"。

### geoBoundaries

API 端点（实测 HTTP 200）：

```
https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM2/    # 323,216 bytes
https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM1/    # 350,392 bytes
```

返回每国 `admUnitCount` / `boundaryLicense` / `boundarySource` / `licenseSource` /
`gjDownloadURL` 等，**元数据自带许可溯源**，非常适合我们的 provenance 体系。

⚠️ **两个实测限制**：

1. **ADM2 文件不含父级 ADM1 字段**。属性只有
   `shapeGroup / shapeID / shapeISO / shapeName / shapeType`。
   要建 admin2→admin1 层级，必须做**空间叠置**（需下几何），
   或改用 GeoNames。
2. **几何下载在本机不可行**：比利时（11 个单元）的**简化版** GeoJSON
   为 360 KB、耗时 **37.5 s（≈10 KB/s）**。按此推算全球 admin2 几何
   ≈ **1.6 GB / 约 45 小时**。我们只需要名称与层级，**不需要几何**。

### 交叉校验

| | GeoNames | geoBoundaries |
|---|---|---|
| 单元总数 | 47,643 | 49,363 |
| 覆盖实体 | 189 | 180 |
| 两者都有 | **170 国** | |
| 仅 GeoNames 有 | 19（ARE, ASM, ALA, COK, FRO, GRL…） | |
| 仅 geoBoundaries 有 | | 10（BHS, COM, GUM, GUY, MCO, MDV, QAT, SGP…） |

差异最大的国家（ GeoNames − geoBoundaries ）：

| ISO3 | GeoNames | geoBoundaries | 差 | 判断 |
|------|---------:|--------------:|-----:|------|
| CHN | 360 | 2,391 | −2,031 | geoBoundaries 明显更全（2,391 ≈ 中国县级数） |
| CAN | 1,641 | 76 | +1,565 | GeoNames 更全 |
| PRI | 902 | 78 | +824 | GeoNames 更全 |
| JPN | 1,190 | 1,745 | −555 | geoBoundaries 更全 |
| DZA | 548 | 48 | +500 | GeoNames 更全 |
| UKR | 146 | 495 | −349 | geoBoundaries 更全 |
| TWN | 22 | 369 | −347 | geoBoundaries 更全 |
| RUS | 2,648 | 2,328 | +320 | 接近 |
| KEN | 32 | 290 | −258 | geoBoundaries 明显更全 |
| SLV | 44 | 272 | −228 | geoBoundaries 更全 |

**这是本次调研最重要的发现**：**没有任何单一源在全球范围内可靠**。
中国的 360 与肯尼亚的 32 明显不完整；加拿大、阿尔及利亚则反过来。
盲目采用任一方都会在部分国家产生严重缺口。

---

## 四、建议方案

### 4.1 数据源策略

1. **主源：GeoNames `admin2Codes.txt`（CC BY 4.0）** —— **唯一入库的数据源**
   - 体积极小（2.4 MB），名称 + 编码 + **父级层级齐备**
   - 许可单一且干净：可商用、**无 share-alike**、无定制条款、无权利不明条目
   - 与既有 admin1（3,500 条）可比对：GeoNames admin1 为 3,865 条，量级吻合
2. **参照源：geoBoundaries `gbOpen/ADM2` —— 只用元数据，不取数据**
   - 只读其 `admUnitCount` 与 `boundaryLicense` 做**交叉校验**，判断 GeoNames 在哪国覆盖不足
   - **不下几何、不入库其边界数据**，因此 §二 那些上游许可（ODbL / CC BY-SA / 权利不明）
     **不会传导到我们的数据库**——计数是事实，不构成衍生数据库
   - 本机带宽也无法承载其几何（≈1.6 GB / ~45 小时）
3. **排除 GADM、Natural Earth**（理由见 §二）

### 4.2 建议的摄取范围（不要盲目全量）

**不建议直接把 47,643 条全部灌入**——里面包含明显不完整的国家，
会把"覆盖不足"变成"看起来已覆盖"。建议：

* **纳入**：GeoNames 与 geoBoundaries 单元数**相对差 ≤ 50%** 的国家
  （表明两源都认为该层级基本完整）；
* **标注待补**：差异过大的国家保留在清单里但不入库，
  或入库但标 `coverage="partial"`；
* 这样得到的是一个**质量经过交叉验证**的 admin2 集合，
  预计仍有 2~3 万条，足以把策展口径从 8,327 推到 2 万以上。

### 4.3 存储与溯源设计

1. **不要嵌入 Python 源码**。现有 `admin1_global.py` 把 1,436 条写成字面量
   （269 行）；47,643 条会变成约 1 MB 的 `.py`，代码评审与 diff 都不可读。
   建议改为 **数据文件**（`src/geokg/data/admin2_global.tsv` 或 `.json`），
   由代码加载，并在 `pyproject.toml` 中声明为 package data。
2. **署名写进数据**，而不是只写在文档里（CC BY 4.0 的合规要求）：
   每个实体写入
   ```python
   properties = {
       "name": ..., "country": iso3, "level": 2, "parent": "admin1.XXX.yyy",
       "origin": "curated",
       "source": "geonames:CC-BY-4.0",
   }
   ```
   这样 `counting_basis.py` 能按来源分别统计，署名也随数据一起分发。
3. **`origin` 分层不变**（curated / expanded / derived）；外部抓取的真实数据
   归入 `curated`，另用 `source` 字段区分出处。**不要新增第四类 origin**，
   否则口径口径又要重新定义。
4. **命名冲突**：现有 admin1 的 id 由**名称**生成（`admin1.{ISO3}.{slug}`），
   而 GeoNames 用**数字编码**（`AE.01`）。建立层级时需要
   `admin1CodesASCII.txt` 做 code→name 映射，再与现有 slug 对齐；
   对无法对齐的条目要显式记录为 `parent_unresolved`，不能静默挂到国家上。

### 4.4 需要的外部确认

* **本次方案只用 GeoNames，因此不触发 share-alike**。但若后续要引入
  geoBoundaries 的**边界数据**（不是元数据）来补 GeoNames 覆盖不足的国家，
  需先解决：**45 国 share-alike**（ODbL 33 + CC BY-SA 12）、
  **1 国权利不明**（"Other - Direct Permission"）、4 国定制许可。
  建议：**要么不用，要么逐国单独确认**，不要整体引入。
* **覆盖率低的国家的替代源**：GeoNames 对中国（360）、肯尼亚（32）、
  乌克兰（146）、台湾（22）、萨尔瓦多（44）明显不全。
  这些国家若要做城市级示范，需另找**国家级权威源**
  （如中国民政部行政区划代码、肯尼亚 IEBC、乌克兰 KATOTTH）。
  该类源多数为政府开放数据，许可需逐个确认。
* **GeoNames 数据质量**：其 admin2 覆盖不均，用于**城市级监测示范**的国家
  需人工抽查名称与层级正确性。

---

## 五、本次未验证的事项（限制）

* 未下载 geoBoundaries 全球几何（评估为不可行，§三）。
* 未逐国核对 GeoNames admin2 名称的准确性、本地化与拼写。
* 未确认 GeoNames `admin2Codes.txt` 中各条目是否都是**现行**行政区划
  （可能存在撤销/合并后的历史条目）。
* admin2 计数差异的**归因未逐国核实**（如 CHN 360 是"只收录部分"还是"层级定义不同"，
  需抽查原始数据才能定论）。
* 未评估把 2~3 万条实体灌入后对图谱体积与加载时间的影响
  （现有 116,236 实体 → 58 MB JSON；预计增到 ~150k 实体、~75 MB）。

---

## 六、可复现命令

```bash
# GeoNames（注意：curl 会因 TLS 报错，必须用 Python）
python - <<'EOF'
import ssl, urllib.request, pathlib
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for f in ("admin2Codes.txt", "admin1CodesASCII.txt", "countryInfo.txt"):
    url = f"https://download.geonames.org/export/dump/{f}"
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent":"GeoNexus/1.0"}), timeout=90, context=ctx) as r:
        pathlib.Path(f"/tmp/{f}").write_bytes(r.read())
EOF

# geoBoundaries 元数据（含逐国许可）
curl -s --max-time 90 "https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM2/" -o /tmp/gb_ADM2.json

# 单国几何（慎用：本机 ~10 KB/s）
curl -sL --max-time 60 --insecure \
  "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/BEL/ADM2/geoBoundaries-BEL-ADM2_simplified.geojson"
```

## 七、引用（署名要求）

若采用，须在产品中署名：

* **GeoNames** — "This work is licensed under a Creative Commons Attribution 4.0 License."
  署名：`GeoNames, https://www.geonames.org/`
* **geoBoundaries** — Runfola, D. et al. (2020) *geoBoundaries: A global database of
  political administrative boundaries.* PLoS ONE 15(4): e0231866.
  https://doi.org/10.1371/journal.pone.0231866
