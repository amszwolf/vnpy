# -*- coding: utf-8 -*-
"""
RQData数据加载器
用于回测引擎从RQData获取期货数据
"""

import pandas as pd
from datetime import datetime
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import DB_TZ
from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.object import HistoryRequest
from vnpy.trader.setting import SETTINGS


# RQData配置
RQDATA_USERNAME = "license"
RQDATA_LICENSE = "DqAHX6WtHmnbcL5Haa6yFrJOJCElKSPTr339DvrbCY61LR1mXFy19fmsv5t6MPB25VjLSubzWjMRHa2Maqo6-35dAUC5SYe3QfNXXAAuNXt3O-xN-ooSKvFwgaJVOxUyR5q3MHGD26tldeymEiHOELLqDGtITB9GOezJGHtHLxM=doeF-hOW0dmHR2_BfG03DCSo7UAg4m_oRuUbJBAaWUN4tB9ZddEArW1SXOIkOSIVO9reBFIiGSvqbgpK9K4Fmrk_tAeVZtSMXmsXy8hSFrXSgZv8VFjs9w03_rKADTfHLFDNQ0x6Ls5dSvbfJFhNX6t087fVmQnX0B2jg57o5zI="


def configure_rqdata():
    """配置RQData数据源"""
    if SETTINGS.get("datafeed.name") != "rqdata":
        SETTINGS["datafeed.name"] = "rqdata"
        SETTINGS["datafeed.username"] = RQDATA_USERNAME
        SETTINGS["datafeed.password"] = RQDATA_LICENSE
        print("✓ RQData配置完成")
    else:
        print("✓ RQData已配置")


def parse_ticker_to_symbol(ticker: str):
    """
    将ticker转换为VNPy格式
    
    Parameters:
    -----------
    ticker : str
        如 'OI.ZCE', 'RB.SHF'
    
    Returns:
    --------
    tuple : (symbol, exchange)
        如 ('OI888', Exchange.CZCE)
    """
    if '.' in ticker:
        symbol_base, exchange_str = ticker.split('.')
        symbol = symbol_base + '888'  # 使用888表示主力合约
    else:
        symbol_base = ticker
        symbol = symbol_base + '888'
        exchange_str = 'CZCE'
    
    exchange_map = {
        'ZCE': Exchange.CZCE,
        'CZCE': Exchange.CZCE,
        'SHF': Exchange.SHFE,
        'SHFE': Exchange.SHFE,
        'DCE': Exchange.DCE,
        'INE': Exchange.INE,
        'CFFEX': Exchange.CFFEX
    }
    
    exchange = exchange_map.get(exchange_str.upper(), Exchange.CZCE)
    
    return symbol, exchange


def load_futures_data_from_rqdata(
    ticker: str,
    start_date: str,
    end_date: str,
    interval: str = '5m'
):
    """
    从RQData加载期货数据
    
    Parameters:
    -----------
    ticker : str
        合约代码，如 'OI.ZCE'
    start_date : str
        开始日期，格式 'YYYY-MM-DD'
    end_date : str
        结束日期，格式 'YYYY-MM-DD'
    interval : str
        数据周期，'1m'或'5m'
    
    Returns:
    --------
    pd.DataFrame : 包含 datetime, open, high, low, close, volume 列
    """
    print(f"\n{'='*60}")
    print(f"从RQData加载数据: {ticker}")
    print(f"时间范围: {start_date} ~ {end_date}")
    print(f"周期: {interval}")
    print(f"{'='*60}")
    
    # 1. 配置RQData
    configure_rqdata()
    
    # 2. 解析ticker
    symbol, exchange = parse_ticker_to_symbol(ticker)
    print(f"  合约: {symbol}.{exchange.value}")
    
    # 3. 初始化datafeed
    datafeed = get_datafeed()
    
    if not datafeed.init():
        print("✗ RQData初始化失败")
        return pd.DataFrame()
    
    print("✓ RQData初始化成功")
    
    # 4. 准备时间参数
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=DB_TZ)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=DB_TZ)
    
    # 5. 创建请求（先获取1分钟数据）
    req = HistoryRequest(
        symbol=symbol,
        exchange=exchange,
        start=start_dt,
        end=end_dt,
        interval=Interval.MINUTE
    )
    
    # 6. 查询数据
    print("  正在下载数据...")
    bars = datafeed.query_bar_history(req)
    
    if not bars:
        print("✗ 没有获取到数据")
        return pd.DataFrame()
    
    print(f"✓ 下载成功: {len(bars)} 根K线")
    
    # 7. 转换为DataFrame
    data_list = []
    for bar in bars:
        data_list.append({
            'datetime': bar.datetime.replace(tzinfo=None),  # 移除时区信息
            'open': bar.open_price,
            'high': bar.high_price,
            'low': bar.low_price,
            'close': bar.close_price,
            'volume': bar.volume
        })
    
    df = pd.DataFrame(data_list)
    
    # 8. 如果需要5分钟数据，进行聚合
    if interval == '5m' and len(df) > 0:
        print("  正在聚合为5分钟数据...")
        df = aggregate_to_5min(df)
        print(f"✓ 聚合完成: {len(df)} 根5分钟K线")
    
    # 9. 数据质量检查
    if len(df) > 0:
        df = df.sort_values('datetime').reset_index(drop=True)
        df = df.drop_duplicates(subset=['datetime'], keep='last')
        
        print(f"\n数据概览:")
        print(f"  首条: {df['datetime'].iloc[0]}")
        print(f"  末条: {df['datetime'].iloc[-1]}")
        print(f"  数据量: {len(df)} 条")
        print(f"  价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    
    return df


def aggregate_to_5min(df: pd.DataFrame) -> pd.DataFrame:
    """
    将1分钟数据聚合为5分钟数据
    
    Parameters:
    -----------
    df : pd.DataFrame
        1分钟数据，包含 datetime, open, high, low, close, volume
    
    Returns:
    --------
    pd.DataFrame : 5分钟数据
    """
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    
    # 聚合规则
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    # 5分钟重采样
    df_5min = df.resample('5min', label='right', closed='right').agg(agg_dict)
    
    # 删除NaN行
    df_5min = df_5min.dropna()
    
    # 重置索引
    df_5min = df_5min.reset_index()
    
    return df_5min


def check_raw_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    数据质量检查（兼容原有函数）
    
    Parameters:
    -----------
    df : pd.DataFrame
        原始数据
    
    Returns:
    --------
    pd.DataFrame : 清洗后的数据
    """
    if df.empty:
        return df
    
    # 删除重复
    df = df.drop_duplicates(subset=['datetime'], keep='last')
    
    # 排序
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # 检查缺失值
    null_counts = df.isnull().sum()
    if null_counts.sum() > 0:
        print(f"  发现缺失值: {dict(null_counts[null_counts > 0])}")
        df = df.dropna()
    
    # 检查异常值（价格<=0或成交量<0）
    invalid_prices = (df['open'] <= 0) | (df['high'] <= 0) | (df['low'] <= 0) | (df['close'] <= 0)
    invalid_volume = df['volume'] < 0
    
    if invalid_prices.sum() > 0:
        print(f"  发现异常价格: {invalid_prices.sum()} 条")
        df = df[~invalid_prices]
    
    if invalid_volume.sum() > 0:
        print(f"  发现异常成交量: {invalid_volume.sum()} 条")
        df = df[~invalid_volume]
    
    return df

