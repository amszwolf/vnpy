"""
复盘分析工具
分析策略的历史表现，找出问题和改进点
"""

import pandas as pd
from datetime import datetime
from typing import Optional


class ReviewAnalyzer:
    """
    复盘分析器
    """
    
    def __init__(self, result_df: pd.DataFrame):
        """
        初始化复盘分析器
        
        参数:
            result_df: 回测结果DataFrame
        """
        self.result_df = result_df
    
    def analyze_trades(self) -> pd.DataFrame:
        """
        分析交易记录
        
        返回:
            交易分析DataFrame
        """
        if 'trade' not in self.result_df.columns:
            print("回测结果中没有交易记录")
            return pd.DataFrame()
        
        trades = self.result_df['trade'].dropna()
        
        if len(trades) == 0:
            print("没有交易记录")
            return pd.DataFrame()
        
        # 分析每笔交易
        trade_analysis = []
        
        for idx, trade_value in trades.items():
            trade_analysis.append({
                "date": idx,
                "profit": trade_value,
                "is_win": trade_value > 0
            })
        
        trade_df = pd.DataFrame(trade_analysis)
        
        # 计算连续盈亏
        trade_df['cumulative_profit'] = trade_df['profit'].cumsum()
        trade_df['max_cumulative'] = trade_df['cumulative_profit'].cummax()
        trade_df['drawdown'] = trade_df['cumulative_profit'] - trade_df['max_cumulative']
        
        return trade_df
    
    def analyze_periods(self) -> dict:
        """
        分析不同时间段的表现
        
        返回:
            时间段分析字典
        """
        if self.result_df.empty:
            return {}
        
        # 确保index是DatetimeIndex
        if not isinstance(self.result_df.index, pd.DatetimeIndex):
            if 'datetime' in self.result_df.columns:
                self.result_df.set_index('datetime', inplace=True)
            else:
                return {}
        
        # 按月分析
        monthly_returns = self.result_df.groupby(
            pd.PeriodIndex(self.result_df.index, freq='M')
        )['return'].sum()
        
        # 按季度分析
        quarterly_returns = self.result_df.groupby(
            pd.PeriodIndex(self.result_df.index, freq='Q')
        )['return'].sum()
        
        return {
            "monthly_returns": monthly_returns.to_dict(),
            "quarterly_returns": quarterly_returns.to_dict(),
            "best_month": monthly_returns.idxmax(),
            "worst_month": monthly_returns.idxmin(),
            "best_quarter": quarterly_returns.idxmax(),
            "worst_quarter": quarterly_returns.idxmin()
        }
    
    def find_problems(self) -> list:
        """
        找出策略存在的问题
        
        返回:
            问题列表
        """
        problems = []
        
        if self.result_df.empty:
            problems.append("回测结果为空")
            return problems
        
        # 检查最大回撤
        if 'balance' in self.result_df.columns:
            balance = self.result_df['balance'].values
            peak = pd.Series(balance).expanding().max()
            drawdown = (balance - peak) / peak
            max_dd = drawdown.min()
        else:
            max_dd = 0
        
        if max_dd < -0.2:
            problems.append(f"最大回撤过大: {max_dd:.2%}，超过20%")
        
        # 检查交易频率
        if 'trade' in self.result_df.columns:
            trades = self.result_df['trade'].dropna()
            if len(trades) < 10:
                problems.append(f"交易次数过少: {len(trades)}次，可能策略信号不足")
            elif len(trades) > 1000:
                problems.append(f"交易次数过多: {len(trades)}次，可能产生过多手续费")
        
        # 检查胜率
        if 'trade' in self.result_df.columns:
            trades = self.result_df['trade'].dropna()
            if len(trades) > 0:
                win_rate = (trades > 0).sum() / len(trades)
                if win_rate < 0.3:
                    problems.append(f"胜率过低: {win_rate:.2%}，低于30%")
        
        # 检查收益率
        if 'return' in self.result_df.columns and 'balance' in self.result_df.columns:
            balance = self.result_df['balance'].values
            returns = self.result_df['return'].values
            if len(balance) > 0 and balance[0] > 0:
                total_return = (balance[-1] - balance[0]) / balance[0]
                if total_return < 0:
                    problems.append(f"总收益率为负: {total_return:.2%}")
        
        return problems
    
    def generate_review_report(self, filepath: str):
        """
        生成复盘报告
        
        参数:
            filepath: 保存路径
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("策略复盘分析报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 交易分析
            trade_df = self.analyze_trades()
            if not trade_df.empty:
                f.write("交易分析:\n")
                f.write(f"总交易次数: {len(trade_df)}\n")
                f.write(f"盈利交易: {(trade_df['is_win']).sum()}\n")
                f.write(f"亏损交易: {(~trade_df['is_win']).sum()}\n")
                f.write(f"最大单笔盈利: {trade_df['profit'].max():.2f}\n")
                f.write(f"最大单笔亏损: {trade_df['profit'].min():.2f}\n")
                f.write(f"最大回撤: {trade_df['drawdown'].min():.2f}\n\n")
            
            # 时间段分析
            periods = self.analyze_periods()
            if periods:
                f.write("时间段表现:\n")
                f.write(f"最佳月份: {periods.get('best_month')}\n")
                f.write(f"最差月份: {periods.get('worst_month')}\n")
                f.write(f"最佳季度: {periods.get('best_quarter')}\n")
                f.write(f"最差季度: {periods.get('worst_quarter')}\n\n")
            
            # 问题分析
            problems = self.find_problems()
            if problems:
                f.write("发现的问题:\n")
                for i, problem in enumerate(problems, 1):
                    f.write(f"{i}. {problem}\n")
            else:
                f.write("未发现明显问题\n")
            
            f.write("\n" + "=" * 60 + "\n")
        
        print(f"复盘报告已保存到: {filepath}")

