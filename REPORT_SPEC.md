# 竹林司马 · 分析报告结构与样式规范

> **版本**: v1.0  
> **创建日期**: 2026-04-17  
> **适用文件**: `src/stock/report/generator.py` + `scripts/analyze_600406.py`  
> **维护原则**: 每次对报告结构或样式做永久性修改，必须同步更新此文档

---

## 一、报告模块结构（固定顺序）

```
分析报告 (HTML)
├── 0. 顶部 Header            股票名称 · 代码 · 交易所 · 行业 · 报告日期
├── 1. Verdict 综合裁决面板   总分 + 等级 + 操作信号（仪表盘）
├── 2. 行情快照               实时价格 · 涨跌 · 振幅 · 成交量 · 成交额 · 换手率 · 量比
│   └── 2b. 区间收益          5D / 10D / 30D / 60D / YTD + 60日高低位置
├── 3. 评分概览               技术面 / 基本面 / 情绪面 三卡片（圆环 + 分值 + 等级）
├── 4. 技术面详情
│   ├── 4a. 均线              MA5 / MA10 / MA20 / MA60 + 趋势判断
│   ├── 4b. MACD              DIF / DEA / Hist + 多空 + 背离
│   ├── 4c. KDJ               K / D / J + 金叉 + 超买超卖
│   ├── 4d. RSI               RSI14 + 状态
│   ├── 4e. 布林带             上轨/中轨/下轨 + 带宽 + 位置 + 收口
│   └── 4f. ATR / OBV         ATR14 + 量能趋势
├── 5. 基本面详情             PE / PB / PS / PEG / ROE / 增速 / 资产负债 / 股息
│   └── 5b. 大师评分          多维度评分卡
├── 6. 情绪面详情             主力净流入（5D/10D/30D）+ 高管动向 + 涨停标记
├── 7. 风险评估               风险分值 + 等级 + 止损 + VaR + 最大回撤 + 风险条目
├── 8. 趋势分析               长/中/短期趋势 + 趋势强度 + 动量 + 支撑/压力位
├── 9. 四大战法评分           锁仓K线 / 竞价弱转强 / 利刃出鞘 / 涨停板法
├── 10. 多空逻辑               做多/做空各3-5条核心逻辑
├── 11. 交易计划               入场价 / 目标价1 / 目标价2 / 止损 / 持仓周期 / 执行步骤
└── 12. 预测分析（可选）       趋势预判 + 三情景分析 + 关键价位预测 + 时机判断
```

> 12号模块通过 `data.prediction_enabled = True` 开关，默认**关闭**。

---

## 二、数据字段规范

### 2.1 行情字段

| 字段 | 类型 | 单位 | 来源 | 备注 |
|------|------|------|------|------|
| `current_price` | float | 元 | 实时接口 | 最新价 |
| `open_price` | float | 元 | 实时接口 | |
| `prev_close` | float | 元 | 实时接口 | |
| `high_price` | float | 元 | 实时接口 | |
| `low_price` | float | 元 | 实时接口 | |
| `change_pct` | float | % | 实时接口 | 今日涨跌幅 |
| `amplitude` | float | % | 实时接口 | 振幅 |
| `volume` | float | **股** | 实时接口 | 不是手，不是万股 |
| `amount` | float | **元** | 实时接口 | 不是万元 |
| `turnover` | float | % | **计算** | 见 §2.2 |
| `volume_ratio` | float | 倍 | 计算 | 今日量 / N日均量 |

### 2.2 换手率计算（必须遵守）

```python
# ✅ 正确方式 — 必须使用真实流通股本
float_share, industry = fetch_float_share(code_6digit)   # AkShare
turnover = (volume_today_in_shares / float_share) * 100  # 单位：%

# ❌ 错误方式 — 禁止使用
turnover = volume / volume_60d_mean   # 无意义比值（会产生75%这样的假数据）
```

> **注意**：AkShare `stock_individual_info_em` 返回的 `value` 列是混合类型（float / str），  
> **必须用** `{str(r['item']).strip(): r['value'] for _, r in df.iterrows()}` 方式转dict，  
> **不能用** `df['value'].str.strip()`（会把 float 值转成 NaN）。

