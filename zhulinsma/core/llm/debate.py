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
    ) -> str:
        """构建股票分析上下文（所有角色共享的基础数据）"""

        lines = [
            f"## 股票: {stock_name}（{stock_code}）",
            f"- 当前价: {current_price}元",
        ]

        # 技术数据
        if technical_data:
            lines.append("\n### 技术面数据")
            for key, val in technical_data.items():
                lines.append(f"- {key}: {val}")

        # 基本面数据
        if fundamental_data:
            lines.append("\n### 基本面数据")
            for key, val in fundamental_data.items():
                lines.append(f"- {key}: {val}")

        # 战法信号
        if strategy_signals:
            lines.append("\n### 战法信号")
            for sig in strategy_signals:
                status = "✅ 已触发" if sig.get("触发") else "⭕ 未触发"
                lines.append(f"- {sig.get('名称', '未知')}: {status}")
                if sig.get("说明"):
                    lines.append(f"  说明: {sig['说明']}")

        # 风险数据
        if risk_data:
            lines.append("\n### 风险评估数据")
            for key, val in risk_data.items():
                lines.append(f"- {key}: {val}")

        # 市场环境
        if market_context:
            lines.append("\n### 市场环境")
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
        individual_views: List[Dict],
        stock_context: str,
    ) -> str:
        """
        汇总辩论，生成最终综合结论

        将四个角色的独立观点汇总，让LLM扮演"首席投资官"进行综合评判。
        """
        views_text = ""
        for v in individual_views:
            if v.get("success"):
                views_text += f"\n### {v['role']}的观点\n{v['viewpoint']}\n"

        prompt = f"""你是竹林司马投研团队的"首席投资官"，现在团队四位分析师已经完成了独立分析。

## 股票: {stock_name}（{stock_code}）

## 四位分析师的观点
{views_text}

## 你的任务
请作为首席投资官，综合四位分析师的观点，做出最终投资决策。

要求:
1. **承认分歧**: 如果分析师意见不一致，明确指出分歧点
2. **加权判断**: 技术面和风险权重更高（各30%），基本面25%，情绪15%
3. **最终结论**: 给出明确的投资建议（买入/观望/回避）+ 仓位建议 + 止损位
4. **风险红线**: 列出2-3条不可违反的风险红线
5. **一句话总结**: 用一句话概括核心观点

输出格式:
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
            system_prompt="你是竹林司马的首席投资官，拥有30年A股投资经验。你擅长综合多方观点，做出理性、果断的投资决策。你永远把风险管理放在第一位。",
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
    ) -> Dict[str, Any]:
        """
        执行完整的多角色辩论分析

        参数:
            stock_name: 股票名称
            stock_code: 股票代码
            current_price: 当前价格
            technical_data: 技术面数据（均线/MACD/RSI/KDJ/量能等）
            fundamental_data: 基本面数据（PE/PB/ROE/市值等）
            strategy_signals: 战法信号列表
            risk_data: 风险评估数据
            market_context: 市场环境数据

        返回:
            {
                "meta": {...},
                "individual_views": {角色名: 分析结果, ...},
                "synthesis": "首席投资官综合结论",
                "debate_report": "完整辩论报告（Markdown）",
                "signal_summary": {"risk": [...], "opportunity": [...], "optimize": [...]},
                "consensus": {"action": "...", "position": "...", "stop_loss": "..."},
            }
        """
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
                individual_views=views_list,
                stock_context=stock_context,
            )
            print("✅")
        except Exception as e:
            synthesis = f"综合评判失败: {str(e)}"
            errors.append(f"综合评判: {str(e)}")
            print(f"❌ {e}")

        total_time = round(time.time() - start_time, 1)

        # 4. 生成完整报告
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
