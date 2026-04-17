#!/usr/bin/env python3
"""
竹林司马 - 多角色辩论分析引擎
版本: 2.0.0
日期: 2026年4月15日

操作指南第十一章「大模型增强模式」的核心实现。

四大角色从不同专业角度分析同一只股票，模拟真实投研团队的辩论过程，
最终汇聚为一份多角度深度分析报告。

四大角色:
1. 技术分析师 - 价格/量能/指标维度
2. 基本面分析师 - 财务/估值/行业维度
3. 情绪分析师 - 新闻/政策/情绪维度
4. 风险管理员 - 波动率/回撤/极端情景维度

核心流程:
  各角色独立分析 → 汇总辩论 → 生成最终结论
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from .client import LLMClient, LLMConfig


# ═══════════════════════════════════════════
# 四大角色定义
# ═══════════════════════════════════════════

ANALYST_ROLES = {
    "技术分析师": {
        "emoji": "📈",
        "color": "#3b82f6",
        "system_prompt": """你是一位拥有25年经验的A股技术分析师。

## 你的核心职责
从价格、量能、技术指标三个维度分析股票，回答核心验证问题。

## 你的分析框架
1. **价格分析**: 趋势方向、关键支撑压力位、K线形态
2. **量能分析**: 成交量变化、量价配合、主力资金动向
3. **指标分析**: MACD/RSI/KDJ/布林带的信号含义

## 输出要求
- 每个观点必须标注概率（如"突破概率65%"）
- 信号分三类：⚠️ 风险信号（需行动）、✅ 机会信号（可执行）、💡 优化建议（提升收益）
- 结论先给具体操作建议，再解释原因
- 字数控制在300-500字""",
        "key_question": "是否突破关键压力位？技术面给出的信号是什么？",
    },
    "基本面分析师": {
        "emoji": "📊",
        "color": "#22c55e",
        "system_prompt": """你是一位专注A股市场的基本面分析师，拥有CPA和CFA双证。

## 你的核心职责
从财务健康、估值水平、行业地位三个维度分析股票。

## 你的分析框架
1. **财务分析**: 营收/净利润增长、ROE、负债率、现金流
2. **估值分析**: PE/PB/PS估值水平、与行业对比
3. **行业分析**: 行业景气度、政策影响、竞争格局

## 输出要求
- 估值必须给出明确的合理区间
- 行业对比必须有数据支撑
- 信号分三类：⚠️ 风险信号、✅ 机会信号、💡 优化建议
- 结论先给投资评级（强烈推荐/推荐/中性/谨慎/回避），再解释
- 字数控制在300-500字""",
        "key_question": "PE是否合理？公司基本面是否支撑当前股价？",
    },
    "情绪分析师": {
        "emoji": "🔥",
        "color": "#f59e0b",
        "system_prompt": """你是一位深谙A股市场情绪的分析师，擅长捕捉政策风向和资金情绪变化。

## 你的核心职责
从市场情绪、政策环境、资金流向三个维度分析股票。

## 你的分析框架
1. **市场情绪**: 整体市场温度、板块轮动、情绪指标
2. **政策分析**: 相关政策利好/利空、政策预期
3. **资金面**: 主力资金动向、北向资金、融资融券

## 输出要求
- 情绪评分用1-10分量化（1极度恐慌，10极度贪婪）
- 明确指出当前市场处于什么阶段
- 信号分三类：⚠️ 风险信号、✅ 机会信号、💡 优化建议
- 特别关注板块热度和资金流向对个股的影响
- 字数控制在300-500字""",
        "key_question": "市场情绪如何？政策面和资金面有没有利好或利空？",
    },
    "风险管理员": {
        "emoji": "🛡️",
        "color": "#ef4444",
        "system_prompt": """你是一位严格的A股风险管理专家，专注下行风险保护。

## 你的核心职责
从波动率、最大回撤、极端情景三个维度评估风险。

## 你的分析框架
1. **波动分析**: 历史波动率、ATR、波动率变化趋势
2. **回撤评估**: 近期最大回撤、回撤持续时间、回撤深度
3. **极端情景**: 跌停/暴跌概率、黑天鹅应对、流动性风险

