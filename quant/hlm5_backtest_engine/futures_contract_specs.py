"""
期货合约规格配置

包含各个期货合约的标准参数：
- 合约乘数
- 手续费标准
- 保证金率
- 滑点设置
"""

import logging

logger = logging.getLogger(__name__)


class FuturesContractSpecs:
    """期货合约规格管理"""
    
    # 合约规格字典
    SPECS = {
        'RB.SHF': {
            'name': '螺纹钢',
            'exchange': '上海期货交易所',
            'multiplier': 10,  # 10吨/手
            'tick_size': 1,    # 最小变动价位：1元/吨
            'commission_type': 'rate',  # rate=按比例, fixed=按手数
            'commission_rate': 0.00005,  # 万分之0.5
            'commission_open': 0.00005,
            'commission_close': 0.00005,
            'commission_per_lot': 0,
            'margin_rate': 0.09,  # 保证金率：9%
            'slippage_ticks': 1,  # 滑点：1个最小变动价位
            'price_unit': '元/吨'
        },
        'OI.ZCE': {
            'name': '菜籽油',
            'exchange': '郑州商品交易所',
            'multiplier': 10,  # 10吨/手
            'tick_size': 2,    # 最小变动价位：2元/吨
            'commission_type': 'fixed',  # 按手数收费
            'commission_rate': 0,
            'commission_open': 2.5,  # 2.5元/手
            'commission_close': 2.5,
            'commission_per_lot': 2.5,
            'margin_rate': 0.08,
            'slippage_ticks': 1,
            'price_unit': '元/吨'
        },
        'CU.SHF': {
            'name': '沪铜',
            'exchange': '上海期货交易所',
            'multiplier': 5,   # 5吨/手
            'tick_size': 10,   # 10元/吨
            'commission_type': 'rate',
            'commission_rate': 0.00005,
            'commission_open': 0.00005,
            'commission_close': 0.00005,
            'commission_per_lot': 0,
            'margin_rate': 0.08,
            'slippage_ticks': 1,
            'price_unit': '元/吨'
        },
        'IF.CFE': {
            'name': '沪深300股指',
            'exchange': '中国金融期货交易所',
            'multiplier': 300,  # 300元/点
            'tick_size': 0.2,   # 0.2点
            'commission_type': 'rate',
            'commission_rate': 0.000023,  # 万分之0.23
            'commission_open': 0.000023,
            'commission_close': 0.000023,
            'commission_per_lot': 0,
            'margin_rate': 0.10,
            'slippage_ticks': 1,
            'price_unit': '点'
        },
        'IC.CFE': {
            'name': '中证500股指',
            'exchange': '中国金融期货交易所',
            'multiplier': 200,
            'tick_size': 0.2,
            'commission_type': 'rate',
            'commission_rate': 0.000023,
            'commission_open': 0.000023,
            'commission_close': 0.000023,
            'commission_per_lot': 0,
            'margin_rate': 0.10,
            'slippage_ticks': 1,
            'price_unit': '点'
        }
    }
    
    @classmethod
    def get_specs(cls, ticker: str) -> dict:
        """
        获取合约规格
        
        Parameters:
        -----------
        ticker : str
            期货代码，如 'RB.SHF'
        
        Returns:
        --------
        dict : 合约规格字典
        """
        if ticker in cls.SPECS:
            return cls.SPECS[ticker].copy()
        else:
            logger.warning(f"合约 {ticker} 规格未定义，使用螺纹钢默认参数")
            return cls.SPECS['RB.SHF'].copy()
    
    @classmethod
    def get_multiplier(cls, ticker: str) -> float:
        """获取合约乘数"""
        specs = cls.get_specs(ticker)
        return specs['multiplier']
    
    @classmethod
    def get_tick_size(cls, ticker: str) -> float:
        """获取最小变动价位"""
        specs = cls.get_specs(ticker)
        return specs['tick_size']
    
    @classmethod
    def get_margin_rate(cls, ticker: str) -> float:
        """获取保证金率"""
        specs = cls.get_specs(ticker)
        return specs['margin_rate']


