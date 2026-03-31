#!/usr/bin/env python3
"""
竹林司马安装脚本
"""

from setuptools import setup, find_packages
from zhulinsma.version import get_version

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="zhulinsma",
    version=get_version(),
    author="竹林司马 Team",
    author_email="zhulinsma@example.com",
    description="为杨总定制的技术分析工具 - 广州优化，双重验证",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/zhulinsma",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=1.3.0",
        "numpy>=1.21.0",
        "matplotlib>=3.5.0",
    ],
    extras_require={
        "full": [
            "plotly>=5.0.0",
            "tushare>=1.2.0",
            "yfinance>=0.1.70",
            "scipy>=1.7.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "zhulinsma=zhulinsma.interface.cli:main",
        ],
    },
)
