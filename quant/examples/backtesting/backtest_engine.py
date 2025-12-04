"""
回测引擎封装
简化回测流程，提供统一的回测接口
"""

from datetime import datetime
from typing import Type, Optional
import pandas as pd

from vnpy.trader.constant import Interval
from vnpy_ctastrategy.backtesting import BacktestingEngine


class QuantBacktestEngine:
    """
    量化回测引擎封装类
    
    提供简化的回测接口，隐藏底层细节
    """
    
    def __init__(self):
        """
        初始化回测引擎
        """
        self.engine = BacktestingEngine()
        self.result_df: Optional[pd.DataFrame] = None
        self.statistics: Optional[dict] = None
    
    def set_parameters(
        self,
        vt_symbol: str,
        interval: str = "1m",
        start: datetime = None,
        end: datetime = None,
        rate: float = 0.3/10000,
        slippage: float = 0.2,
        size: int = 1,
        pricetick: float = 0.2,
        capital: int = 1_000_000
    ):
        """
        设置回测参数
        
        参数:
            vt_symbol: 交易合约（格式：symbol.exchange，如IF888.CFFEX）
            interval: K线周期（"1m", "5m", "1h", "d"等）
            start: 开始日期
            end: 结束日期
            rate: 手续费率（默认0.3/10000，即万0.3）
            slippage: 滑点（默认0.2）
            size: 合约乘数（默认1）
            pricetick: 价格跳动（默认0.2）
            capital: 初始资金（默认100万）
        """
        if start is None:
            start = datetime(2019, 1, 1)
        if end is None:
            end = datetime.now()
        
        self.engine.set_parameters(
            vt_symbol=vt_symbol,
            interval=interval,
            start=start,
            end=end,
            rate=rate,
            slippage=slippage,
            size=size,
            pricetick=pricetick,
            capital=capital
        )
    
    def add_strategy(self, strategy_class: Type, setting: dict = None):
        """
        添加策略
        
        参数:
            strategy_class: 策略类
            setting: 策略参数字典
        """
        if setting is None:
            setting = {}
        
        self.engine.add_strategy(strategy_class, setting)
    
    def run_backtest(self) -> pd.DataFrame:
        """
        运行回测
        
        返回:
            回测结果DataFrame
        """
        # 加载数据
        self.engine.load_data()
        
        # 运行回测
        self.engine.run_backtesting()
        
        # 计算结果
        self.result_df = self.engine.calculate_result()
        
        # 计算统计指标（calculate_statistics会打印统计信息并返回字典）
        self.statistics = self.engine.calculate_statistics()
        
        return self.result_df
    
    def get_statistics(self) -> dict:
        """
        获取回测统计指标
        
        返回:
            统计指标字典
        """
        if self.statistics is None:
            if self.result_df is not None:
                # calculate_statistics会打印统计信息，但不返回字典
                # 需要从result_df中提取统计信息
                self.engine.calculate_statistics()
                # 从引擎中获取统计信息（如果可用）
                if hasattr(self.engine, 'statistics'):
                    self.statistics = self.engine.statistics
                else:
                    # 从result_df计算基本统计
                    self.statistics = self._calculate_from_df()
            else:
                return {}
        
        return self.statistics
    
    def _calculate_from_df(self) -> dict:
        """
        从result_df计算基本统计指标
        """
        if self.result_df is None or self.result_df.empty:
            return {}
        
        balance = self.result_df['balance'].values
        returns = self.result_df['return'].values
        
        start_balance = balance[0] if len(balance) > 0 else 0
        end_balance = balance[-1] if len(balance) > 0 else 0
        total_return = (end_balance - start_balance) / start_balance if start_balance > 0 else 0
        
        days = len(self.result_df)
        years = days / 252 if days > 0 else 1
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 计算最大回撤
        peak = pd.Series(balance).expanding().max()
        drawdown = (balance - peak) / peak
        max_dd = drawdown.min()
        
        # 计算夏普比率
        if len(returns) > 0 and returns.std() > 0:
            sharpe_ratio = pd.Series(returns).mean() / pd.Series(returns).std() * (252 ** 0.5)
        else:
            sharpe_ratio = 0
        
        return {
            "start_balance": start_balance,
            "end_balance": end_balance,
            "total_return": total_return,
            "annual_return": annual_return,
            "max_dd": max_dd,
            "sharpe_ratio": sharpe_ratio,
            "return_drawdown_ratio": annual_return / abs(max_dd) if max_dd != 0 else 0,
            "total_trade_count": 0,
            "win_rate": 0,
            "average_win": 0,
            "average_loss": 0,
            "profit_loss_ratio": 0
        }
    
    def show_chart(self):
        """
        显示回测图表
        """
        if self.result_df is not None:
            self.engine.show_chart()
        else:
            print("请先运行回测")
    
    def print_statistics(self):
        """
        打印回测统计指标
        """
        stats = self.get_statistics()
        
        if not stats:
            print("暂无统计数据（统计信息已在回测过程中打印）")
            return
        
        print("=" * 60)
        print("回测统计指标（从引擎获取）")
        print("=" * 60)
        print(f"起始资金: {stats.get('capital', 0):,.2f}")
        print(f"结束资金: {stats.get('end_balance', 0):,.2f}")
        print(f"总收益率: {stats.get('total_return', 0):.2%}")
        print(f"年化收益率: {stats.get('annual_return', 0):.2%}")
        print(f"最大回撤: {stats.get('max_ddpercent', 0):.2%}")
        print(f"夏普比率: {stats.get('sharpe_ratio', 0):.2f}")
        print(f"收益回撤比: {stats.get('return_drawdown_ratio', 0):.2f}")
        print(f"总成交次数: {stats.get('total_trade_count', 0)}")
        print(f"总盈亏: {stats.get('total_net_pnl', 0):,.2f}")
        print(f"总手续费: {stats.get('total_commission', 0):,.2f}")
        print(f"总滑点: {stats.get('total_slippage', 0):,.2f}")
        print("=" * 60)
    
    def save_result(self, filepath: str):
        """
        保存回测结果到CSV文件
        
        参数:
            filepath: 保存路径
        """
        if self.result_df is not None:
            self.result_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"回测结果已保存到: {filepath}")
        else:
            print("请先运行回测")