class CommissionModel:
    """手续费计算模型"""
    
    def __init__(self, ticker: str):
        """
        初始化手续费模型
        
        Parameters:
        -----------
        ticker : str
            期货代码
        """
        self.ticker = ticker
        self.specs = FuturesContractSpecs.get_specs(ticker)
        self.logger = logging.getLogger(__name__)
    
    def calculate_commission(self, price: float, volume: int, action: str = 'both') -> float:
        """
        计算手续费
        
        Parameters:
        -----------
        price : float
            成交价格
        volume : int
            成交手数（绝对值）
        action : str
            'open' = 仅开仓手续费
            'close' = 仅平仓手续费
            'both' = 开仓+平仓手续费
        
        Returns:
        --------
        float : 手续费金额（元）
        """
        volume = abs(volume)
        
        if self.specs['commission_type'] == 'rate':
            # 按比例收费
            contract_value = price * volume * self.specs['multiplier']
            
            if action == 'open':
                commission = contract_value * self.specs['commission_open']
            elif action == 'close':
                commission = contract_value * self.specs['commission_close']
            else:  # both
                commission = contract_value * (self.specs['commission_open'] + 
                                              self.specs['commission_close'])
        else:
            # 按手数固定收费
            if action == 'open':
                commission = self.specs['commission_open'] * volume
            elif action == 'close':
                commission = self.specs['commission_close'] * volume
            else:  # both
                commission = (self.specs['commission_open'] + 
                            self.specs['commission_close']) * volume
        
        return commission
    
    def get_commission_info(self, price: float, volume: int) -> dict:
        """
        获取详细手续费信息
        
        Returns:
        --------
        dict : 包含各项手续费的字典
        """
        return {
            'open_commission': self.calculate_commission(price, volume, 'open'),
            'close_commission': self.calculate_commission(price, volume, 'close'),
            'total_commission': self.calculate_commission(price, volume, 'both'),
            'commission_type': self.specs['commission_type'],
            'volume': volume
        }


class SlippageModel:
    """滑点模型"""
    
    def __init__(self, ticker: str, slippage_ticks: int = None):
        """
        初始化滑点模型
        
        Parameters:
        -----------
        ticker : str
            期货代码
        slippage_ticks : int, optional
            滑点跳数，None则使用默认值
        """
        self.ticker = ticker
        self.specs = FuturesContractSpecs.get_specs(ticker)
        
        if slippage_ticks is not None:
            self.slippage_ticks = slippage_ticks
        else:
            self.slippage_ticks = self.specs['slippage_ticks']
        
        self.tick_size = self.specs['tick_size']
    
    def apply_slippage(self, price: float, direction: int) -> float:
        """
        应用滑点
        
        Parameters:
        -----------
        price : float
            原始价格
        direction : int
            方向（正数=买入，负数=卖出）
        
        Returns:
        --------
        float : 应用滑点后的价格
        """
        slippage_amount = self.slippage_ticks * self.tick_size
        
        if direction > 0:  # 买入，价格提高
            return price + slippage_amount
        else:  # 卖出，价格降低
            return price - slippage_amount
    
    def get_slippage_cost(self, price: float, volume: int, direction: int) -> float:
        """
        计算滑点成本
        
        Parameters:
        -----------
        price : float
            原始价格
        volume : int
            交易手数（绝对值）
        direction : int
            方向（正数=买入，负数=卖出）
        
        Returns:
        --------
        float : 滑点成本（元）
        """
        slippage_amount = self.slippage_ticks * self.tick_size
        multiplier = self.specs['multiplier']
        volume = abs(volume)
        
        return slippage_amount * volume * multiplier


