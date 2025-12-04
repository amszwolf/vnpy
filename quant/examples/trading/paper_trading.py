"""
模拟交易
优先使用PaperAccount进行模拟交易，如果需要实时行情则连接SimNow
"""

import sys
import time
import importlib.util
from pathlib import Path
from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.logger import INFO
from vnpy.trader.constant import Exchange
from vnpy.trader.object import SubscribeRequest, TickData, LogData
from vnpy.trader.event import EVENT_TICK, EVENT_LOG

# 添加策略目录到路径
examples_dir = Path(__file__).parent.parent
sys.path.insert(0, str(examples_dir))
sys.path.insert(0, str(examples_dir / "strategies"))

from vnpy_ctastrategy import CtaStrategyApp, CtaEngine
from vnpy_ctastrategy.base import EVENT_CTA_LOG
from ma_cross_strategy import MaCrossStrategy


def is_module_installed(module_name: str) -> bool:
    """检查模块是否已安装"""
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def get_simnow_config():
    """
    获取SimNow模拟盘配置
    """
    simnow_setting = {
        "用户名": "005442",
        "密码": "983311",
        "经纪商代码": "9999",
        "交易服务器": "tcp://180.168.146.187:10201",  # 电信主服务器
        "行情服务器": "tcp://180.168.146.187:10211",  # 电信主服务器
        "产品名称": "simnow_client_test",
        "授权编码": "0000000000000000",
        "柜台环境": "仿真"
    }
    return simnow_setting


def process_tick_event(event: Event):
    """
    处理行情事件，打印行情数据
    """
    tick = event.data
    print(f"\n{'='*80}")
    print(f"[行情数据接收] 接收时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  合约: {tick.symbol}.{tick.exchange.value}")
    print(f"  数据时间: {tick.datetime}")
    print(f"  最新价: {tick.last_price:.2f}")
    print(f"  涨跌: {(tick.last_price - tick.pre_close):.2f} ({((tick.last_price/tick.pre_close-1)*100):.2f}%)")
    print(f"  买一: {tick.bid_price_1:.2f} x {tick.bid_volume_1}")
    print(f"  卖一: {tick.ask_price_1:.2f} x {tick.ask_volume_1}")
    print(f"  成交量: {tick.volume} | 持仓量: {tick.open_interest}")
    print(f"  涨停: {tick.limit_up:.2f} | 跌停: {tick.limit_down:.2f}")
    print(f"{'='*80}")


def process_log_event(event: Event):
    """
    处理日志事件，打印重要日志
    """
    log = event.data
    # 只打印包含关键信息的日志
    keywords = ["登录", "连接", "成功", "失败", "查询", "订阅"]
    if any(keyword in log.msg for keyword in keywords):
        print(f"[系统] {log.msg}")


