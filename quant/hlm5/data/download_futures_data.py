# -*- coding: utf-8 -*-
"""
期货主力合约数据下载 (通用版本)

支持任意期货品种的主力合约数据下载
使用 VNPy datafeed 接口，支持 RQData/TuShare 等数据源

特点：
- 使用 VNPy datafeed 统一接口
- 支持任意期货品种（IF, OI, RB等）
- 自动使用888主力合约
- 支持1分钟和5分钟数据
- 自动保存到VNPy数据库
"""

from datetime import datetime, timedelta
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database, DB_TZ
from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.object import HistoryRequest
from vnpy.trader.setting import SETTINGS

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from futures_config import FUTURES_CONFIG, DATA_SOURCE_CONFIG

# ====================================================================
# RQData 配置（参考 examples 的成功配置）
# ====================================================================

# RQData 固定用户名和 License
RQDATA_USERNAME = "license"  # RQData固定为"license"
RQDATA_LICENSE = "DqAHX6WtHmnbcL5Haa6yFrJOJCElKSPTr339DvrbCY61LR1mXFy19fmsv5t6MPB25VjLSubzWjMRHa2Maqo6-35dAUC5SYe3QfNXXAAuNXt3O-xN-ooSKvFwgaJVOxUyR5q3MHGD26tldeymEiHOELLqDGtITB9GOezJGHtHLxM=doeF-hOW0dmHR2_BfG03DCSo7UAg4m_oRuUbJBAaWUN4tB9ZddEArW1SXOIkOSIVO9reBFIiGSvqbgpK9K4Fmrk_tAeVZtSMXmsXy8hSFrXSgZv8VFjs9w03_rKADTfHLFDNQ0x6Ls5dSvbfJFhNX6t087fVmQnX0B2jg57o5zI="


def configure_rqdata_if_needed():
    """
    检查并配置 RQData
    如果未配置，自动配置
    """
    if SETTINGS.get("datafeed.name") != "rqdata":
        print("\n⚠️ 数据源未配置为RQData")
        print("正在自动配置RQData...")
        
        SETTINGS["datafeed.name"] = "rqdata"
        SETTINGS["datafeed.username"] = RQDATA_USERNAME
        SETTINGS["datafeed.password"] = RQDATA_LICENSE
        
        print("✓ RQData配置完成")
        return True
    else:
        print("✓ RQData已配置")
        return True


def parse_interval(interval_str):
    """
    将字符串间隔转换为 Interval 枚举
    
    Parameters:
    -----------
    interval_str : str
        时间周期字符串，如 '1m', '5m', '1h', '1d'
    
    Returns:
    --------
    Interval
        对应的 Interval 枚举值
    """
    interval_map = {
        '1m': Interval.MINUTE,
        '5m': Interval.MINUTE,  # VNPy使用 MINUTE，需要下载1分钟后合成5分钟
        '15m': Interval.MINUTE,
        '1h': Interval.HOUR,
        '1d': Interval.DAILY,
    }
    
    return interval_map.get(interval_str, Interval.MINUTE)


def download_futures_data(
    symbol: str = "OI888",
    exchange: Exchange = Exchange.CZCE,
    start_date=None,
    end_date=None,
    interval_str='1m'  # 注意：先下载1分钟数据
):
    """
    下载期货主力合约数据
    
    Parameters:
    -----------
    symbol : str
        合约代码（使用888表示主力合约，如 IF888, OI888, RB888）
    exchange : Exchange
        交易所（CFFEX, CZCE, SHFE, DCE, INE）
    start_date : datetime, optional
        开始日期
    end_date : datetime, optional
        结束日期
    interval_str : str
        数据周期 ('1m', '5m', '1h', '1d')
        注意：RQData 可能只支持1分钟数据，5分钟需要后续合成
        
    Returns:
    --------
    bool : 下载是否成功
    """
    # 1. 设置默认参数
    if start_date is None:
        start_date_str = FUTURES_CONFIG['BACKTEST_CONFIG']['start_date']
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=DB_TZ)
    
    if end_date is None:
        end_date = datetime.now(tz=DB_TZ)
    
    # 确保时区
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=DB_TZ)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=DB_TZ)
    
    print("=" * 60)
    print("期货主力合约数据下载")
    print("=" * 60)
    print(f"合约: {symbol}.{exchange.value}")
    print(f"时间范围: {start_date.date()} 至 {end_date.date()}")
    print(f"K线周期: {interval_str}")
    print("=" * 60)
    
    # 2. 配置 RQData
    configure_rqdata_if_needed()
    
    # 3. 获取数据服务和数据库
    print("\n初始化数据服务...")
    datafeed = get_datafeed()
    database = get_database()
    
    if datafeed is None:
        print("✗ 无法获取数据服务")
        print("  请检查 RQData 配置")
        return False
    
    # 4. 初始化数据服务
    if not datafeed.init():
        print("⚠️ 数据服务初始化失败")
        print("  请检查RQData配置是否正确")
        print("  用户名:", SETTINGS.get("datafeed.username"))
        print("  License:", SETTINGS.get("datafeed.password", "")[:30] + "...")
        return False
    
    print("✓ 数据服务初始化成功")
    
    # 5. 创建历史数据请求
    # 注意：对于5分钟数据，先下载1分钟数据（因为RQData可能不直接支持5分钟）
    actual_interval = Interval.MINUTE if interval_str in ['1m', '5m'] else parse_interval(interval_str)
    
    req = HistoryRequest(
        symbol=symbol,
        exchange=exchange,
        start=start_date,
        end=end_date,
        interval=actual_interval
    )
    
    # 6. 下载数据
    print(f"\n开始下载数据...")
    print("这可能需要一些时间，请耐心等待...")
    
    bars = datafeed.query_bar_history(req)
    
    if bars:
        # 保存数据
        print(f"\n下载成功: {len(bars)} 根K线")
        print("正在保存到数据库...")
        database.save_bar_data(bars)
        print("✓ 数据保存成功")
        
        # 显示数据概览
        if len(bars) > 0:
            print(f"\n数据概览:")
            print(f"  第一根K线: {bars[0].datetime}")
            print(f"  最后一根K线: {bars[-1].datetime}")
            print(f"  总数据量: {len(bars)} 根")
            print(f"  价格范围: {min(b.close_price for b in bars):.2f} ~ {max(b.close_price for b in bars):.2f}")
        
        return True
    else:
        print("✗ 下载失败")
        print("\n可能的原因：")
        print("1. RQData License无效或过期")
        print("2. 网络连接问题")
        print("3. 合约代码不正确")
        print("4. 该时间段没有数据")
        print("5. 权限不足（需要期货数据权限）")
        return False