## 输出要求
- 必须给出具体的止损位和仓位建议
- 风险分三级：A级（高确定性）、B级（中确定性）、C级（低确定性）
- 明确"最大可承受亏损"
- 信号分三类：⚠️ 风险信号（必须行动）、✅ 安全确认、💡 优化建议
- 永远把保护本金放在第一位
- 字数控制在300-500字""",
        "key_question": "最大风险是什么？如果入场，最坏情况会亏多少？",
    },
}


class MultiPerspectiveAgent:
    """
    多角色辩论分析引擎

    模拟四大专业分析师（技术/基本面/情绪/风险）独立分析同一只股票，
    然后汇总辩论，生成多角度深度分析报告。

    使用方式:
        agent = MultiPerspectiveAgent()
        report = agent.analyze(stock_data)

        # 获取辩论报告
        print(report['debate_report'])

        # 获取各角色独立观点
        for role, analysis in report['individual_views'].items():
            print(f"{role}: {analysis['viewpoint']}")
    """

    def __init__(self, client: Optional[LLMClient] = None, **kwargs):
        """
        初始化辩论引擎

        参数:
            client: LLMClient 实例（如不传则自动创建）
            **kwargs: 传递给 LLMClient 的配置参数
        """
        self.client = client or LLMClient(**kwargs)
        self._roles = ANALYST_ROLES

    def _build_stock_context(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        technical_data: Optional[Dict] = None,
        fundamental_data: Optional[Dict] = None,
        strategy_signals: Optional[List[Dict]] = None,
        risk_data: Optional[Dict] = None,
        market_context: Optional[Dict] = None,
        # ====== 新增七大维度 (2026-04-16) ======
        money_flow: Optional[Dict] = None,       # 资金流向
        north_flow: Optional[Dict] = None,       # 北向资金
        dragon_tiger: Optional[Dict] = None,     # 龙虎榜
        announcements: Optional[Dict] = None,    # 公告
        financials: Optional[Dict] = None,       # 财务数据
        sector_info: Optional[Dict] = None,      # 板块信息
        market_env: Optional[Dict] = None,       # 大盘环境
    ) -> str:
        """构建股票分析上下文（所有角色共享的基础数据）"""

        lines = [
            f"## 股票: {stock_name}（{stock_code}）",
            f"- 当前价: {current_price}元",
        ]

        # ── 技术面数据 ──────────────────────────────
        if technical_data:
            lines.append("\n### 📈 技术面数据")
            for key, val in technical_data.items():
                lines.append(f"- {key}: {val}")

        # ── 基本面数据 ──────────────────────────────
        # 优先使用详细 financials，其次 fundamental_data
        fin = financials or fundamental_data
        if fin:
            lines.append("\n### 📊 基本面 / 财务数据")
            for key, val in fin.items():
                if key != "错误":
                    lines.append(f"- {key}: {val}")

        # ── 资金流向 ────────────────────────────────
        if money_flow and "错误" not in money_flow:
            lines.append("\n### 💰 资金流向（实时）")
            lines.append(f"- 主力净流入: {money_flow.get('主力净流入', 0)/1e4:.0f}万元 "
                         f"({money_flow.get('主力净流入占比', 0):.1f}%)")
            lines.append(f"- 超大单净流入: {money_flow.get('超大单净流入', 0)/1e4:.0f}万元")
            lines.append(f"- 大单净流入: {money_flow.get('大单净流入', 0)/1e4:.0f}万元")
            lines.append(f"- 资金面判断: {money_flow.get('资金流向判断', 'N/A')}")

        # ── 北向资金 ────────────────────────────────
        if north_flow and "错误" not in north_flow:
            lines.append("\n### 🌐 北向资金（沪深港通）")
            lines.append(f"- 今日北向净买入: {north_flow.get('今日北向净买入(亿)', 0):.2f}亿元")
            lines.append(f"- 近5日累计: {north_flow.get('近5日累计(亿)', 0):.2f}亿元")
            lines.append(f"- 外资动向: {north_flow.get('市场情绪', 'N/A')}")

        # ── 龙虎榜 ──────────────────────────────────
        if dragon_tiger and dragon_tiger.get("上榜次数", 0) > 0:
            lines.append("\n### 🐉 龙虎榜记录（近20日）")
            lines.append(f"- 上榜次数: {dragon_tiger.get('上榜次数', 0)}")
            lines.append(f"- 机构买入次数: {dragon_tiger.get('机构买入次数', 0)}")
            lines.append(f"- 净买入合计: {dragon_tiger.get('净买入合计(万)', 0):.0f}万元")
            lines.append(f"- 综合判断: {dragon_tiger.get('上榜判断', 'N/A')}")
            for rec in (dragon_tiger.get("上榜记录") or [])[:3]:
                lines.append(f"  · {rec.get('日期','')} {rec.get('上榜原因','')} "
                             f"净额{rec.get('净额(万)',0):.0f}万")

        # ── 公告信息 ────────────────────────────────
        if announcements and announcements.get("公告数量", 0) > 0:
            lines.append("\n### 📢 近期公告（近30日）")
            lines.append(f"- 公告数量: {announcements.get('公告数量', 0)}")
            lines.append(f"- 利好公告: {announcements.get('利好公告数', 0)}条")
            lines.append(f"- 利空公告: {announcements.get('利空公告数', 0)}条")
            lines.append(f"- 消息面情绪: {announcements.get('情绪倾向', '中性')}")
            for ann in (announcements.get("重大公告") or [])[:3]:
                lines.append(f"  · [{ann.get('日期','')}] {ann.get('标题','')} [{ann.get('类型','')}]")

        # ── 板块信息 ────────────────────────────────
        if sector_info and "错误" not in sector_info:
            lines.append("\n### 🏭 板块信息")
            lines.append(f"- 所属行业: {sector_info.get('所属行业', 'N/A')}")
            lines.append(f"- 行业今日涨跌: {sector_info.get('行业涨跌(%)', 0):.2f}%")
            lines.append(f"- 行业排名: {sector_info.get('行业排名', 'N/A')}")
            lines.append(f"- 板块热度: {sector_info.get('板块热度', 'N/A')}")

        # ── 大盘环境 ────────────────────────────────
        if market_env and "错误" not in market_env:
            lines.append("\n### 🌏 大盘环境")
            lines.append(f"- 上证指数: {market_env.get('上证涨跌(%)', 0):+.2f}%")
            lines.append(f"- 深证成指: {market_env.get('深证涨跌(%)', 0):+.2f}%")
            lines.append(f"- 创业板: {market_env.get('创业板涨跌(%)', 0):+.2f}%")
            lines.append(f"- 沪深300: {market_env.get('沪深300涨跌(%)', 0):+.2f}%")
            lines.append(f"- 大盘情绪: {market_env.get('大盘情绪', 'N/A')}")

        # ── 战法信号 ────────────────────────────────
        if strategy_signals:
            lines.append("\n### ⚡ 战法信号（规则引擎）")
            for sig in strategy_signals:
                status = "✅ 已触发" if sig.get("触发") else "⭕ 未触发"
                lines.append(f"- {sig.get('名称', '未知')}: {status}")
                if sig.get("说明"):
                    lines.append(f"  说明: {sig['说明']}")

        # ── 风险评估 ────────────────────────────────
        if risk_data:
            lines.append("\n### 🛡️ 风险评估数据")
            for key, val in risk_data.items():
                lines.append(f"- {key}: {val}")

        # ── 市场环境（兼容旧参数）────────────────────
        if market_context:
            lines.append("\n### 市场环境（补充）")
            for key, val in market_context.items():
                lines.append(f"- {key}: {val}")

        return "\n".join(lines)

    def _ask_role(
        self,
        role_name: str,
        role_config: Dict,
        stock_context: str,
    ) -> Dict[str, Any]:
        """
        向单个角色提问

        返回:
            {
                "role": "技术分析师",
                "viewpoint": "...",
                "signals": [...],
                "confidence": "高/中/低",
                "action": "买入/卖出/观望",
                "key_data": {...},
                "token_usage": 123,
            }
        """
        key_q = role_config["key_question"]
        prompt = f"""请从你的专业角度分析以下股票。

