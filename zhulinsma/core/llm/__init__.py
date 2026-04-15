"""
竹林司马 - 大模型(LLM)集成模块
版本: 2.0.0
日期: 2026年4月15日

对应操作指南第十一章「大模型增强模式」。

提供统一的大模型调用接口，支持多供应商:
- DeepSeek (深度求索)
- OpenAI (GPT-4o / GPT-4o-mini)
- Qwen (通义千问, 阿里云 DashScope)
- 智谱 GLM-4
- Ollama (本地部署)

架构设计:
1. LLMClient - 统一客户端，自动路由到对应供应商
2. StockAnalyst - 股票分析专用 Agent，封装 prompt 工程
3. EnhancedAnalysis - 增强分析引擎，融合规则引擎 + LLM
4. MultiPerspectiveAgent - 多角色辩论引擎（四大角色深度分析）

三种使用模式:
- llm_enhanced: LLM增强模式（单分析师深度解读）
- multi_perspective: 多角度辩论模式（四大角色辩论）
- interactive: 交互式分析模式（持续对话追问）
"""

from .client import LLMClient, LLMConfig, LLMProvider
from .stock_analyst import StockAnalyst
from .enhanced import EnhancedAnalysis
from .debate import MultiPerspectiveAgent, ANALYST_ROLES

__all__ = [
    "LLMClient", "LLMConfig", "LLMProvider",
    "StockAnalyst", "EnhancedAnalysis",
    "MultiPerspectiveAgent", "ANALYST_ROLES",
]