def check_database(symbol="OI888", exchange=Exchange.CZCE):
    """
    检查数据库中已有的数据
    
    Parameters:
    -----------
    symbol : str
        合约代码
    exchange : Exchange
        交易所
    """
    try:
        database = get_database()
        
        # 查询数据
        bars = database.load_bar_data(
            symbol=symbol,
            exchange=exchange,
            interval=Interval.MINUTE,
            start=datetime(2020, 1, 1, tzinfo=DB_TZ),
            end=datetime.now(tz=DB_TZ)
        )
        
        if not bars:
            print(f"\n数据库中没有 {symbol}.{exchange.value} 的数据")
            return None
        
        print("\n" + "=" * 60)
        print("数据库数据检查")
        print("=" * 60)
        print(f"合约: {symbol}.{exchange.value}")
        print(f"周期: 1分钟")
        print(f"数据量: {len(bars)} 条")
        print(f"起始时间: {bars[0].datetime}")
        print(f"结束时间: {bars[-1].datetime}")
        print("=" * 60)
        
        return bars
        
    except Exception as e:
        print(f"查询数据库失败: {e}")
        import traceback
        traceback.print_exc()
        return None


# ====================================================================
# 主程序
# ====================================================================

def main():
    """主程序：下载期货数据"""
    import argparse
    
    parser = argparse.ArgumentParser(description='下载期货主力合约数据')
    parser.add_argument('--symbol', type=str, default='OI888',
                       help='合约代码（如 IF888, OI888, RB888）')
    parser.add_argument('--exchange', type=str, default='CZCE',
                       help='交易所（CFFEX, CZCE, SHFE, DCE, INE）')
    parser.add_argument('--start', type=str, help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--interval', type=str, default='1m', 
                       help='数据周期 (1m, 5m, 15m, 1h, 1d)')
    parser.add_argument('--check', action='store_true', 
                       help='仅检查数据库中的数据')
    
    args = parser.parse_args()
    
    # 解析交易所
    exchange_map = {
        'CFFEX': Exchange.CFFEX,
        'CZCE': Exchange.CZCE,
        'SHFE': Exchange.SHFE,
        'DCE': Exchange.DCE,
        'INE': Exchange.INE,
    }
    exchange = exchange_map.get(args.exchange.upper(), Exchange.CZCE)
    
    # 如果只是检查数据库
    if args.check:
        check_database(args.symbol, exchange)
        return
    
    # 解析日期参数
    start_date = None
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        start_date = start_date.replace(tzinfo=DB_TZ)
    
    end_date = None
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
        end_date = end_date.replace(tzinfo=DB_TZ)
    
    # 下载数据
    success = download_futures_data(
        symbol=args.symbol,
        exchange=exchange,
        start_date=start_date,
        end_date=end_date,
        interval_str=args.interval
    )
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 数据下载完成！")
        print("=" * 60)
        print("\n下一步：")
        print("  1. 运行回测：python backtesting/run_backtest.py")
        print("  2. 参数优化：python backtesting/optimizer.py")
        print("  3. 模拟交易：python trading/paper_trading.py")
    else:
        print("\n" + "=" * 60)
        print("✗ 数据下载失败")
        print("=" * 60)
        print("\n故障排查：")
        print("  1. 检查 RQData License 是否正确配置")
        print("  2. 检查网络连接")
        print("  3. 检查日期范围是否合理")
        print("  4. 确认 RQData 账户有期货数据权限")


if __name__ == "__main__":
    main()