{stock_context}

## 你的核心验证问题
**{key_q}**

请严格按照你的分析框架输出，确保:
1. 先给结论（操作建议+概率），再展开分析
2. 至少包含一个⚠️风险信号或✅机会信号
3. 用数据说话，避免空泛判断
4. 最后用一句话总结你的核心观点"""

        start = time.time()
        try:
            response = self.client.chat(
                message=prompt,
                system_prompt=role_config["system_prompt"],
                temperature=0.4,  # 略高于默认，增加观点多样性
            )
            elapsed = time.time() - start

            return {
                "role": role_name,
                "viewpoint": response.strip(),
                "confidence": self._extract_confidence(response),
                "action": self._extract_action(response),
                "key_question": key_q,
                "elapsed": round(elapsed, 1),
                "success": True,
            }
        except Exception as e:
            return {
                "role": role_name,
                "viewpoint": f"分析失败: {str(e)}",
                "confidence": "N/A",
                "action": "N/A",
                "key_question": key_q,
                "elapsed": 0,
                "success": False,
                "error": str(e),
            }

    def _synthesis(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        individual_views: List[Dict],
        stock_context: str,
    ) -> str:
        """
        汇总辩论，生成最终综合结论 + 预测分析

        将四个角色的独立观点汇总，让LLM扮演"首席投资官"进行综合评判，
        并输出结构化的预测分析（三情景、趋势预判、关键催化）。
        """
        views_text = ""
        for v in individual_views:
            if v.get("success"):
                views_text += f"\n### {v['role']}的观点\n{v['viewpoint']}\n"

        prompt = f"""你是竹林司马投研团队的"首席投资官"，现在团队四位分析师已经完成了独立分析。

