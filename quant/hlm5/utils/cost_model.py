# -*- coding: utf-8 -*-
"""
期货交易成本模型
从 hlm5_all_parallel.py 移植

包含：
- FuturesContractSpecs: 期货合约规格
- TradingCostCalculator: 交易成本计算器（滑点+手续费）
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from futures_config import FUTURES_SPECS, get_contract_specs

class FuturesContractSpecs:
    """
    期货合约规格管理
    
    从 futures_config.py 读取合约规格
    """
    
    @staticmethod
    def get_specs(symbol):
        """
        获取期货合约规格
        
        Parameters:
        -----------
        symbol : str
            期货代码（如 'OI.ZCE', 'OI888.CZCE', 'OI'）
            
        Returns:
        --------
        dict : 合约规格字典
        """
        # 提取品种代码
        commodity = ''.join([c for c in symbol.split('.')[0] if c.isalpha()])
        return get_contract_specs(commodity)
    
    @staticmethod
    def get_multiplier(symbol):
        """获取合约乘数"""
        specs = FuturesContractSpecs.get_specs(symbol)
        return specs['multiplier']
    
    @staticmethod
    def get_pricetick(symbol):
        """获取最小变动价位"""
        specs = FuturesContractSpecs.get_specs(symbol)
        return specs['pricetick']
    
    @staticmethod
    def get_margin_rate(symbol):
        """获取保证金比例"""
        specs = FuturesContractSpecs.get_specs(symbol)
        return specs['margin_rate']


class SlippageModel:
    """
    滑点模型
    
    ⚠️ 从 hlm5_all_parallel.py 移植
    """
    
    def __init__(self, symbol):
        """
        初始化滑点模型
        
        Parameters:
        -----------
        symbol : str
            期货代码
        """
        self.symbol = symbol
        self.specs = FuturesContractSpecs.get_specs(symbol)
        self.pricetick = self.specs['pricetick']
        self.fixed_slippage = self.specs['slippage']['fixed_slippage']
        self.ratio_slippage = self.specs['slippage']['ratio_slippage']
    
    def apply_slippage(self, price, direction):
        """
        应用滑点到价格
        
        Parameters:
        -----------
        price : float
            原始价格
        direction : int
            方向（1=买入，-1=卖出）
            
        Returns:
        --------
        float : 含滑点的价格
        """
        # 固定滑点（按跳数计算）
        fixed_slip = self.fixed_slippage * self.pricetick * direction
        
        # 比例滑点（按价格百分比）
        ratio_slip = price * self.ratio_slippage * direction
        
        # 总滑点
        total_slip = fixed_slip + ratio_slip
        
        return price + total_slip


class CommissionModel:
    """
    手续费模型
    
    ⚠️ 从 hlm5_all_parallel.py 移植
    """
    
    def __init__(self, symbol):
        """
        初始化手续费模型
        
        Parameters:
        -----------
        symbol : str
            期货代码
        """
        self.symbol = symbol
        self.specs = FuturesContractSpecs.get_specs(symbol)
        self.multiplier = self.specs['multiplier']
        self.commission_rates = self.specs['commission']
    
    def calculate_commission(self, price, volume, action='open'):
        """
        计算手续费
        
        Parameters:
        -----------
        price : float
            成交价格
        volume : int
            成交手数
        action : str
            操作类型 ('open'=开仓, 'close'=平仓, 'close_today'=平今)
            
        Returns:
        --------
        float : 手续费金额（元）
        """
        # 获取对应的手续费率
        if action == 'open':
            rate = self.commission_rates['open_ratio']
        elif action == 'close_today':
            rate = self.commission_rates['close_today_ratio']
        else:  # close
            rate = self.commission_rates['close_ratio']
        
        # 计算手续费 = 价格 * 合约乘数 * 手数 * 费率
        commission = price * self.multiplier * volume * rate
        
        return commission


class TradingCostCalculator:
    """
    交易成本计算器
    
    整合滑点模型和手续费模型
    ⚠️ 从 hlm5_all_parallel.py 移植
    """
    
    def __init__(self, symbol):
        """
        初始化交易成本计算器
        
        Parameters:
        -----------
        symbol : str
            期货代码（如 'OI', 'OI888.CZCE'）
        """
        self.symbol = symbol
        self.specs = FuturesContractSpecs.get_specs(symbol)
        
        # 初始化滑点模型和手续费模型
        self.slippage_model = SlippageModel(symbol)
        self.commission_model = CommissionModel(symbol)
        
        # 缓存常用值
        self.multiplier = self.specs['multiplier']
        self.pricetick = self.specs['pricetick']
    
    def calculate_buy_cost(self, price, volume, action='open'):
        """
        计算买入成本
        
        Parameters:
        -----------
        price : float
            原始价格
        volume : int
            手数
        action : str
            操作类型
            
        Returns:
        --------
        tuple : (含滑点的价格, 手续费)
        """
        # 买入方向滑点
        price_with_slippage = self.slippage_model.apply_slippage(price, direction=1)
        
        # 计算手续费
        commission = self.commission_model.calculate_commission(
            price_with_slippage, volume, action
        )
        
        return price_with_slippage, commission
    
    def calculate_sell_cost(self, price, volume, action='close'):
        """
        计算卖出成本
        
        Parameters:
        -----------
        price : float
            原始价格
        volume : int
            手数
        action : str
            操作类型
            
        Returns:
        --------
        tuple : (含滑点的价格, 手续费)
        """
        # 卖出方向滑点
        price_with_slippage = self.slippage_model.apply_slippage(price, direction=-1)
        
        # 计算手续费
        commission = self.commission_model.calculate_commission(
            price_with_slippage, volume, action
        )
        
        return price_with_slippage, commission
    
    def calculate_round_trip_cost(self, entry_price, exit_price, volume):
        """
        计算往返交易成本（开仓+平仓）
        
        Parameters:
        -----------
        entry_price : float
            开仓价格
        exit_price : float
            平仓价格
        volume : int
            手数
            
        Returns:
        --------
        dict : 成本明细
        """
        # 开仓成本
        entry_price_slip, entry_commission = self.calculate_buy_cost(
            entry_price, volume, 'open'
        )
        
        # 平仓成本
        exit_price_slip, exit_commission = self.calculate_sell_cost(
            exit_price, volume, 'close'
        )
        
        # 总滑点成本
        total_slippage = (
            (entry_price_slip - entry_price) + 
            (exit_price - exit_price_slip)
        ) * self.multiplier * volume
        
        # 总手续费
        total_commission = entry_commission + exit_commission
        
        # 总成本
        total_cost = abs(total_slippage) + total_commission
        
        return {
            'entry_price_with_slippage': entry_price_slip,
            'exit_price_with_slippage': exit_price_slip,
            'entry_commission': entry_commission,
            'exit_commission': exit_commission,
            'total_slippage': total_slippage,
            'total_commission': total_commission,
            'total_cost': total_cost
        }
    
    def calculate_pnl(self, entry_price, exit_price, volume, direction='long'):
        """
        计算盈亏（含成本）
        
        Parameters:
        -----------
        entry_price : float
            开仓价格
        exit_price : float
            平仓价格
        volume : int
            手数
        direction : str
            方向 ('long'=做多, 'short'=做空)
            
        Returns:
        --------
        dict : 盈亏明细
        """
        if direction == 'long':
            # 做多：买入开仓，卖出平仓
            entry_price_slip, entry_commission = self.calculate_buy_cost(
                entry_price, volume, 'open'
            )
            exit_price_slip, exit_commission = self.calculate_sell_cost(
                exit_price, volume, 'close'
            )
            
            # 毛盈亏
            gross_pnl = (exit_price_slip - entry_price_slip) * self.multiplier * volume
            
        else:  # short
            # 做空：卖出开仓，买入平仓
            entry_price_slip, entry_commission = self.calculate_sell_cost(
                entry_price, volume, 'open'
            )
            exit_price_slip, exit_commission = self.calculate_buy_cost(
                exit_price, volume, 'close'
            )
            
            # 毛盈亏
            gross_pnl = (entry_price_slip - exit_price_slip) * self.multiplier * volume
        
        # 净盈亏（扣除手续费）
        net_pnl = gross_pnl - (entry_commission + exit_commission)
        
        return {
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'total_commission': entry_commission + exit_commission,
            'return_rate': net_pnl / (entry_price * self.multiplier * volume) * 100
        }


# ====================================================================
# 测试代码
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("交易成本模型测试")
    print("=" * 60)
    
    # 测试OI期货
    symbol = 'OI'
    calculator = TradingCostCalculator(symbol)
    
    print(f"\n测试合约: {symbol}")
    print("-" * 60)
    
    # 获取合约规格
    specs = calculator.specs
    print("\n合约规格:")
    print(f"  合约乘数: {specs['multiplier']} 吨/手")
    print(f"  最小变动: {specs['pricetick']} 元/吨")
    print(f"  保证金率: {specs['margin_rate']*100}%")
    print(f"  开仓手续费率: {specs['commission']['open_ratio']*10000:.2f} 万分之一")
    
    # 测试交易成本计算
    entry_price = 10000.0  # 开仓价
    exit_price = 10100.0   # 平仓价
    volume = 1             # 1手
    
    print(f"\n交易示例:")
    print(f"  开仓价: {entry_price:.2f} 元/吨")
    print(f"  平仓价: {exit_price:.2f} 元/吨")
    print(f"  手数: {volume} 手")
    
    # 计算做多盈亏
    pnl_long = calculator.calculate_pnl(entry_price, exit_price, volume, 'long')
    print(f"\n做多盈亏:")
    print(f"  毛盈亏: {pnl_long['gross_pnl']:.2f} 元")
    print(f"  手续费: {pnl_long['total_commission']:.2f} 元")
    print(f"  净盈亏: {pnl_long['net_pnl']:.2f} 元")
    print(f"  收益率: {pnl_long['return_rate']:.2f}%")
    
    # 计算往返成本
    cost = calculator.calculate_round_trip_cost(entry_price, exit_price, volume)
    print(f"\n往返成本:")
    print(f"  总滑点: {cost['total_slippage']:.2f} 元")
    print(f"  总手续费: {cost['total_commission']:.2f} 元")
    print(f"  总成本: {cost['total_cost']:.2f} 元")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

