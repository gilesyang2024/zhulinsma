#!/usr/bin/env python3
"""
竹林司马 - 股票分析专用 Agent
版本: 1.0.0

将技术指标数据转化为大模型可理解的上下文，
通过精心设计的 Prompt 获得专业的投资分析建议。

核心能力:
1. 市场解读 - 用通俗语言解读技术指标
2. 投资建议 - 基于多维度数据的综合建议
3. 趋势预测 - 短期趋势判断与价格预测
4. 风险评估 - 深度风险分析与应对策略
5. 形态分析 - K线形态的市场含义解读
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .client import LLMClient, LLMConfig, LLMProvider


class StockAnalyst:
    """
    股票分析 Agent

    封装了专业的 Prompt 工程和结构化输出，
    将竹林司马的量化数据转化为自然语言分析报告。

    使用方式:
        analyst = StockAnalyst()  # 默认 DeepSeek
        report = analyst.analyze(stock_data)
    """

    # 系统人设
    SYSTEM_PROMPT = """你是"竹林司马"AI 首席分析师，一位拥有20年A股市场经验的资深投资顾问。

## 你的分析风格
- **数据驱动**: 每个观点必须有数据支撑，不空谈
- **通俗易懂**: 用投资者能理解的语言，避免堆砌术语
- **客观中立**: 不带情绪，不主观臆断，承认不确定性
- **操作导向**: 每次分析都要给出可执行的操作建议
- **风险优先**: 永远把风险提示放在第一位

## 你的分析框架
1. **趋势判断**: 当前处于什么趋势？多头/空头/震荡？
2. **信号解读**: 技术指标在说什么？有什么形态？
3. **量能分析**: 资金在做什么？主力动向如何？
4. **风险评估**: 最大风险是什么？如何防范？
5. **操作建议**: 具体怎么做？买卖点在哪？仓位多少？

## 输出要求
- 回答要结构化，使用标题和要点
- 关键数据要加粗显示
- 投资评级使用: ⭐ 强烈推荐 / 👍 推荐 / 😐 中性 / ⚠️ 谨慎 / 🚫 回避
- 必须包含风险提示"""

    def __init__(self, client: Optional[LLMClient] = None, **kwargs):
        """
        初始化分析 Agent

        参数:
            client: LLMClient 实例（如不传则自动创建）
            **kwargs: 传递给 LLMClient 的配置参数
        """
        self.client = client or LLMClient(**kwargs)

    def analyze_dimensions(
        self,
        stock_name: str,
        stock_code: str,
        price_info: Dict,
        ma_data: Dict,
        macd_data: Dict,
        rsi_data: Dict,
        kdj_data: Dict,
        volume_info: Dict,
        trend_info: Dict,
    ) -> str:
        """
        通俗解读选股分析维度

        将技术指标转化为投资者能理解的自然语言。
        """
        prompt = f"""请用通俗易懂的语言，为一位普通投资者解读以下股票的技术分析数据。

## 股票信息
- **{stock_name}（{stock_code}）**
- 最新价: {price_info.get('close', 'N/A')}元
- 涨跌幅: {price_info.get('change_pct', 'N/A')}

## 均线系统
- 当前价与MA5: {ma_data.get('price_vs_ma5', 'N/A')}
- 当前价与MA10: {ma_data.get('price_vs_ma10', 'N/A')}
- 当前价与MA20: {ma_data.get('price_vs_ma20', 'N/A')}
- 当前价与MA60: {ma_data.get('price_vs_ma60', 'N/A')}
- 均线排列: {ma_data.get('arrangement', 'N/A')}

## MACD 指标
- DIF: {macd_data.get('dif', 'N/A')}
- DEA(Signal): {macd_data.get('signal', 'N/A')}
- MACD柱: {macd_data.get('histogram', 'N/A')}
- 金叉/死叉: {macd_data.get('cross', 'N/A')}

## RSI 指标
- RSI6: {rsi_data.get('rsi6', 'N/A')}
- RSI14: {rsi_data.get('rsi14', 'N/A')}
- 超买超卖: {rsi_data.get('status', 'N/A')}