## 股票: {stock_name}（{stock_code}）· 当前价 {current_price}元

## 四位分析师的观点
{views_text}

## 你的任务
请作为首席投资官，综合四位分析师的观点，做出最终投资决策和预测分析。

### 第一部分：投资决策
1. **承认分歧**: 如果分析师意见不一致，明确指出分歧点
2. **加权判断**: 技术面和风险权重更高（各30%），基本面25%，情绪15%
3. **最终结论**: 给出明确的投资建议（买入/观望/回避）+ 仓位建议 + 止损位
4. **风险红线**: 列出2-3条不可违反的风险红线
5. **一句话总结**: 用一句话概括核心观点

### 第二部分：预测分析（重要！必须严格按JSON格式输出）
请基于当前技术面、基本面、情绪面数据，给出未来3-5个交易日的预测分析。

请用以下格式输出预测部分（必须严格遵守JSON格式，不要有多余文字）：

```PREDICTION_JSON
{{
  "trend_forecast": "一句话趋势预判",
  "trend_confidence": "高/中/低",
  "forecast_horizon": "3-5个交易日",
  "scenario_bull": {{
    "target": "¥目标价",
    "prob": "30%",
    "trigger": "触发条件",
    "desc": "情景描述"
  }},
  "scenario_base": {{
    "target": "¥目标价",
    "prob": "50%",
    "trigger": "维持现状条件",
    "desc": "情景描述"
  }},
  "scenario_bear": {{
    "target": "¥目标价",
    "prob": "20%",
    "trigger": "触发条件",
    "desc": "情景描述"
  }},
  "predicted_support": 25.00,
  "predicted_resistance": 28.00,
  "breakout_up_prob": "25%",
  "breakout_down_prob": "35%",
  "best_entry_window": "建议入场时机描述",
  "key_catalyst": "可能推动上涨的催化因素",
  "risk_event": "需要警惕的风险事件"
}}
```

输出格式（决策部分）:
**🎯 首席投资官最终结论**
（一句话核心观点）

**📊 多空辩论汇总**
（汇总各方观点，指出分歧和共识）

**📋 投资决策**
- 操作建议:
- 建议仓位:
- 入场条件:
- 止损位:
- 目标价位:

