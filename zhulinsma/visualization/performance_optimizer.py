#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竹林司马 - 可视化性能优化器
优化图表和报告生成性能，提升用户体验

作者：杨总的工作助手
日期：2026年3月30日
版本：1.0.0
"""

import time
import psutil
from typing import Dict, List, Optional, Union, Any, Callable
from functools import lru_cache, wraps
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')


class PerformanceOptimizer:
    """可视化性能优化器"""
    
    def __init__(self, 
                 缓存大小: int = 100,
                 启用缓存: bool = True,
                 启用懒加载: bool = True,
                 启用并行处理: bool = True):
        """
        初始化性能优化器
        
        参数:
           缓存大小: 缓存大小限制
           启用缓存: 是否启用缓存机制
           启用懒加载: 是否启用懒加载
           启用并行处理: 是否启用并行处理
        """
        self.缓存大小 = 缓存大小
        self.启用缓存 = 启用缓存
        self.启用懒加载 = 启用懒加载
        self.启用并行处理 = 启用并行处理
        
        # 性能统计
        self.性能统计 = {
            '总图表生成次数': 0,
            '缓存命中次数': 0,
            '平均生成时间_ms': 0.0,
            '最大内存使用_MB': 0.0,
            '并行任务数': 0
        }
        
        # 缓存存储
        self.图表缓存 = {}
        self.数据缓存 = {}
        
        print(f"[性能优化器] 初始化完成 - 缓存: {启用缓存}, 懒加载: {启用懒加载}, 并行: {启用并行处理}")
    
    def 性能监控(self, func: Callable) -> Callable:
        """
        性能监控装饰器
        
        参数:
            func: 要监控的函数
            
        返回:
            装饰后的函数
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 记录开始时间
            开始时间 = time.time()
            
            # 监控内存使用
            开始内存 = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            try:
                # 执行函数
                result = func(*args, **kwargs)
                
                # 计算执行时间
                结束时间 = time.time()
                执行时间_ms = (结束时间 - 开始时间) * 1000
                
                # 记录结束内存
                结束内存 = psutil.Process().memory_info().rss / 1024 / 1024
                内存增量 = 结束内存 - 开始内存
                
                # 更新性能统计
                self.性能统计['总图表生成次数'] += 1
                self.性能统计['平均生成时间_ms'] = (
                    self.性能统计['平均生成时间_ms'] * (self.性能统计['总图表生成次数'] - 1) + 执行时间_ms
                ) / self.性能统计['总图表生成次数']
                
                if 内存增量 > self.性能统计['最大内存使用_MB']:
                    self.性能统计['最大内存使用_MB'] = 内存增量
                
                # 打印性能信息（仅在调试模式下）
                if kwargs.get('debug', False):
                    print(f"[性能监控] {func.__name__} - 时间: {执行时间_ms:.1f}ms, 内存: {内存增量:.1f}MB")
                
                return result
                
            except Exception as e:
                # 计算错误情况下的执行时间
                结束时间 = time.time()
                执行时间_ms = (结束时间 - 开始时间) * 1000
                print(f"[性能监控] {func.__name__} 失败 - 时间: {执行时间_ms:.1f}ms, 错误: {e}")
                raise
        
        return wrapper
    
    def 缓存装饰器(self, maxsize: Optional[int] = None):
        """
        缓存装饰器工厂
        
        参数:
            maxsize: 缓存大小（默认使用类配置）
            
        返回:
            缓存装饰器
        """
        if maxsize is None:
            maxsize = self.缓存大小
        
        def decorator(func: Callable) -> Callable:
            if not self.启用缓存:
                return func
            
            @lru_cache(maxsize=maxsize)
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                缓存键 = self._生成缓存键(func.__name__, args, kwargs)
                
                # 检查缓存
                if 缓存键 in self.图表缓存:
                    self.性能统计['缓存命中次数'] += 1
                    if kwargs.get('debug', False):
                        print(f"[缓存命中] {func.__name__}")
                    return self.图表缓存[缓存键]
                
                # 执行函数
                result = func(*args, **kwargs)
                
                # 更新缓存
                self.图表缓存[缓存键] = result
                
                # 清理过期缓存
                self._清理缓存()
                
                return result
            
            return wrapper
        
        return decorator
    
    def 懒加载装饰器(self, func: Callable) -> Callable:
        """
        懒加载装饰器
        
        参数:
            func: 要懒加载的函数
            
        返回:
            装饰后的函数
        """
        if not self.启用懒加载:
            return func
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 创建懒加载对象
            class LazyResult:
                def __init__(self, func, args, kwargs):
                    self.func = func
                    self.args = args
                    self.kwargs = kwargs
                    self._result = None
                    self._computed = False
                
                def compute(self):
                    if not self._computed:
                        self._result = self.func(*self.args, **self.kwargs)
                        self._computed = True
                    return self._result
                
                def __repr__(self):
                    if self._computed:
                        return f"LazyResult(computed={self._result})"
                    return "LazyResult(not computed)"
            
            return LazyResult(func, args, kwargs)
        
        return wrapper
    
    def 优化图表数据(self, 
                   数据: Union[np.ndarray, pd.Series, List],
                   采样策略: str = 'auto',
                   最大点数: int = 1000) -> Union[np.ndarray, pd.Series]:
        """
        优化图表数据（减少数据点）
        
        参数:
           数据: 原始数据
           采样策略: 采样策略（auto, first, last, random, decimate）
           最大点数: 最大数据点数
            
        返回:
            优化后的数据
        """
        if not isinstance(数据, (np.ndarray, pd.Series, list)):
            return 数据
        
        # 转换为数组
        if isinstance(数据, pd.Series):
            数据数组 = 数据.values
        elif isinstance(数据, list):
            数据数组 = np.array(数据)
        else:
            数据数组 = 数据
        
        # 如果数据点不超过最大点数，直接返回
        if len(数据数组) <= 最大点数:
            return 数据数组
        
        # 根据策略采样
        if 采样策略 == 'first':
            # 取前N个点
            return 数据数组[:最大点数]
        
        elif 采样策略 == 'last':
            # 取后N个点
            return 数据数组[-最大点数:]
        
        elif 采样策略 == 'random':
            # 随机采样
            indices = np.random.choice(len(数据数组), 最大点数, replace=False)
            return 数据数组[np.sort(indices)]
        
        elif 采样策略 == 'decimate':
            # 等间隔采样
            间隔 = len(数据数组) // 最大点数
            return 数据数组[::间隔][:最大点数]
        
        else:  # 'auto'
            # 自动选择策略：对于时间序列，使用等间隔采样
            return 数据数组[::len(数据数组)//最大点数][:最大点数]
    
    def 优化图表配置(self,
                   图表配置: Dict[str, Any],
                   优化级别: str = 'balanced') -> Dict[str, Any]:
        """
        优化图表配置
        
        参数:
           图表配置: 原始图表配置
           优化级别: 优化级别（minimal, balanced, aggressive）
            
        返回:
            优化后的图表配置
        """
        优化配置 = 图表配置.copy()
        
        if 优化级别 == 'minimal':
            # 最小化优化：保留基本功能
            优化配置.update({
                'showlegend': False,
                'hovermode': False,
                'dragmode': False
            })
        
        elif 优化级别 == 'balanced':
            # 平衡优化：保留核心交互功能
            优化配置.update({
                'showlegend': True,
                'hovermode': 'x unified',
                'dragmode': 'pan',
                'modebar_remove': ['lasso2d', 'select2d', 'hoverClosestCartesian']
            })
        
        elif 优化级别 == 'aggressive':
            # 激进优化：最大化性能
            优化配置.update({
                'showlegend': False,
                'hovermode': False,
                'dragmode': False,
                'staticPlot': True
            })
        
        return 优化配置
    
    def 批量生成优化(self,
                   生成函数: Callable,
                   参数列表: List[Dict],
                   批量大小: int = 10,
                   使用并行: bool = True) -> List[Any]:
        """
        批量生成优化
        
        参数:
           生成函数: 图表生成函数
           参数列表: 参数列表
           批量大小: 批量大小
           使用并行: 是否使用并行处理
            
        返回:
            生成结果列表
        """
        if not 参数列表:
            return []
        
        if not 使用并行 or not self.启用并行处理:
            # 顺序处理
            results = []
            for 参数 in 参数列表:
                try:
                    result = 生成函数(**参数)
                    results.append(result)
                except Exception as e:
                    print(f"[批量生成] 处理失败: {e}")
                    results.append(None)
            return results
        
        # 并行处理
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            results = [None] * len(参数列表)
            
            with ThreadPoolExecutor(max_workers=min(批量大小, len(参数列表))) as executor:
                # 提交任务
                未来任务 = {}
                for idx, 参数 in enumerate(参数列表):
                    future = executor.submit(生成函数, **参数)
                    未来任务[future] = idx
                
                # 收集结果
                for future in as_completed(未来任务):
                    idx = 未来任务[future]
                    try:
                        results[idx] = future.result()
                    except Exception as e:
                        print(f"[并行生成] 任务 {idx} 失败: {e}")
                        results[idx] = None
            
            self.性能统计['并行任务数'] += len(参数列表)
            return results
            
        except ImportError:
            print("[警告] 未找到concurrent.futures，回退到顺序处理")
            return self.批量生成优化(生成函数, 参数列表, 批量大小, 使用并行=False)
    
    def 内存优化(self, 数据: Any, 优化策略: str = 'compact') -> Any:
        """
        内存优化
        
        参数:
           数据: 原始数据
           优化策略: 优化策略（compact, dtype, sparse）
            
        返回:
            优化后的数据
        """
        if isinstance(数据, np.ndarray):
            if 优化策略 == 'dtype':
                # 优化数据类型
                if 数据.dtype == np.float64:
                    return 数据.astype(np.float32)
                elif 数据.dtype == np.int64:
                    return 数据.astype(np.int32)
                else:
                    return 数据
            
            elif 优化策略 == 'sparse':
                # 转换为稀疏矩阵（如果有很多零值）
                零值比例 = np.sum(数据 == 0) / 数据.size
                if 零值比例 > 0.5:
                    from scipy import sparse
                    return sparse.csr_matrix(数据)
                else:
                    return 数据
            
            else:  # 'compact'
                # 紧凑存储
                return 数据.copy(order='C')
        
        elif isinstance(数据, pd.DataFrame) or isinstance(数据, pd.Series):
            # 优化pandas数据类型
            return 数据.copy()
        
        else:
            return 数据
    
    def 清理缓存(self, 清理比例: float = 0.2):
        """
        清理缓存
        
        参数:
           清理比例: 清理比例（0-1）
        """
        if not self.图表缓存:
            return
        
        # 计算要清理的数量
        清理数量 = int(len(self.图表缓存) * 清理比例)
        
        if 清理数量 > 0:
            # 简单的LRU清理：删除最早的条目
            缓存键列表 = list(self.图表缓存.keys())
            for 键 in 缓存键列表[:清理数量]:
                del self.图表缓存[键]
            
            print(f"[缓存清理] 清理了 {清理数量} 个缓存条目")
    
    def 获取性能报告(self) -> Dict[str, Any]:
        """获取性能报告"""
        # 计算缓存命中率
        总生成次数 = self.性能统计['总图表生成次数']
        缓存命中次数 = self.性能统计['缓存命中次数']
        
        if 总生成次数 > 0:
            缓存命中率 = (缓存命中次数 / 总生成次数) * 100
        else:
            缓存命中率 = 0.0
        
        # 构建报告
        报告 = {
            '性能统计': self.性能统计.copy(),
            '缓存统计': {
                '图表缓存大小': len(self.图表缓存),
                '数据缓存大小': len(self.数据缓存),
                '缓存命中率': f'{缓存命中率:.1f}%',
                '缓存命中次数': 缓存命中次数
            },
            '优化配置': {
                '启用缓存': self.启用缓存,
                '启用懒加载': self.启用懒加载,
                '启用并行处理': self.启用并行处理,
                '缓存大小': self.缓存大小
            },
            '当前状态': {
                '内存使用_MB': psutil.Process().memory_info().rss / 1024 / 1024,
                'CPU使用率': psutil.cpu_percent(),
                '活跃进程数': len(psutil.pids())
            }
        }
        
        return 报告
    
    def _生成缓存键(self, 函数名: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        # 简化参数表示
        args_repr = str(args)[:100]  # 限制长度
        kwargs_repr = str(sorted(kwargs.items()))[:100]
        
        return f"{函数名}|{args_repr}|{kwargs_repr}"
    
    def _清理缓存(self):
        """清理过期缓存"""
        if len(self.图表缓存) > self.缓存大小 * 1.5:
            self.清理缓存(清理比例=0.3)


# 性能优化工具函数
class PerformanceUtils:
    """性能工具类"""
    
    @staticmethod
    def 计算数据大小(数据: Any) -> float:
        """计算数据大小（MB）"""
        if isinstance(数据, np.ndarray):
            return 数据.nbytes / 1024 / 1024
        elif isinstance(数据, pd.DataFrame) or isinstance(数据, pd.Series):
            return 数据.memory_usage(deep=True).sum() / 1024 / 1024
        elif isinstance(数据, list):
            # 估算列表大小
            return len(str(数据)) / 1024 / 1024
        else:
            return len(str(数据).encode('utf-8')) / 1024 / 1024
    
    @staticmethod
    def 时间统计(函数: Callable, *args, **kwargs) -> Dict[str, Any]:
        """函数执行时间统计"""
        开始时间 = time.time()
        开始内存 = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            result = 函数(*args, **kwargs)
            状态 = '成功'
        except Exception as e:
            result = None
            状态 = f'失败: {str(e)}'
        
        结束时间 = time.time()
        结束内存 = psutil.Process().memory_info().rss / 1024 / 1024
        
        统计结果 = {
            '函数名称': 函数.__name__,
            '执行时间_ms': (结束时间 - 开始时间) * 1000,
            '内存增量_MB': 结束内存 - 开始内存,
            '状态': 状态,
            '时间戳': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return 统计结果, result
    
    @staticmethod
    def 批量性能测试(函数列表: List[Callable], 
                    参数列表: List[Dict],
                    测试次数: int = 3) -> Dict[str, List[Dict]]:
        """批量性能测试"""
        结果 = {}
        
        for 函数 in 函数列表:
            函数名 = 函数.__name__
            结果[函数名] = []
            
            for 参数 in 参数列表:
                多次测试结果 = []
                
                for i in range(测试次数):
                    统计, _ = PerformanceUtils.时间统计(函数, **参数)
                    多次测试结果.append(统计['执行时间_ms'])
                
                # 计算统计信息
                测试结果 = {
                    '参数': 参数,
                    '平均时间_ms': np.mean(多次测试结果),
                    '最小时间_ms': np.min(多次测试结果),
                    '最大时间_ms': np.max(多次测试结果),
                    '标准差_ms': np.std(多次测试结果),
                    '测试次数': 测试次数
                }
                
                结果[函数名].append(测试结果)
        
        return 结果


# 测试代码
if __name__ == "__main__":
    print("=== 竹林司马性能优化器测试 ===")
    
    # 创建性能优化器
    optimizer = PerformanceOptimizer(缓存大小=50, 启用缓存=True, 启用懒加载=True)
    
    # 测试性能监控
    @optimizer.性能监控
    def 测试函数(数据大小: int = 1000):
        """测试函数"""
        time.sleep(0.01)  # 模拟计算
        return np.random.randn(数据大小)
    
    # 测试缓存
    @optimizer.缓存装饰器(maxsize=10)
    def 缓存测试函数(数据大小: int):
        """缓存测试函数"""
        time.sleep(0.02)
        return np.random.randn(数据大小)
    
    print("1. 测试性能监控...")
    for i in range(5):
        结果 = 测试函数(数据大小=1000)
        print(f"   第{i+1}次执行完成")
    
    print("2. 测试缓存功能...")
    for i in range(10):
        结果 = 缓存测试函数(数据大小=100)
    
    print("3. 测试数据优化...")
    大数据 = np.random.randn(10000)
    优化数据 = optimizer.优化图表数据(大数据, 最大点数=1000)
    print(f"   数据优化: {len(大数据)} -> {len(优化数据)} 点")
    
    print("4. 测试批量生成...")
    参数列表 = [
        {'数据大小': 100},
        {'数据大小': 200},
        {'数据大小': 300},
        {'数据大小': 400}
    ]
    批量结果 = optimizer.批量生成优化(缓存测试函数, 参数列表, 批量大小=2)
    print(f"   批量生成完成，结果数: {len(批量结果)}")
    
    print("5. 获取性能报告...")
    性能报告 = optimizer.获取性能报告()
    print(f"   总生成次数: {性能报告['性能统计']['总图表生成次数']}")
    print(f"   缓存命中率: {性能报告['缓存统计']['缓存命中率']}")
    print(f"   平均生成时间: {性能报告['性能统计']['平均生成时间_ms']:.1f}ms")
    
    print("\n=== 测试完成 ===")