## KDJ 指标
- K: {kdj_data.get('k', 'N/A')}
- D: {kdj_data.get('d', 'N/A')}
- J: {kdj_data.get('j', 'N/A')}
- 金叉/死叉: {kdj_data.get('cross', 'N/A')}

## 成交量分析
- 量比: {volume_info.get('volume_ratio', 'N/A')}
- 5日均量 vs 20日均量: {volume_info.get('ma5_vs_ma20', 'N/A')}
- 量价关系: {volume_info.get('price_volume_relation', 'N/A')}

## 趋势判断
- 短期趋势(5日): {trend_info.get('short_term', 'N/A')}
- 中期趋势(20日): {trend_info.get('mid_term', 'N/A')}
- 趋势强度: {trend_info.get('strength', 'N/A')}

请按以下结构输出（每段3-5句话，通俗易读）：

**📍 当前在什么位置？**
（解读均线系统和价格位置）

**💨 动量怎么样？**
（解读MACD、RSI、KDJ动量指标）

**📈 是什么趋势？**
（解读趋势方向和强度）

**💹 买卖活跃吗？**
（解读成交量和量价关系）"""

        return self.client.chat(prompt, system_prompt=self.SYSTEM_PROMPT)

    def analyze_strategies(
        self,
        stock_name: str,
        stock_code: str,
        strategy_signals: List[Dict],
    ) -> str:
        """
        解读选股战法信号

        将四大战法的触发结果转化为通俗的投资逻辑说明。
        """
        # 构建战法描述
        signals_text = ""
        for sig in strategy_signals:
            status = "✅ 已触发" if sig.get("触发") else "⭕ 未触发"
            signals_text += f"\n- **{sig.get('战法名称', '未知战法')}** {status}"
            if sig.get("触发"):
                signals_text += f"\n  - 信号类型: {sig.get('信号类型', 'N/A')}"
                signals_text += f"\n  - 置信度: {sig.get('置信度', 'N/A')}"
                signals_text += f"\n  - 核心依据: {sig.get('说明', 'N/A')}"
                signals_text += f"\n  - 评分: {sig.get('评分', 'N/A')}/100"

        prompt = f"""请解读以下选股战法信号，为投资者提供通俗的说明。

## 股票: {stock_name}（{stock_code}）

## 战法信号
{signals_text if signals_text else "无触发信号"}

请按以下结构输出：

**🎯 战法信号解读**
（用通俗语言解释每个触发的战法意味着什么，为什么这个信号重要）

**📊 综合判断**
（多个战法同时触发或未触发，整体说明了什么？市场在传递什么信号？）

**⚡ 行动建议**
（基于战法信号，短线/中线投资者分别应该怎么做？）"""

        return self.client.chat(prompt, system_prompt=self.SYSTEM_PROMPT)

    def analyze_risk(
        self,
        stock_name: str,
        stock_code: str,
        risk_data: Dict,
        current_price: float,
    ) -> str:
        """
        AI 深度风险评估

        不仅给出数字，更要解读风险背后的市场逻辑。
        """
        tp = risk_data.get('止盈目标', {})
        tp_text = "N/A"
        if isinstance(tp, dict) and tp:
            tp_text = f"保守{tp.get('保守', 'N/A')} / 基准{tp.get('基准', 'N/A')} / 乐观{tp.get('乐观', 'N/A')}"
        elif isinstance(tp, (list, tuple, str)):
            tp_text = str(tp)

        prompt = f"""请对以下股票进行深度风险评估，重点解读风险来源和应对策略。

## 股票: {stock_name}（{stock_code}）当前价 {current_price}元

## 风险评估数据
- 风险等级: {risk_data.get('风险等级', 'N/A')}
- 综合风险分: {risk_data.get('综合风险分数', 'N/A')}/100
- 年化波动率: {risk_data.get('风险明细', {}).get('年化波动率', 'N/A')}
- 20日最大回撤: {risk_data.get('风险明细', {}).get('最大回撤', 'N/A')}
- ATR(真实波幅): {risk_data.get('风险明细', {}).get('ATR', 'N/A')}
- 波动风险分: {risk_data.get('风险明细', {}).get('波动风险分', 'N/A')}
- 回撤风险分: {risk_data.get('风险明细', {}).get('回撤风险分', 'N/A')}
- 趋势风险分: {risk_data.get('风险明细', {}).get('趋势风险分', 'N/A')}
- 止损位: {risk_data.get('止损位', 'N/A')}元
- 止盈(保守/基准/乐观): {tp_text}

