#!/usr/bin/env python3
"""
竹林司马 - AI 智能分析模块
版本: 1.0.0
日期: 2026年4月14日
位置: 广州

提供五大 AI 分析能力的统一接口:
1. 智能评分 (AIScoreEngine) - 多维度加权评分
2. 信号融合 (SignalFusion) - 多策略信号叠加与置信度
3. 模式识别 (PatternRecognition) - K线形态识别
4. 风险评估 (AIRiskEngine) - 动态风险等级与仓位建议
5. 智能推荐 (AIRecommender) - 个性化推荐与决策支持

当前实现基于规则引擎 + 统计模型，预留 ML/LLM 集成接口。
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 1. 智能评分引擎（v2.0 - 10维自适应，2026-04-16）
# ============================================================

class AIScoreEngine:
    """
    AI 智能评分引擎 v2.0

    从 v1.0 的 6 维升级到 10 维自适应评分:
    ① 趋势强度   (基于均线多头+线性斜率)
    ② 动量指标   (RSI + 5日/20日涨幅)
    ③ 波动风险   (ATR + 日波动率，高分=低风险)
    ④ 量价关系   (修复：使用当日量比 vs 10日均量)
    ⑤ 策略信号   (战法触发数+强度)
    ⑥ 真实资金面  (主力净流入，需外部注入)
    ⑦ 北向资金   (外资今日净买入，需外部注入)
    ⑧ 消息面情绪  (利好/利空公告数，需外部注入)
    ⑨ 板块热度   (行业涨跌排名，需外部注入)
    ⑩ 大盘适配   (大盘涨跌 × 个股强弱)

    外部数据（⑥~⑩）通过 extra_data 参数注入，
    未注入时自动降级到规则引擎默认值（50分中性）。

    预留接口: 替换为 ML 模型 (XGBoost/LightGBM) 进行训练评分
    """

    def __init__(self):
        # 默认权重（10维）
        self.权重 = {
            "趋势强度": 0.20,
            "动量指标": 0.15,
            "波动风险": 0.10,
            "量价关系": 0.12,
            "策略信号": 0.13,
            "真实资金面": 0.12,
            "北向资金":  0.06,
            "消息面情绪": 0.05,
            "板块热度":  0.04,
            "大盘适配":  0.03,
        }

    def 评分(
        self,
        df: pd.DataFrame,
        策略信号列表: Optional[List[Dict]] = None,
        extra_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        综合评分（10维）

        参数:
            df: 标准化 DataFrame (需含 open/high/low/close/volume)
            策略信号列表: StrategyEngine 返回的信号列表
            extra_data: 外部数据字典，可传入 StockDataService.获取全维度数据() 的结果
                {
                    "资金流向": {"主力净流入": float, "主力净流入占比": float},
                    "北向资金": {"今日北向净买入(亿)": float},
                    "公告":     {"利好公告数": int, "利空公告数": int, "情绪倾向": str},
                    "板块信息": {"行业涨跌(%)": float},
                    "大盘环境": {"沪深300涨跌(%)": float},
                }

        返回:
            评分报告（含维度得分、权重、评级说明）
        """
        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)
        extra_data = extra_data or {}

        各维度 = {}

        # ① 趋势强度
        各维度["趋势强度"] = self._趋势评分(close)

        # ② 动量指标
        各维度["动量指标"] = self._动量评分(close)

        # ③ 波动风险（高分=低风险）
        各维度["波动风险"] = self._波动评分(close, high, low)

        # ④ 量价关系（修复：使用真实量比 vs 10日均量）
        各维度["量价关系"] = self._量价评分_v2(close, volume)

        # ⑤ 策略信号
        if 策略信号列表:
            触发信号 = [s for s in 策略信号列表 if s.get("触发")]
            信号平均分 = np.mean([s.get("评分", 0) for s in 触发信号]) if 触发信号 else 0
            触发率 = len(触发信号) / len(策略信号列表) if 策略信号列表 else 0
            各维度["策略信号"] = min(100, 信号平均分 * 0.7 + 触发率 * 30)
        else:
            各维度["策略信号"] = 50

        # ⑥ 真实资金面
        各维度["真实资金面"] = self._真实资金评分(extra_data.get("资金流向"))

        # ⑦ 北向资金
        各维度["北向资金"] = self._北向评分(extra_data.get("北向资金"))

        # ⑧ 消息面情绪
        各维度["消息面情绪"] = self._消息评分(extra_data.get("公告"))

        # ⑨ 板块热度
        各维度["板块热度"] = self._板块评分(extra_data.get("板块信息"))

        # ⑩ 大盘适配
        各维度["大盘适配"] = self._大盘评分(close, extra_data.get("大盘环境"))

        # 加权综合分（有无外部数据均可用）
        综合分 = sum(各维度[k] * self.权重[k] for k in self.权重)

        # 投资评级
        if 综合分 >= 85:
            评级 = "强烈推荐"
        elif 综合分 >= 70:
            评级 = "推荐关注"
        elif 综合分 >= 55:
            评级 = "中性观望"
        elif 综合分 >= 40:
            评级 = "谨慎"
        else:
            评级 = "回避"

        # 标记哪些维度使用了真实数据（排除含"错误"键的降级结果）
        _dim_to_key = {
            "真实资金面": "资金流向",
            "北向资金":   "北向资金",
            "消息面情绪": "公告",
            "板块热度":   "板块信息",
            "大盘适配":   "大盘环境",
        }
        真实数据维度 = [
            k for k in _dim_to_key
            if isinstance(extra_data.get(_dim_to_key[k]), dict)
            and "错误" not in extra_data[_dim_to_key[k]]
        ]

        return {
            "综合评分": round(综合分, 1),
            "投资评级": 评级,
            "各维度评分": {k: round(v, 1) for k, v in 各维度.items()},
            "权重": self.权重,
            "真实数据维度": 真实数据维度,
            "数据完整度": f"{len(真实数据维度)}/5 外部数据维度已注入",
            "评级说明": self._评级说明(评级, 各维度),
        }

    # ───── 基础维度（纯K线计算）─────

    def _趋势评分(self, close: np.ndarray) -> float:
        if len(close) < 20:
            return 50
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        多头 = ma5 > ma10 > ma20
        x = np.arange(20)
        slope = np.polyfit(x, close[-20:], 1)[0]
        标准化斜率 = slope / (np.mean(close[-20:]) + 1e-10)
        score = 50
        if 多头:
            score += 20
        if 标准化斜率 > 0.001:
            score += int(min(30, 标准化斜率 * 5000))
        elif 标准化斜率 < -0.001:
            score -= int(min(30, abs(标准化斜率) * 5000))
        # 加分：价格站上 MA60
        if len(close) >= 60:
            ma60 = np.mean(close[-60:])
            if close[-1] > ma60:
                score += 5
        return max(0, min(100, score))

    def _动量评分(self, close: np.ndarray) -> float:
        if len(close) < 15:
            return 50
        # RSI14 简化计算
        delta = np.diff(close[-15:])
        gains = delta[delta > 0]
        losses = abs(delta[delta < 0])
        avg_gain = np.mean(gains) if len(gains) > 0 else 1e-10
        avg_loss = np.mean(losses) if len(losses) > 0 else 1e-10
        rs = avg_gain / avg_loss
        rsi = 100 - 100 / (1 + rs)
        涨幅5 = (close[-1] - close[-6]) / close[-6] * 100 if len(close) > 5 else 0
        涨幅20 = (close[-1] - close[-21]) / close[-21] * 100 if len(close) > 20 else 0
        # RSI 在 40-65 为强势区
        score = 50
        if 40 <= rsi <= 65:
            score += 15
        elif rsi > 70:
            score -= 10  # 超买风险
        elif rsi < 30:
            score += 10  # 超卖反弹机会
        score += min(20, max(-20, 涨幅5 * 4))
        score += min(15, max(-15, 涨幅20 * 2))
        return max(0, min(100, score))

    def _波动评分(self, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> float:
        if len(close) < 10:
            return 50
        日波动率 = np.mean(np.abs(close[1:] - close[:-1]) / (close[:-1] + 1e-10))
        atr = np.mean(high[-14:] - low[-14:]) / np.mean(close[-14:]) if len(close) >= 14 else 0
        score = 50
        if 日波动率 < 0.015:
            score += 20
        elif 日波动率 < 0.03:
            score += 10
        elif 日波动率 > 0.05:
            score -= 20
        if atr < 0.03:
            score += 10
        elif atr > 0.06:
            score -= 10
        return max(0, min(100, score))

    def _量价评分_v2(self, close: np.ndarray, volume: np.ndarray) -> float:
        """
        量价关系评分 v2
        修复：量比 = 今日量 / 10日均量（而非5日均量/20日均量）
        今日量放大 + 价格上涨 = 积极信号
        """
        if len(close) < 11:
            return 50
        今日量 = volume[-1]
        均量10日 = np.mean(volume[-11:-1])  # 不含今日
        量比 = 今日量 / (均量10日 + 1e-10)

        近1日涨幅 = (close[-1] - close[-2]) / close[-2] if len(close) > 1 else 0
        近5日涨幅 = (close[-1] - close[-6]) / close[-6] if len(close) > 5 else 0

        score = 50
        # 量价配合判断
        if 近1日涨幅 > 0.005 and 1.3 <= 量比 <= 3.0:
            score += 30   # 价涨量增（理想形态）
        elif 近1日涨幅 < -0.005 and 量比 > 1.5:
            score -= 25   # 价跌量增（主力出货嫌疑）
        elif 近1日涨幅 > 0.005 and 量比 < 0.8:
            score -= 10   # 价涨缩量（上涨无力）
        elif 近1日涨幅 < -0.005 and 量比 < 0.7:
            score += 8    # 价跌缩量（控盘良好）
        elif 量比 > 3.0:
            score -= 5    # 过度放量警惕

        # 5日趋势附加
        score += min(10, max(-10, 近5日涨幅 * 100))
        return max(0, min(100, score))

    # ───── 外部数据维度（需注入）─────

    def _真实资金评分(self, 资金数据: Optional[Dict]) -> float:
        """真实资金面评分（基于 StockDataService.获取资金流向()）"""
        if not 资金数据 or "错误" in 资金数据:
            return 50  # 无数据时中性
        主力净流入 = float(资金数据.get("主力净流入", 0) or 0)
        占比 = float(资金数据.get("主力净流入占比", 0) or 0)
        score = 50
        if 主力净流入 > 5e7:     score += 40
        elif 主力净流入 > 2e7:   score += 30
        elif 主力净流入 > 5e6:   score += 20
        elif 主力净流入 > 0:     score += 10
        elif 主力净流入 > -1e7:  score -= 10
        elif 主力净流入 > -5e7:  score -= 25
        else:                    score -= 40
        # 占比修正
        if abs(占比) > 5:
            score += 5 if 占比 > 0 else -5
        return max(0, min(100, score))

    def _北向评分(self, 北向数据: Optional[Dict]) -> float:
        """北向资金评分"""
        if not 北向数据 or "错误" in 北向数据:
            return 50
        今日净买入 = float(北向数据.get("今日北向净买入(亿)", 0) or 0)
        近5日 = float(北向数据.get("近5日累计(亿)", 0) or 0)
        score = 50
        if 今日净买入 > 50:    score += 30
        elif 今日净买入 > 20:  score += 20
        elif 今日净买入 > 0:   score += 10
        elif 今日净买入 > -20: score -= 10
        else:                  score -= 20
        if 近5日 > 100:        score += 10
        elif 近5日 < -50:      score -= 10
        return max(0, min(100, score))

    def _消息评分(self, 公告数据: Optional[Dict]) -> float:
        """消息面情绪评分（基于公告）"""
        if not 公告数据 or "错误" in 公告数据:
            return 50
        利好 = int(公告数据.get("利好公告数", 0) or 0)
        利空 = int(公告数据.get("利空公告数", 0) or 0)
        情绪 = 公告数据.get("情绪倾向", "中性")
        score = 50
        if 情绪 == "利好":
            score += min(30, 利好 * 10)
        elif 情绪 == "利空":
            score -= min(30, 利空 * 10)
        return max(0, min(100, score))

    def _板块评分(self, 板块数据: Optional[Dict]) -> float:
        """板块热度评分（行业今日涨跌幅）"""
        if not 板块数据 or "错误" in 板块数据:
            return 50
        行业涨跌 = float(板块数据.get("行业涨跌(%)", 0) or 0)
        score = 50 + min(30, max(-30, 行业涨跌 * 10))
        return max(0, min(100, score))

    def _大盘评分(self, close: np.ndarray, 大盘数据: Optional[Dict]) -> float:
        """大盘适配评分（大盘强弱 × 个股相对强弱）"""
        大盘涨跌 = 0.0
        if 大盘数据 and "错误" not in 大盘数据:
            大盘涨跌 = float(大盘数据.get("沪深300涨跌(%)", 0) or 0)

        score = 50 + min(20, max(-20, 大盘涨跌 * 5))

        # 个股相对强弱（今日涨幅 vs 大盘）
        if len(close) > 1:
            个股今日涨幅 = (close[-1] - close[-2]) / close[-2] * 100
            相对强弱 = 个股今日涨幅 - 大盘涨跌
            if 相对强弱 > 3:
                score += 10   # 强于大盘
            elif 相对强弱 < -3:
                score -= 10   # 弱于大盘

        return max(0, min(100, score))

    def _评级说明(self, 评级: str, 各维度: Dict) -> str:
        weak = [k for k, v in 各维度.items() if v < 40]
        strong = [k for k, v in 各维度.items() if v > 70]
        parts = []
        if 评级 in ("强烈推荐", "推荐关注"):
            if strong:
                parts.append(f"强项: {'、'.join(strong)}")
        if weak:
            parts.append(f"弱项: {'、'.join(weak)}")
        return " ".join(parts) if parts else "各维度均衡"


# ============================================================
# 2. 信号融合引擎
# ============================================================

class SignalFusion:
    """
    信号融合引擎

    将多策略信号进行融合，计算综合置信度。
    支持加权投票、贝叶斯融合等策略。

    预留接口: 替换为深度学习融合模型
    """

    def 融合(self, 信号列表: List[Dict]) -> Dict[str, Any]:
        """
        融合多策略信号

        参数:
            信号列表: StrategySignal.to_dict() 的列表

        返回:
            融合结果
        """
        if not 信号列表:
            return {"置信度": 0, "方向": "观望", "说明": "无信号"}

        触发信号 = [s for s in 信号列表 if s.get("触发")]
        买入信号 = [s for s in 触发信号 if s.get("信号类型") == "买入"]
        卖出信号 = [s for s in 触发信号 if s.get("信号类型") == "卖出"]

        总数 = len(信号列表)
        触发数 = len(触发信号)
        买入数 = len(买入信号)
        卖出数 = len(卖出信号)

        # 加权置信度（基于评分）
        if 触发信号:
            总评分 = sum(s.get("评分", 0) for s in 触发信号)
            置信度 = min(100, 总评分 / 触发数)
        else:
            置信度 = 0

        # 方向判断
        if 买入数 > 卖出数 and 买入数 >= 2:
            方向 = "看多"
        elif 卖出数 > 买入数 and 卖出数 >= 1:
            方向 = "看空"
        else:
            方向 = "观望"

        # 信号强度
        if 置信度 >= 80:
            强度 = "强"
        elif 置信度 >= 50:
            强度 = "中"
        else:
            强度 = "弱"

        return {
            "置信度": round(置信度, 1),
            "方向": 方向,
            "强度": 强度,
            "触发统计": {
                "总策略数": 总数,
                "触发数": 触发数,
                "买入数": 买入数,
                "卖出数": 卖出数,
                "触发率": round(触发数 / 总数, 2) if 总数 > 0 else 0,
            },
            "建议": f"{方向}{强度}，置信度{置信度:.0f}%",
        }


# ============================================================
# 3. K线形态识别
# ============================================================

class PatternRecognition:
    """
    K线形态识别器

    识别常见K线形态: 锤子线/十字星/吞没/启明星/黄昏星等。
    基于规则匹配，预留 CNN/LSTM 图像识别接口。
    """

    def 识别(self, df: pd.DataFrame, 最近N日: int = 3) -> Dict[str, Any]:
        """识别最近的K线形态"""
        open_ = df["open"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        close = df["close"].values.astype(float)

        n = len(close)
        if n < 5:
            return {"形态列表": [], "说明": "数据不足"}

        形态列表 = []
        实体 = close - open_
        影线上 = high - np.maximum(close, open_)
        影线下 = np.minimum(close, open_) - low
        实体绝对 = np.abs(实体)
        总幅度 = high - low

        # 检测最近N日的形态
        for i in range(max(0, n - 最近N日), n - 1):
            形态 = self._检测单日形态(
                实体绝对[i], 实体[i], 影线上[i], 影线下[i], 总幅度[i]
            )
            if 形态:
                形态["位置"] = i
                形态列表.append(形态)

            # 双日形态
            if i > 0:
                双日 = self._检测双日形态(实体[i-1:i+1], close[i-1:i+1])
                if 双日:
                    双日["位置"] = i - 1
                    形态列表.append(双日)

        # 整体形态判断
        综合信号 = "中性"
        看多形态 = [f for f in 形态列表 if f.get("信号") == "看多"]
        看空形态 = [f for f in 形态列表 if f.get("信号") == "看空"]

        if len(看多形态) > len(看空形态):
            综合信号 = "偏多"
        elif len(看空形态) > len(看多形态):
            综合信号 = "偏空"

        return {
            "形态列表": 形态列表,
            "综合信号": 综合信号,
            "看多形态数": len(看多形态),
            "看空形态数": len(看空形态),
        }

    def _检测单日形态(self, 实体绝对, 实体, 影线上, 影线下, 总幅度) -> Optional[Dict]:
        if 总幅度 < 1e-10:
            return None

        上影比 = 影线上 / 总幅度
        下影比 = 影线下 / 总幅度
        实体比 = 实体绝对 / 总幅度

        # 锤子线: 下影线长，上影线短，实体小
        if 下影比 > 0.6 and 上影比 < 0.1 and 实体比 < 0.3:
            return {"名称": "锤子线", "信号": "看多", "强度": "强"}

        # 倒锤子线: 上影线长，下影线短
        if 上影比 > 0.6 and 下影比 < 0.1 and 实体比 < 0.3:
            return {"名称": "倒锤子线", "信号": "看空", "强度": "中"}

        # 十字星: 实体极小
        if 实体比 < 0.1:
            return {"名称": "十字星", "信号": "转折", "强度": "中"}

        # 大阳线: 实体大且阳线
        if 实体 > 0 and 实体比 > 0.7:
            return {"名称": "大阳线", "信号": "看多", "强度": "强"}

        # 大阴线: 实体大且阴线
        if 实体 < 0 and 实体比 > 0.7:
            return {"名称": "大阴线", "信号": "看空", "强度": "强"}

        return None

    def _检测双日形态(self, 实体, close) -> Optional[Dict]:
        if len(实体) < 2:
            return None

        # 看涨吞没: 阴线+阳线，阳线实体完全包含阴线
        if 实体[0] < 0 and 实体[1] > 0:
            if close[1] > close[0] and abs(实体[1]) > abs(实体[0]):
                return {"名称": "看涨吞没", "信号": "看多", "强度": "强"}

        # 看跌吞没: 阳线+阴线
        if 实体[0] > 0 and 实体[1] < 0:
            if close[1] < close[0] and abs(实体[1]) > abs(实体[0]):
                return {"名称": "看跌吞没", "信号": "看空", "强度": "强"}

        return None


# ============================================================
# 4. AI 风险引擎
# ============================================================

class AIRiskEngine:
    """
    AI 风险引擎 v2.0

    基于多维度动态风险评估，提供:
    - 风险等级（低/中/高/极高）
    - 建议仓位上限
    - 智能止损位（优先使用支撑阻力位，次用 ATR-based）
    - 止盈目标（保守/基准/乐观，参考阻力位）

    v2.0 新增: 集成 SupportResistanceAnalyzer，止损止盈更精准
    预留接口: 集成 VaR/CVaR 模型
    """

    def 评估(self, df: pd.DataFrame, 持仓成本: Optional[float] = None) -> Dict[str, Any]:
        """综合风险评估"""
        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        if len(close) < 20:
            return {"风险等级": "未知", "说明": "数据不足"}

        当前价 = float(close[-1])

        # 1. 波动率风险
        日收益率 = np.diff(close) / close[:-1]
        日波动率 = np.std(日收益率[-20:]) if len(日收益率) >= 20 else np.std(日收益率)
        年化波动率 = 日波动率 * np.sqrt(252)

        # 2. ATR
        atr = np.mean((high[-14:] - low[-14:])) if len(close) >= 14 else np.mean(high - low)

        # 3. 最大回撤（20日）
        滚动最大 = np.maximum.accumulate(close[-20:])
        回撤 = (滚动最大 - close[-20:]) / 滚动最大
        最大回撤 = float(np.max(回撤))

        # 4. 综合风险分数
        波动风险分 = min(40, 年化波动率 * 100)
        回撤风险分 = min(40, 最大回撤 * 200)
        趋势风险分 = self._趋势风险分(close)
        总风险分 = 波动风险分 + 回撤风险分 + 趋势风险分

        if 总风险分 < 30:
            风险等级 = "低风险"
        elif 总风险分 < 55:
            风险等级 = "中风险"
        elif 总风险分 < 75:
            风险等级 = "高风险"
        else:
            风险等级 = "极高风险"

        仓位映射 = {"低风险": 0.30, "中风险": 0.20, "高风险": 0.10, "极高风险": 0.0}
        仓位上限 = 仓位映射.get(风险等级, 0.0)

        # ── 新增：支撑阻力分析，优化止损止盈 ──────────────────
        支撑阻力结果 = {}
        止损位 = 当前价 - 2 * atr  # ATR默认
        止盈保守 = 当前价 + atr
        止盈基准 = 当前价 + 2 * atr
        止盈乐观 = 当前价 + 3 * atr

        try:
            from zhulinsma.core.analysis.support_resistance import SupportResistanceAnalyzer
            sr = SupportResistanceAnalyzer(灵敏度=0.02)
            sr_result = sr.分析支撑阻力(收盘价=close, 最高价=high, 最低价=low)
            支撑阻力结果 = sr_result

            # 用最近支撑位做止损（比纯ATR更精准）
            最近支撑 = sr_result.get("最近支撑")
            if 最近支撑 and 最近支撑 > 当前价 * 0.85:
                # 支撑位有效（不超过15%距离）→ 在支撑位下方留1%缓冲
                止损位 = round(最近支撑 * 0.99, 2)
            else:
                止损位 = round(当前价 - 2 * atr, 2)

            # 用阻力位做止盈
            阻力位列表 = sr_result.get("阻力位", [])
            if 阻力位列表:
                止盈保守 = round(阻力位列表[0], 2)  # 第一阻力
                止盈基准 = round(阻力位列表[1] if len(阻力位列表) > 1 else 当前价 + 2 * atr, 2)
                止盈乐观 = round(阻力位列表[2] if len(阻力位列表) > 2 else 当前价 + 3 * atr, 2)
        except Exception:
            pass

        # 持仓成本保护（用 is not None，允许成本=0时也生效）
        if 持仓成本 is not None and 持仓成本 > 0:
            止损位 = min(止损位, 持仓成本 * 0.95)

        return {
            "风险等级": 风险等级,
            "综合风险分": round(总风险分, 1),
            "当前价": round(当前价, 2),
            "止损位": round(止损位, 2),
            "止损参考": f"支撑位下方1%缓冲" if 支撑阻力结果.get("最近支撑") else "ATR×2",
            "止盈目标": {
                "保守": round(止盈保守, 2),
                "基准": round(止盈基准, 2),
                "乐观": round(止盈乐观, 2),
            },
            "仓位上限": f"{仓位上限*100:.0f}%",
            "支撑阻力": {
                "支撑位": 支撑阻力结果.get("支撑位", []),
                "阻力位": 支撑阻力结果.get("阻力位", []),
                "最近支撑": 支撑阻力结果.get("最近支撑"),
                "最近阻力": 支撑阻力结果.get("最近阻力"),
                "支撑强度": 支撑阻力结果.get("支撑强度", "N/A"),
                "阻力强度": 支撑阻力结果.get("阻力强度", "N/A"),
            },
            "风险明细": {
                "年化波动率": f"{年化波动率:.1%}",
                "最大回撤": f"{最大回撤:.1%}",
                "ATR": round(atr, 2),
                "波动风险分": round(波动风险分, 1),
                "回撤风险分": round(回撤风险分, 1),
                "趋势风险分": round(趋势风险分, 1),
            },
        }

    def _趋势风险分(self, close: np.ndarray) -> float:
        if len(close) < 20:
            return 20
        ma5 = np.mean(close[-5:])
        ma20 = np.mean(close[-20:])
        if ma5 < ma20:
            return 20
        return 5


# ============================================================
# 5. 智能推荐引擎
# ============================================================

class AIRecommender:
    """
    智能推荐引擎

    整合评分、信号融合、形态识别、风险评估，
    输出结构化的投资建议。

    预留接口: 集成 LLM 生成自然语言分析报告
    """

    def __init__(self):
        self.评分引擎 = AIScoreEngine()
        self.信号融合 = SignalFusion()
        self.形态识别 = PatternRecognition()
        self.风险引擎 = AIRiskEngine()

    def 分析(
        self,
        df: pd.DataFrame,
        股票代码: str = "",
        策略信号列表: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        综合智能分析

        整合五大AI能力，输出完整分析报告。
        """
        # 1. 智能评分
        评分报告 = self.评分引擎.评分(df, 策略信号列表)

        # 2. 信号融合
        信号融合结果 = self.信号融合.融合(策略信号列表 or [])

        # 3. 形态识别
        形态结果 = self.形态识别.识别(df)

        # 4. 风险评估
        风险报告 = self.风险引擎.评估(df)

        # 5. 综合建议
        建议 = self._生成建议(评分报告, 信号融合结果, 风险报告)

        return {
            "股票代码": 股票代码,
            "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "最新价": 风险报告["当前价"],
            "AI评分": 评分报告,
            "信号融合": 信号融合结果,
            "形态识别": 形态结果,
            "风险评估": 风险报告,
            "综合建议": 建议,
            "免责声明": "本分析基于历史数据和技术指标，仅供参考，不构成投资建议。投资有风险，入市需谨慎。",
        }

    def _生成建议(self, 评分, 信号, 风险) -> str:
        parts = []

        if 评分["投资评级"] in ("强烈推荐", "推荐关注"):
            parts.append(评分["投资评级"])
        if 信号["方向"] == "看多":
            parts.append("多信号共振")
        elif 信号["方向"] == "看空":
            parts.append("偏空信号")

        if 风险["风险等级"] == "低风险":
            parts.append("风险可控")
        elif 风险["风险等级"] in ("高风险", "极高风险"):
            parts.append("注意风险")

        return "，".join(parts) if parts else "暂无明显方向"


# ========== 测试 ==========

if __name__ == "__main__":
    import json

    np.random.seed(42)
    n = 80
    close = 28.5 + np.cumsum(np.random.randn(n) * 0.3)
    close = np.clip(close, 24.0, 36.0)

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n),
        "open": close + np.random.randn(n) * 0.2,
        "high": close + np.abs(np.random.randn(n)) * 0.3,
        "low": close - np.abs(np.random.randn(n)) * 0.3,
        "close": close,
        "volume": np.abs(np.random.randn(n)) * 5000000 + 8000000,
    })

    recommender = AIRecommender()
    report = recommender.分析(df, "600406")

    print("=" * 60)
    print("  竹林司马 - AI 智能分析报告")
    print("=" * 60)
    print(f"\n股票: {report['股票代码']}")
    print(f"最新价: {report['最新价']}")
    print(f"\nAI评分: {report['AI评分']['综合评分']} ({report['AI评分']['投资评级']})")
    print(f"信号融合: {report['信号融合']['建议']}")
    print(f"形态识别: {report['形态识别']['综合信号']} ({report['形态识别']['看多形态数']}多/{report['形态识别']['看空形态数']}空)")
    print(f"风险: {report['风险评估']['风险等级']} (仓位{report['风险评估']['仓位上限']})")
    print(f"综合建议: {report['综合建议']}")
    print(f"\n各维度评分:")
    for k, v in report['AI评分']['各维度评分'].items():
        bar = '█' * (v // 10) + '░' * (10 - v // 10)
        print(f"  {k}: {v:>5.1f}  {bar}")
