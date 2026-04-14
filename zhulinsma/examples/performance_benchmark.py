#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 性能基准测试示例
运行全量基准测试，对比传统实现与向量化引擎的加速效果
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import warnings
warnings.filterwarnings("ignore")


def main():
    print("\n" + "═" * 65)
    print("  🚀 竹林司马 (Zhulinsma) - 性能基准测试")
    print("═" * 65)

    from zhulinsma.core.performance.benchmark import PerformanceBenchmark

    bench = PerformanceBenchmark(重复次数=5)

    for 数据量 in [1000, 5000, 10000]:
        print(f"\n⚡ 数据量: {数据量:,} 条")
        报告 = bench.运行全量基准测试(数据量=数据量)
        bench.打印报告(报告)

    print("📊 基准测试完成！向量化引擎在大数据量下加速效果更显著。")
    print("═" * 65 + "\n")


if __name__ == "__main__":
    main()