def main():
    """
    模拟交易主函数
    优先使用PaperAccount，如果需要实时行情则连接SimNow
    """
    print("=" * 60)
    print("模拟交易系统")
    print("=" * 60)
    print("\n⚠️  注意：这是模拟交易，不涉及真实资金\n")
    
    # 配置日志
    SETTINGS["log.active"] = True
    SETTINGS["log.level"] = INFO
    SETTINGS["log.console"] = True
    SETTINGS["log.file"] = True
    
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 创建主引擎
    main_engine = MainEngine(event_engine)
    
    # 1. 尝试添加PaperAccount（优先）
    use_paper_account = False
    if is_module_installed("vnpy_paperaccount"):
        from vnpy_paperaccount import PaperAccountApp
        main_engine.add_app(PaperAccountApp)
        use_paper_account = True
        print("✓ PaperAccount模拟账户已添加（优先使用）")
    else:
        print("⚠ vnpy_paperaccount 未安装，将使用SimNow获取实时行情")
        print("  安装命令: pip install vnpy_paperaccount")
    
    # 2. 添加CTA策略模块
    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)
    print("✓ CTA策略模块已添加")
    
    # 注册CTA日志事件
    log_engine = main_engine.get_engine("log")
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    
    # 注册行情事件监听（打印行情数据）
    event_engine.register(EVENT_TICK, process_tick_event)
    print("✓ 行情事件监听已注册")
    
    # 注册系统日志事件监听（打印连接状态）
    event_engine.register(EVENT_LOG, process_log_event)
    print("✓ 系统日志事件监听已注册")
    
    # 3. 如果需要实时行情，连接SimNow
    if not use_paper_account:
        print("\n连接SimNow获取实时行情...")
        from vnpy_ctp import CtpGateway
        
        main_engine.add_gateway(CtpGateway, "CTP_SIMNOW")
        print("✓ CTP Gateway已添加")
        
        simnow_setting = get_simnow_config()
        
        # 准备配置
        prepared_setting = simnow_setting.copy()
        prepared_setting["柜台环境"] = "仿真"
        
        print(f"  交易服务器: {prepared_setting.get('交易服务器', 'N/A')}")
        print(f"  行情服务器: {prepared_setting.get('行情服务器', 'N/A')}")
        print("  正在连接...")
        
        main_engine.connect(prepared_setting, "CTP_SIMNOW")
        print("✓ 连接请求已发送，等待连接建立...")
        
        # 等待连接建立
        time.sleep(10)
    
    # 4. 初始化CTA引擎
    print("\n初始化CTA引擎...")
    cta_engine.init_engine()
    print("✓ CTA引擎初始化完成")
    
    # 5. 手动注册策略类到CTA引擎
    print("\n注册策略类...")
    cta_engine.classes["MaCrossStrategy"] = MaCrossStrategy
    print("✓ 策略类已注册")
    
    # 6. 添加策略实例（使用优化后的最优参数）
    print("\n添加策略实例（使用优化后的最优参数）...")
    strategy_setting = {
        "fast_window": 10,      # 优化后的最优参数
        "slow_window": 30,      # 优化后的最优参数
        "fixed_size": 1,
        "sl_percent": 0.03,     # 止损3%（优化后的最优参数）
        "tp_percent": 0.08      # 止盈8%（优化后的最优参数）
    }
    
    strategy_name = "MaCross_IF2512_Paper"
    vt_symbol = "IF2512.CFFEX"
    
    cta_engine.add_strategy(
        "MaCrossStrategy",      # 使用策略类名字符串
        strategy_name,
        vt_symbol,
        strategy_setting
    )
    print(f"✓ 策略实例已添加: {strategy_name}")
    print(f"  交易合约: {vt_symbol}")
    print(f"  策略参数: {strategy_setting}")
    
    # 7. 如果使用SimNow，订阅行情
    if not use_paper_account:
        print(f"\n订阅行情: {vt_symbol}...")
        subscribe_req = SubscribeRequest(
            symbol="IF2512",
            exchange=Exchange.CFFEX
        )
        main_engine.subscribe(subscribe_req, "CTP_SIMNOW")
        print("✓ 行情订阅请求已发送")
    
    # 8. 初始化策略
    print("\n初始化策略...")
    cta_engine.init_strategy(strategy_name)
    print("✓ 策略初始化完成")
    
    # 9. 启动策略
    print("\n启动策略...")
    cta_engine.start_strategy(strategy_name)
    print("✓ 策略已启动")
    
    print("\n" + "=" * 60)
    print("模拟交易系统运行中...")
    print("=" * 60)
    print("\n策略信息：")
    print(f"  策略名称: {strategy_name}")
    print(f"  交易合约: {vt_symbol}")
    print(f"  快速均线: {strategy_setting['fast_window']}")
    print(f"  慢速均线: {strategy_setting['slow_window']}")
    print(f"  止损比例: {strategy_setting['sl_percent']*100}%")
    print(f"  止盈比例: {strategy_setting['tp_percent']*100}%")
    
    if use_paper_account:
        print("\n账户类型: PaperAccount（纯模拟账户）")
        print("提示：")
        print("  1. 使用PaperAccount进行模拟交易")
        print("  2. 需要连接交易接口获取实时行情")
        print("  3. 所有交易都是模拟的，不涉及真实资金")
    else:
        print("\n账户类型: SimNow模拟盘")
        print("提示：")
        print("  1. 已连接SimNow获取实时行情")
        print("  2. 策略将根据实时行情自动交易（模拟）")
        print("  3. 所有交易都是模拟的，不涉及真实资金")
    
    print("  4. 按Ctrl+C停止策略并退出")
    print("\n" + "=" * 60)
    
    # 10. 保持运行并定期打印状态
    print("\n等待行情数据...")
    print("提示：行情数据会实时显示在下方\n")
    
    try:
        tick_count = 0
        last_status_time = time.time()
        
        while True:
            time.sleep(1)
            
            # 每30秒打印一次状态
            current_time = time.time()
            if current_time - last_status_time >= 30:
                print(f"\n{'='*60}")
                print(f"[状态检查] {time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 获取网关状态
                gateway = main_engine.get_gateway("CTP_SIMNOW")
                if gateway:
                    print(f"[连接] CTP Gateway 运行中")
                else:
                    print(f"[连接] CTP Gateway 未连接")
                
                # 获取策略状态
                strategy = cta_engine.strategies.get(strategy_name)
                if strategy:
                    print(f"[策略] {strategy_name} 运行中")
                    print(f"[策略] 持仓: {strategy.pos}")
                    print(f"[策略] inited={strategy.inited}, trading={strategy.trading}")
                else:
                    print(f"[策略] {strategy_name} 未找到")
                
                print(f"{'='*60}\n")
                last_status_time = current_time
                
    except KeyboardInterrupt:
        print("\n\n正在停止策略...")
        cta_engine.stop_strategy(strategy_name)
        main_engine.close()
        print("系统已关闭")
        print("\n✓ 退出完成")


if __name__ == "__main__":
    main()

