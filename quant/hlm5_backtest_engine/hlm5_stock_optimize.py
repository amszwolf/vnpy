#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
HLM5 Stock Strategy Optimization System
High-performance stock strategy parameter optimization, supporting single or multiple stock portfolio optimization

Main Features:
1. Strategy optimization based on existing technical indicators
2. Support for 1-5 stock portfolio optimization
3. Bayesian optimization algorithm
4. Vectorized high-speed backtesting
5. Multi-process parallel computation
6. Complete result recording and analysis

Author: HLM5 Team
Version: 1.0
"""

import sys
import io
import numpy as np
import pandas as pd
import sqlite3
import os
import json
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import webbrowser
import tempfile
import logging
import codecs

# Force UTF-8 encoding for stdout and stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set environment encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 优化相关
try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    from skopt.acquisition import gaussian_ei
except ImportError:
    print("请先安装scikit-optimize包:")
    print("pip install scikit-optimize")
    exit(1)

# 可视化相关
import plotly.graph_objects as go
import plotly.subplots as sp
from plotly.offline import plot

# 数据处理
import sqlite3
import logging

# Import existing modules with fallback handling
try:
    from hlm5_all_parallel import (
        calculate_macd_signals, 
        check_entry_conditions, 
        check_exit_conditions,
        generate_performance_metrics
    )
    print("[OK] Successfully imported hlm5_all_parallel")
except ImportError as e:
    print(f"[WARNING] hlm5_all_parallel import failed: {e}")
    # Provide fallback implementations
    def calculate_macd_signals(data, macd_long=26, macd_mid=12, macd_short=9, diff_ema_period=3):
        """Fallback MACD calculation"""
        if len(data) < macd_long:
            return pd.DataFrame(index=data.index, columns=['MACD', 'Signal', 'Hist', 'Cross_1', 'XLPL_Phase'])
        
        ema_short = data.ewm(span=macd_short).mean()
        ema_mid = data.ewm(span=macd_mid).mean()
        ema_long = data.ewm(span=macd_long).mean()
        
        macd = ema_mid - ema_long
        signal = macd.ewm(span=diff_ema_period).mean()
        hist = macd - signal
        
        # Simple cross detection
        cross = (macd > signal).astype(int) - (macd < signal).astype(int)
        cross_1 = cross.diff().fillna(0)
        
        # Simple phase detection
        xlpl_phase = (macd > 0).astype(int) + 1
        
        return pd.DataFrame({
            'MACD': macd,
            'Signal': signal,
            'Hist': hist,
            'Cross_1': cross_1,
            'XLPL_Phase': xlpl_phase
        }, index=data.index)
    
    def check_entry_conditions(current_data, prev_data):
        """Fallback entry condition check"""
        try:
            price_cross = current_data.get('Price_Cross', 0)
            volume_cross = current_data.get('Volume_Cross', 0)
            return price_cross > 0 and volume_cross > 0
        except:
            return False
    
    def check_exit_conditions(current_data, position_data):
        """Fallback exit condition check"""
        try:
            price_cross = current_data.get('Price_Cross', 0)
            return price_cross < 0
        except:
            return False
    
    def generate_performance_metrics(trades):
        """Fallback performance metrics"""
        return {}

try:
    from trading_signal_database_manager import TradingSignalDatabaseManager
    print("[OK] Successfully imported TradingSignalDatabaseManager")
except ImportError as e:
    print(f"[WARNING] TradingSignalDatabaseManager import failed: {e}")
    # Provide fallback implementation
    class TradingSignalDatabaseManager:
        def __init__(self, db_path):
            self.db_path = db_path
            print(f"[FALLBACK] Using fallback TradingSignalDatabaseManager for {db_path}")
        
        def get_data(self, ticker, start_date=None, end_date=None, columns=None):
            """Fallback data getter - returns dummy data"""
            print(f"[FALLBACK] Generating dummy data for {ticker}")
            import numpy as np
            
            # Generate dummy data for testing
            dates = pd.date_range(start='2022-01-01', end='2024-12-31', freq='D')
            n = len(dates)
            
            # Generate realistic price data
            np.random.seed(hash(ticker) % (2**32))  # Use ticker as seed for consistency
            returns = np.random.normal(0.001, 0.02, n)
            price = 100 * np.exp(np.cumsum(returns))
            
            data = pd.DataFrame({
                'close': price,
                'high': price * (1 + np.random.uniform(0, 0.03, n)),
                'low': price * (1 - np.random.uniform(0, 0.03, n)),
                'volume': np.random.uniform(1000000, 10000000, n),
                'Price_MACD': np.random.uniform(-1, 1, n),
                'Price_MACD_Signal': np.random.uniform(-1, 1, n),
                'Price_MACD_Hist': np.random.uniform(-0.5, 0.5, n),
                'Price_XLPL_Phase': np.random.choice([1, 2], n),
                'Price_Cross': np.random.choice([-1, 0, 1], n),
                'Volume_MACD': np.random.uniform(-1, 1, n),
                'Volume_MACD_Signal': np.random.uniform(-1, 1, n),
                'Volume_MACD_Hist': np.random.uniform(-0.5, 0.5, n),
                'Volume_XLPL_Phase': np.random.choice([1, 2], n),
                'Volume_Cross': np.random.choice([-1, 0, 1], n),
                'HLBW_Trend_Line': np.random.uniform(20, 80, n),
                'HLBW_MACD': np.random.uniform(-1, 1, n),
                'HLBW_MACD_Signal': np.random.uniform(-1, 1, n),
                'HLBW_MACD_Hist': np.random.uniform(-0.5, 0.5, n),
                'HLBW_XLPL_Phase': np.random.choice([1, 2], n),
                'HLBW_Cross': np.random.choice([-1, 0, 1], n),
                'PH_yhat': price * (1 + np.random.uniform(-0.1, 0.1, n)),
                'PH_MACD': np.random.uniform(-1, 1, n),
                'PH_MACD_Signal': np.random.uniform(-1, 1, n),
                'PH_MACD_Hist': np.random.uniform(-0.5, 0.5, n),
                'PH_XLPL_Phase': np.random.choice([1, 2], n),
                'PH_Cross': np.random.choice([-1, 0, 1], n),
                'PH_Trend_Duration': np.random.choice([1, 2, 3, 4, 5], n)
            }, index=dates)
            
            if columns:
                available_columns = [col for col in columns if col in data.columns]
                data = data[available_columns]
            
            return data.fillna(method='ffill').fillna(method='bfill')
        
        def close(self):
            pass

try:
    from finscreener_database_manager import FinScreenerDBManager
    print("[OK] Successfully imported FinScreenerDBManager")
except ImportError as e:
    print(f"[WARNING] FinScreenerDBManager import failed: {e}")
    # Provide fallback implementation
    class FinScreenerDBManager:
        def __init__(self):
            print("[FALLBACK] Using fallback FinScreenerDBManager")
        
        def get_top_n_stocks(self, n=10):
            """Fallback stock selector - returns some common stocks"""
            common_stocks = [
                {'ticker': '000001.SZ'}, {'ticker': '000002.SZ'}, {'ticker': '000858.SZ'}, 
                {'ticker': '600036.SH'}, {'ticker': '600519.SH'}, {'ticker': '600000.SH'},
                {'ticker': '000725.SZ'}, {'ticker': '600439.SH'}, {'ticker': '600753.SH'},
                {'ticker': '000030.SZ'}, {'ticker': '600395.SH'}, {'ticker': '002142.SZ'}
            ]
            return common_stocks[:n]

try:
    from hlm5_config import EQUITY_CONFIG
    print("[OK] Successfully imported hlm5_config")
except ImportError as e:
    print(f"[WARNING] hlm5_config import failed: {e}")
    # Provide fallback config
    EQUITY_CONFIG = {
        'optimization': {
            'max_stocks': 10,
            'min_stocks': 1
        }
    }

# Configure logging with proper encoding handling for Windows
os.makedirs('logs', exist_ok=True)

# Configure basic logging to avoid conflicts
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/hlm5_stock_optimize.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

warnings.filterwarnings('ignore')

@dataclass
class OptimizationConfig:
    """优化配置参数"""
    max_stocks: int = 100  # 优化: 10 → 100，大幅扩大投资组合
    min_stocks: int = 30   # 优化: 1 → 30，确保足够分散投资
    optimization_method: str = 'bayesian'  # 'bayesian', 'random', 'grid'
    n_calls: int = 100  # 优化: 50 → 100，提高优化质量
    cv_folds: int = 3  # 交叉验证折数
    test_period_days: int = 252  # 测试期长度（天）
    min_trade_days: int = 20  # 优化: 30 → 20，降低数据要求
    parallel_jobs: int = -1  # 并行任务数
    random_state: int = 42
    
    # 性能指标权重 - 平衡收益和频率（根据报告优化）
    return_weight: float = 0.4           # 优化: 0.5 → 0.4，降低收益权重
    drawdown_weight: float = 0.25        # 优化: 0.3 → 0.25，调整回撤权重
    sharpe_weight: float = 0.15          # 保持夏普权重
    win_rate_weight: float = 0.1         # 优化: 0.05 → 0.1，提高胜率权重
    trade_frequency_weight: float = 0.1  # 新增: 交易频率权重
    
    # 股票替换机制配置
    enable_stock_replacement: bool = True
    replacement_threshold: float = 0.02  # 优化: 0.05 → 0.02，更积极的替换策略
    min_optimization_rounds: int = 1     # 优化: 2 → 1，更快的替换响应
    replacement_candidate_pool: int = 100  # 优化: 30 → 100，更大的候选池

class OptimizationVisualizer:
    """优化结果可视化器"""
    
    def __init__(self):
        self.colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
    
    def create_optimization_dashboard(self, optimization_results: Dict, 
                                    convergence_data: List[float],
                                    stock_performances: Dict[str, Dict]) -> str:
        """创建全面的优化分析仪表板"""
        
        # 创建包含更多子图的综合仪表板
        fig = sp.make_subplots(
            rows=4, cols=2,
            subplot_titles=(
                '优化收敛过程', '各股票表现对比',
                '收益率 vs 回撤率散点图', '参数敏感性分析',
                '各股票详细资金曲线', '各股票详细收益率曲线',
                '整体投资组合资金曲线', '整体投资组合与个股对比'
            ),
            specs=[
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}]
            ],
            vertical_spacing=0.08
        )
        
        # 1. 优化收敛过程
        fig.add_trace(
            go.Scatter(
                x=list(range(1, len(convergence_data) + 1)),
                y=[-x for x in convergence_data],  # 转为正值
                mode='lines+markers',
                name='目标函数值',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=6)
            ),
            row=1, col=1
        )
        
        # 2. 各股票表现对比
        tickers = list(stock_performances.keys())
        returns = [stock_performances[ticker]['annual_return'] * 100 for ticker in tickers]
        drawdowns = [abs(stock_performances[ticker]['max_drawdown']) * 100 for ticker in tickers]
        
        fig.add_trace(
            go.Bar(
                x=tickers,
                y=returns,
                name='年化收益率(%)',
                marker_color='#2ca02c',
                yaxis='y2'
            ),
            row=1, col=2
        )
        
        fig.add_trace(
            go.Bar(
                x=tickers,
                y=[-d for d in drawdowns],  # 负值显示回撤
                name='最大回撤(%)',
                marker_color='#d62728',
                yaxis='y2'
            ),
            row=1, col=2
        )
        
        # 3. 收益率 vs 回撤率散点图
        fig.add_trace(
            go.Scatter(
                x=drawdowns,
                y=returns,
                mode='markers+text',
                text=tickers,
                textposition='top center',
                name='股票分布',
                marker=dict(
                    size=12,
                    color=returns,
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="年化收益率(%)")
                )
            ),
            row=2, col=1
        )
        
        # 4. 参数敏感性分析（示例）
        params = list(optimization_results['best_params'].keys())[:6]  # 取前6个参数
        param_values = [optimization_results['best_params'][p] for p in params]
        
        fig.add_trace(
            go.Bar(
                x=params,
                y=param_values,
                name='最优参数值',
                marker_color='#9467bd'
            ),
            row=2, col=2
        )
        
        # 5. 各股票详细资金曲线
        for i, (ticker, perf) in enumerate(stock_performances.items()):
            color = self.colors[i % len(self.colors)]
            if 'equity_curve' in perf and perf['equity_curve']:
                equity_curve = perf['equity_curve']
                dates = pd.date_range(start='2022-01-01', periods=len(equity_curve), freq='D')
                
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=equity_curve,
                        mode='lines',
                        name=f'{ticker} 资金曲线',
                        line=dict(color=color, width=2),
                        showlegend=False
                    ),
                    row=3, col=1
                )
        
        # 6. 各股票详细收益率曲线
        for i, (ticker, perf) in enumerate(stock_performances.items()):
            color = self.colors[i % len(self.colors)]
            if 'equity_curve' in perf and perf['equity_curve']:
                equity_curve = perf['equity_curve']
                dates = pd.date_range(start='2022-01-01', periods=len(equity_curve), freq='D')
                
                if len(equity_curve) > 1:
                    initial_value = equity_curve[0]
                    returns_curve = [(val - initial_value) / initial_value * 100 for val in equity_curve]
                    
                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=returns_curve,
                            mode='lines',
                            name=f'{ticker} 收益率',
                            line=dict(color=color, width=2),
                            showlegend=False
                        ),
                        row=3, col=2
                    )
                    
                    # 添加最终收益率标注
                    final_return = returns_curve[-1]
                    fig.add_annotation(
                        x=dates[-1],
                        y=final_return,
                        text=f"{final_return:.1f}%",
                        showarrow=True,
                        arrowhead=2,
                        arrowcolor=color,
                        font=dict(color=color, size=8),
                        row=3, col=2
                    )
        
        # 7. 计算并显示整体投资组合资金曲线
        portfolio_equity_curve = self._calculate_portfolio_curve(stock_performances)
        if portfolio_equity_curve:
            dates = pd.date_range(start='2022-01-01', periods=len(portfolio_equity_curve), freq='D')
            
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=portfolio_equity_curve,
                    mode='lines',
                    name='投资组合',
                    line=dict(color='#FF6B6B', width=3),
                    showlegend=False
                ),
                row=4, col=1
            )
            
            # 添加投资组合统计信息
            initial_value = portfolio_equity_curve[0]
            final_value = portfolio_equity_curve[-1]
            total_return = (final_value - initial_value) / initial_value * 100
            
            fig.add_annotation(
                x=dates[-1],
                y=final_value,
                text=f"组合总收益: {total_return:.1f}%",
                showarrow=True,
                arrowhead=2,
                arrowcolor='#FF6B6B',
                font=dict(color='#FF6B6B', size=10, weight='bold'),
                row=4, col=1
            )
        
        # 8. 整体投资组合与个股收益率对比
        if portfolio_equity_curve:
            # 投资组合收益率曲线
            portfolio_returns = [(val - portfolio_equity_curve[0]) / portfolio_equity_curve[0] * 100 
                               for val in portfolio_equity_curve]
            
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=portfolio_returns,
                    mode='lines',
                    name='投资组合收益率',
                    line=dict(color='#FF6B6B', width=4),
                    showlegend=False
                ),
                row=4, col=2
            )
            
            # 添加个股收益率对比（半透明）
            for i, (ticker, perf) in enumerate(stock_performances.items()):
                if 'equity_curve' in perf and perf['equity_curve']:
                    equity_curve = perf['equity_curve']
                    if len(equity_curve) > 1:
                        initial_value = equity_curve[0]
                        returns_curve = [(val - initial_value) / initial_value * 100 for val in equity_curve]
                        color = self.colors[i % len(self.colors)]
                        
                        fig.add_trace(
                            go.Scatter(
                                x=dates,
                                y=returns_curve,
                                mode='lines',
                                name=f'{ticker}',
                                line=dict(color=color, width=1, dash='dot'),
                                opacity=0.6,
                                showlegend=False
                            ),
                            row=4, col=2
                        )
        
        # 为收益率图添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=2)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=4, col=2)
        
        # 更新布局
        fig.update_layout(
            height=1600,  # 增加高度以容纳更多子图
            title_text=f"股票策略优化全面分析报告 - {optimization_results['experiment_name']}",
            title_x=0.5,
            showlegend=True,
            template='plotly_white'
        )
        
        # 更新子图标题和轴标签
        fig.update_xaxes(title_text="迭代次数", row=1, col=1)
        fig.update_yaxes(title_text="目标函数值", row=1, col=1)
        
        fig.update_xaxes(title_text="股票代码", row=1, col=2)
        fig.update_yaxes(title_text="收益率/回撤率(%)", row=1, col=2)
        
        fig.update_xaxes(title_text="最大回撤(%)", row=2, col=1)
        fig.update_yaxes(title_text="年化收益率(%)", row=2, col=1)
        
        fig.update_xaxes(title_text="参数名称", row=2, col=2)
        fig.update_yaxes(title_text="参数值", row=2, col=2)
        
        fig.update_xaxes(title_text="日期", row=3, col=1)
        fig.update_yaxes(title_text="资金价值 (元)", row=3, col=1)
        
        fig.update_xaxes(title_text="日期", row=3, col=2)
        fig.update_yaxes(title_text="收益率 (%)", row=3, col=2)
        
        fig.update_xaxes(title_text="日期", row=4, col=1)
        fig.update_yaxes(title_text="投资组合价值 (元)", row=4, col=1)
        
        fig.update_xaxes(title_text="日期", row=4, col=2)
        fig.update_yaxes(title_text="收益率 (%)", row=4, col=2)
        
        # 保存HTML文件并在浏览器中打开
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
        plot(fig, filename=temp_file.name, auto_open=False)
        
        # 在浏览器中打开
        webbrowser.open('file://' + temp_file.name)
        
        return temp_file.name
    
    def _calculate_portfolio_curve(self, stock_performances: Dict[str, Dict]) -> List[float]:
        """计算等权重投资组合的资金曲线"""
        try:
            valid_curves = []
            
            # 收集有效的equity curves
            for ticker, perf in stock_performances.items():
                if 'equity_curve' in perf and perf['equity_curve']:
                    equity_curve = perf['equity_curve']
                    if len(equity_curve) > 1:
                        valid_curves.append(equity_curve)
            
            if not valid_curves:
                return []
            
            # 确保所有曲线长度一致
            min_length = min(len(curve) for curve in valid_curves)
            normalized_curves = [curve[:min_length] for curve in valid_curves]
            
            # 计算等权重组合曲线
            portfolio_curve = []
            for i in range(min_length):
                # 在每个时间点，计算所有股票的平均值
                avg_value = sum(curve[i] for curve in normalized_curves) / len(normalized_curves)
                portfolio_curve.append(avg_value)
            
            return portfolio_curve
            
        except Exception as e:
            logger.error(f"计算投资组合曲线失败: {e}")
            return []
    
    def create_equity_curves(self, stock_performances: Dict[str, Dict]) -> str:
        """创建各股票资金曲线和收益曲线对比图"""
        
        # 创建子图：资金曲线和收益曲线
        fig = sp.make_subplots(
            rows=2, cols=1,
            subplot_titles=('各股票资金曲线对比', '各股票收益率曲线对比'),
            vertical_spacing=0.1,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )
        
        for i, (ticker, perf) in enumerate(stock_performances.items()):
            color = self.colors[i % len(self.colors)]
            
            if 'equity_curve' in perf and perf['equity_curve']:
                equity_curve = perf['equity_curve']
                dates = pd.date_range(start='2022-01-01', periods=len(equity_curve), freq='D')
                
                # 1. 资金曲线
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=equity_curve,
                        mode='lines',
                        name=f'{ticker} 资金',
                        line=dict(color=color, width=2),
                        showlegend=True
                    ),
                    row=1, col=1
                )
                
                # 2. 收益率曲线 (相对于初始资金的收益率)
                if len(equity_curve) > 1:
                    initial_value = equity_curve[0]
                    returns_curve = [(val - initial_value) / initial_value * 100 for val in equity_curve]
                    
                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=returns_curve,
                            mode='lines',
                            name=f'{ticker} 收益率',
                            line=dict(color=color, width=2, dash='dot'),
                            showlegend=True
                        ),
                        row=2, col=1
                    )
                    
                    # 添加收益率统计信息到悬停框
                    final_return = returns_curve[-1]
                    max_return = max(returns_curve)
                    min_return = min(returns_curve)
                    
                    # 在图上标注最终收益率
                    fig.add_annotation(
                        x=dates[-1],
                        y=returns_curve[-1],
                        text=f"{final_return:.1f}%",
                        showarrow=True,
                        arrowhead=2,
                        arrowcolor=color,
                        font=dict(color=color, size=10),
                        row=2, col=1
                    )
        
        # 更新布局
        fig.update_layout(
            title='股票策略表现分析图表',
            title_x=0.5,
            height=800,
            template='plotly_white',
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # 更新X轴和Y轴标签
        fig.update_xaxes(title_text="日期", row=1, col=1)
        fig.update_xaxes(title_text="日期", row=2, col=1)
        fig.update_yaxes(title_text="资金价值 (元)", row=1, col=1)
        fig.update_yaxes(title_text="收益率 (%)", row=2, col=1)
        
        # 为收益率图添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
        
        # 保存HTML文件
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
        plot(fig, filename=temp_file.name, auto_open=False)
        
        return temp_file.name

class StockReplacementManager:
    """股票替换管理器"""
    
    def __init__(self, config: OptimizationConfig, finscreener_db: 'FinScreenerDBManager'):
        self.config = config
        self.finscreener_db = finscreener_db
        self.replacement_history = []
    
    def evaluate_stock_performance(self, stock_results: Dict[str, Dict]) -> Dict[str, float]:
        """评估股票表现，返回评分（严格标准，收益为王）"""
        scores = {}
        
        for ticker, performance in stock_results.items():
            annual_return = performance['annual_return']
            
            # 优化: 允许小幅负收益，鼓励更多交易机会
            if annual_return <= -0.05:  # 优化: 0 → -0.05，允许-5%以内负收益
                scores[ticker] = -10.0  # 严厉惩罚严重负收益
                continue
            
            # 优化质量检查 - 根据报告放宽标准，提升交易频率
            if (performance['total_trades'] < 5 or      # 优化: 10 → 5，最少5笔交易
                performance['sharpe_ratio'] < 0.3 or    # 优化: 0.5 → 0.3，夏普比率≥0.3
                abs(performance['max_drawdown']) > 0.4 or  # 优化: 0.3 → 0.4，回撤≤40%
                performance['win_rate'] < 0.25):        # 优化: 0.3 → 0.25，胜率≥25%
                scores[ticker] = -5.0  # 质量不达标惩罚
                continue
            
            # 复合评分：平衡收益和频率（包含新增的交易频率权重）
            return_score = annual_return * self.config.return_weight
            drawdown_score = -abs(performance['max_drawdown']) * self.config.drawdown_weight
            sharpe_score = performance['sharpe_ratio'] * self.config.sharpe_weight
            win_rate_score = performance['win_rate'] * self.config.win_rate_weight
            
            # 新增: 交易频率评分，鼓励更多交易机会
            trade_frequency_score = min(performance['total_trades'] / 20.0, 1.0) * self.config.trade_frequency_weight
            
            total_score = return_score + drawdown_score + sharpe_score + win_rate_score + trade_frequency_score
            
            # 🎯 优化奖励机制：目标200%收益率和<5%回撤
            if annual_return > 2.0 and abs(performance['max_drawdown']) < 0.05:
                total_score *= 3.0  # 超级奖励：200%+收益 + <5%回撤
            elif annual_return > 1.5 and abs(performance['max_drawdown']) < 0.05:
                total_score *= 2.5  # 高奖励：150%+收益 + <5%回撤
            elif annual_return > 1.0 and abs(performance['max_drawdown']) < 0.05:
                total_score *= 2.0  # 良好奖励：100%+收益 + <5%回撤
            elif annual_return > 0.5 and abs(performance['max_drawdown']) < 0.08:
                total_score *= 1.5  # 中等奖励：50%+收益 + <8%回撤
            elif annual_return > 0.2 and abs(performance['max_drawdown']) < 0.10:
                total_score *= 1.2  # 基础奖励：20%+收益 + <10%回撤
            
            scores[ticker] = total_score
            
        return scores
    
    def identify_underperforming_stocks(self, stock_scores: Dict[str, float]) -> List[str]:
        """Identify underperforming stocks"""
        underperforming = []
        
        for ticker, score in stock_scores.items():
            if score < self.config.replacement_threshold:
                underperforming.append(ticker)
                logger.info(f"Identified low-performance stock: {ticker}, score: {score:.4f}")
        
        return underperforming
    
    def get_replacement_candidates(self, current_tickers: List[str], 
                                 num_candidates: int = None) -> List[str]:
        """Get replacement candidate stocks"""
        if num_candidates is None:
            num_candidates = self.config.replacement_candidate_pool
        
        try:
            # Get high-scoring stocks from finscreener
            candidate_stocks = self.finscreener_db.get_top_n_stocks(
                n=num_candidates + len(current_tickers) * 2
            )
            
            # Filter out current stocks
            candidates = []
            for stock in candidate_stocks:
                ticker = stock['ticker']
                if ticker not in current_tickers and ticker not in [r['ticker'] for r in self.replacement_history]:
                    candidates.append(ticker)
                    if len(candidates) >= num_candidates:
                        break
            
            logger.info(f"Got replacement candidates: {candidates[:5]}...")  # Show first 5
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to get candidate stocks: {e}")
            return []
    
    def replace_stocks(self, current_tickers: List[str], 
                      underperforming: List[str]) -> List[str]:
        """Execute stock replacement"""
        if not self.config.enable_stock_replacement or not underperforming:
            return current_tickers
        
        # Get candidates
        candidates = self.get_replacement_candidates(current_tickers, len(underperforming) * 2)
        
        if not candidates:
            logger.warning("No suitable replacement candidates found")
            return current_tickers
        
        # Execute replacement
        new_tickers = current_tickers.copy()
        replacements = 0
        
        for old_ticker in underperforming:
            if replacements >= len(candidates):
                break
                
            new_ticker = candidates[replacements]
            
            # Record replacement history
            replacement_record = {
                'timestamp': datetime.now().isoformat(),
                'old_ticker': old_ticker,
                'new_ticker': new_ticker,
                'reason': 'underperformance'
            }
            self.replacement_history.append(replacement_record)
            
            # Execute replacement
            if old_ticker in new_tickers:
                idx = new_tickers.index(old_ticker)
                new_tickers[idx] = new_ticker
                replacements += 1
                
                logger.info(f"Stock replacement: {old_ticker} → {new_ticker}")
        
        return new_tickers

class StockOptimizeDatabase:
    """股票优化数据库管理器"""
    
    def __init__(self, db_path: str = 'hlm5_stock_optimize.db'):
        self.db_path = db_path
        self.conn = None
        self._create_connection()
        self._create_tables()
        
    def _create_connection(self):
        """创建数据库连接"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA cache_size=10000")
            logger.info(f"Created database connection: {self.db_path}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def _create_tables(self):
        """创建优化相关表"""
        try:
            cursor = self.conn.cursor()
            
            # 股票组合表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_groups (
                group_id TEXT PRIMARY KEY,
                group_name TEXT,
                tickers TEXT,  -- JSON format for stock list
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
            ''')
            
            # 回测结果表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                result_id TEXT PRIMARY KEY,
                group_id TEXT,
                experiment_name TEXT,
                parameters TEXT,  -- JSON format for parameters
                
                -- Performance metrics
                total_return REAL,
                annual_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                volatility REAL,
                win_rate REAL,
                profit_factor REAL,
                total_trades INTEGER,
                
                -- Time information
                start_date TEXT,
                end_date TEXT,
                backtest_duration REAL,  -- Backtest time (seconds)
                
                -- Detailed results
                trade_details TEXT,  -- JSON format for trade details
                equity_curve TEXT,   -- JSON format for equity curve
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (group_id) REFERENCES stock_groups (group_id)
            )
            ''')
            
            # 优化历史表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS optimization_history (
                optimization_id TEXT PRIMARY KEY,
                group_id TEXT,
                optimization_type TEXT,  -- 'single_stock', 'multi_stock'
                target_metric TEXT,      -- 'return', 'sharpe', 'composite'
                
                -- Optimization parameters
                search_space TEXT,       -- JSON format for search space
                n_iterations INTEGER,
                best_params TEXT,        -- JSON format for best parameters
                best_score REAL,
                
                -- Optimization process
                convergence_data TEXT,   -- JSON format for convergence process
                optimization_time REAL,  -- Optimization time (seconds)
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (group_id) REFERENCES stock_groups (group_id)
            )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_group ON backtest_results(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_return ON backtest_results(total_return)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_sharpe ON backtest_results(sharpe_ratio)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_optimization_group ON optimization_history(group_id)')
            
            self.conn.commit()
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def save_stock_group(self, group_id: str, group_name: str, tickers: List[str], description: str = ""):
        """Save stock group"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO stock_groups 
            (group_id, group_name, tickers, description, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (group_id, group_name, json.dumps(tickers), description))
            self.conn.commit()
            logger.info(f"Saved stock group: {group_id}, stocks: {tickers}")
        except Exception as e:
            logger.error(f"Failed to save stock group: {e}")
            raise
    
    def save_backtest_result(self, result_data: Dict):
        """Save backtest result"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO backtest_results 
            (result_id, group_id, experiment_name, parameters, total_return, annual_return,
             sharpe_ratio, max_drawdown, volatility, win_rate, profit_factor, total_trades,
             start_date, end_date, backtest_duration, trade_details, equity_curve)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result_data['result_id'], result_data['group_id'], result_data['experiment_name'],
                json.dumps(result_data['parameters']), result_data['total_return'], 
                result_data['annual_return'], result_data['sharpe_ratio'], result_data['max_drawdown'],
                result_data['volatility'], result_data['win_rate'], result_data['profit_factor'],
                result_data['total_trades'], result_data['start_date'], result_data['end_date'],
                result_data['backtest_duration'], json.dumps(result_data.get('trade_details', [])),
                json.dumps(result_data.get('equity_curve', []))
            ))
            self.conn.commit()
            logger.info(f"Saved backtest result: {result_data['result_id']}")
        except Exception as e:
            logger.error(f"Failed to save backtest result: {e}")
            raise
    
    def get_best_results(self, group_id: str, metric: str = 'sharpe_ratio', top_n: int = 10) -> pd.DataFrame:
        """Get best backtest results"""
        try:
            query = f'''
            SELECT * FROM backtest_results 
            WHERE group_id = ? 
            ORDER BY {metric} DESC 
            LIMIT ?
            '''
            return pd.read_sql(query, self.conn, params=(group_id, top_n))
        except Exception as e:
            logger.error(f"Failed to get best results: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

class VectorizedBacktester:
    """向量化回测引擎"""
    
    def __init__(self, data: pd.DataFrame, initial_capital: float = 100000):
        self.data = data
        self.initial_capital = initial_capital
        self.results = {}
        
    def backtest_vectorized(self, entry_signals: pd.Series, exit_signals: pd.Series, 
                          commission: float = 0.001) -> Dict:
        """向量化回测"""
        try:
            # 确保信号和价格数据对齐
            prices = self.data['close'].reindex(entry_signals.index, method='ffill')
            
            # 生成持仓信号
            positions = self._generate_positions(entry_signals, exit_signals)
            
            # 计算收益
            returns = prices.pct_change()
            strategy_returns = positions.shift(1) * returns
            
            # 考虑交易成本
            trades = positions.diff().abs()
            transaction_costs = trades * commission
            strategy_returns = strategy_returns - transaction_costs
            
            # 计算累积收益
            equity_curve = (1 + strategy_returns).cumprod() * self.initial_capital
            
            # 计算性能指标
            performance = self._calculate_performance_metrics(
                strategy_returns, equity_curve, positions, prices
            )
            
            return performance
            
        except Exception as e:
            logger.error(f"向量化回测失败: {e}")
            return {
                'total_return': 0, 'annual_return': 0, 'sharpe_ratio': 0,
                'max_drawdown': -1, 'volatility': 0, 'win_rate': 0,
                'profit_factor': 0, 'total_trades': 0
            }
    
    def _generate_positions(self, entry_signals: pd.Series, exit_signals: pd.Series) -> pd.Series:
        """生成持仓信号"""
        positions = pd.Series(0, index=entry_signals.index, dtype=float)
        current_position = 0
        
        for i, (entry, exit) in enumerate(zip(entry_signals, exit_signals)):
            if entry > 0 and current_position == 0:  # 入场
                current_position = 1
            elif exit and current_position > 0:  # 出场
                current_position = 0
            positions.iloc[i] = current_position
            
        return positions
    
    def _calculate_performance_metrics(self, returns: pd.Series, equity_curve: pd.Series, 
                                     positions: pd.Series, prices: pd.Series) -> Dict:
        """计算性能指标"""
        try:
            # 基础指标
            total_return = (equity_curve.iloc[-1] / self.initial_capital) - 1
            annual_return = (1 + total_return) ** (252 / len(returns)) - 1
            
            # 风险指标
            volatility = returns.std() * np.sqrt(252)
            sharpe_ratio = annual_return / volatility if volatility > 0 else 0
            
            # 回撤
            rolling_max = equity_curve.expanding().max()
            drawdowns = (equity_curve - rolling_max) / rolling_max
            max_drawdown = drawdowns.min()
            
            # 交易统计
            position_changes = positions.diff()
            trades = (position_changes > 0).sum()
            
            if trades > 0:
                trade_returns = []
                entry_price = None
                for i, pos_change in enumerate(position_changes):
                    if pos_change > 0:  # 入场
                        entry_price = prices.iloc[i]
                    elif pos_change < 0 and entry_price is not None:  # 出场
                        exit_price = prices.iloc[i]
                        trade_return = (exit_price - entry_price) / entry_price
                        trade_returns.append(trade_return)
                        entry_price = None
                
                if trade_returns:
                    win_rate = sum(1 for r in trade_returns if r > 0) / len(trade_returns)
                    winning_trades = [r for r in trade_returns if r > 0]
                    losing_trades = [r for r in trade_returns if r <= 0]
                    
                    if winning_trades and losing_trades:
                        avg_win = np.mean(winning_trades)
                        avg_loss = abs(np.mean(losing_trades))
                        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
                    else:
                        profit_factor = 0
                else:
                    win_rate = 0
                    profit_factor = 0
            else:
                win_rate = 0
                profit_factor = 0
            
            return {
                'total_return': total_return,
                'annual_return': annual_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'volatility': volatility,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': int(trades),
                'equity_curve': equity_curve.tolist(),
                'returns': returns.tolist()
            }
            
        except Exception as e:
            logger.error(f"性能计算失败: {e}")
            return {
                'total_return': 0, 'annual_return': 0, 'sharpe_ratio': 0,
                'max_drawdown': -1, 'volatility': 0, 'win_rate': 0,
                'profit_factor': 0, 'total_trades': 0
            }

class StrategyOptimizer:
    """策略优化器"""
    
    def __init__(self, config: OptimizationConfig, trading_db_path: str = 'trading_signals.db', finscreener_db_path: str = 'finscreener.db'):
        self.config = config
        self.db = StockOptimizeDatabase()
        self.trading_db = TradingSignalDatabaseManager(trading_db_path)
        self.finscreener_db = FinScreenerDBManager()
        self.visualizer = OptimizationVisualizer()
        self.replacement_manager = StockReplacementManager(config, self.finscreener_db)
        self.optimization_round = 0
        
        # 定义搜索空间
        self.search_space = [
            # Price MACD参数
            Integer(10, 20, name='price_macd_long'),
            Integer(5, 15, name='price_macd_mid'),
            Integer(3, 10, name='price_macd_short'),
            Integer(2, 5, name='price_diff_ema'),
            
            # Volume MACD参数
            Integer(20, 35, name='volume_macd_long'),
            Integer(8, 18, name='volume_macd_mid'),
            Integer(6, 12, name='volume_macd_short'),
            Integer(3, 8, name='volume_diff_ema'),
            
            # HLBW参数
            Integer(40, 70, name='hlbw_lookback'),
            Integer(3, 8, name='hlbw_inner_ema'),
            Integer(2, 5, name='hlbw_outer_ema'),
            Integer(2, 5, name='hlbw_trend_ema'),
            
            # Prophet参数
            Integer(20, 60, name='prophet_periods'),
            Real(0.01, 0.1, name='prophet_changepoint_scale'),
            
            # 交易参数
            Real(0.0005, 0.005, name='commission'),
            Real(0.02, 0.10, name='stop_loss'),
            Integer(3, 10, name='min_trend_duration'),
        ]
        
    def select_stocks_from_finscreener(self, max_stocks: int = 5) -> List[str]:
        """从finscreener数据库选择股票"""
        try:
            top_stocks = self.finscreener_db.get_top_n_stocks(n=max_stocks * 2)  # 获取更多候选
            
            # 过滤掉没有足够数据的股票
            valid_tickers = []
            for stock in top_stocks:
                ticker = stock['ticker']
                # 检查是否有足够的历史数据
                data = self.trading_db.get_data(ticker, columns=['close'])
                if len(data) >= self.config.min_trade_days:
                    valid_tickers.append(ticker)
                    if len(valid_tickers) >= max_stocks:
                        break
            
            logger.info(f"从finscreener选择股票: {valid_tickers}")
            return valid_tickers
            
        except Exception as e:
            logger.error(f"选择股票失败: {e}")
            return []
    
    def prepare_data_for_optimization(self, tickers: List[str], 
                                    start_date: str = '2022-01-01',
                                    end_date: str = None) -> Dict[str, pd.DataFrame]:
        """为优化准备数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            
        stock_data = {}
        
        for ticker in tickers:
            try:
                # 获取技术指标数据
                columns = [
                    'close', 'high', 'low', 'volume',
                    'Price_MACD', 'Price_MACD_Signal', 'Price_MACD_Hist', 'Price_XLPL_Phase', 'Price_Cross',
                    'Volume_MACD', 'Volume_MACD_Signal', 'Volume_MACD_Hist', 'Volume_XLPL_Phase', 'Volume_Cross',
                    'HLBW_Trend_Line', 'HLBW_MACD', 'HLBW_MACD_Signal', 'HLBW_MACD_Hist', 'HLBW_XLPL_Phase', 'HLBW_Cross',
                    'PH_yhat', 'PH_MACD', 'PH_MACD_Signal', 'PH_MACD_Hist', 'PH_XLPL_Phase', 'PH_Cross', 'PH_Trend_Duration'
                ]
                
                data = self.trading_db.get_data(ticker, start_date, end_date, columns=columns)
                
                if len(data) >= self.config.min_trade_days:
                    # 填充缺失值
                    data = data.fillna(method='ffill').fillna(method='bfill')
                    stock_data[ticker] = data
                    logger.info(f"加载数据: {ticker}, 记录数: {len(data)}")
                else:
                    logger.warning(f"股票 {ticker} 数据不足，跳过")
                    
            except Exception as e:
                logger.error(f"加载股票 {ticker} 数据失败: {e}")
                
        return stock_data
    
    def objective_function(self, **params) -> float:
        """目标函数"""
        try:
            # 解包参数
            price_macd_params = {
                'macd_long': params['price_macd_long'],
                'macd_mid': params['price_macd_mid'], 
                'macd_short': params['price_macd_short'],
                'diff_ema_period': params['price_diff_ema']
            }
            
            volume_macd_params = {
                'macd_long': params['volume_macd_long'],
                'macd_mid': params['volume_macd_mid'],
                'macd_short': params['volume_macd_short'], 
                'diff_ema_period': params['volume_diff_ema']
            }
            
            hlbw_params = {
                'lookback_period': params['hlbw_lookback'],
                'inner_ema': params['hlbw_inner_ema'],
                'outer_ema': params['hlbw_outer_ema'],
                'trend_ema': params['hlbw_trend_ema']
            }
            
            prophet_params = {
                'periods': params['prophet_periods'],
                'changepoint_prior_scale': params['prophet_changepoint_scale']
            }
            
            trading_params = {
                'commission': params['commission'],
                'stop_loss': params['stop_loss'],
                'min_trend_duration': params['min_trend_duration']
            }
            
            # 计算组合回测结果
            total_score = 0
            valid_stocks = 0
            
            for ticker, data in self.current_stock_data.items():
                try:
                    # 重新计算技术指标（使用新参数）
                    entry_signals, exit_signals = self._calculate_signals_with_params(
                        data, price_macd_params, volume_macd_params, hlbw_params, 
                        prophet_params, trading_params
                    )
                    
                    # 向量化回测
                    backtester = VectorizedBacktester(data)
                    performance = backtester.backtest_vectorized(
                        entry_signals, exit_signals, params['commission']
                    )
                    
                    # 严格的回测标准 - 确保有足够的交易样本
                    if performance['total_trades'] >= 10:  # 提高到至少10笔交易
                        annual_return = performance['annual_return']
                        
                        # 🚨 收益是绝对重要的 - 严格剔除负收益股票
                        if annual_return <= 0:
                            # 负收益股票直接给予严厉惩罚，不参与评分
                            continue
                        
                        # 额外的质量检查
                        if (performance['sharpe_ratio'] < 0.5 or  # 夏普比率过低
                            abs(performance['max_drawdown']) > 0.3 or  # 回撤过大(>30%)
                            performance['win_rate'] < 0.3):  # 胜率过低(<30%)
                            # 质量不达标的股票也不参与评分
                            continue
                        
                        # 收益分数：年化收益率（绝对重要）
                        return_score = annual_return * self.config.return_weight
                        
                        # 回撤分数：最大回撤的负值（回撤越小越好）
                        drawdown_score = -abs(performance['max_drawdown']) * self.config.drawdown_weight
                        
                        # 风险调整收益
                        sharpe_score = performance['sharpe_ratio'] * self.config.sharpe_weight
                        
                        # 胜率分数
                        win_rate_score = performance['win_rate'] * self.config.win_rate_weight
                        
                        # 复合评分：重点关注高收益低回撤
                        score = return_score + drawdown_score + sharpe_score + win_rate_score
                        
                        # 🎯 多层奖励机制 - 鼓励高质量股票
                        if annual_return > 0.30 and abs(performance['max_drawdown']) < 0.08:
                            score *= 1.5  # 50%奖励：高收益低回撤
                        elif annual_return > 0.20 and abs(performance['max_drawdown']) < 0.10:
                            score *= 1.3  # 30%奖励：较好表现
                        elif annual_return > 0.10 and abs(performance['max_drawdown']) < 0.15:
                            score *= 1.1  # 10%奖励：基本达标
                        
                        # 额外奖励：交易次数越多，可信度越高
                        if performance['total_trades'] >= 20:
                            score *= 1.1  # 交易样本充足奖励
                        
                        total_score += score
                        valid_stocks += 1
                        
                except Exception as e:
                    logger.warning(f"回测股票 {ticker} 失败: {e}")
                    continue
            
            # 记录被剔除的股票信息
            total_stocks = len(self.current_stock_data)
            excluded_stocks = total_stocks - valid_stocks
            if excluded_stocks > 0:
                logger.warning(f"本轮优化剔除了 {excluded_stocks}/{total_stocks} 只股票（负收益或质量不达标）")
            
            # 返回平均分数（取负值用于最小化）
            if valid_stocks > 0:
                avg_score = total_score / valid_stocks
                logger.info(f"有效股票: {valid_stocks}/{total_stocks}, 平均评分: {avg_score:.4f}")
                return -avg_score  # scikit-optimize进行最小化
            else:
                logger.error("没有股票通过质量检查！所有股票都被剔除")
                return 1000  # 惩罚值
                
        except Exception as e:
            logger.error(f"目标函数计算失败: {e}")
            return 1000  # 惩罚值
    
    def _calculate_signals_with_params(self, data: pd.DataFrame, price_macd_params: Dict,
                                     volume_macd_params: Dict, hlbw_params: Dict,
                                     prophet_params: Dict, trading_params: Dict) -> Tuple[pd.Series, pd.Series]:
        """使用给定参数计算交易信号"""
        try:
            # 重新计算Price MACD
            price_signals = calculate_macd_signals(
                data['close'],
                macd_long=price_macd_params['macd_long'],
                macd_mid=price_macd_params['macd_mid'],
                macd_short=price_macd_params['macd_short'],
                diff_ema_period=price_macd_params['diff_ema_period']
            )
            
            # 重新计算Volume MACD
            volume_signals = calculate_macd_signals(
                data['volume'],
                macd_long=volume_macd_params['macd_long'],
                macd_mid=volume_macd_params['macd_mid'],
                macd_short=volume_macd_params['macd_short'],
                diff_ema_period=volume_macd_params['diff_ema_period']
            )
            
            # 重新计算HLBW（简化版本）
            llv_low = data['low'].rolling(window=hlbw_params['lookback_period']).min()
            hhv_high = data['high'].rolling(window=hlbw_params['lookback_period']).max()
            basic_ratio = (data['close'] - llv_low) / (hhv_high - llv_low) * 100
            sma_inner = basic_ratio.ewm(span=hlbw_params['inner_ema']).mean()
            sma_outer = sma_inner.ewm(span=hlbw_params['outer_ema']).mean()
            x_7 = 3 * sma_inner - 2 * sma_outer
            hlbw_trend_line = x_7.ewm(span=hlbw_params['trend_ema']).mean()
            hlbw_signals = calculate_macd_signals(hlbw_trend_line)
            
            # 生成Entry/Exit信号
            entry_signals = pd.Series(0, index=data.index)
            exit_signals = pd.Series(False, index=data.index)
            
            for i in range(1, len(data)):
                # 构建当前和前一时刻的数据切片
                current_slice = pd.Series({
                    'Price_Cross': price_signals['Cross_1'].iloc[i] if 'Cross_1' in price_signals else 0,
                    'Price_XLPL_Phase': price_signals['XLPL_Phase'].iloc[i] if 'XLPL_Phase' in price_signals else 1,
                    'Volume_Cross': volume_signals['Cross_1'].iloc[i] if 'Cross_1' in volume_signals else 0,
                    'Volume_XLPL_Phase': volume_signals['XLPL_Phase'].iloc[i] if 'XLPL_Phase' in volume_signals else 1,
                    'HLBW_Cross': hlbw_signals['Cross_1'].iloc[i] if 'Cross_1' in hlbw_signals else 0,
                    'HLBW_XLPL_Phase': hlbw_signals['XLPL_Phase'].iloc[i] if 'XLPL_Phase' in hlbw_signals else 1,
                    'PH_XLPL_Phase': 2,  # 简化Prophet信号
                    'PH_Trend_Duration': trading_params['min_trend_duration']
                })
                
                prev_slice = pd.Series({
                    'Price_Cross': price_signals['Cross_1'].iloc[i-1] if 'Cross_1' in price_signals else 0,
                    'Volume_Cross': volume_signals['Cross_1'].iloc[i-1] if 'Cross_1' in volume_signals else 0,
                    'HLBW_Cross': hlbw_signals['Cross_1'].iloc[i-1] if 'Cross_1' in hlbw_signals else 0,
                })
                
                # 使用现有的entry/exit逻辑
                try:
                    entry_condition = check_entry_conditions(current_slice, prev_slice)
                    exit_condition = check_exit_conditions(current_slice, None)  # 简化
                    
                    entry_signals.iloc[i] = entry_condition
                    exit_signals.iloc[i] = exit_condition
                except:
                    # 简化的信号逻辑作为备用
                    if (price_signals['Cross_1'].iloc[i] > 0 and 
                        volume_signals['Cross_1'].iloc[i] > 0):
                        entry_signals.iloc[i] = 1
                    elif (price_signals['Cross_1'].iloc[i] < 0):
                        exit_signals.iloc[i] = True
            
            return entry_signals, exit_signals
            
        except Exception as e:
            logger.error(f"信号计算失败: {e}")
            # 返回默认信号
            return pd.Series(0, index=data.index), pd.Series(False, index=data.index)
    
    def optimize_strategy(self, tickers: List[str], experiment_name: str = None) -> Dict:
        """Execute strategy optimization (supporting multiple rounds and stock replacement)"""
        if experiment_name is None:
            experiment_name = f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.optimization_round += 1
        logger.info(f"Starting strategy optimization (Round {self.optimization_round}): {experiment_name}, stocks: {tickers}")
        start_time = time.time()
        
        current_tickers = tickers.copy()
        best_overall_result = None
        all_results = []
        
        # Multiple optimization rounds
        max_rounds = 3 if self.config.enable_stock_replacement else 1
        
        for round_num in range(max_rounds):
            logger.info(f"=== Optimization Round {round_num + 1}/{max_rounds} ===")
            logger.info(f"Current stock portfolio: {current_tickers}")
            
            # Prepare data
            self.current_stock_data = self.prepare_data_for_optimization(current_tickers)
            
            if not self.current_stock_data:
                logger.error("No valid stock data, optimization failed")
                if best_overall_result:
                    return best_overall_result
                return {}
            
            # Create stock group
            group_id = f"group_{datetime.now().strftime('%Y%m%d_%H%M%S')}_round{round_num + 1}"
            self.db.save_stock_group(group_id, f"{experiment_name}_round{round_num + 1}", current_tickers, "Strategy optimization portfolio")
            
            # Set objective function search space
            objective_with_space = use_named_args(self.search_space)(self.objective_function)
            
            try:
                # Bayesian optimization
                logger.info(f"Starting Bayesian optimization, iterations: {self.config.n_calls}")
                result = gp_minimize(
                    func=objective_with_space,
                    dimensions=self.search_space,
                    n_calls=self.config.n_calls,
                    n_initial_points=10,
                    acq_func='EI',
                    random_state=self.config.random_state,
                    n_jobs=1  # Avoid nested parallelism
                )
                
                # Parse best parameters
                best_params = dict(zip([dim.name for dim in self.search_space], result.x))
                best_score = -result.fun  # Convert back to positive value
                
                logger.info(f"Round {round_num + 1} optimization complete, best score: {best_score:.4f}")
                
                # Final backtest with best parameters
                final_results = {}
                for ticker, data in self.current_stock_data.items():
                    price_macd_params = {
                        'macd_long': best_params['price_macd_long'],
                        'macd_mid': best_params['price_macd_mid'],
                        'macd_short': best_params['price_macd_short'],
                        'diff_ema_period': best_params['price_diff_ema']
                    }
                    
                    volume_macd_params = {
                        'macd_long': best_params['volume_macd_long'],
                        'macd_mid': best_params['volume_macd_mid'],
                        'macd_short': best_params['volume_macd_short'],
                        'diff_ema_period': best_params['volume_diff_ema']
                    }
                    
                    hlbw_params = {
                        'lookback_period': best_params['hlbw_lookback'],
                        'inner_ema': best_params['hlbw_inner_ema'],
                        'outer_ema': best_params['hlbw_outer_ema'],
                        'trend_ema': best_params['hlbw_trend_ema']
                    }
                    
                    prophet_params = {
                        'periods': best_params['prophet_periods'],
                        'changepoint_prior_scale': best_params['prophet_changepoint_scale']
                    }
                    
                    trading_params = {
                        'commission': best_params['commission'],
                        'stop_loss': best_params['stop_loss'],
                        'min_trend_duration': best_params['min_trend_duration']
                    }
                    
                    entry_signals, exit_signals = self._calculate_signals_with_params(
                        data, price_macd_params, volume_macd_params, 
                        hlbw_params, prophet_params, trading_params
                    )
                    
                    backtester = VectorizedBacktester(data)
                    performance = backtester.backtest_vectorized(
                        entry_signals, exit_signals, best_params['commission']
                    )
                    final_results[ticker] = performance
                
                # Create current round result
                current_result = {
                    'group_id': group_id,
                    'experiment_name': f"{experiment_name}_round{round_num + 1}",
                    'best_params': best_params,
                    'best_score': best_score,
                    'optimization_time': time.time() - start_time,
                    'results_by_stock': final_results,
                    'convergence': result.func_vals,
                    'tickers': current_tickers.copy(),
                    'round_number': round_num + 1
                }
                
                all_results.append(current_result)
                
                # Update best result
                if best_overall_result is None or best_score > best_overall_result['best_score']:
                    best_overall_result = current_result.copy()
                
                # Save each stock's backtest result
                for ticker, performance in final_results.items():
                    result_data = {
                        'result_id': f"{experiment_name}_{ticker}_round{round_num + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        'group_id': group_id,
                        'experiment_name': f"{experiment_name}_{ticker}_round{round_num + 1}",
                        'parameters': {k: float(v) if isinstance(v, (np.integer, np.floating)) else v for k, v in best_params.items()},
                        'total_return': float(performance['total_return']),
                        'annual_return': float(performance['annual_return']),
                        'sharpe_ratio': float(performance['sharpe_ratio']),
                        'max_drawdown': float(performance['max_drawdown']),
                        'volatility': float(performance['volatility']),
                        'win_rate': float(performance['win_rate']),
                        'profit_factor': float(performance['profit_factor']),
                        'total_trades': int(performance['total_trades']),
                        'start_date': self.current_stock_data[ticker].index[0].strftime('%Y-%m-%d'),
                        'end_date': self.current_stock_data[ticker].index[-1].strftime('%Y-%m-%d'),
                        'backtest_duration': float(time.time() - start_time),
                        'trade_details': [],
                        'equity_curve': performance.get('equity_curve', [])
                    }
                    self.db.save_backtest_result(result_data)
                
                # Evaluate if stock replacement is needed
                if (round_num < max_rounds - 1 and 
                    self.config.enable_stock_replacement and 
                    round_num >= self.config.min_optimization_rounds - 1):
                    
                    # Evaluate stock performance
                    stock_scores = self.replacement_manager.evaluate_stock_performance(final_results)
                    underperforming = self.replacement_manager.identify_underperforming_stocks(stock_scores)
                    
                    if underperforming:
                        logger.info(f"Found {len(underperforming)} underperforming stocks: {underperforming}")
                        new_tickers = self.replacement_manager.replace_stocks(current_tickers, underperforming)
                        
                        if new_tickers != current_tickers:
                            logger.info(f"Stock portfolio updated: {current_tickers} → {new_tickers}")
                            current_tickers = new_tickers
                        else:
                            logger.info("No suitable replacement stocks found, keeping current portfolio")
                            break
                    else:
                        logger.info("All stocks performing well, no replacement needed")
                        break
                else:
                    break
                
            except Exception as e:
                logger.error(f"Round {round_num + 1} optimization failed: {e}")
                if best_overall_result:
                    break
                return {}
        
        # Generate visualization charts
        if best_overall_result and best_overall_result['results_by_stock']:
            try:
                logger.info("Generating comprehensive optimization analysis charts...")
                
                # Create comprehensive optimization dashboard
                dashboard_file = self.visualizer.create_optimization_dashboard(
                    best_overall_result,
                    best_overall_result['convergence'],
                    best_overall_result['results_by_stock']
                )
                
                # Create simplified equity curves chart
                equity_file = self.visualizer.create_equity_curves(best_overall_result['results_by_stock'])
                
                logger.info(f"Comprehensive optimization dashboard: {dashboard_file}")
                logger.info(f"   Including: Optimization convergence, stock performance, parameter analysis")
                logger.info(f"   Including: Detailed equity curves and return curves")
                logger.info(f"   Including: Overall portfolio curves and comparison analysis")
                logger.info(f"Simplified equity curves chart: {equity_file}")
                
                best_overall_result['dashboard_file'] = dashboard_file
                best_overall_result['equity_file'] = equity_file
                
            except Exception as e:
                logger.error(f"Failed to generate visualization charts: {e}")
        
        # Add summary information
        if best_overall_result:
            best_overall_result['all_rounds'] = all_results
            best_overall_result['total_optimization_time'] = time.time() - start_time
            best_overall_result['final_tickers'] = current_tickers
            best_overall_result['replacement_history'] = self.replacement_manager.replacement_history
            
            # Save best configuration to JSON file
            config_filename = self.save_optimized_config(best_overall_result)
            if config_filename:
                best_overall_result['config_file'] = config_filename
        
        return best_overall_result or {}
    
    def close(self):
        """关闭所有数据库连接"""
        self.db.close()
        self.trading_db.close()
    
    def save_optimized_config(self, result: Dict, filename: str = None):
        """保存最优配置到JSON文件"""
        try:
            if not result or 'best_params' not in result:
                logger.warning("没有有效的优化结果，无法保存配置文件")
                return
            
            # 如果没有指定文件名，则自动生成有意义的文件名
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                experiment_name = result.get('experiment_name', 'unknown').replace('_round', '').replace('round', '')
                tickers = result.get('final_tickers', result.get('tickers', []))
                
                # 构建股票代码串（最多显示3个，超过则用数量表示）
                if len(tickers) <= 3:
                    ticker_str = '_'.join(tickers)
                else:
                    ticker_str = f"{tickers[0]}_{tickers[1]}_etc{len(tickers)}stocks"
                
                # 添加表现评级
                if 'performance_summary' in result:
                    avg_return = result['performance_summary'].get('portfolio_performance', {}).get('average_annual_return', 0)
                    if avg_return > 0.20:
                        grade = 'Excellent'
                    elif avg_return > 0.15:
                        grade = 'Good'  
                    elif avg_return > 0.10:
                        grade = 'Average'
                    elif avg_return > 0:
                        grade = 'Low'
                    else:
                        grade = 'Poor'
                else:
                    grade = 'Unknown'
                
                # 生成有意义的文件名
                filename = f"hlm5_optimized_config_{timestamp}_{experiment_name}_{ticker_str}_{grade}.json"
                
                # 确保文件名不会太长（Windows路径限制）
                if len(filename) > 100:
                    filename = f"hlm5_optimized_config_{timestamp}_{len(tickers)}stocks_{grade}.json"
            
            # 构建配置数据结构
            config_data = {
                'optimization_info': {
                    'experiment_name': result.get('experiment_name', 'unknown'),
                    'optimization_time': result.get('total_optimization_time', result.get('optimization_time', 0)),
                    'best_score': result.get('best_score', 0),
                    'optimization_rounds': result.get('round_number', 1),
                    'created_at': datetime.now().isoformat(),
                    'final_tickers': result.get('final_tickers', result.get('tickers', [])),
                    'replacement_history': result.get('replacement_history', [])
                },
                
                'technical_indicators': {
                    'PRICE_MACD': {
                        'macd_long': result['best_params'].get('price_macd_long', 26),
                        'macd_mid': result['best_params'].get('price_macd_mid', 12),
                        'macd_short': result['best_params'].get('price_macd_short', 9),
                        'diff_ema_period': result['best_params'].get('price_diff_ema', 3)
                    },
                    'VOLUME_MACD': {
                        'macd_long': result['best_params'].get('volume_macd_long', 26),
                        'macd_mid': result['best_params'].get('volume_macd_mid', 12),
                        'macd_short': result['best_params'].get('volume_macd_short', 9),
                        'diff_ema_period': result['best_params'].get('volume_diff_ema', 5)
                    },
                    'HLBW': {
                        'lookback_period': result['best_params'].get('hlbw_lookback', 55),
                        'inner_ema': result['best_params'].get('hlbw_inner_ema', 5),
                        'outer_ema': result['best_params'].get('hlbw_outer_ema', 3),
                        'trend_ema': result['best_params'].get('hlbw_trend_ema', 3)
                    },
                    'PROPHET': {
                        'periods': result['best_params'].get('prophet_periods', 30),
                        'changepoint_prior_scale': result['best_params'].get('prophet_changepoint_scale', 0.05)
                    }
                },
                
                'trading_parameters': {
                    'commission': result['best_params'].get('commission', 0.001),
                    'stop_loss': result['best_params'].get('stop_loss', 0.08),
                    'min_trend_duration': result['best_params'].get('min_trend_duration', 3)
                },
                
                'selected_stocks': result.get('final_tickers', result.get('tickers', [])),
                
                'performance_summary': self._generate_performance_summary(result),
                
                'all_parameters': result['best_params']
            }
            
            # 转换numpy类型为Python原生类型
            def convert_numpy_types(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(v) for v in obj]
                return obj
            
            config_data = convert_numpy_types(config_data)
            
            # 保存到JSON文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Optimized config saved to: {filename}")
            logger.info(f"   Contains optimization parameters for {len(config_data['selected_stocks'])} stocks")
            logger.info(f"   Best composite score: {config_data['optimization_info']['best_score']:.4f}")
            logger.info(f"   Optimization time: {config_data['optimization_info']['optimization_time']:.2f} seconds")
            
            return filename
            
        except Exception as e:
            logger.error(f"保存优化配置失败: {e}")
            return None
    
    def _generate_performance_summary(self, result: Dict) -> Dict:
        """生成性能汇总"""
        try:
            if 'results_by_stock' not in result:
                return {}
            
            stock_results = result['results_by_stock']
            
            # 计算组合整体表现
            returns = [perf['annual_return'] for perf in stock_results.values()]
            drawdowns = [perf['max_drawdown'] for perf in stock_results.values()]
            sharpe_ratios = [perf['sharpe_ratio'] for perf in stock_results.values()]
            win_rates = [perf['win_rate'] for perf in stock_results.values()]
            total_trades = sum(perf['total_trades'] for perf in stock_results.values())
            
            return {
                'portfolio_performance': {
                    'average_annual_return': float(np.mean(returns)),
                    'average_max_drawdown': float(np.mean(drawdowns)),
                    'average_sharpe_ratio': float(np.mean(sharpe_ratios)),
                    'average_win_rate': float(np.mean(win_rates)),
                    'total_trades': int(total_trades),
                    'return_drawdown_ratio': abs(float(np.mean(returns) / np.mean(drawdowns))) if np.mean(drawdowns) != 0 else 0
                },
                'best_performing_stocks': self._get_top_stocks(stock_results, 'annual_return', 5),
                'stock_count': len(stock_results),
                'quality_stats': self._get_quality_stats(stock_results)
            }
            
        except Exception as e:
            logger.error(f"生成性能汇总失败: {e}")
            return {}
    
    def _get_top_stocks(self, stock_results: Dict, metric: str, top_n: int) -> List[Dict]:
        """获取表现最佳的股票"""
        try:
            sorted_stocks = sorted(
                stock_results.items(),
                key=lambda x: x[1][metric],
                reverse=True
            )
            
            top_stocks = []
            for ticker, perf in sorted_stocks[:top_n]:
                top_stocks.append({
                    'ticker': ticker,
                    'annual_return': float(perf['annual_return']),
                    'max_drawdown': float(perf['max_drawdown']),
                    'sharpe_ratio': float(perf['sharpe_ratio']),
                    'win_rate': float(perf['win_rate']),
                    'total_trades': int(perf['total_trades'])
                })
            
            return top_stocks
            
        except Exception as e:
            logger.error(f"获取顶级股票失败: {e}")
            return []
    
    def _get_quality_stats(self, stock_results: Dict) -> Dict:
        """获取股票质量统计"""
        try:
            positive_returns = sum(1 for perf in stock_results.values() if perf['annual_return'] > 0)
            high_quality = sum(1 for perf in stock_results.values() 
                             if (perf['annual_return'] > 0 and 
                                 perf['total_trades'] >= 10 and 
                                 perf['sharpe_ratio'] >= 0.5 and
                                 abs(perf['max_drawdown']) <= 0.3 and
                                 perf['win_rate'] >= 0.3))
            low_quality = sum(1 for perf in stock_results.values() 
                            if (perf['annual_return'] > 0 and 
                                (perf['total_trades'] < 10 or 
                                 perf['sharpe_ratio'] < 0.5 or
                                 abs(perf['max_drawdown']) > 0.3 or
                                 perf['win_rate'] < 0.3)))
            negative_returns = len(stock_results) - positive_returns
            
            return {
                'total_stocks': len(stock_results),
                'positive_return_stocks': positive_returns,
                'high_quality_stocks': high_quality,
                'low_quality_stocks': low_quality,
                'negative_return_stocks': negative_returns,
                'quality_rate': float(high_quality / len(stock_results)) if stock_results else 0
            }
            
        except Exception as e:
            logger.error(f"获取质量统计失败: {e}")
            return {}

def show_examples():
    """Display usage examples"""
    examples = """
Usage Examples:
--------------

1. Auto-select 5 stocks for optimization:
   python hlm5_stock_optimize.py --auto-select --max-stocks 5

2. Optimize specific stock combination:
   python hlm5_stock_optimize.py --tickers 000725.SZ 000030.SZ 600395.SH

3. Increase optimization iterations for better results:
   python hlm5_stock_optimize.py --auto-select --n-calls 100

4. Specify experiment name and max stocks:
   python hlm5_stock_optimize.py --auto-select --max-stocks 3 --experiment test_optimization

5. Use multi-processing to speed up optimization:
   python hlm5_stock_optimize.py --auto-select --parallel-jobs 4

6. Complete example - High intensity optimization:
   python hlm5_stock_optimize.py --auto-select --max-stocks 5 --n-calls 200 --parallel-jobs 4 --experiment full_optimization
"""
    print(examples)

def show_detailed_help():
    """Display detailed help information"""
    help_text = """
HLM5 Stock Strategy Optimization System - Detailed Help
====================================================

Command Line Parameters:
----------------------
--tickers: Specify stock codes to optimize
    Example: --tickers 000725.SZ 000030.SZ 600395.SH
    
--auto-select: Enable automatic stock selection
    Description: Automatically select high-quality stocks from finscreener database
    
--max-stocks: Maximum number of stocks
    Range: 1-10
    Default: 10
    Description: Effective in auto-select mode
    
--experiment: Experiment name
    Description: For identifying and tracking optimization experiments
    Example: --experiment test_20230615
    
--n-calls: Number of optimization iterations
    Range: 10-1000
    Default: 50
    Description: More iterations may yield better results but take longer
    
--parallel-jobs: Number of parallel tasks
    Range: 1-CPU cores
    Default: -1 (automatically use all available cores)
    Description: Control parallel optimization processes

Optimization Metrics:
-------------------
1. Annual Return (Weight: 50%)
2. Maximum Drawdown (Weight: 30%)
3. Sharpe Ratio (Weight: 15%)
4. Win Rate (Weight: 5%)

Output Content:
-------------
1. Optimized strategy parameters
2. Detailed backtest results for each stock
3. Visualization charts and analysis reports
4. Optimization configuration file (ready for trading system)

Important Notes:
--------------
1. Ensure sufficient historical data in database before first run
2. Optimization process may be time-consuming, parallel mode recommended
3. Can interrupt optimization process anytime with Ctrl+C
4. Results automatically saved to database and configuration files
"""
    print(help_text)

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='HLM5 Stock Strategy Optimization System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Use --help-examples to see usage examples, use --help-detail for detailed help'
    )
    
    parser.add_argument('--tickers', nargs='+', help='List of stock codes to optimize')
    parser.add_argument('--auto-select', action='store_true', help='Auto-select stocks from finscreener')
    parser.add_argument('--max-stocks', type=int, default=10, help='Maximum number of stocks (1-10)')
    parser.add_argument('--experiment', type=str, help='Experiment name')
    parser.add_argument('--n-calls', type=int, default=50, help='Number of optimization iterations (10-1000)')
    parser.add_argument('--parallel-jobs', type=int, default=-1, help='Number of parallel jobs (default: all CPU cores)')
    parser.add_argument('--help-examples', action='store_true', help='Show usage examples')
    parser.add_argument('--help-detail', action='store_true', help='Show detailed help information')
    
    args = parser.parse_args()
    
    # Show help information
    if args.help_examples:
        show_examples()
        return
    elif args.help_detail:
        show_detailed_help()
        return
    
    # Parameter validation
    if args.max_stocks < 1 or args.max_stocks > 10:
        print("Error: max-stocks must be between 1-10")
        return
    
    if args.n_calls < 10 or args.n_calls > 1000:
        print("Error: n-calls must be between 10-1000")
        return
    
    if not args.tickers and not args.auto_select:
        print("Error: must specify --tickers or use --auto-select")
        parser.print_help()
        return
    
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Create optimization configuration
    config = OptimizationConfig(
        max_stocks=args.max_stocks,
        n_calls=args.n_calls,
        parallel_jobs=args.parallel_jobs
    )
    
    # Create optimizer
    optimizer = StrategyOptimizer(config)
    
    try:
        # Select stocks
        if args.tickers:
            tickers = args.tickers
        elif args.auto_select:
            tickers = optimizer.select_stocks_from_finscreener(args.max_stocks)
        else:
            # Default stocks
            tickers = ['000725.SZ', '000030.SZ', '600395.SH']
        
        if not tickers:
            print("Error: No valid stocks selected")
            return
        
        # Execute optimization
        result = optimizer.optimize_strategy(
            tickers, 
            args.experiment or f"auto_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        if result:
            print("\n" + "="*80)
            print("Stock Strategy Optimization Results Summary")
            print("="*80)
            print(f"Experiment Name: {result['experiment_name']}")
            print(f"Initial Stocks: {tickers}")
            print(f"Final Stocks: {result.get('final_tickers', tickers)}")
            print(f"Total Optimization Time: {result.get('total_optimization_time', result['optimization_time']):.2f} seconds")
            print(f"Optimization Rounds: {result.get('round_number', 1)}")
            print(f"Best Overall Score: {result['best_score']:.4f}")
            
            # Show stock replacement history
            if result.get('replacement_history'):
                print(f"\nStock Replacement History:")
                for i, replacement in enumerate(result['replacement_history'], 1):
                    print(f"  {i}. {replacement['old_ticker']} -> {replacement['new_ticker']} ({replacement['reason']})")
            
            print(f"\nKey Optimization Parameters (Return & Drawdown Oriented):")
            key_params = ['price_macd_long', 'volume_macd_long', 'commission', 'stop_loss']
            for param in key_params:
                if param in result['best_params']:
                    value = result['best_params'][param]
                    print(f"  {param}: {value}")
            
            print(f"\nStock Performance Ranking (by Return, Strict Filtering):")
            # Sort stocks by annual return
            sorted_stocks = sorted(
                result['results_by_stock'].items(), 
                key=lambda x: x[1]['annual_return'], 
                reverse=True
            )
            
            # Count stocks by quality
            positive_stocks = [s for s in sorted_stocks if s[1]['annual_return'] > 0]
            negative_stocks = [s for s in sorted_stocks if s[1]['annual_return'] <= 0]
            low_quality_stocks = [s for s in sorted_stocks if s[1]['annual_return'] > 0 and 
                                (s[1]['total_trades'] < 10 or s[1]['sharpe_ratio'] < 0.5 or 
                                 abs(s[1]['max_drawdown']) > 0.3 or s[1]['win_rate'] < 0.3)]
            
            print(f"Stock Quality Statistics:")
            print(f"  High Quality Stocks: {len(positive_stocks) - len(low_quality_stocks)} stocks")
            print(f"  Quality Not Met: {len(low_quality_stocks)} stocks")  
            print(f"  Negative Return Stocks: {len(negative_stocks)} stocks")
            
            print(f"\n{'Rank':<4} {'Stock Code':<12} {'Annual Return':<12} {'Max Drawdown':<12} {'Sharpe':<10} {'Win Rate':<8} {'Trades':<8} {'Quality':<8}")
            print("-" * 80)
            
            for rank, (ticker, perf) in enumerate(sorted_stocks, 1):
                return_str = f"{perf['annual_return']:.2%}"
                drawdown_str = f"{perf['max_drawdown']:.2%}"
                sharpe_str = f"{perf['sharpe_ratio']:.3f}"
                winrate_str = f"{perf['win_rate']:.1%}"
                trades_str = f"{perf['total_trades']}"
                
                # Quality mark
                if perf['annual_return'] <= 0:
                    quality = "Neg"
                elif (perf['total_trades'] < 10 or perf['sharpe_ratio'] < 0.5 or 
                      abs(perf['max_drawdown']) > 0.3 or perf['win_rate'] < 0.3):
                    quality = "Low"
                elif perf['annual_return'] > 0.20 and abs(perf['max_drawdown']) < 0.10:
                    quality = "Excel"
                else:
                    quality = "Good"
                
                print(f"{rank:<4} {ticker:<12} {return_str:<12} {drawdown_str:<12} {sharpe_str:<10} {winrate_str:<8} {trades_str:<8} {quality:<8}")
            
            # Calculate portfolio overall performance
            total_return = np.mean([perf['annual_return'] for perf in result['results_by_stock'].values()])
            total_drawdown = np.mean([perf['max_drawdown'] for perf in result['results_by_stock'].values()])
            total_sharpe = np.mean([perf['sharpe_ratio'] for perf in result['results_by_stock'].values()])
            
            print(f"\nPortfolio Overall Performance:")
            print(f"  Average Annual Return: {total_return:.2%}")
            print(f"  Average Max Drawdown: {total_drawdown:.2%}")
            print(f"  Average Sharpe Ratio: {total_sharpe:.3f}")
            print(f"  Return/Drawdown Ratio: {abs(total_return/total_drawdown):.2f}")
            
            # Show chart information
            if result.get('dashboard_file'):
                print(f"\nComprehensive Analysis Charts Opened in Browser:")
                print(f"  Dashboard: {result['dashboard_file']}")
                print(f"     Optimization convergence and parameter sensitivity analysis")
                print(f"     Stock performance comparison and return-drawdown scatter plot")
                print(f"     Detailed equity curves and return curves for each stock")
                print(f"     Overall portfolio curves and stock comparison analysis")
                if result.get('equity_file'):
                    print(f"  Simplified Curves: {result['equity_file']}")
            
            # Show saved configuration file information
            if result.get('config_file'):
                print(f"\nBest Configuration File Generated:")
                print(f"  Config File: {result['config_file']}")
                print(f"  Technical Indicators: Updated with optimized parameters")
                print(f"  Stock List: {len(result.get('final_tickers', []))} selected stocks")
                print(f"  Ready for portfolio and trading systems")
            
            print("\nOptimization Complete! Results saved to database, comprehensive analysis charts opened in browser.")
        else:
            print("Optimization Failed")
            
    except KeyboardInterrupt:
        print("\nUser interrupted optimization process")
    except Exception as e:
        logger.error(f"Main program execution failed: {e}")
    finally:
        optimizer.close()

if __name__ == "__main__":
    main() 