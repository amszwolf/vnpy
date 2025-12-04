"""
加仓策略测试系统 (Position Scaling Strategy Test System)

基于 hlm5_all_parallel.py 的加仓策略框架，支持多种加仓方式的回测和对比。

支持的加仓策略：
1. Linear Scaling (线性加仓)
2. Pyramid Scaling (金字塔加仓)
3. Inverse Pyramid Scaling (倒金字塔加仓)
4. Fixed Fraction (固定分数加仓)

Python环境：aidata311
"""

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import copy

from trading_signal_database_manager import TradingSignalDatabaseManager
from futures_contract_specs import (
    FuturesContractSpecs, 
    CommissionModel, 
    SlippageModel, 
    TradingCostCalculator
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScalingConfig:
    """加仓策略配置类"""
    
    def __init__(self, 
                 scaling_method: str = "pyramid",
                 max_position: int = 10,
                 scaling_sequence: List[int] = None,
                 add_position_condition: str = "price_move",
                 add_position_threshold: float = 0.005,
                 use_trailing_stop: bool = True,
                 trailing_stop_pct: float = 0.02):
        """
        初始化加仓配置
        
        Parameters:
        -----------
        scaling_method : str
            加仓方式：'linear', 'pyramid', 'inverse_pyramid', 'fixed_fraction'
        max_position : int
            最大持仓手数
        scaling_sequence : List[int]
            加仓序列（用于金字塔等）
        add_position_condition : str
            加仓条件：'price_move', 'signal_confirm', 'profit_threshold'
        add_position_threshold : float
            加仓阈值（价格移动百分比或利润百分比）
        use_trailing_stop : bool
            是否使用移动止损
        trailing_stop_pct : float
            移动止损百分比
        """
        self.scaling_method = scaling_method
        self.max_position = max_position
        self.add_position_condition = add_position_condition
        self.add_position_threshold = add_position_threshold
        self.use_trailing_stop = use_trailing_stop
        self.trailing_stop_pct = trailing_stop_pct
        
        # 设置默认加仓序列
        if scaling_sequence is None:
            if scaling_method == "pyramid":
                self.scaling_sequence = [4, 3, 2, 1]  # 总计10手
            elif scaling_method == "inverse_pyramid":
                self.scaling_sequence = [1, 2, 3, 4]  # 总计10手
            elif scaling_method == "linear":
                self.scaling_sequence = [1] * 10  # 每次1手
            elif scaling_method == "fixed_fraction":
                self.scaling_sequence = [2, 2, 2, 2, 2]  # 每次2手
        else:
            self.scaling_sequence = scaling_sequence
    
    def __str__(self):
        return f"ScalingConfig(method={self.scaling_method}, max_pos={self.max_position}, seq={self.scaling_sequence})"


class PositionTracker:
    """持仓状态跟踪器"""
    
    def __init__(self, ticker: str = 'RB.SHF'):
        """
        初始化持仓跟踪器
        
        Parameters:
        -----------
        ticker : str
            期货代码，用于获取合约规格
        """
        self.ticker = ticker
        self.specs = FuturesContractSpecs.get_specs(ticker)
        self.contract_multiplier = self.specs['multiplier']
        self.reset()
    
    def reset(self):
        """重置所有状态"""
        self.current_position = 0  # 当前持仓数量（正=多，负=空）
        self.current_scaling_level = 0  # 当前加仓层级
        self.entry_prices = []  # 各次开仓价格列表
        self.entry_sizes = []  # 各次开仓手数列表
        self.total_invested = 0.0  # 总投入资金
        self.highest_price = 0.0  # 持仓期间最高价（用于移动止损）
        self.lowest_price = float('inf')  # 持仓期间最低价
        self.initial_entry_time = None  # 首次开仓时间
    
    def add_position(self, price: float, size: int, timestamp: datetime):
        """添加仓位"""
        self.entry_prices.append(price)
        self.entry_sizes.append(size)
        self.current_position += size
        self.current_scaling_level += 1
        self.total_invested += price * size
        
        if self.initial_entry_time is None:
            self.initial_entry_time = timestamp
        
        # 更新价格极值
        if size > 0:  # 多仓
            self.highest_price = max(self.highest_price, price)
            self.lowest_price = min(self.lowest_price, price)
        else:  # 空仓
            self.highest_price = min(self.highest_price, price) if self.highest_price != 0 else price
            self.lowest_price = max(self.lowest_price, price) if self.lowest_price != float('inf') else price
    
    def update_extremes(self, price: float):
        """更新价格极值（用于移动止损）"""
        if self.current_position > 0:  # 多仓
            self.highest_price = max(self.highest_price, price)
        elif self.current_position < 0:  # 空仓
            self.lowest_price = max(self.lowest_price, price)
    
    def get_average_price(self) -> float:
        """获取平均开仓价格"""
        if not self.entry_prices:
            return 0.0
        
        # 使用绝对值计算，确保做空时价格也是正数
        total_value = sum(p * abs(s) for p, s in zip(self.entry_prices, self.entry_sizes))
        total_size = sum(abs(s) for s in self.entry_sizes)
        return total_value / total_size if total_size > 0 else 0.0
    
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """
        计算未实现盈亏（元）
        
        Parameters:
        -----------
        current_price : float
            当前价格
        
        Returns:
        --------
        float : 未实现盈亏金额（元）
        """
        if self.current_position == 0:
            return 0.0
        
        avg_price = self.get_average_price()
        position_size = abs(self.current_position)
        
        if self.current_position > 0:  # 多仓
            # 做多盈亏 = (当前价 - 平均入场价) × 手数 × 合约乘数
            pnl = (current_price - avg_price) * position_size * self.contract_multiplier
        else:  # 空仓
            # 做空盈亏 = (平均入场价 - 当前价) × 手数 × 合约乘数
            pnl = (avg_price - current_price) * position_size * self.contract_multiplier
        
        return pnl


class ScalingStrategyEngine:
    """加仓策略引擎"""
    
    def __init__(self, config: ScalingConfig, ticker: str = 'RB.SHF'):
        """
        初始化加仓策略引擎
        
        Parameters:
        -----------
        config : ScalingConfig
            加仓策略配置
        ticker : str
            期货代码，用于获取合约规格和计算交易成本
        """
        self.config = config
        self.ticker = ticker
        self.tracker = PositionTracker(ticker)
        self.cost_calculator = TradingCostCalculator(
            ticker, 
            enable_commission=True, 
            enable_slippage=True
        )
        self.logger = logging.getLogger(__name__)
    
    def calculate_scaling_size(self, direction: int) -> int:
        """
        计算本次加仓手数
        
        Parameters:
        -----------
        direction : int
            方向（1=多，-1=空）
        
        Returns:
        --------
        int : 本次加仓手数（带方向）
        """
        level = self.tracker.current_scaling_level
        
        # 检查是否超过最大持仓
        if abs(self.tracker.current_position) >= self.config.max_position:
            return 0
        
        # 检查加仓序列是否用完
        if level >= len(self.config.scaling_sequence):
            return 0
        
        # 获取本次加仓手数
        size = self.config.scaling_sequence[level]
        
        # 确保不超过最大持仓
        remaining = self.config.max_position - abs(self.tracker.current_position)
        size = min(size, remaining)
        
        return size * direction
    
    def check_add_position_condition(self, current_price: float, 
                                     new_signal: bool = False) -> bool:
        """
        检查是否满足加仓条件
        
        Parameters:
        -----------
        current_price : float
            当前价格
        new_signal : bool
            是否有新的同向信号
        
        Returns:
        --------
        bool : 是否应该加仓
        """
        if self.tracker.current_position == 0:
            return False
        
        if abs(self.tracker.current_position) >= self.config.max_position:
            return False
        
        condition = self.config.add_position_condition
        
        # 1. 基于价格移动的加仓
        if condition == "price_move":
            if not self.tracker.entry_prices:
                return False
            
            last_entry = self.tracker.entry_prices[-1]
            price_move = abs(current_price - last_entry) / last_entry
            
            # 价格朝有利方向移动
            if self.tracker.current_position > 0:  # 多仓
                favorable_move = current_price > last_entry
            else:  # 空仓
                favorable_move = current_price < last_entry
            
            return price_move >= self.config.add_position_threshold and favorable_move
        
        # 2. 基于信号确认的加仓
        elif condition == "signal_confirm":
            return new_signal
        
        # 3. 基于利润阈值的加仓
        elif condition == "profit_threshold":
            unrealized_pnl = self.tracker.calculate_unrealized_pnl(current_price)
            return unrealized_pnl >= self.config.add_position_threshold * 100
        
        return False
    
    def check_trailing_stop(self, current_price: float) -> bool:
        """
        检查移动止损条件
        
        Returns:
        --------
        bool : 是否触发移动止损
        """
        if not self.config.use_trailing_stop:
            return False
        
        if self.tracker.current_position == 0:
            return False
        
        if self.tracker.current_position > 0:  # 多仓
            if self.tracker.highest_price == 0:
                return False
            drawdown = (self.tracker.highest_price - current_price) / self.tracker.highest_price
            return drawdown >= self.config.trailing_stop_pct
        
        else:  # 空仓
            if self.tracker.lowest_price == float('inf'):
                return False
            drawdown = (current_price - self.tracker.lowest_price) / self.tracker.lowest_price
            return drawdown >= self.config.trailing_stop_pct
    
    def on_signal(self, signal_type: int, current_price: float, 
                  timestamp: datetime) -> Dict:
        """
        处理交易信号
        
        Parameters:
        -----------
        signal_type : int
            信号类型（>0=做多，<0=做空，0=无信号）
        current_price : float
            当前价格
        timestamp : datetime
            时间戳
        
        Returns:
        --------
        Dict : 交易动作 {'action': 'entry'/'add'/'exit', 'size': int, 'price': float}
        """
        result = {'action': None, 'size': 0, 'price': current_price}
        
        # 更新价格极值
        if self.tracker.current_position != 0:
            self.tracker.update_extremes(current_price)
        
        # 检查移动止损
        if self.check_trailing_stop(current_price):
            result['action'] = 'exit_trailing_stop'
            result['size'] = -self.tracker.current_position
            self.tracker.reset()
            return result
        
        # 情况1：无持仓，新信号入场
        if self.tracker.current_position == 0 and signal_type != 0:
            direction = 1 if signal_type > 0 else -1
            size = self.calculate_scaling_size(direction)
            
            if size != 0:
                self.tracker.add_position(current_price, size, timestamp)
                result['action'] = 'entry'
                result['size'] = size
                result['signal_type'] = signal_type
        
        # 情况2：已有持仓，同向信号，检查加仓
        elif self.tracker.current_position != 0 and \
             np.sign(signal_type) == np.sign(self.tracker.current_position):
            
            if self.check_add_position_condition(current_price, new_signal=(signal_type != 0)):
                direction = np.sign(self.tracker.current_position)
                size = self.calculate_scaling_size(direction)
                
                if size != 0:
                    self.tracker.add_position(current_price, size, timestamp)
                    result['action'] = 'add'
                    result['size'] = size
                    result['scaling_level'] = self.tracker.current_scaling_level
        
        # 情况3：反向信号，平仓
        elif self.tracker.current_position != 0 and \
             signal_type != 0 and \
             np.sign(signal_type) != np.sign(self.tracker.current_position):
            
            result['action'] = 'exit'
            result['size'] = -self.tracker.current_position
            
            # 计算盈亏（已实现盈亏）
            avg_price = self.tracker.get_average_price()
            position_size = abs(self.tracker.current_position)
            contract_multiplier = self.tracker.contract_multiplier
            
            # 计算毛盈亏
            if self.tracker.current_position > 0:  # 平多仓
                gross_pnl = (current_price - avg_price) * position_size * contract_multiplier
            else:  # 平空仓
                gross_pnl = (avg_price - current_price) * position_size * contract_multiplier
            
            # 计算交易成本
            cost_info = self.cost_calculator.calculate_round_trip_cost(
                avg_price, current_price, position_size
            )
            total_cost = cost_info['total_cost']
            
            # 净盈亏 = 毛盈亏 - 交易成本
            net_pnl = gross_pnl - total_cost
            
            result['pnl'] = net_pnl
            result['gross_pnl'] = gross_pnl
            result['trading_cost'] = total_cost
            result['avg_entry_price'] = avg_price
            result['scaling_levels'] = self.tracker.current_scaling_level
            
            self.tracker.reset()
        
        return result


def generate_scaling_signals(db: TradingSignalDatabaseManager,
                            ticker: str,
                            start_date: str,
                            end_date: str,
                            scaling_config: ScalingConfig,
                            enable_bidirectional_trading: bool = True) -> pd.DataFrame:
    """
    生成加仓策略的交易信号
    
    Parameters:
    -----------
    db : TradingSignalDatabaseManager
        数据库管理器
    ticker : str
        期货代码
    start_date : str
        开始日期
    end_date : str
        结束日期
    scaling_config : ScalingConfig
        加仓策略配置
    enable_bidirectional_trading : bool
        是否启用双向交易
    
    Returns:
    --------
    pd.DataFrame : 包含交易信号和仓位信息的DataFrame
    """
    logger.info(f"Generating scaling signals for {ticker} using {scaling_config.scaling_method}")
    
    # 从数据库读取基础信号
    query = """
    SELECT datetime, close, 
           Entry_Signal, Exit_Signal, Position,
           Entry_Price, Exit_Price, Profit_Loss
    FROM trading_data 
    WHERE ticker = ? AND datetime >= date(?) AND datetime < date(?, '+1 day')
    ORDER BY datetime
    """
    params = [ticker, start_date, end_date]
    df = pd.read_sql(query, db.conn, params=params)
    
    if df.empty:
        logger.warning(f"No data found for {ticker}")
        return pd.DataFrame()
    
    # 初始化加仓策略引擎
    engine = ScalingStrategyEngine(scaling_config, ticker)
    
    # 初始化结果列
    df['Scaling_Position'] = 0  # 加仓后的实际持仓
    df['Scaling_Action'] = ''  # 交易动作
    df['Scaling_Action_Code'] = 0  # 交易动作代码（用于保存到数据库）
    df['Scaling_Size'] = 0  # 本次交易手数
    df['Scaling_Level'] = 0  # 当前加仓层级
    df['Scaling_Direction'] = 0  # 持仓方向（1=多，-1=空，0=无）
    df['Avg_Entry_Price'] = 0.0  # 平均开仓价
    df['Unrealized_PnL'] = 0.0  # 未实现盈亏
    df['Realized_PnL'] = 0.0  # 已实现盈亏
    
    # 遍历每个时间点
    for i in range(len(df)):
        row = df.iloc[i]
        current_price = row['close']
        timestamp = pd.to_datetime(row['datetime'])
        
        # 获取基础信号（来自原始策略）
        base_signal = 0
        if row['Entry_Signal'] != 0:
            base_signal = row['Entry_Signal']
        elif row['Exit_Signal']:
            # 判断是平多还是平空
            if i > 0 and df.iloc[i-1]['Scaling_Position'] > 0:
                base_signal = -1  # 平多信号
            elif i > 0 and df.iloc[i-1]['Scaling_Position'] < 0:
                base_signal = 1  # 平空信号
        
        # 处理信号
        action_result = engine.on_signal(base_signal, current_price, timestamp)
        
        # 记录结果
        action_str = action_result.get('action', '')
        df.loc[i, 'Scaling_Action'] = action_str
        df.loc[i, 'Scaling_Size'] = action_result.get('size', 0)
        df.loc[i, 'Scaling_Position'] = engine.tracker.current_position
        df.loc[i, 'Scaling_Level'] = engine.tracker.current_scaling_level
        
        # 记录持仓方向（1=多，-1=空，0=无）
        if engine.tracker.current_position > 0:
            df.loc[i, 'Scaling_Direction'] = 1  # 做多
        elif engine.tracker.current_position < 0:
            df.loc[i, 'Scaling_Direction'] = -1  # 做空
        else:
            df.loc[i, 'Scaling_Direction'] = 0  # 无持仓
        
        # 生成动作代码（用于保存到数据库）
        # 0=无动作, 1=首次开仓, 2-10=加仓层级, -1=平仓
        action_code = 0
        if action_str == 'entry':
            action_code = 1
        elif action_str == 'add':
            action_code = engine.tracker.current_scaling_level
        elif action_str in ['exit', 'exit_trailing_stop']:
            action_code = -1
        df.loc[i, 'Scaling_Action_Code'] = action_code
        
        if engine.tracker.current_position != 0:
            df.loc[i, 'Avg_Entry_Price'] = engine.tracker.get_average_price()
            df.loc[i, 'Unrealized_PnL'] = engine.tracker.calculate_unrealized_pnl(current_price)
        
        if action_result.get('action') in ['exit', 'exit_trailing_stop']:
            df.loc[i, 'Realized_PnL'] = action_result.get('pnl', 0.0)
    
    logger.info(f"Generated {len(df)} signals with {(df['Realized_PnL'] != 0).sum()} completed trades")
    
    return df


def calculate_scaling_performance(signals_df: pd.DataFrame, 
                                 initial_capital: float = 10000) -> Dict:
    """
    计算加仓策略的性能指标
    
    Parameters:
    -----------
    signals_df : pd.DataFrame
        包含交易信号的DataFrame
    initial_capital : float
        初始资金
    
    Returns:
    --------
    Dict : 性能指标字典
    """
    if signals_df.empty:
        return {}
    
    # 提取已实现盈亏
    realized_pnl = signals_df['Realized_PnL']
    trades = realized_pnl[realized_pnl != 0]
    
    if len(trades) == 0:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_return': 0,
            'annual_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'profit_factor': 0,
            'avg_trade': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'avg_scaling_levels': 0
        }
    
    # 基础统计
    total_trades = len(trades)
    winning_trades = len(trades[trades > 0])
    losing_trades = len(trades[trades < 0])
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    # 收益统计
    total_return = trades.sum()
    final_capital = initial_capital + total_return
    
    # 计算年化收益（假设252个交易日）
    trading_days = len(signals_df)
    annual_return = total_return * (252 / trading_days) if trading_days > 0 else 0
    
    # 夏普比率
    if trades.std() != 0:
        sharpe_ratio = np.sqrt(252) * trades.mean() / trades.std()
    else:
        sharpe_ratio = 0
    
    # 最大回撤（基于权益曲线）
    cumulative_pnl = trades.cumsum()
    equity_curve = initial_capital + cumulative_pnl
    peak = equity_curve.expanding().max()
    
    # 回撤 = (峰值 - 当前权益) / 峰值
    drawdown_pct = (peak - equity_curve) / peak
    max_drawdown_pct = drawdown_pct.max()  # 最大回撤百分比
    
    # 最大回撤金额
    max_drawdown = (peak - equity_curve).max()
    
    # 盈亏比
    gross_profit = trades[trades > 0].sum() if winning_trades > 0 else 0
    gross_loss = abs(trades[trades < 0].sum()) if losing_trades > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # 平均交易
    avg_trade = trades.mean()
    avg_win = trades[trades > 0].mean() if winning_trades > 0 else 0
    avg_loss = trades[trades < 0].mean() if losing_trades > 0 else 0
    
    # 加仓层级统计
    exit_rows = signals_df[signals_df['Scaling_Action'].str.contains('exit', na=False)]
    avg_scaling_levels = exit_rows['Scaling_Level'].mean() if len(exit_rows) > 0 else 0
    
    return {
        'initial_capital': initial_capital,
        'final_capital': final_capital,
        'total_return': total_return,
        'total_return_pct': (total_return / initial_capital) * 100,
        'annual_return': annual_return,
        'annual_return_pct': (annual_return / initial_capital) * 100,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': max_drawdown_pct * 100,  # 转换为百分比
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_trade': avg_trade,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'avg_scaling_levels': avg_scaling_levels,
        'trading_days': trading_days
    }


