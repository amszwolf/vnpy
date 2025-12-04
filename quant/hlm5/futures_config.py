# -*- coding: utf-8 -*-
"""
期货交易专用配置
补充 hlm5_config.py 中的配置，增加期货特定参数

从 hlm5_all_parallel.py 移植期货合约规格和交易时段配置
"""

from hlm5_config import EQUITY_CONFIG

# ====================================================================
# 期货合约规格（从 hlm5_all_parallel.py 移植）
# ====================================================================

FUTURES_SPECS = {
    'OI': {  # 菜籽油期货
        'name': '菜籽油',
        'exchange': 'CZCE',       # 郑州商品交易所
        'multiplier': 10,         # 合约乘数：10吨/手
        'pricetick': 2,           # 最小变动价位：2元/吨
        'margin_rate': 0.08,      # 保证金比例：8%
        'commission': {
            'open_ratio': 0.00002,         # 开仓手续费率：万分之2
            'close_ratio': 0.00002,        # 平仓手续费率：万分之2
            'close_today_ratio': 0.00002,  # 平今手续费率：万分之2
        },
        'slippage': {
            'fixed_slippage': 0.25,    # 固定滑点（跳数）- 优化: 1→0.25 (10元/手→2.5元/手)
            'ratio_slippage': 0.0,     # 比例滑点
        },
        'main_contract_rule': 'OI888',  # 主力合约代码规则（888表示主力）
    },
    'RB': {  # 螺纹钢期货（用于对比测试）
        'name': '螺纹钢',
        'exchange': 'SHFE',       # 上海期货交易所
        'multiplier': 10,         # 合约乘数：10吨/手
        'pricetick': 1,           # 最小变动价位：1元/吨
        'margin_rate': 0.09,      # 保证金比例：9%
        'commission': {
            'open_ratio': 0.0001,          # 开仓手续费率：万分之1
            'close_ratio': 0.0001,         # 平仓手续费率：万分之1
            'close_today_ratio': 0.0001,   # 平今手续费率：万分之1
        },
        'slippage': {
            'fixed_slippage': 1,
            'ratio_slippage': 0.0,
        },
        'main_contract_rule': 'RB888',
    }
}

# ====================================================================
# 期货交易时段（从 hlm5_all_parallel.py 移植）
# ====================================================================

FUTURES_TRADING_HOURS = {
    'OI': {  # 菜油期货交易时段
        'day_session': [
            ('09:00:00', '10:15:00'),   # 上午第一节
            ('10:30:00', '11:30:00'),   # 上午第二节
            ('13:30:00', '15:00:00'),   # 下午
        ],
        'night_session': [
            ('21:00:00', '23:00:00'),   # 夜盘
        ],
        'close_buffer_minutes': 5,   # 收盘前5分钟强制平仓
        'open_buffer_minutes': 0,    # 开盘缓冲期（禁用，根据测试结果）
        'hold_overnight': False,     # 不持仓过夜
    },
    'RB': {  # 螺纹钢交易时段
        'day_session': [
            ('09:00:00', '10:15:00'),
            ('10:30:00', '11:30:00'),
            ('13:30:00', '15:00:00'),
        ],
        'night_session': [
            ('21:00:00', '23:00:00'),
        ],
        'close_buffer_minutes': 5,
        'open_buffer_minutes': 0,
        'hold_overnight': False,
    }
}

# ====================================================================
# 数据源配置（RQData 和 TuShare）
# ====================================================================

DATA_SOURCE_CONFIG = {
    'rqdata': {
        'enabled': True,
        'priority': 1,  # 优先使用 RQData
        'main_contract_method': 'get_dominant',  # 使用主力合约接口
        'data_fields': ['open', 'high', 'low', 'close', 'volume', 'open_interest'],
        'frequency': '1m',  # 下载1分钟数据
    },
    'tushare': {
        'enabled': True,
        'priority': 2,  # 备用数据源
        'api_token': '',  # 需要配置
        'data_fields': ['open', 'high', 'low', 'close', 'vol'],
        'frequency': '1min',
    }
}

# ====================================================================
# 回测配置
# ====================================================================

BACKTEST_CONFIG = {
    'start_date': '2025-01-01',
    'end_date': None,  # None 表示到最新
    'initial_capital': 100000,  # 初始资金：10万
    'interval': '5m',           # 回测周期：5分钟
    'slippage_type': 'fixed',   # 滑点类型：fixed 或 ratio
    'size': 1,                  # 默认下单手数
    'pricetick': 2,             # OI 最小变动价位
    'rate': 0.00002,            # 手续费率（双边万分之2）
}

# ====================================================================
# 合并配置
# ====================================================================

FUTURES_CONFIG = {
    **EQUITY_CONFIG,  # 继承所有 hlm5_config 配置
    'FUTURES_SPECS': FUTURES_SPECS,
    'FUTURES_TRADING_HOURS': FUTURES_TRADING_HOURS,
    'DATA_SOURCE_CONFIG': DATA_SOURCE_CONFIG,
    'BACKTEST_CONFIG': BACKTEST_CONFIG,
    'TRADING_MODE': 'futures',  # 标记为期货模式
}

# ====================================================================
# 辅助函数
# ====================================================================

def get_contract_specs(symbol: str) -> dict:
    """
    获取期货合约规格
    
    Parameters:
    -----------
    symbol : str
        期货代码，如 'OI', 'RB'
    
    Returns:
    --------
    dict : 合约规格字典
    """
    # 提取品种代码（去除数字和交易所后缀）
    commodity = ''.join([c for c in symbol if c.isalpha()])
    
    if commodity in FUTURES_SPECS:
        return FUTURES_SPECS[commodity]
    else:
        raise ValueError(f"未找到期货品种 {commodity} 的规格配置")

def get_trading_hours(symbol: str) -> dict:
    """
    获取期货交易时段
    
    Parameters:
    -----------
    symbol : str
        期货代码
    
    Returns:
    --------
    dict : 交易时段配置
    """
    commodity = ''.join([c for c in symbol if c.isalpha()])
    
    if commodity in FUTURES_TRADING_HOURS:
        return FUTURES_TRADING_HOURS[commodity]
    else:
        raise ValueError(f"未找到期货品种 {commodity} 的交易时段配置")

# ====================================================================
# 打印配置信息
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("期货配置信息")
    print("=" * 60)
    
    print("\n支持的期货品种：")
    for symbol, specs in FUTURES_SPECS.items():
        print(f"  {symbol}: {specs['name']}")
        print(f"    交易所: {specs['exchange']}")
        print(f"    合约乘数: {specs['multiplier']}吨/手")
        print(f"    最小变动: {specs['pricetick']}元/吨")
        print(f"    保证金率: {specs['margin_rate']*100}%")
        print(f"    手续费率: 开{specs['commission']['open_ratio']*10000}万分之一")
    
    print("\n回测配置：")
    print(f"  起始日期: {BACKTEST_CONFIG['start_date']}")
    print(f"  初始资金: {BACKTEST_CONFIG['initial_capital']:,}元")
    print(f"  回测周期: {BACKTEST_CONFIG['interval']}")
    
    print("\n数据源配置：")
    for source, config in DATA_SOURCE_CONFIG.items():
        if config['enabled']:
            print(f"  {source}: 优先级{config['priority']}")