class TradingCostCalculator:
    """交易成本综合计算器"""
    
    def __init__(self, ticker: str, enable_commission: bool = True, 
                 enable_slippage: bool = True, slippage_ticks: int = None):
        """
        初始化交易成本计算器
        
        Parameters:
        -----------
        ticker : str
            期货代码
        enable_commission : bool
            是否启用手续费计算
        enable_slippage : bool
            是否启用滑点计算
        slippage_ticks : int, optional
            自定义滑点跳数
        """
        self.ticker = ticker
        self.enable_commission = enable_commission
        self.enable_slippage = enable_slippage
        
        self.commission_model = CommissionModel(ticker)
        self.slippage_model = SlippageModel(ticker, slippage_ticks)
        self.specs = FuturesContractSpecs.get_specs(ticker)
    
    def calculate_entry_cost(self, price: float, volume: int, direction: int) -> dict:
        """
        计算开仓成本
        
        Returns:
        --------
        dict : 包含各项成本的字典
        """
        volume = abs(volume)
        
        # 手续费
        commission = 0.0
        if self.enable_commission:
            commission = self.commission_model.calculate_commission(price, volume, 'open')
        
        # 滑点
        slippage_cost = 0.0
        adjusted_price = price
        if self.enable_slippage:
            adjusted_price = self.slippage_model.apply_slippage(price, direction)
            slippage_cost = self.slippage_model.get_slippage_cost(price, volume, direction)
        
        return {
            'original_price': price,
            'adjusted_price': adjusted_price,
            'commission': commission,
            'slippage_cost': slippage_cost,
            'total_cost': commission + slippage_cost,
            'volume': volume
        }
    
    def calculate_exit_cost(self, price: float, volume: int, direction: int) -> dict:
        """
        计算平仓成本
        
        Parameters:
        -----------
        direction : int
            平仓方向（注意：与持仓方向相反）
        """
        return self.calculate_entry_cost(price, volume, direction)
    
    def calculate_round_trip_cost(self, entry_price: float, exit_price: float, 
                                  volume: int) -> dict:
        """
        计算一个完整交易的往返成本
        
        Parameters:
        -----------
        entry_price : float
            开仓价格
        exit_price : float
            平仓价格
        volume : int
            交易手数
        
        Returns:
        --------
        dict : 往返成本详情
        """
        volume = abs(volume)
        
        # 开仓成本（假设做多，实际方向不影响手续费计算）
        entry_commission = self.commission_model.calculate_commission(entry_price, volume, 'open')
        entry_slippage = self.slippage_model.get_slippage_cost(entry_price, volume, 1)
        
        # 平仓成本
        exit_commission = self.commission_model.calculate_commission(exit_price, volume, 'close')
        exit_slippage = self.slippage_model.get_slippage_cost(exit_price, volume, -1)
        
        total_commission = entry_commission + exit_commission
        total_slippage = entry_slippage + exit_slippage
        
        return {
            'entry_commission': entry_commission,
            'exit_commission': exit_commission,
            'total_commission': total_commission,
            'entry_slippage': entry_slippage,
            'exit_slippage': exit_slippage,
            'total_slippage': total_slippage,
            'total_cost': total_commission + total_slippage,
            'volume': volume
        }


def print_contract_info(ticker: str):
    """打印合约详细信息"""
    specs = FuturesContractSpecs.get_specs(ticker)
    
    print(f"\n{'='*60}")
    print(f"期货合约规格 - {specs['name']} ({ticker})")
    print(f"{'='*60}")
    print(f"交易所：{specs['exchange']}")
    print(f"合约乘数：{specs['multiplier']} {specs['price_unit'].split('/')[1] if '/' in specs['price_unit'] else ''}/手")
    print(f"最小变动价位：{specs['tick_size']} {specs['price_unit']}")
    print(f"保证金率：{specs['margin_rate']*100}%")
    print(f"\n手续费标准：")
    if specs['commission_type'] == 'rate':
        print(f"  类型：按成交金额比例")
        print(f"  开仓：{specs['commission_open']*10000:.2f}‱ (万分之{specs['commission_open']*10000:.2f})")
        print(f"  平仓：{specs['commission_close']*10000:.2f}‱")
    else:
        print(f"  类型：按手数固定")
        print(f"  开仓：{specs['commission_open']}元/手")
        print(f"  平仓：{specs['commission_close']}元/手")
    print(f"\n滑点设置：{specs['slippage_ticks']}跳 = {specs['slippage_ticks'] * specs['tick_size']}{specs['price_unit']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # 示例使用
    logging.basicConfig(level=logging.INFO)
    
    # 打印合约信息
    for ticker in ['RB.SHF', 'OI.ZCE']:
        print_contract_info(ticker)
        
        # 测试手续费计算
        commission_model = CommissionModel(ticker)
        price = 3500 if ticker == 'RB.SHF' else 8000
        volume = 4
        
        print(f"交易案例：{ticker}")
        print(f"  价格：{price}元")
        print(f"  手数：{volume}手")
        
        info = commission_model.get_commission_info(price, volume)
        print(f"\n手续费明细：")
        print(f"  开仓手续费：{info['open_commission']:.2f}元")
        print(f"  平仓手续费：{info['close_commission']:.2f}元")
        print(f"  往返手续费：{info['total_commission']:.2f}元")
        
        # 测试滑点
        slippage_model = SlippageModel(ticker)
        buy_price = slippage_model.apply_slippage(price, 1)
        sell_price = slippage_model.apply_slippage(price, -1)
        
        print(f"\n滑点影响：")
        print(f"  原始价格：{price}元")
        print(f"  买入价格：{buy_price}元 (+{buy_price-price}元)")
        print(f"  卖出价格：{sell_price}元 ({sell_price-price}元)")
        
        # 计算往返成本
        calculator = TradingCostCalculator(ticker)
        cost_info = calculator.calculate_round_trip_cost(price, price + 50, volume)
        
        print(f"\n往返总成本：")
        print(f"  手续费：{cost_info['total_commission']:.2f}元")
        print(f"  滑点成本：{cost_info['total_slippage']:.2f}元")
        print(f"  合计：{cost_info['total_cost']:.2f}元")
        print(f"\n{'-'*60}\n")

