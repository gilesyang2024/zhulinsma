# 竹林司马 (Zhulinsma)

> 专业A股技术分析工具 | Professional A-Share Technical Analysis Toolkit

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-orange)](zhulinsma/version.py)

---

## 🎋 项目简介

**竹林司马（Zhulinsma）** 是一款专为A股投资者设计的技术分析工具，具备以下核心能力：

- **双重验证机制**：所有技术指标使用两种独立算法交叉验证，确保计算精度
- **多维度选股战法**：趋势强度、动量信号、波动特征、量价关系综合评分
- **性能极致优化**：向量化计算，SMA加速273倍，RSI加速8倍
- **完整API体系**：支持RESTful API，可集成到任何交易系统
- **中国市场适配**：红涨绿跌，A股交易规则，广州用户优化

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基础使用

```python
from zhulinsma import TechnicalAPI

# 创建分析实例
api = TechnicalAPI()

# 计算SMA均线
import numpy as np
prices = np.random.randn(100).cumsum() + 100
result = api.计算SMA(prices, period=20)
print(result)
```

### 完整选股分析

```python
from zhulinsma.interface.technical_api import TechnicalAPI
from zhulinsma.interface.analysis_api import AnalysisAPI

# 技术指标
tech = TechnicalAPI()
sma20 = tech.计算SMA(prices, 20)
rsi = tech.计算RSI(prices, 14)
macd_result = tech.计算MACD(prices)

# 综合分析
analysis = AnalysisAPI()
report = analysis.执行技术分析(prices, volumes)
print(f"综合评分: {report['数据']['综合评分']}/10")
print(f"投资建议: {report['数据']['操作建议']}")
```

---

## 📦 项目结构

```
zhulinsma/
├── core/                    # 核心计算引擎
│   ├── indicators/          # 技术指标（SMA/EMA/RSI/MACD/布林带）
│   ├── analysis/            # 综合分析（趋势/支撑阻力/风险评估）
│   ├── data/                # 数据处理与验证
│   ├── quality/             # 数据质量保证
│   ├── monitoring/          # 实时监控
│   └── validation/          # 多源数据验证
├── interface/               # API接口层
│   ├── technical_api.py     # 技术指标API
│   ├── analysis_api.py      # 综合分析API
│   ├── data_quality_api.py  # 数据质量API
│   └── web_api.py           # Web RESTful API
├── visualization/           # 可视化与报告
├── config/                  # 配置文件
├── docs/                    # 文档
│   └── api_documentation.md
├── examples/                # 示例代码
│   ├── easyfactor_analysis.py      # 多因子选股分析示例
│   ├── performance_benchmark.py    # 性能基准测试
│   └── 国电南瑞选股战法分析.py      # 实战分析示例
└── tests/                   # 测试用例
```

---

## 📊 核心功能

### 1. 技术指标

| 指标 | 方法 | 说明 |
|------|------|------|
| 简单移动平均 | `计算SMA(prices, period)` | 支持5/10/20/30/60日 |
| 指数移动平均 | `计算EMA(prices, period)` | 12/26日EMA |
| 相对强弱指数 | `计算RSI(prices, period=14)` | 超买超卖信号 |
| MACD | `计算MACD(prices)` | DIF/DEA/柱状图 |
| 布林带 | `计算布林带(prices, period=20)` | 上轨/中轨/下轨 |

### 2. 综合评分（满分10分）

- **趋势强度**（25%）：均线多空排列，价格趋势判断
- **动量信号**（25%）：RSI超买超卖，MACD金死叉
- **波动特征**（20%）：ATR波动率，布林带位置
- **量价关系**（30%）：OBV能量潮，量价匹配度

### 3. 性能基准

| 指标 | 优化前 | 优化后 | 加速比 |
|------|--------|--------|--------|
| SMA(10000条) | 121ms | 0.44ms | **275x** |
| RSI(10000条) | 89ms | 10.8ms | **8.2x** |
| MACD(10000条) | 95ms | 12ms | **7.9x** |

---

## 🛡️ 数据质量保证

- **多源验证**：支持6种数据源交叉验证（akshare/tushare/baostock/yfinance等）
- **实时监控**：6个关键质量指标，5级报警机制
- **准确性标准**：数据准确性≥99%，完整性≥98%

---

## 🌐 Web API

```bash
# 启动Web API服务
python -m zhulinsma.interface.web_api

# API调用示例
curl -X POST http://localhost:5000/api/technical/sma \
  -H "Content-Type: application/json" \
  -d '{"prices": [100, 102, 98, 105, 103], "period": 3}'
```

---

## 📋 开发路线图

- [x] 核心技术指标（SMA/EMA/RSI/MACD/布林带）
- [x] 双重验证机制
- [x] 向量化性能优化（SMA加速273倍）
- [x] 多源数据验证体系
- [x] 完整API接口
- [x] Web RESTful API
- [x] 可视化与HTML报告
- [ ] 实时数据流处理
- [ ] 机器学习选股模型
- [ ] 量化回测框架集成

---

## 📄 文档

- [使用手册](docs/Zhulinsma_使用手册.md)
- [API文档](zhulinsma/docs/api_documentation.md)
- [架构分析](docs/ta_lib_architecture_analysis.md)
- [七日完善计划](docs/Zhulinsma_七日完善计划执行状态报告.md)

---

## ⚠️ 免责声明

本工具仅供技术分析学习研究使用，不构成任何投资建议。投资有风险，入市需谨慎。

---

## 📜 License

MIT License © 2026 gilesyang2024