### 2.3 评分权重

| 维度 | 权重 | 等级阈值 |
|------|------|---------|
| 技术面 | **40%** | A≥70, B≥55, C≥40, D<40 |
| 基本面 | **35%** | 同上 |
| 情绪面 | **25%** | 同上 |

**综合得分** = `tech_score × 0.4 + fund_score × 0.35 + emotion_score × 0.25`

### 2.4 操作信号规则

| 综合分 | 操作信号 |
|--------|---------|
| ≥ 70 | **BUY** |
| 55 ~ 70 | **HOLD** |
| 40 ~ 55 | **WAIT** |
| < 40 | **SELL** |

---

## 三、样式规范（Design Tokens）

### 3.1 颜色系统

```css
/* 背景层级 */
--bg:       #0a0e1a   /* 最底层背景 */
--card:     #111827   /* 卡片背景 */
--border:   #1e2d45   /* 边框 */
--text:     #e0e4f0   /* 主文字 */
--muted:    #7a8599   /* 次要文字 */

/* 语义色 */
--green:    #00e5a0   /* 看多 / 上涨 / 低风险 / A-B级 */
--yellow:   #f5a623   /* 中性 / C级 / WAIT信号 */
--orange:   #ff7b4f   /* 偏弱 / D级分界 */
--red:      #ff4d6d   /* 看空 / 下跌 / 高风险 / D级 */
--blue:     #6c8ef5   /* HOLD信号 / 中性badge */
--purple:   #a78bfa   /* 特殊标注（预测模块）*/
```

### 3.2 评分颜色阈值

```python
def _score_color(s: float) -> str:
    if s >= 70: return "#00e5a0"   # 绿：良好
    if s >= 55: return "#f5a623"   # 黄：中性
    if s >= 40: return "#ff7b4f"   # 橙：偏弱
    return "#ff4d6d"               # 红：差
```

### 3.3 等级颜色映射

| 等级 | 颜色 | 含义 |
|------|------|------|
| A级 | `#00e5a0`（绿） | 优秀 |
| B级 | `#00e5a0`（绿） | 良好 |
| C级 | `#f5a623`（黄） | 中性 |
| D级 | `#ff4d6d`（红） | 较差 |

### 3.4 操作信号颜色

| 信号 | 颜色 | 含义 |
|------|------|------|
| BUY  | `#00e5a0`（绿） | 建议买入 |
| HOLD | `#6c8ef5`（蓝） | 持有观望 |
| WAIT | `#f5a623`（黄） | 等待信号 |
| SELL | `#ff4d6d`（红） | 建议卖出 |

### 3.5 Badge 样式规则

```html
<!-- 通用badge（CSS class版） -->
<span class="badge-buy">买入</span>     <!-- 绿色背景透明10% + 绿字 -->
<span class="badge-sell">卖出</span>    <!-- 红色背景透明10% + 红字 -->
<span class="badge-warn">中性</span>    <!-- 黄色背景透明10% + 黄字 -->
<span class="badge-neutral">—</span>   <!-- 蓝灰色 -->

<!-- Verdict面板（内联样式版，带颜色背景） -->
<!-- _grade_badge_html() 生成，不使用badge-xxx class -->
```

> **关键规则**：`_grade_badge()` 和 `_action_badge()` 返回**纯文本**（不含HTML标签）。  
> 需要HTML时调用 `_grade_badge_html()` / `_action_badge_html()`。  
> 禁止模板对这些函数的返回值**二次包裹span**（会产生嵌套badge问题）。

---

## 四、格式化函数规范

