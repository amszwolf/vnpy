# -*- coding: utf-8 -*-
"""
HLM5 策略性能分析工具

分析回测结果，生成详细的性能报告
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


class PerformanceAnalyzer:
    """
    性能分析器
    
    从回测结果中提取和分析各项性能指标
    """
    
    def __init__(self, backtest_result_df=None, trades_list=None):
        """
        初始化性能分析器
        
        Parameters:
        -----------
        backtest_result_df : pandas.DataFrame, optional
            回测结果DataFrame（包含balance等列）
        trades_list : list, optional
            交易记录列表
        """
        self.result_df = backtest_result_df
        self.trades = trades_list
        
        # 性能指标
        self.metrics = {}
    
    def analyze(self):
        """
        执行完整的性能分析
        
        Returns:
        --------
        dict : 性能指标字典
        """
        print("=" * 60)
        print("性能分析")
        print("=" * 60)
        
        if self.result_df is not None and not self.result_df.empty:
            self._analyze_returns()
            self._analyze_drawdown()
            self._analyze_risk_metrics()
        
        if self.trades is not None and len(self.trades) > 0:
            self._analyze_trades()
        
        return self.metrics
    
    def _analyze_returns(self):
        """分析收益指标"""
        if 'balance' not in self.result_df.columns:
            return
        
        balance = self.result_df['balance']
        initial_balance = balance.iloc[0]
        final_balance = balance.iloc[-1]
        
        # 总收益率
        total_return = (final_balance - initial_balance) / initial_balance
        self.metrics['total_return'] = total_return
        
        # 计算日收益率
        daily_returns = balance.pct_change().dropna()
        
        # 年化收益率
        trading_days = len(self.result_df)
        if trading_days > 0:
            annual_return = (1 + total_return) ** (252 / trading_days) - 1
            self.metrics['annual_return'] = annual_return
        
        # 平均日收益率
        self.metrics['avg_daily_return'] = daily_returns.mean()
        self.metrics['daily_return_std'] = daily_returns.std()
        
        print(f"\n收益指标:")
        print(f"  总收益率: {total_return*100:.2f}%")
        print(f"  年化收益率: {self.metrics.get('annual_return', 0)*100:.2f}%")
        print(f"  日均收益率: {self.metrics['avg_daily_return']*100:.4f}%")
    
    def _analyze_drawdown(self):
        """分析回撤指标"""
        if 'balance' not in self.result_df.columns:
            return
        
        balance = self.result_df['balance']
        
        # 计算累计最大值
        cum_max = balance.cummax()
        
        # 计算回撤
        drawdown = (balance - cum_max) / cum_max
        
        # 最大回撤
        max_drawdown = drawdown.min()
        self.metrics['max_drawdown'] = max_drawdown
        
        # 最大回撤发生时间
        max_dd_idx = drawdown.idxmin()
        self.metrics['max_drawdown_date'] = max_dd_idx
        
        # 平均回撤
        negative_dd = drawdown[drawdown < 0]
        if len(negative_dd) > 0:
            self.metrics['avg_drawdown'] = negative_dd.mean()
        else:
            self.metrics['avg_drawdown'] = 0
        
        print(f"\n回撤指标:")
        print(f"  最大回撤: {max_drawdown*100:.2f}%")
        print(f"  平均回撤: {self.metrics['avg_drawdown']*100:.2f}%")
        print(f"  最大回撤日期: {max_dd_idx}")
    
    def _analyze_risk_metrics(self):
        """分析风险指标"""
        if 'balance' not in self.result_df.columns:
            return
        
        balance = self.result_df['balance']
        daily_returns = balance.pct_change().dropna()
        
        # 夏普比率（假设无风险利率为0）
        if daily_returns.std() != 0:
            sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
            self.metrics['sharpe_ratio'] = sharpe_ratio
        else:
            self.metrics['sharpe_ratio'] = 0
        
        # 收益回撤比
        if self.metrics.get('max_drawdown', 0) != 0:
            return_drawdown_ratio = abs(
                self.metrics.get('total_return', 0) / self.metrics['max_drawdown']
            )
            self.metrics['return_drawdown_ratio'] = return_drawdown_ratio
        else:
            self.metrics['return_drawdown_ratio'] = 0
        
        # 胜率（需要交易记录）
        if self.trades and len(self.trades) > 0:
            winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
            win_rate = len(winning_trades) / len(self.trades)
            self.metrics['win_rate'] = win_rate
        
        print(f"\n风险指标:")
        print(f"  夏普比率: {self.metrics.get('sharpe_ratio', 0):.3f}")
        print(f"  收益回撤比: {self.metrics.get('return_drawdown_ratio', 0):.3f}")
        if 'win_rate' in self.metrics:
            print(f"  胜率: {self.metrics['win_rate']*100:.2f}%")
    
    def _analyze_trades(self):
        """分析交易记录"""
        if not self.trades or len(self.trades) == 0:
            return
        
        # 总交易次数
        total_trades = len(self.trades)
        self.metrics['total_trades'] = total_trades
        
        # 盈利交易和亏损交易
        winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.trades if t.get('pnl', 0) <= 0]
        
        self.metrics['winning_trades'] = len(winning_trades)
        self.metrics['losing_trades'] = len(losing_trades)
        
        # 胜率
        if total_trades > 0:
            self.metrics['win_rate'] = len(winning_trades) / total_trades
        
        # 平均盈亏
        if len(winning_trades) > 0:
            avg_win = np.mean([t['pnl'] for t in winning_trades])
            self.metrics['avg_win'] = avg_win
        else:
            self.metrics['avg_win'] = 0
        
        if len(losing_trades) > 0:
            avg_loss = np.mean([t['pnl'] for t in losing_trades])
            self.metrics['avg_loss'] = avg_loss
        else:
            self.metrics['avg_loss'] = 0
        
        # 盈亏比
        if self.metrics['avg_loss'] != 0:
            profit_loss_ratio = abs(self.metrics['avg_win'] / self.metrics['avg_loss'])
            self.metrics['profit_loss_ratio'] = profit_loss_ratio
        else:
            self.metrics['profit_loss_ratio'] = 0
        
        print(f"\n交易统计:")
        print(f"  总交易次数: {total_trades}")
        print(f"  盈利次数: {len(winning_trades)}")
        print(f"  亏损次数: {len(losing_trades)}")
        print(f"  胜率: {self.metrics['win_rate']*100:.2f}%")
        print(f"  平均盈利: {self.metrics['avg_win']:.2f}")
        print(f"  平均亏损: {self.metrics['avg_loss']:.2f}")
        print(f"  盈亏比: {self.metrics['profit_loss_ratio']:.2f}")
    
    def generate_report(self, output_path=None):
        """
        生成详细的性能分析报告
        
        Parameters:
        -----------
        output_path : str, optional
            输出文件路径
            
        Returns:
        --------
        str : 报告内容
        """
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("HLM5 策略性能分析报告")
        report_lines.append("=" * 60)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 收益指标
        report_lines.append("【收益指标】")
        report_lines.append(f"  总收益率: {self.metrics.get('total_return', 0)*100:.2f}%")
        report_lines.append(f"  年化收益率: {self.metrics.get('annual_return', 0)*100:.2f}%")
        report_lines.append(f"  日均收益率: {self.metrics.get('avg_daily_return', 0)*100:.4f}%")
        report_lines.append("")
        
        # 风险指标
        report_lines.append("【风险指标】")
        report_lines.append(f"  最大回撤: {self.metrics.get('max_drawdown', 0)*100:.2f}%")
        report_lines.append(f"  平均回撤: {self.metrics.get('avg_drawdown', 0)*100:.2f}%")
        report_lines.append(f"  夏普比率: {self.metrics.get('sharpe_ratio', 0):.3f}")
        report_lines.append(f"  收益回撤比: {self.metrics.get('return_drawdown_ratio', 0):.3f}")
        report_lines.append("")
        
        # 交易统计
        if 'total_trades' in self.metrics:
            report_lines.append("【交易统计】")
            report_lines.append(f"  总交易次数: {self.metrics.get('total_trades', 0)}")
            report_lines.append(f"  盈利次数: {self.metrics.get('winning_trades', 0)}")
            report_lines.append(f"  亏损次数: {self.metrics.get('losing_trades', 0)}")
            report_lines.append(f"  胜率: {self.metrics.get('win_rate', 0)*100:.2f}%")
            report_lines.append(f"  平均盈利: {self.metrics.get('avg_win', 0):.2f}")
            report_lines.append(f"  平均亏损: {self.metrics.get('avg_loss', 0):.2f}")
            report_lines.append(f"  盈亏比: {self.metrics.get('profit_loss_ratio', 0):.2f}")
            report_lines.append("")
        
        report_lines.append("=" * 60)
        
        report_content = "\n".join(report_lines)
        
        # 输出到控制台
        print("\n" + report_content)
        
        # 保存到文件
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"\n报告已保存到: {output_path}")
        
        return report_content


# ====================================================================
# 主程序
# ====================================================================

def main():
    """主程序 - 示例"""
    print("=" * 60)
    print("性能分析工具示例")
    print("=" * 60)
    
    # 创建示例数据
    dates = pd.date_range('2025-01-01', periods=100, freq='D')
    np.random.seed(42)
    
    # 模拟账户余额曲线
    returns = np.random.randn(100) * 0.02 + 0.001
    balance = 100000 * (1 + returns).cumprod()
    
    result_df = pd.DataFrame({
        'balance': balance
    }, index=dates)
    
    # 模拟交易记录
    trades = []
    for i in range(20):
        pnl = np.random.randn() * 1000
        trades.append({'pnl': pnl})
    
    # 创建分析器
    analyzer = PerformanceAnalyzer(
        backtest_result_df=result_df,
        trades_list=trades
    )
    
    # 执行分析
    metrics = analyzer.analyze()
    
    # 生成报告
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    analyzer.generate_report(str(output_file))
    
    print("\n示例分析完成！")


if __name__ == "__main__":
    main()

