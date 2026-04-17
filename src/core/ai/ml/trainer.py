#!/usr/bin/env python3
"""
MLTrainer - 训练脚本
完整训练流程：数据获取 → 特征工程 → 模型训练 → 评估 → 持久化

竹林司马 AI驱动A股技术分析引擎 · ML预测模块

使用方式：
    python trainer.py --codes 600000,000001 --start 20180101 --end 20251231
"""

import os
import sys
import argparse
import json
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline import MLDataPipeline
from models.price_direction import PriceDirectionModel
from models.risk_quant import RiskQuantModel


def parse_args():
    parser = argparse.ArgumentParser(description="A股ML模型训练")
    parser.add_argument("--codes", type=str, default="600000,000001,600036,601318",
                        help="股票代码，逗号分隔")
    parser.add_argument("--start", type=str, default="20180101")
    parser.add_argument("--end",   type=str, default="20251231")
    parser.add_argument("--model_dir", type=str, default="models/ml")
    parser.add_argument("--index_code", type=str, default="sh000001")
    return parser.parse_args()


def main():
    args = parse_args()
    stock_codes = [c.strip() for c in args.codes.split(",")]
    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        args.model_dir
    )

    print("=" * 60)
    print("竹林司马 · ML模型训练")
    print(f"股票数量: {len(stock_codes)}")
    print(f"日期范围: {args.start} ~ {args.end}")
    print(f"模型目录: {model_dir}")
    print("=" * 60)

    # ── Step 1: 数据管道 ──────────────────────────
    print("\n[Step 1] 构建数据集 ...")
    pipeline = MLDataPipeline(
        stock_codes=stock_codes,
        index_code=args.index_code,
    )
    dataset = pipeline.build_dataset(
        start_date=args.start,
        end_date=args.end,
        horizons=[1, 5, 20],
    )
    df_all = pd.merge(dataset["features"], dataset["labels"], on=["stock_code", "date"], how="inner")

    if len(df_all) < 200:
        print("[警告] 样本量过少，建议增加股票数量或拉长日期范围")
        return

    # ── Step 2: 涨跌方向模型 ──────────────────────
    print("\n[Step 2] 训练涨跌方向模型 (XGBoost) ...")
    direction_model = PriceDirectionModel(model_dir=model_dir)
    direction_results = direction_model.fit(
        df_features=df_all,
        horizons=[1, 5, 20],
        val_size=0.2,
    )

    # ── Step 3: 风险量化模型 ──────────────────────
    print("\n[Step 3] 训练风险量化模型 (LightGBM) ...")
    risk_model = RiskQuantModel(model_dir=model_dir)
    risk_results = risk_model.fit(df_features=df_all, val_size=0.2)

    # ── Step 4: 保存训练报告 ──────────────────────
    report = {
        "trained_at": datetime.now().isoformat(),
        "stock_codes": stock_codes,
        "date_range": {"start": args.start, "end": args.end},
        "total_samples": int(len(df_all)),
        "features_count": int(len([c for c in df_all.columns
                                   if c not in ["stock_code","date","close"]])),
        "direction_model": {
            f"horizon_{h}d": v for h, v in direction_results.items()
        },
        "risk_model": risk_results,
    }

    report_path = os.path.join(model_dir, "training_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 训练报告已保存: {report_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