| 函数 | 用途 | 示例 |
|------|------|------|
| `_price(v)` | 价格，¥前缀，2位小数 | `¥26.35` |
| `_pct(v)` | 百分比，2位小数 | `1.06%` |
| `_num(v, dec)` | 数字，指定小数位 | `48.3` |
| `_amt(v)` | 金额，自动亿/万换算 | `12.34亿` |
| `_vol(v)` | 成交量，自动亿/万换算 | `8456万股` |
| `_s(v)` | 分数，取整 | `68` |
| `_ret_badge(v)` | 区间收益率badge | `+2.35%`（绿）|
| `_trend_badge(t)` | 趋势文字badge | `上升`（绿）|
| `_grade_badge(g)` | 等级纯文本 | `C级` |
| `_grade_badge_html(g)` | 等级彩色HTML | `<span>C级</span>` |
| `_action_badge(a)` | 操作信号纯文本 | `HOLD` |
| `_action_badge_html(a)` | 操作信号彩色HTML | `<span>· HOLD</span>` |

---

## 五、数据来源规范

### 5.1 标准数据采集流程

```python
# Step 1: K线数据（120条，含技术指标计算）
df = fetch_kline("sh600406", count=120)

# Step 2: 实时行情（最新价、涨跌、成交量等）
snapshot = fetch_realtime("sh600406")

# Step 3: 流通股本 + 行业（必须在技术指标计算前）
float_share, industry = fetch_float_share("600406")

# Step 4: 换手率修正（覆盖bundle默认值）
bundle.turnover = (snapshot["volume"] / float_share * 100) if float_share > 0 else 0.0

# Step 5: 技术指标 + 评分
bundle = TechnicalIndicators().compute_all(df)

# Step 6: 风险/趋势/基本面/情绪（复用bundle.turnover已修正的值）
risk = RiskAnalyzer().analyze(bundle, ...)
```

> **关键顺序**：`fetch_float_share` 必须在 `compute_all` 之后、`analyze` 之前调用，  
> 然后立即用 `bundle.turnover = correct_turnover` 覆盖，确保所有下游分析用正确值。

### 5.2 数据新鲜度

```python
last_kline_date = df["date"].max().date()
data.data_days = (datetime.now().date() - last_kline_date).days
# data_days == 0: 今日数据（交易日内）
# data_days == 1: 昨日数据（正常，T+1）
# data_days >= 3: 数据陈旧（节假日后返回提醒）
```

---

## 六、报告文件输出规范

| 配置项 | 规范 |
|--------|------|
| 输出目录 | `/Users/gilesyang/Downloads/gilesyang2024/` |
| 文件名格式 | `{股票拼音}_{report_type}_{yyyymmdd}.html` |
| 当前文件名 | `guodian_nanrui_report_0416.html` |
| 本地预览端口 | `http://localhost:7795/` |
| 主题 | 暗色（Dark），背景 `#0a0e1a` |
| 字体 | `Inter, -apple-system, 'PingFang SC', sans-serif` |
| 最大宽度 | `1200px`，居中布局 |

---

## 七、字段"黄金值"（国电南瑞 600406 参考基准）

> 当前最新一次正确报告数据，用于验证脚本修复效果

| 字段 | 正确值 | 常见错误值 |
|------|--------|-----------|
| 换手率 | ~1.06% | ~~75.43%~~（误用60日均量分母） |
| 流通股 | ~80.08亿股 | N/A（需AkShare查询） |
| 行业 | 电网设备 | ~~空白~~（未查询时） |
| 综合等级 | C级 | ~~C级级~~（重复"级"字bug） |
| BUY/HOLD | HOLD | ~~HOLD·HOLD~~（嵌套badge bug） |

---

## 八、禁止事项（Linting Rules）

1. **禁止**在模板里对 `{overall_grade}` 或 `{overall_action}` 外面再套 `badge-xxx` 的span
2. **禁止**使用K线量/N日均量比值计算换手率
3. **禁止** `df['value'].str.strip()` 处理混合类型AkShare数据
4. **禁止** `data.industry` 留空（至少填写默认"电网设备"）
5. **禁止**不设置 `data.data_days`（必须计算真实天数）
6. **禁止**同一等级字母重复追加"级"（如 `f"{g}级级"`）

---

## 九、变更日志

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-04-17 | v1.0 | 初始版本，固化修复后的所有规范 |

