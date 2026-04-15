#!/usr/bin/env python3
"""
竹林司马 - 大模型客户端封装
版本: 1.0.0

统一的大模型调用接口，支持:
- DeepSeek (api.deepseek.com)
- OpenAI (api.openai.com)
- Qwen 通义千问 (dashscope.aliyuncs.com)
- 智谱 GLM (open.bigmodel.cn)
- Ollama 本地模型 (localhost:11434)

所有供应商统一为 OpenAI 兼容协议，仅切换 base_url + api_key。
"""

import os
import json
import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class LLMProvider(Enum):
    """大模型供应商"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    QWEN = "qwen"
    GLM = "glm"
    OLLAMA = "ollama"


# 供应商默认配置
PROVIDER_DEFAULTS = {
    LLMProvider.DEEPSEEK: {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "env_key": "DEEPSEEK_API_KEY",
    },
    LLMProvider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
        "env_key": "OPENAI_API_KEY",
    },
    LLMProvider.QWEN: {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "env_key": "QWEN_API_KEY",
    },
    LLMProvider.GLM: {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4"],
        "env_key": "GLM_API_KEY",
    },
    LLMProvider.OLLAMA: {
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:7b",
        "models": [],  # 动态获取
        "env_key": "",  # Ollama 不需要 API Key
    },
}


@dataclass
class LLMConfig:
    """大模型配置"""
    provider: LLMProvider = LLMProvider.DEEPSEEK
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60
    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 缓存1小时
    # 重试配置
    max_retries: int = 2
    retry_delay: float = 1.0


class LLMClient:
    """
    统一大模型客户端

    使用方式:
        # 从环境变量自动加载
        client = LLMClient()  # 默认 DeepSeek

        # 指定供应商
        client = LLMClient(provider="openai")

        # 调用
        result = client.chat("分析一下贵州茅台的趋势")

        # 结构化输出
        result = client.chat_json("给这只股票打分", schema={...})
    """

    def __init__(self, config: Optional[LLMConfig] = None, **kwargs):
        """
        初始化客户端

        参数:
            config: LLMConfig 配置对象
            **kwargs: 覆盖配置项，如 provider="openai", model="gpt-4o"
        """
        if config:
            self.config = config
        else:
            self.config = self._build_config(**kwargs)

        self._cache: Dict[str, tuple] = {}  # {prompt_hash: (response, timestamp)}
        self._session = None  # 延迟初始化

    def _build_config(self, **kwargs) -> LLMConfig:
        """从环境变量和参数构建配置"""
        # 确定供应商
        provider_str = kwargs.get("provider", os.getenv("LLM_PROVIDER", "deepseek"))
        provider = LLMProvider(provider_str.lower())

        defaults = PROVIDER_DEFAULTS[provider]

        # API Key 优先级: kwargs > 环境变量(供应商特定) > 环境变量(通用)
        api_key = kwargs.get("api_key") or os.getenv(defaults["env_key"]) or os.getenv("LLM_API_KEY", "")

        return LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=kwargs.get("base_url", defaults["base_url"]),
            model=kwargs.get("model", os.getenv("LLM_MODEL", defaults["default_model"])),
            temperature=float(kwargs.get("temperature", os.getenv("LLM_TEMPERATURE", "0.3"))),
            max_tokens=int(kwargs.get("max_tokens", os.getenv("LLM_MAX_TOKENS", "4096"))),
            timeout=int(kwargs.get("timeout", os.getenv("LLM_TIMEOUT", "60"))),
            cache_enabled=kwargs.get("cache_enabled", True),
            max_retries=int(kwargs.get("max_retries", 2)),
        )

    @property
    def _http_session(self):
        """延迟创建 HTTP session"""
        if self._session is None:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            self._session = ctx
        return self._session

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _make_request(self, messages: List[Dict], **override_kwargs) -> Dict:
        """
        发送聊天请求 (使用 urllib，无第三方依赖)

        所有供应商兼容 OpenAI Chat Completions API 格式。
        """
        import urllib.request
        import urllib.error
        import ssl

        url = f"{self.config.base_url}/chat/completions"
        payload = {
            "model": override_kwargs.get("model", self.config.model),
            "messages": messages,
            "temperature": override_kwargs.get("temperature", self.config.temperature),
            "max_tokens": override_kwargs.get("max_tokens", self.config.max_tokens),
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._get_headers(), method="POST")

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=self.config.timeout, context=ctx) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    return result
            except urllib.error.HTTPError as e:
                last_error = e
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 429:  # Rate limit
                    wait = self.config.retry_delay * (attempt + 1)
                    time.sleep(wait)
                    continue
                elif e.code >= 500:  # Server error
                    if attempt < self.config.max_retries:
                        time.sleep(self.config.retry_delay)
                        continue
                raise RuntimeError(f"LLM API 错误 {e.code}: {body}") from e
            except urllib.error.URLError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    continue
                raise RuntimeError(f"LLM 连接失败: {e.reason}") from e
            except Exception as e:
                last_error = e
                raise

        raise RuntimeError(f"LLM 请求失败，已重试 {self.config.max_retries} 次: {last_error}")

    def _extract_content(self, response: Dict) -> str:
        """从 API 响应中提取文本内容"""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise RuntimeError(f"LLM 响应格式异常: {json.dumps(response, ensure_ascii=False)[:200]}")

    def _cache_key(self, messages: List[Dict], **kwargs) -> str:
        """生成缓存键"""
        text = json.dumps(messages, ensure_ascii=False) + str(kwargs.get("temperature", ""))
        return hashlib.md5(text.encode()).hexdigest()

    def chat(
        self,
        message: str,
        system_prompt: str = "你是一位专业的股票分析师。",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
    ) -> str:
        """
        发送聊天消息

        参数:
            message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度（覆盖配置）
            max_tokens: 最大token数（覆盖配置）
            use_cache: 是否使用缓存

        返回:
            模型回复文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # 缓存检查
        if use_cache and self.config.cache_enabled:
            key = self._cache_key(messages, **kwargs)
            if key in self._cache:
                cached_content, cached_time = self._cache[key]
                if time.time() - cached_time < self.config.cache_ttl:
                    return cached_content

        response = self._make_request(messages, **kwargs)
        content = self._extract_content(response)

        # 缓存写入
        if use_cache and self.config.cache_enabled:
            self._cache[key] = (content, time.time())

        return content

    def chat_json(
        self,
        message: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
    ) -> Dict:
        """
        发送聊天消息并解析 JSON 响应

        会自动从回复中提取 JSON 内容（支持 markdown 代码块包裹）。
        """
        if not system_prompt:
            system_prompt = (
                "你是一个数据分析助手。请严格按照要求的 JSON 格式回复，"
                "不要添加任何额外的文字说明。"
            )

        raw = self.chat(message, system_prompt=system_prompt, temperature=temperature)

        # 尝试解析 JSON（处理 markdown 代码块包裹）
        json_str = raw.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            # 去掉首行 ```json 和末行 ```
            lines = [l for l in lines if not l.strip().startswith("```")]
            json_str = "\n".join(lines)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试找到 JSON 子串
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise RuntimeError(f"无法解析 LLM JSON 响应: {raw[:500]}")

    def is_available(self) -> bool:
        """检测大模型是否可用"""
        if not self.config.api_key and self.config.provider != LLMProvider.OLLAMA:
            return False
        try:
            result = self.chat("你好，请回复'OK'", use_cache=False, max_tokens=10)
            return len(result.strip()) > 0
        except Exception:
            return False

    def info(self) -> Dict[str, Any]:
        """返回客户端信息"""
        return {
            "provider": self.config.provider.value,
            "model": self.config.model,
            "base_url": self.config.base_url,
            "has_api_key": bool(self.config.api_key),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
