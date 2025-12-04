"""
下载主力合约5分钟数据
使用RQData，基于OI（持仓量）判断主力合约
简化版本：直接下载IF888主力合约的5分钟数据
"""

from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.database import get_database, DB_TZ
from vnpy.trader.constant import Exchange
from vnpy.trader.object import HistoryRequest
from vnpy.trader.setting import SETTINGS


def download_main_contract_data(
    symbol: str = "IF888",
    exchange: Exchange = Exchange.CFFEX,
    start: datetime = None,
    end: datetime = None,
    interval_str: str = "5m"  # 5分钟K线（字符串格式）
):
    """
    下载主力合约数据
    
    参数:
        symbol: 合约代码（使用888表示主力合约，如IF888）
        exchange: 交易所
        start: 开始日期
        end: 结束日期
        interval: K线周期（默认5分钟）
    """
    if start is None:
        start = datetime(2023, 1, 1, tzinfo=DB_TZ)
    if end is None:
        end = datetime(2023, 12, 31, tzinfo=DB_TZ)
    
    print("=" * 60)
    print("下载主力合约5分钟数据")
    print("=" * 60)
    print(f"合约: {symbol}.{exchange.value}")
    print(f"时间范围: {start.date()} 至 {end.date()}")
    print(f"K线周期: {interval_str}")
    
    # 确保RQData已配置
    if SETTINGS.get("datafeed.name") != "rqdata":
        print("\n⚠ 数据源未配置为RQData")
        print("正在尝试配置RQData...")
        from configure_rqdata import configure_rqdata, RQDATA_USERNAME, RQDATA_LICENSE
        configure_rqdata(RQDATA_USERNAME, RQDATA_LICENSE)
    
    # 获取数据服务和数据库
    print("\n初始化数据服务...")
    datafeed = get_datafeed()
    database = get_database()
    
    # 初始化数据服务
    if not datafeed.init():
        print("⚠ 数据服务初始化失败")
        print("请检查RQData配置是否正确")
        return False
    
    print("✓ 数据服务初始化成功")
    
    # 创建历史数据请求
    # 注意：RQData可能不支持直接下载5分钟数据，需要下载1分钟然后合成
    # 这里先尝试下载1分钟数据
    from vnpy.trader.constant import Interval
    req = HistoryRequest(
        symbol=symbol,
        exchange=exchange,
        start=start,
        end=end,
        interval=Interval.MINUTE  # 先下载1分钟数据
    )
    
    # 下载数据
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
        
        return True
    else:
        print("⚠ 下载失败")
        print("可能的原因：")
        print("1. RQData License无效或过期")
        print("2. 网络连接问题")
        print("3. 合约代码不正确")
        print("4. 该时间段没有数据")
        return False


def main():
    """
    主函数
    """
    # 下载IF888主力合约的5分钟数据
    success = download_main_contract_data(
        symbol="IF888",
        exchange=Exchange.CFFEX,
        start=datetime(2023, 1, 1, tzinfo=DB_TZ),
        end=datetime(2023, 12, 31, tzinfo=DB_TZ),
        interval_str="5m"
    )
    
    if success:
        print("\n" + "=" * 60)
        print("数据下载完成！")
        print("=" * 60)
        print("\n下一步：运行策略回测")
        print("  cd quant/examples")
        print("  python backtesting/run_backtest.py")
    else:
        print("\n数据下载失败，请检查配置和网络连接")


if __name__ == "__main__":
    main()
