#!/usr/bin/env python3
"""
竹林司马 - AI 增强分析模块 (LLM-Enhanced)
版本: 1.0.0
日期: 2026年4月15日

本模块是大模型增强模式的入口，将规则引擎与 LLM 融合:
- 量化指标由规则引擎快速计算（确定性、低延迟）
- 解读/建议/预测由 LLM 生成（语义理解、自然语言输出）
- 双引擎协同：规则引擎提供数据，LLM 提供洞察

降级策略:
1. 优先使用 LLM 增强模式
2. LLM 不可用时自动降级到纯规则引擎
3. 缓存 LLM 响应避免重复调用
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime


class EnhancedAnalysis:
    """
    增强分析引擎

    融合规则引擎（量化计算）+ LLM（语义理解），
    提供比纯规则引擎更专业、更易读的分析报告。

    使用方式:
        enhanced = EnhancedAnalysis()
        result = enhanced.full_analysis(df, "600406", "国电南瑞")
    """

    def __init__(self, **llm_kwargs):
        """
        初始化增强引擎

        参数:
            **llm_kwargs: 传递给 LLMClient 的配置
                provider: "deepseek" / "openai" / "qwen" / "glm" / "ollama"
                api_key: API 密钥（也可通过环境变量设置）
                model: 模型名称
        """
        self._llm_available = None  # 延迟检测
        self._client = None
        self._analyst = None
        self._llm_kwargs = llm_kwargs

        # 规则引擎（始终可用）
        self._init_rule_engines()

    def _init_rule_engines(self):
        """初始化规则引擎"""
        try:
            from zhulinsma.core.ai import (
                AIScoreEngine, SignalFusion,
                PatternRecognition, AIRiskEngine,
            )
            from zhulinsma.core.analysis.risk_analyzer import RiskAnalyzer

            self.score_engine = AIScoreEngine()
            self.signal_fusion = SignalFusion()
            self.pattern_recognition = PatternRecognition()
            self.risk_engine = AIRiskEngine()
            self.risk_analyzer = RiskAnalyzer()
            self._rules_ok = True
        except ImportError as e:
            self._rules_ok = False
            self._import_error = str(e)

    def _init_llm(self):
        """延迟初始化 LLM"""
        if self._llm_available is not None:
            return

        try:
            from zhulinsma.core.llm import LLMClient, StockAnalyst

            self._client = LLMClient(**self._llm_kwargs)
            self._analyst = StockAnalyst(client=self._client)
            self._llm_available = True
        except Exception as e:
            self._llm_available = False
            self._llm_error = str(e)

    @property
    def llm_available(self) -> bool:
        """LLM 是否可用"""
        self._init_llm()
        return self._llm_available

    @property
    def mode(self) -> str:
        """当前分析模式"""
        if self.llm_available:
            return "LLM 增强模式"
        return "规则引擎模式（LLM 不可用）"

    def full_analysis(
        self,
        df,
        stock_code: str,
        stock_name: str,
        strategy_signals: Optional[List[Dict]] = None,
        price_info: Optional[Dict] = None,
        ma_data: Optional[Dict] = None,
        macd_data: Optional[Dict] = None,
        rsi_data: Optional[Dict] = None,
        kdj_data: Optional[Dict] = None,
        volume_info: Optional[Dict] = None,
        trend_info: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        完整增强分析

        执行规则引擎计算 + LLM 解读，返回全部分析结果。

        参数:
            df: 标准 DataFrame (open/high/low/close/volume)
            stock_code: 股票代码
            stock_name: 股票名称
            strategy_signals: 战法信号列表
            price_info/ma_data/...: 各维度的预计算数据

        返回:
            完整分析结果字典，包含各模块的分析文本
        """
        import numpy as np

        # ── 第一步：规则引擎计算（始终执行）──
        rule_results = self._run_rule_engines(df, stock_code, strategy_signals)

        # ── 第二步：LLM 增强（如果可用）──
        llm_results = {}
        if self.llm_available and price_info:
            current_price = float(df["close"].values[-1])
            llm_results = self._run_llm_analysis(
                stock_name=stock_name,
                stock_code=stock_code,
                current_price=current_price,
                price_info=price_info or {},
                ma_data=ma_data or {},
                macd_data=macd_data or {},
                rsi_data=rsi_data or {},
                kdj_data=kdj_data or {},
                volume_info=volume_info or {},
                trend_info=trend_info or {},
                strategy_signals=strategy_signals or [],
                rule_results=rule_results,
            )

        return {
            "meta": {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": self.mode,
                "llm_provider": self._client.info().get("provider") if self._client else None,
            },
            "rule_engine": rule_results,
            "llm_enhanced": llm_results,
        }

    def _run_rule_engines(self, df, stock_code: str, strategy_signals: List) -> Dict:
        """运行规则引擎，返回各模块结果"""
        if not self._rules_ok:
            return {"error": f"规则引擎加载失败: {self._import_error}"}

        results = {}

        # 1. AI 评分
        try:
            results["score"] = self.score_engine.评分(df, strategy_signals)
        except Exception as e:
            results["score"] = {"error": str(e)}

        # 2. 信号融合
        try:
            results["signal_fusion"] = self.signal_fusion.融合(strategy_signals or [])
        except Exception as e:
            results["signal_fusion"] = {"error": str(e)}

        # 3. 形态识别
        try:
            results["pattern"] = self.pattern_recognition.识别(df)
        except Exception as e:
            results["pattern"] = {"error": str(e)}

        # 4. 风险评估（双引擎）
        try:
            results["risk"] = self.risk_engine.评估(df)
        except Exception as e:
            results["risk"] = {"error": str(e)}

        try:
            close = df["close"].values.astype(float)
            volume = df["volume"].values.astype(float) if "volume" in df.columns else None
            results["risk_detail"] = self.risk_analyzer.评估风险(
                收盘价=close, 成交量=volume
            )
        except Exception as e:
            results["risk_detail"] = {"error": str(e)}

        return results

    def _run_llm_analysis(
        self,
        stock_name: str,
        stock_code: str,
        current_price: float,
        price_info: Dict,
        ma_data: Dict,
        macd_data: Dict,
        rsi_data: Dict,
        kdj_data: Dict,
        volume_info: Dict,
        trend_info: Dict,
        strategy_signals: List[Dict],
        rule_results: Dict,
    ) -> Dict[str, Any]:
        """运行 LLM 增强分析"""
        results = {}
        errors = []

        # 1. 选股维度解读
        try:
            results["dimensions"] = self._analyst.analyze_dimensions(
                stock_name=stock_name,
                stock_code=stock_code,
                price_info=price_info,
                ma_data=ma_data,
                macd_data=macd_data,
                rsi_data=rsi_data,
                kdj_data=kdj_data,
                volume_info=volume_info,
                trend_info=trend_info,
            )
        except Exception as e:
            errors.append(f"维度解读失败: {e}")
            results["dimensions"] = ""

        # 2. 战法信号解读
        try:
            results["strategies"] = self._analyst.analyze_strategies(
                stock_name=stock_name,
                stock_code=stock_code,
                strategy_signals=strategy_signals,
            )
        except Exception as e:
            errors.append(f"战法解读失败: {e}")
            results["strategies"] = ""

        # 3. 操作执行方案
        try:
            score = rule_results.get("score", {})
            signal = rule_results.get("signal_fusion", {})
            risk = rule_results.get("risk", {})
            results["execution_plan"] = self._analyst.generate_execution_plan(
                stock_name=stock_name,
                stock_code=stock_code,
                current_price=current_price,
                risk_report=risk,
                signal_fusion=signal,
                score_report=score,
            )
        except Exception as e:
            errors.append(f"操作方案失败: {e}")
            results["execution_plan"] = ""

        # 4. 风险评估深度解读
        try:
            risk = rule_results.get("risk", {})
            results["risk_analysis"] = self._analyst.analyze_risk(
                stock_name=stock_name,
                stock_code=stock_code,
                risk_data=risk,
                current_price=current_price,
            )
        except Exception as e:
            errors.append(f"风险解读失败: {e}")
            results["risk_analysis"] = ""

        # 5. 投资建议
        try:
            score = rule_results.get("score", {})
            signal = rule_results.get("signal_fusion", {})
            risk = rule_results.get("risk", {})
            pattern = rule_results.get("pattern", {})
            results["investment_advice"] = self._analyst.generate_investment_advice(
                stock_name=stock_name,
                stock_code=stock_code,
                current_price=current_price,
                score_report=score,
                signal_fusion=signal,
                risk_report=risk,
                pattern_result=pattern,
                strategy_signals=strategy_signals,
            )
        except Exception as e:
            errors.append(f"投资建议失败: {e}")
            results["investment_advice"] = ""

        # 6. 趋势预测
        try:
            # 从 price_info 提取近期价格
            recent_prices = price_info.get("recent_prices", [])
            results["trend_prediction"] = self._analyst.predict_trend(
                stock_name=stock_name,
                stock_code=stock_code,
                current_price=current_price,
                ma_data=ma_data,
                macd_data=macd_data,
                score_report=rule_results.get("score", {}),
                recent_prices=recent_prices,
            )
        except Exception as e:
            errors.append(f"趋势预测失败: {e}")
            results["trend_prediction"] = ""

        results["_errors"] = errors
        results["_success_count"] = 6 - len(errors)
        return results