## 风险因素
{chr(10).join('- ' + f for f in risk_data.get('风险因素', []))}

请按以下结构输出：

**🔴 风险全景**
（用通俗语言描述当前这只股票面临的主要风险）

**⚠️ 风险来源分析**
（解释每个风险维度的具体含义和成因）

**🛡️ 风险应对策略**
（针对识别出的风险，给出具体的防范措施）
- 仓位控制建议
- 止损止盈设置
- 持仓周期建议

**📊 风险收益比评估**
（当前风险水平下，是否值得参与？预期收益空间多大？）"""

        return self.client.chat(prompt, system_prompt=self.SYSTEM_PROMPT)

    def generate_investment_advice(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        score_report: Dict,
        signal_fusion: Dict,
        risk_report: Dict,
        pattern_result: Dict,
        strategy_signals: List[Dict],
    ) -> str:
        """
        生成 AI 投资建议

        综合所有分析维度，给出最终的投资建议和操作方案。
        """
        # 格式化各维度评分
        dim_scores = score_report.get("各维度评分", {})
        dim_text = "\n".join(f"  - {k}: {v}/100" for k, v in dim_scores.items())

        # 格式化形态
        patterns = pattern_result.get("形态列表", [])
        pattern_text = "\n".join(
            f"  - {p.get('名称', 'N/A')} ({p.get('信号', 'N/A')}, {p.get('强度', 'N/A')})"
            for p in patterns
        ) if patterns else "  - 未识别到明显形态"

        # 格式化战法
        triggered = [s for s in strategy_signals if s.get("触发")]
        strategy_text = "\n".join(
            f"  - {s.get('战法名称', 'N/A')}: {s.get('信号类型', 'N/A')} (评分{s.get('评分', 0)})"
            for s in triggered
        ) if triggered else "  - 无战法触发"

        prompt = f"""请基于以下多维度分析数据，为投资者生成专业的投资建议报告。

## 股票: {stock_name}（{stock_code}）当前价 {current_price}元

## AI 综合评分: {score_report.get('综合评分', 'N/A')}/100 评级: {score_report.get('投资评级', 'N/A')}
{dim_text}

## 信号融合
- 方向: {signal_fusion.get('方向', 'N/A')}
- 强度: {signal_fusion.get('强度', 'N/A')}
- 置信度: {signal_fusion.get('置信度', 'N/A')}%
- 建议: {signal_fusion.get('建议', 'N/A')}

## 风险评估
- 风险等级: {risk_report.get('风险等级', 'N/A')}
- 止损位: {risk_report.get('止损位', 'N/A')}元
- 仓位上限: {risk_report.get('仓位上限', 'N/A')}

## K线形态
{pattern_text}

## 触发的战法
{strategy_text}

请按以下结构输出完整的投资建议报告：

**💡 综合投资评级**
（给出最终评级和一句话核心观点，如"⭐ 强烈推荐：技术面多头共振，量能配合，适合分批建仓"）

**📊 多维度分析摘要**
（用2-3段话概括各维度的核心发现）

**🎯 操作方案**
（给出具体的操作建议，包括：买入/卖出/观望、建议仓位、分批策略）

**⏰ 关键时间节点**
（接下来需要关注的几个重要时刻或价格位置）

**⚠️ 风险提示**
（列出2-3个最重要的风险点）

> 免责声明：以上分析基于历史数据和技术指标，仅供参考，不构成投资建议。投资有风险，入市需谨慎。"""

        return self.client.chat(prompt, system_prompt=self.SYSTEM_PROMPT)

    def predict_trend(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        ma_data: Dict,
        macd_data: Dict,
        score_report: Dict,
        recent_prices: List[float],
    ) -> str:
        """
        AI 趋势预测

        基于多因子分析，给出短期趋势判断和价格区间预测。
        """
        # 计算近期走势特征
        if len(recent_prices) >= 5:
            change_5d = (recent_prices[-1] - recent_prices[-6]) / recent_prices[-6] * 100 if len(recent_prices) > 5 else 0
        else:
            change_5d = 0

        prompt = f"""请对以下股票进行短期趋势预测分析。