**⚠️ 风险红线**
（不可违反的风险底线）"""

        return self.client.chat(
            message=prompt,
            system_prompt="你是竹林司马的首席投资官，拥有30年A股投资经验。你擅长综合多方观点，做出理性、果断的投资决策。你永远把风险管理放在第一位。你的预测分析必须基于客观数据，避免过度乐观或悲观。",
            temperature=0.2,  # 综合判断用低温度，更确定
        )

    def analyze(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        technical_data: Optional[Dict] = None,
        fundamental_data: Optional[Dict] = None,
        strategy_signals: Optional[List[Dict]] = None,
        risk_data: Optional[Dict] = None,
        market_context: Optional[Dict] = None,
        # ====== 新增七大维度 (2026-04-16) ======
        money_flow: Optional[Dict] = None,
        north_flow: Optional[Dict] = None,
        dragon_tiger: Optional[Dict] = None,
        announcements: Optional[Dict] = None,
        financials: Optional[Dict] = None,
        sector_info: Optional[Dict] = None,
        market_env: Optional[Dict] = None,
        # ====== 快捷模式：传入 full_data_dict 自动拆包 ======
        full_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的多角色辩论分析

        参数:
            stock_name: 股票名称
            stock_code: 股票代码
            current_price: 当前价格
            technical_data: 技术面数据
            fundamental_data: 基本面数据（传统接口，可被 financials 覆盖）
            strategy_signals: 战法信号列表
            risk_data: 风险评估数据
            market_context: 市场环境数据（兼容旧版）
            money_flow: 资金流向（StockDataService.获取资金流向）
            north_flow: 北向资金（StockDataService.获取北向资金）
            dragon_tiger: 龙虎榜（StockDataService.获取龙虎榜）
            announcements: 公告（StockDataService.获取公告）
            financials: 财务数据（StockDataService.获取财务数据）
            sector_info: 板块信息（StockDataService.获取板块信息）
            market_env: 大盘环境（StockDataService.获取大盘环境）
            full_data: 传入 StockDataService.获取全维度数据() 的返回值，自动拆包

        返回:
            {
                "meta": {...},
                "individual_views": {角色名: 分析结果, ...},
                "synthesis": "首席投资官综合结论",
                "debate_report": "完整辩论报告（Markdown）",
                "signal_summary": {...},
                "consensus": {...},
            }
        """
        # 自动拆包 full_data
        if full_data:
            money_flow = money_flow or full_data.get("资金流向")
            north_flow = north_flow or full_data.get("北向资金")
            dragon_tiger = dragon_tiger or full_data.get("龙虎榜")
            announcements = announcements or full_data.get("公告")
            financials = financials or full_data.get("财务数据")
            sector_info = sector_info or full_data.get("板块信息")
            market_env = market_env or full_data.get("大盘环境")

        start_time = time.time()

        # 1. 构建共享上下文
        stock_context = self._build_stock_context(
            stock_name=stock_name,
            stock_code=stock_code,
            current_price=current_price,
            technical_data=technical_data,
            fundamental_data=fundamental_data,
            strategy_signals=strategy_signals,
            risk_data=risk_data,
            market_context=market_context,
            money_flow=money_flow,
            north_flow=north_flow,
            dragon_tiger=dragon_tiger,
            announcements=announcements,
            financials=financials,
            sector_info=sector_info,
            market_env=market_env,
        )

        # 2. 各角色独立分析
        print("🎭 启动四大角色辩论分析...")
        individual_views = {}
        errors = []

        for role_name, role_config in self._roles.items():
            emoji = role_config["emoji"]
            print(f"   {emoji} {role_name} 分析中...", end=" ", flush=True)
            result = self._ask_role(role_name, role_config, stock_context)
            individual_views[role_name] = result

            if result["success"]:
                print(f"✅ ({result['elapsed']}s)")
            else:
                print(f"❌ {result.get('error', '未知错误')}")
                errors.append(f"{role_name}: {result.get('error', '')}")

        # 3. 汇总辩论
        print("   🧠 首席投资官综合评判中...", end=" ", flush=True)
        views_list = list(individual_views.values())
        synthesis = ""
        try:
            synthesis = self._synthesis(
                stock_name=stock_name,
                stock_code=stock_code,
                current_price=current_price,
                individual_views=views_list,
                stock_context=stock_context,
            )
            print("✅")
        except Exception as e:
            synthesis = f"综合评判失败: {str(e)}"
            errors.append(f"综合评判: {str(e)}")
            print(f"❌ {e}")

        total_time = round(time.time() - start_time, 1)

        # 4. 解析预测分析
        prediction = self._parse_prediction(synthesis, current_price)

        # 5. 生成完整报告
        debate_report = self._format_debate_report(
            stock_name=stock_name,
            stock_code=stock_code,
            current_price=current_price,
            individual_views=individual_views,
            synthesis=synthesis,
        )

        # 5. 提取信号汇总
        signal_summary = self._extract_signals(individual_views)

        # 6. 提取共识结论
        consensus = self._extract_consensus(individual_views)

        return {
            "meta": {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "多角色辩论模式",
                "total_time": total_time,
                "roles_completed": sum(1 for v in individual_views.values() if v.get("success")),
                "roles_total": 4,
                "errors": errors,
            },
            "individual_views": individual_views,
            "synthesis": synthesis,
            "debate_report": debate_report,
            "signal_summary": signal_summary,
            "consensus": consensus,
            "prediction": prediction,
        }

    def _format_debate_report(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        individual_views: Dict,
        synthesis: str,
    ) -> str:
        """格式化完整辩论报告（Markdown）"""
        lines = [
            f"# 🎭 竹林司马多角色辩论分析报告",
            f"",
            f"**{stock_name}（{stock_code}）** · 当前价 {current_price}元",
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"---",
            f"",
        ]

        # 各角色观点
        for role_name, result in individual_views.items():
            config = self._roles[role_name]
            emoji = config["emoji"]
            lines.append(f"## {emoji} {role_name}")
            lines.append(f"**核心验证**: {result.get('key_question', 'N/A')}")
            lines.append(f"**置信度**: {result.get('confidence', 'N/A')} · **操作倾向**: {result.get('action', 'N/A')}")
            lines.append("")
            lines.append(result.get("viewpoint", "分析失败"))
            lines.append("")
            lines.append("---")
            lines.append("")

        # 综合结论
        lines.append("## 🧠 首席投资官综合结论")
        lines.append("")
        lines.append(synthesis)
        lines.append("")

        return "\n".join(lines)

    def _extract_confidence(self, text: str) -> str:
        """从分析文本中提取置信度"""
        text_lower = text.lower()
        high_keywords = ["高概率", "较高", "强烈", "非常确定", "大概率", "确定"]
        low_keywords = ["不确定", "模糊", "观望", "谨慎", "低概率", "难以判断"]

        for kw in high_keywords:
            if kw in text:
                return "高"
        for kw in low_keywords:
            if kw in text:
                return "低"
        return "中"

    def _extract_action(self, text: str) -> str:
        """从分析文本中提取操作倾向"""
        text_lower = text.lower()
        buy_keywords = ["买入", "建仓", "介入", "做多", "积极", "逢低买入"]
        sell_keywords = ["卖出", "减仓", "离场", "回避", "做空", "止损", "退出"]

        for kw in buy_keywords:
            if kw in text:
                return "买入"
        for kw in sell_keywords:
            if kw in text:
                return "卖出"
        return "观望"

    def _extract_signals(self, views: Dict) -> Dict[str, List[str]]:
        """从各角色分析中提取信号"""
        risk_signals = []
        opportunity_signals = []
        optimize_signals = []

        for role_name, result in views.items():
            text = result.get("viewpoint", "")
            if not text:
                continue

            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if "⚠️" in line:
                    risk_signals.append(f"[{role_name}] {line.replace('⚠️', '').strip()}")
                elif "✅" in line:
                    opportunity_signals.append(f"[{role_name}] {line.replace('✅', '').strip()}")
                elif "💡" in line:
                    optimize_signals.append(f"[{role_name}] {line.replace('💡', '').strip()}")

        return {
            "risk": risk_signals,
            "opportunity": opportunity_signals,
            "optimize": optimize_signals,
        }

    def _extract_consensus(self, views: Dict) -> Dict[str, Any]:
        """提取各角色共识"""
        actions = [v.get("action") for v in views.values() if v.get("action") != "N/A"]

        # 统计操作倾向
        action_count = {}
        for a in actions:
            action_count[a] = action_count.get(a, 0) + 1

        # 多数派观点
        consensus_action = max(action_count, key=action_count.get) if action_count else "观望"
        consensus_strength = sum(
            1 for a in actions if a == consensus_action
        ) / len(actions) if actions else 0

        return {
            "action": consensus_action,
            "strength": f"{consensus_strength:.0%}",
            "action_distribution": action_count,
        }

    def _parse_prediction(self, synthesis: str, current_price: float) -> Dict[str, Any]:
        """
        从综合评判文本中解析预测分析JSON块

        返回:
            {
                "trend_forecast": str,
                "trend_confidence": str,
                "forecast_horizon": str,
                "scenario_bull": dict,
                "scenario_base": dict,
                "scenario_bear": dict,
                "predicted_support": float,
                "predicted_resistance": float,
                "breakout_up_prob": str,
                "breakout_down_prob": str,
                "best_entry_window": str,
                "key_catalyst": str,
                "risk_event": str,
            }
        """
        import re

        # 尝试提取 PREDICTION_JSON 块
        pattern = r'```PREDICTION_JSON\s*\n(.*?)\n```'
        match = re.search(pattern, synthesis, re.DOTALL)

        if not match:
            # 兜底：尝试提取任何 JSON 块
            pattern2 = r'```\s*\n(\{.*?\})\n```'
            match = re.search(pattern2, synthesis, re.DOTALL)

        if match:
            try:
                pred = json.loads(match.group(1).strip())
                # 修正数值类型
                pred.setdefault("trend_forecast", "")
                pred.setdefault("trend_confidence", "中")
                pred.setdefault("forecast_horizon", "3-5个交易日")
                pred.setdefault("scenario_bull", {})
                pred.setdefault("scenario_base", {})
                pred.setdefault("scenario_bear", {})
                pred.setdefault("predicted_support", 0.0)
                pred.setdefault("predicted_resistance", 0.0)
                pred.setdefault("breakout_up_prob", "")
                pred.setdefault("breakout_down_prob", "")
                pred.setdefault("best_entry_window", "")
                pred.setdefault("key_catalyst", "")
                pred.setdefault("risk_event", "")
                return pred
            except (json.JSONDecodeError, KeyError) as e:
                print(f"   ⚠️ 预测JSON解析失败: {e}")

        # JSON 解析失败时，基于规则引擎生成基础预测
        return self._rule_based_prediction(current_price)

    def _rule_based_prediction(self, current_price: float) -> Dict[str, Any]:
        """规则引擎兜底：基于当前价格生成基础预测"""
        # 简单基于价格波动范围计算情景
        return {
            "trend_forecast": "数据不足，需更多分析",
            "trend_confidence": "低",
            "forecast_horizon": "3-5个交易日",
            "scenario_bull": {
                "target": f"¥{current_price * 1.08:.2f}",
                "prob": "30%",
                "trigger": "放量突破阻力位",
                "desc": "若主力资金回流且均线多头排列",
            },
            "scenario_base": {
                "target": f"¥{current_price:.2f}",
                "prob": "50%",
                "trigger": "维持当前震荡格局",
                "desc": "继续区间震荡，等待方向选择",
            },
            "scenario_bear": {
                "target": f"¥{current_price * 0.92:.2f}",
                "prob": "20%",
                "trigger": "跌破关键支撑位",
                "desc": "若主力持续流出或大盘跳水",
            },
            "predicted_support": round(current_price * 0.96, 2),
            "predicted_resistance": round(current_price * 1.05, 2),
            "breakout_up_prob": "25%",
            "breakout_down_prob": "35%",
            "best_entry_window": "等待回调至支撑位附近",
            "key_catalyst": "待确认",
            "risk_event": "大盘系统性风险",
        }
