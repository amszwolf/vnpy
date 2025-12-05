"""
加仓策略可视化模块 (Scaling Strategy Visualizer)

使用 Bokeh 生成交互式图表，展示加仓策略的详细信号、回测曲线和对比分析。

Python环境：aidata311
"""

import numpy as np
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Tuple

from bokeh.plotting import figure, output_file, save
from bokeh.layouts import column, row, gridplot
from bokeh.models import (
    HoverTool, ColumnDataSource, Legend, Range1d,
    LinearAxis, BoxAnnotation, Span, Label
)
from bokeh.palettes import Category20, Set3
from bokeh.io import export_png

import logging

logger = logging.getLogger(__name__)


class ScalingStrategyVisualizer:
    """加仓策略可视化器"""
    
    def __init__(self, output_dir: str = "scaling_charts"):
        """
        初始化可视化器
        
        Parameters:
        -----------
        output_dir : str
            输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 颜色配置
        self.colors = {
            'price': '#1f77b4',
            'entry': '#2ca02c',
            'exit': '#d62728',
            'add': '#ff7f0e',
            'profit': '#2ca02c',
            'loss': '#d62728',
            'position': '#9467bd'
        }
        
        # 策略颜色映射
        self.strategy_colors = {
            'pyramid': '#1f77b4',
            'inverse_pyramid': '#ff7f0e',
            'linear': '#2ca02c',
            'fixed_fraction': '#d62728',
            'aggressive_pyramid': '#9467bd'
        }
    
    def plot_single_strategy(self, 
                            signals_df: pd.DataFrame,
                            ticker: str,
                            strategy_name: str,
                            metrics: Dict) -> str:
        """
        绘制单个策略的详细图表
        
        Parameters:
        -----------
        signals_df : pd.DataFrame
            包含交易信号的DataFrame
        ticker : str
            期货代码
        strategy_name : str
            策略名称
        metrics : Dict
            性能指标
        
        Returns:
        --------
        str : 输出文件路径
        """
        logger.info(f"Plotting {strategy_name} for {ticker}")
        
        # 准备数据
        df = signals_df.copy()
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['datetime_str'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
        
        # 创建输出文件
        output_file_path = os.path.join(
            self.output_dir,
            f"{ticker}_{strategy_name}_analysis.html"
        )
        output_file(output_file_path)
        
        # 创建图表布局
        plots = []
        
        # 1. 价格和加仓信号图（主图，不传入x_range）
        p1 = self._plot_price_and_signals(df, ticker, strategy_name)
        plots.append(p1)
        
        # 2. 持仓变化图（共享横轴）
        p2 = self._plot_position_changes(df, ticker, strategy_name, x_range=p1.x_range)
        plots.append(p2)
        
        # 3. 累计收益曲线（共享横轴）
        p3 = self._plot_cumulative_pnl(df, ticker, strategy_name, metrics, x_range=p1.x_range)
        plots.append(p3)
        
        # 4. 加仓层级分布（共享横轴）
        p4 = self._plot_scaling_levels(df, ticker, strategy_name, x_range=p1.x_range)
        plots.append(p4)
        
        # 组合所有图表
        layout = column(*plots)
        
        # 保存
        save(layout)
        logger.info(f"Chart saved to: {output_file_path}")
        
        return output_file_path
    
    def _plot_price_and_signals(self, df: pd.DataFrame, 
                                ticker: str, 
                                strategy_name: str):
        """绘制价格和加仓信号"""
        
        # 创建图表（增强交互工具）
        p = figure(
            width=1400,
            height=400,
            title=f"{ticker} - {strategy_name} 价格走势与加仓信号",
            x_axis_type='datetime',
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save,crosshair'
        )
        
        # 绘制价格线
        source = ColumnDataSource(df)
        p.line('datetime', 'close', source=source,
               line_width=1.5, color=self.colors['price'],
               legend_label='价格')
        
        # ========== 做多信号 ==========
        # 做多入场信号（深绿色圆圈）
        long_entry_df = df[(df['Scaling_Action'] == 'entry') & (df['Scaling_Direction'] == 1)]
        if not long_entry_df.empty:
            p.circle('datetime', 'close', source=ColumnDataSource(long_entry_df),
                    size=14, color='#2ca02c', line_color='darkgreen', line_width=2,
                    legend_label='做多开仓', alpha=0.9)
        
        # 做多加仓信号（绿色上三角）
        long_add_df = df[(df['Scaling_Action'] == 'add') & (df['Scaling_Direction'] == 1)]
        if not long_add_df.empty:
            for level in sorted(long_add_df['Scaling_Level'].unique()):
                level_df = long_add_df[long_add_df['Scaling_Level'] == level]
                p.triangle('datetime', 'close', source=ColumnDataSource(level_df),
                          size=10 + level * 2, color='#7fbc41', line_color='green', line_width=1,
                          legend_label=f'做多加仓 Lv{level}', alpha=0.8)
        
        # 做多平仓信号（绿色方块）
        long_exit_df = df[(df['Scaling_Action'].str.contains('exit', na=False)) & 
                         (df['Scaling_Direction'].shift(1) == 1)]
        if not long_exit_df.empty:
            p.square('datetime', 'close', source=ColumnDataSource(long_exit_df),
                    size=12, color='#a8ddb5', line_color='green', line_width=2,
                    legend_label='做多平仓', alpha=0.8)
        
        # ========== 做空信号 ==========
        # 做空入场信号（深红色圆圈）
        short_entry_df = df[(df['Scaling_Action'] == 'entry') & (df['Scaling_Direction'] == -1)]
        if not short_entry_df.empty:
            p.circle('datetime', 'close', source=ColumnDataSource(short_entry_df),
                    size=14, color='#d62728', line_color='darkred', line_width=2,
                    legend_label='做空开仓', alpha=0.9)
        
        # 做空加仓信号（红色下三角）
        short_add_df = df[(df['Scaling_Action'] == 'add') & (df['Scaling_Direction'] == -1)]
        if not short_add_df.empty:
            for level in sorted(short_add_df['Scaling_Level'].unique()):
                level_df = short_add_df[short_add_df['Scaling_Level'] == level]
                p.inverted_triangle('datetime', 'close', source=ColumnDataSource(level_df),
                                   size=10 + level * 2, color='#fc8d59', line_color='red', line_width=1,
                                   legend_label=f'做空加仓 Lv{level}', alpha=0.8)
        
        # 做空平仓信号（红色方块）
        short_exit_df = df[(df['Scaling_Action'].str.contains('exit', na=False)) & 
                          (df['Scaling_Direction'].shift(1) == -1)]
        if not short_exit_df.empty:
            p.square('datetime', 'close', source=ColumnDataSource(short_exit_df),
                    size=12, color='#fdae6b', line_color='red', line_width=2,
                    legend_label='做空平仓', alpha=0.8)
        
        # 配置悬停工具
        hover = HoverTool(
            tooltips=[
                ('时间', '@datetime_str'),
                ('价格', '@close{0.00}'),
                ('动作', '@Scaling_Action'),
                ('方向', '@Scaling_Direction{0}'),  # 1=多，-1=空
                ('持仓', '@Scaling_Position'),
                ('层级', '@Scaling_Level')
            ]
        )
        p.add_tools(hover)
        
        # 配置图例
        p.legend.location = "top_left"
        p.legend.click_policy = "hide"
        
        return p
    
    def _plot_position_changes(self, df: pd.DataFrame,
                              ticker: str,
                              strategy_name: str,
                              x_range=None):
        """绘制持仓变化"""
        
        p = figure(
            width=1400,
            height=250,
            title=f"{ticker} - {strategy_name} 持仓变化",
            x_axis_type='datetime',
            x_range=x_range,  # 共享横轴范围
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save,crosshair'
        )
        
        # 添加零线列
        df['zero'] = 0
        
        # 绘制持仓线
        source = ColumnDataSource(df)
        p.line('datetime', 'Scaling_Position', source=source,
               line_width=2, color=self.colors['position'],
               legend_label='持仓数量')
        
        # 添加零线
        p.line('datetime', 'zero', source=source,
               line_width=1, color='gray', alpha=0.5,
               line_dash='dashed')
        
        # 配置悬停工具
        hover = HoverTool(
            tooltips=[
                ('时间', '@datetime_str'),
                ('持仓', '@Scaling_Position'),
                ('层级', '@Scaling_Level')
            ]
        )
        p.add_tools(hover)
        
        p.legend.location = "top_left"
        
        return p
    
    def _plot_cumulative_pnl(self, df: pd.DataFrame,
                            ticker: str,
                            strategy_name: str,
                            metrics: Dict,
                            x_range=None):
        """绘制累计收益曲线"""
        
        # 计算累计收益
        df['Cumulative_PnL'] = df['Realized_PnL'].cumsum()
        df['zero'] = 0
        
        p = figure(
            width=1400,
            height=300,
            title=f"{ticker} - {strategy_name} 累计收益曲线 (总收益: {metrics.get('total_return_pct', 0):.2f}%)",
            x_axis_type='datetime',
            x_range=x_range,  # 共享横轴范围
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save,crosshair'
        )
        
        # 绘制累计收益线
        source = ColumnDataSource(df)
        p.line('datetime', 'Cumulative_PnL', source=source,
               line_width=2.5, color=self.colors['profit'],
               legend_label='累计收益')
        
        # 填充正收益区域
        positive_mask = df['Cumulative_PnL'] >= 0
        if positive_mask.any():
            p.varea('datetime', 0, 'Cumulative_PnL', 
                   source=ColumnDataSource(df[positive_mask]),
                   color=self.colors['profit'], alpha=0.2)
        
        # 填充负收益区域
        negative_mask = df['Cumulative_PnL'] < 0
        if negative_mask.any():
            p.varea('datetime', 'Cumulative_PnL', 0,
                   source=ColumnDataSource(df[negative_mask]),
                   color=self.colors['loss'], alpha=0.2)
        
        # 添加零线
        p.line('datetime', 'zero', source=source,
               line_width=1, color='gray', alpha=0.5,
               line_dash='dashed')
        
        # 添加性能指标文本
        metrics_text = (
            f"夏普比率: {metrics.get('sharpe_ratio', 0):.4f} | "
            f"胜率: {metrics.get('win_rate', 0):.2%} | "
            f"最大回撤: {metrics.get('max_drawdown_pct', 0):.2f}%"
        )
        label = Label(
            x=10, y=10, x_units='screen', y_units='screen',
            text=metrics_text,
            text_font_size='10pt',
            text_color='navy'
        )
        p.add_layout(label)
        
        # 配置悬停工具
        hover = HoverTool(
            tooltips=[
                ('时间', '@datetime_str'),
                ('累计收益', '@Cumulative_PnL{0.00}'),
                ('本次收益', '@Realized_PnL{0.00}')
            ]
        )
        p.add_tools(hover)
        
        p.legend.location = "top_left"
        
        return p
    
    def _plot_scaling_levels(self, df: pd.DataFrame,
                            ticker: str,
                            strategy_name: str,
                            x_range=None):
        """绘制加仓层级分布"""
        
        p = figure(
            width=1400,
            height=200,
            title=f"{ticker} - {strategy_name} 加仓层级时序",
            x_axis_type='datetime',
            x_range=x_range,  # 共享横轴范围
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save,crosshair'
        )
        
        # 绘制加仓层级
        source = ColumnDataSource(df)
        p.line('datetime', 'Scaling_Level', source=source,
               line_width=2, color='orange',
               legend_label='加仓层级')
        
        # 配置悬停工具
        hover = HoverTool(
            tooltips=[
                ('时间', '@datetime_str'),
                ('层级', '@Scaling_Level'),
                ('持仓', '@Scaling_Position')
            ]
        )
        p.add_tools(hover)
        
        p.legend.location = "top_left"
        
        return p
    
    def plot_strategy_comparison(self,
                                results: Dict[str, Dict],
                                ticker: str) -> str:
        """
        绘制多个策略的对比图
        
        Parameters:
        -----------
        results : Dict[str, Dict]
            各策略的测试结果
        ticker : str
            期货代码
        
        Returns:
        --------
        str : 输出文件路径
        """
        logger.info(f"Creating comparison chart for {ticker}")
        
        # 创建输出文件
        output_file_path = os.path.join(
            self.output_dir,
            f"{ticker}_strategy_comparison.html"
        )
        output_file(output_file_path)
        
        plots = []
        
        # 1. 收益曲线对比（主图）
        p1 = self._plot_pnl_comparison(results, ticker)
        plots.append(p1)
        
        # 2. 性能指标柱状图（独立图表，横轴是策略名称）
        p2 = self._plot_metrics_comparison(results, ticker)
        plots.append(p2)
        
        # 3. 风险收益散点图（独立图表）
        p3 = self._plot_risk_return_scatter(results, ticker)
        plots.append(p3)
        
        # 组合图表
        layout = column(*plots)
        save(layout)
        
        logger.info(f"Comparison chart saved to: {output_file_path}")
        
        return output_file_path
    
    def _plot_pnl_comparison(self, results: Dict, ticker: str):
        """绘制收益曲线对比"""
        
        p = figure(
            width=1400,
            height=450,
            title=f"{ticker} - 各策略累计收益对比",
            x_axis_type='datetime',
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save,crosshair'
        )
        
        # 为每个策略绘制收益曲线
        for strategy_name, result in results.items():
            if result['status'] != 'success':
                continue
            
            signals_df = result['signals_df']
            signals_df['datetime'] = pd.to_datetime(signals_df['datetime'])
            signals_df['Cumulative_PnL'] = signals_df['Realized_PnL'].cumsum()
            
            color = self.strategy_colors.get(strategy_name, '#333333')
            
            source = ColumnDataSource(signals_df)
            p.line('datetime', 'Cumulative_PnL', source=source,
                   line_width=2.5, color=color,
                   legend_label=strategy_name, alpha=0.8)
        
        # 添加零线
        p.line([signals_df['datetime'].min(), signals_df['datetime'].max()],
               [0, 0], line_width=1, color='gray', alpha=0.5,
               line_dash='dashed')
        
        p.legend.location = "top_left"
        p.legend.click_policy = "hide"
        
        # 配置悬停工具
        hover = HoverTool(
            tooltips=[
                ('策略', '$name'),
                ('累计收益', '$y{0.00}')
            ]
        )
        p.add_tools(hover)
        
        return p
    
    def _plot_metrics_comparison(self, results: Dict, ticker: str):
        """绘制性能指标对比"""
        
        # 提取指标数据
        strategies = []
        returns = []
        sharpes = []
        win_rates = []
        drawdowns = []
        
        for strategy_name, result in results.items():
            if result['status'] != 'success':
                continue
            
            metrics = result['metrics']
            strategies.append(strategy_name)
            returns.append(metrics['total_return_pct'])
            sharpes.append(metrics['sharpe_ratio'])
            win_rates.append(metrics['win_rate'] * 100)
            drawdowns.append(abs(metrics['max_drawdown_pct']))
        
        # 创建图表
        p = figure(
            width=1400,
            height=350,
            title=f"{ticker} - 关键指标对比",
            x_range=strategies,
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save'
        )
        
        # 设置多个Y轴
        p.y_range = Range1d(0, max(returns) * 1.2)
        
        # 绘制收益率柱状图
        p.vbar(x=strategies, top=returns, width=0.15, 
               color=self.colors['profit'], alpha=0.7,
               legend_label='总收益率(%)')
        
        # 绘制夏普比率（缩放）
        sharpes_scaled = [s * 100 for s in sharpes]
        p.vbar(x=[s + ' ' for s in strategies], top=sharpes_scaled, 
               width=0.15, color='orange', alpha=0.7,
               legend_label='夏普比率(×100)')
        
        p.xaxis.major_label_orientation = 0.785  # 45度
        p.legend.location = "top_right"
        
        return p
    
    def _plot_risk_return_scatter(self, results: Dict, ticker: str):
        """绘制风险收益散点图"""
        
        # 提取数据
        strategies = []
        returns = []
        risks = []
        colors = []
        
        for strategy_name, result in results.items():
            if result['status'] != 'success':
                continue
            
            metrics = result['metrics']
            strategies.append(strategy_name)
            returns.append(metrics['total_return_pct'])
            risks.append(abs(metrics['max_drawdown_pct']))
            colors.append(self.strategy_colors.get(strategy_name, '#333333'))
        
        # 创建图表
        p = figure(
            width=700,
            height=400,
            title=f"{ticker} - 风险收益分析（左下角最优）",
            toolbar_location='above',
            tools='pan,wheel_zoom,box_zoom,reset,save'
        )
        
        # 绘制散点
        source = ColumnDataSource(dict(
            x=risks,
            y=returns,
            strategy=strategies,
            color=colors
        ))
        
        p.circle('x', 'y', source=source, size=20,
                color='color', alpha=0.7)
        
        # 添加策略标签
        for i, strategy in enumerate(strategies):
            label = Label(
                x=risks[i], y=returns[i],
                text=strategy,
                x_offset=10, y_offset=5,
                text_font_size='9pt'
            )
            p.add_layout(label)
        
        p.xaxis.axis_label = "最大回撤 (%)"
        p.yaxis.axis_label = "总收益率 (%)"
        
        # 配置悬停工具
        hover = HoverTool(
            tooltips=[
                ('策略', '@strategy'),
                ('收益率', '@y{0.00}%'),
                ('最大回撤', '@x{0.00}%')
            ]
        )
        p.add_tools(hover)
        
        return p


def visualize_all_strategies(results: Dict[str, Dict[str, Dict]],
                            output_dir: str = "scaling_charts") -> Dict[str, List[str]]:
    """
    为所有策略生成可视化图表
    
    Parameters:
    -----------
    results : Dict[str, Dict[str, Dict]]
        测试结果 {ticker: {strategy_name: result}}
    output_dir : str
        输出目录
    
    Returns:
    --------
    Dict[str, List[str]] : 生成的图表文件路径
    """
    visualizer = ScalingStrategyVisualizer(output_dir)
    chart_files = {}
    
    for ticker, strategies_result in results.items():
        chart_files[ticker] = []
        
        # 为每个策略生成详细图表
        for strategy_name, result in strategies_result.items():
            if result['status'] != 'success':
                continue
            
            file_path = visualizer.plot_single_strategy(
                result['signals_df'],
                ticker,
                strategy_name,
                result['metrics']
            )
            chart_files[ticker].append(file_path)
        
        # 生成对比图表
        comparison_path = visualizer.plot_strategy_comparison(
            strategies_result,
            ticker
        )
        chart_files[ticker].append(comparison_path)
    
    return chart_files


if __name__ == "__main__":
    print("Scaling Strategy Visualizer Module Loaded Successfully")