# 预定义的加仓策略配置
SCALING_CONFIGS = {
    'pyramid': ScalingConfig(
        scaling_method='pyramid',
        max_position=10,
        scaling_sequence=[4, 3, 2, 1],
        add_position_condition='price_move',
        add_position_threshold=0.005,  # 0.5%价格移动
        use_trailing_stop=True,
        trailing_stop_pct=0.02  # 2%移动止损
    ),
    
    'inverse_pyramid': ScalingConfig(
        scaling_method='inverse_pyramid',
        max_position=10,
        scaling_sequence=[1, 2, 3, 4],
        add_position_condition='price_move',
        add_position_threshold=0.005,
        use_trailing_stop=True,
        trailing_stop_pct=0.02
    ),
    
    'linear': ScalingConfig(
        scaling_method='linear',
        max_position=10,
        scaling_sequence=[1] * 10,
        add_position_condition='price_move',
        add_position_threshold=0.003,  # 0.3%价格移动（更频繁）
        use_trailing_stop=True,
        trailing_stop_pct=0.02
    ),
    
    'fixed_fraction': ScalingConfig(
        scaling_method='fixed_fraction',
        max_position=10,
        scaling_sequence=[2, 2, 2, 2, 2],
        add_position_condition='price_move',
        add_position_threshold=0.005,
        use_trailing_stop=True,
        trailing_stop_pct=0.02
    ),
    
    'aggressive_pyramid': ScalingConfig(
        scaling_method='pyramid',
        max_position=10,
        scaling_sequence=[5, 3, 2],
        add_position_condition='profit_threshold',
        add_position_threshold=0.01,  # 1%盈利后加仓
        use_trailing_stop=True,
        trailing_stop_pct=0.015  # 1.5%移动止损
    ),
}


if __name__ == "__main__":
    # 测试代码
    print("Scaling Strategy Module Loaded Successfully")
    print("\nAvailable Scaling Strategies:")
    for name, config in SCALING_CONFIGS.items():
        print(f"  - {name}: {config}")