## 股票: {stock_name}（{stock_code}）当前价 {current_price}元
- 近5日涨跌幅: {change_5d:.2f}%
- 近10日收盘价: {', '.join(f'{p:.2f}' for p in recent_prices[-10:])}

## 关键技术信号
- 均线排列: {ma_data.get('arrangement', 'N/A')}
- MACD信号: DIF={macd_data.get('dif', 'N/A')}, Signal={macd_data.get('signal', 'N/A')}
- AI综合评分: {score_report.get('综合评分', 'N/A')}/100
- 评级: {score_report.get('投资评级', 'N/A')}

请按以下结构输出：

**🔮 短期趋势判断**
（判断未来1-3个交易日的走势方向，并给出判断依据）

**📊 关键价位分析**
- 支撑位: （列出1-3个关键支撑价位及理由）
- 压力位: （列出1-3个关键压力价位及理由）

**📈 情景分析**
（列出乐观/中性/悲观三种情景下的价格区间和触发条件）

**⏰ 关注时间窗口**
（指出接下来最可能发生趋势变化的时间点）

> 注意：趋势预测存在不确定性，仅供参考。实际走势可能偏离预测，请严格做好风险管理。"""

        return self.client.chat(prompt, system_prompt=self.SYSTEM_PROMPT)

    def generate_execution_plan(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        risk_report: Dict,
        signal_fusion: Dict,
        score_report: Dict,
    ) -> str:
        """
        生成选股后操作执行方案

        给出清晰的、可执行的买入/卖出/持仓管理方案。
        """
        tp = risk_report.get('止盈目标', {})
        tp_text = "N/A"
        if isinstance(tp, dict) and tp:
            tp_text = f"保守{tp.get('保守', 'N/A')} / 基准{tp.get('基准', 'N/A')} / 乐观{tp.get('乐观', 'N/A')}"
        elif isinstance(tp, (list, tuple, str)):
            tp_text = str(tp)

        prompt = f"""请为以下股票制定详细的操作执行方案。

## 股票: {stock_name}（{stock_code}）当前价 {current_price}元

## 分析依据
- AI综合评分: {score_report.get('综合评分', 'N/A')}/100 ({score_report.get('投资评级', 'N/A')})
- 信号方向: {signal_fusion.get('方向', 'N/A')}，置信度 {signal_fusion.get('置信度', 'N/A')}%
- 风险等级: {risk_report.get('风险等级', 'N/A')}
- 止损位: {risk_report.get('止损位', 'N/A')}元
- 止盈(保守/基准/乐观): {tp_text}
- 建议仓位上限: {risk_report.get('仓位上限', 'N/A')}

请按以下格式输出操作执行方案：

**📋 操作执行方案**

**Step 1: 趋势确认**
（入场前需要确认的条件）

**Step 2: 买入计划**
（如果决定买入）
- 建议买入价:
- 分批策略: 第1批___% @ ___元，第2批___% @ ___元
- 总仓位控制在: ___%

**Step 3: 止损设置**
（严格的风险控制）
- 初始止损位: ___元 (跌幅___%)
- 移动止损规则: ___
- 极端止损: 跌破___元无条件离场

**Step 4: 止盈计划**
（分批获利了结）
- 第一目标: ___元 (涨幅___%)，减仓___%
- 第二目标: ___元 (涨幅___%)，减仓___%
- 第三目标: ___元 (涨幅___%)，清仓

**Step 5: 持仓管理**
（持有期间的注意事项）
- 每日检查: ___
- 加仓条件: ___
- 减仓条件: ___
- 清仓信号: ___

**Step 6: 异常处理**
- 大盘暴跌应对: ___
- 个股利空应对: ___
- 止损触发后: ___"""

        return self.client.chat(prompt, system_prompt=self.SYSTEM_PROMPT)
