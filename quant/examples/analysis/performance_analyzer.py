"""
绩效分析工具
分析策略回测和实盘交易的绩效
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional


class PerformanceAnalyzer:
    """
    绩效分析器
    """
    
    def __init__(self, result_df: pd.DataFrame):
        """
        初始化分析器
        
        参数:
            result_df: 回测结果DataFrame
        """
        self.result_df = result_df
        self.statistics = {}
    
    def calculate_statistics(self) -> dict:
        """
        计算统计指标
        
        返回:
            统计指标字典
        """
        if self.result_df.empty:
            return {}
        
        # 提取关键列
        balance = self.result_df['balance'].values
        returns = self.result_df['return'].values
        
        # 基本统计
        start_balance = balance[0]
        end_balance = balance[-1]
        total_return = (end_balance - start_balance) / start_balance
        
        # 计算年化收益率
        days = len(self.result_df)
        years = days / 252  # 假设一年252个交易日
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 计算最大回撤
        max_dd = self._calculate_max_drawdown(balance)
        
        # 计算夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        
        # 计算收益回撤比
        return_drawdown_ratio = annual_return / abs(max_dd) if max_dd != 0 else 0
        
        # 交易统计（如果有trade列）
        if 'trade' in self.result_df.columns:
            trades = self.result_df['trade'].dropna()
            total_trades = len(trades)
            
            if total_trades > 0:
                winning_trades = trades[trades > 0]
                losing_trades = trades[trades < 0]
                
                win_rate = len(winning_trades) / total_trades
                average_win = winning_trades.mean() if len(winning_trades) > 0 else 0
                average_loss = abs(losing_trades.mean()) if len(losing_trades) > 0 else 0
                profit_loss_ratio = average_win / average_loss if average_loss > 0 else 0
            else:
                win_rate = 0
                average_win = 0
                average_loss = 0
                profit_loss_ratio = 0
        else:
            total_trades = 0
            win_rate = 0
            average_win = 0
            average_loss = 0
            profit_loss_ratio = 0
        
        self.statistics = {
            "start_balance": start_balance,
            "end_balance": end_balance,
            "total_return": total_return,
            "annual_return": annual_return,
            "max_dd": max_dd,
            "sharpe_ratio": sharpe_ratio,
            "return_drawdown_ratio": return_drawdown_ratio,
            "total_trade_count": total_trades,
            "win_rate": win_rate,
            "average_win": average_win,
            "average_loss": average_loss,
            "profit_loss_ratio": profit_loss_ratio
        }
        
        return self.statistics
    
    def _calculate_max_drawdown(self, balance: np.ndarray) -> float:
        """
        计算最大回撤
        """
        peak = np.maximum.accumulate(balance)
        drawdown = (balance - peak) / peak
        return drawdown.min()
    
    def _calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.03) -> float:
        """
        计算夏普比率
        
        参数:
            returns: 收益率序列
            risk_free_rate: 无风险利率（默认3%）
        """
        if len(returns) == 0:
            return 0
        
        excess_returns = returns - risk_free_rate / 252  # 日化无风险利率
        if excess_returns.std() == 0:
            return 0
        
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        return sharpe
    
    def print_statistics(self):
        """
        打印统计指标
        """
        if not self.statistics:
            self.calculate_statistics()
        
        stats = self.statistics
        
        print("=" * 60)
        print("绩效统计指标")
        print("=" * 60)
        print(f"起始资金: {stats.get('start_balance', 0):,.2f}")
        print(f"结束资金: {stats.get('end_balance', 0):,.2f}")
        print(f"总收益率: {stats.get('total_return', 0):.2%}")
        print(f"年化收益率: {stats.get('annual_return', 0):.2%}")
        print(f"最大回撤: {stats.get('max_dd', 0):.2%}")
        print(f"夏普比率: {stats.get('sharpe_ratio', 0):.2f}")
        print(f"收益回撤比: {stats.get('return_drawdown_ratio', 0):.2f}")
        print(f"总成交次数: {stats.get('total_trade_count', 0)}")
        print(f"胜率: {stats.get('win_rate', 0):.2%}")
        print(f"平均盈利: {stats.get('average_win', 0):.2f}")
        print(f"平均亏损: {stats.get('average_loss', 0):.2f}")
        print(f"盈亏比: {stats.get('profit_loss_ratio', 0):.2f}")
        print("=" * 60)
    
    def export_report(self, filepath: str):
        """
        导出分析报告
        
        参数:
            filepath: 保存路径
        """
        if not self.statistics:
            self.calculate_statistics()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("策略绩效分析报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            stats = self.statistics
            f.write("统计指标:\n")
            f.write(f"起始资金: {stats.get('start_balance', 0):,.2f}\n")
            f.write(f"结束资金: {stats.get('end_balance', 0):,.2f}\n")
            f.write(f"总收益率: {stats.get('total_return', 0):.2%}\n")
            f.write(f"年化收益率: {stats.get('annual_return', 0):.2%}\n")
            f.write(f"最大回撤: {stats.get('max_dd', 0):.2%}\n")
            f.write(f"夏普比率: {stats.get('sharpe_ratio', 0):.2f}\n")
            f.write(f"收益回撤比: {stats.get('return_drawdown_ratio', 0):.2f}\n")
            f.write(f"总成交次数: {stats.get('total_trade_count', 0)}\n")
            f.write(f"胜率: {stats.get('win_rate', 0):.2%}\n")
            f.write(f"平均盈利: {stats.get('average_win', 0):.2f}\n")
            f.write(f"平均亏损: {stats.get('average_loss', 0):.2f}\n")
            f.write(f"盈亏比: {stats.get('profit_loss_ratio', 0):.2f}\n")
            f.write("=" * 60 + "\n")
        
        print(f"分析报告已保存到: {filepath}")

