# -*- coding: utf-8 -*-
"""
HLM5 策略模拟交易

使用 SimNow 模拟账户或 PaperAccountApp
实时运行 HLM5 策略
"""

import sys
import time
import importlib.util
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "strategies"))

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.object import SubscribeRequest, TickData, LogData
from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctastrategy.base import EVENT_CTA_LOG, EVENT_TICK, EVENT_LOG

# 导入策略
from strategies.hlm5_strategy import HLM5Strategy

# 导入配置
from hlm5_config import EQUITY_CONFIG
from futures_config import FUTURES_CONFIG


def is_module_installed(module_name):
    """检查模块是否已安装"""
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def get_simnow_config():
    """
    获取 SimNow 配置
    
    使用用户提供的 SimNow 账户配置
    """
    return {
        "用户名": "005442",
        "密码": "983311",
        "经纪商代码": "9999",
        "交易服务器": "180.168.146.187:10201",
        "行情服务器": "180.168.146.187:10211",
        "产品名称": "simnow_client_test",
        "授权编码": "0000000000000000",
        "产品信息": ""
    }


def process_tick_event(event: Event):
    """处理行情事件，打印行情数据"""
    tick: TickData = event.data
    print(f"=" * 80)
    print(f"[行情数据接收] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  合约: {tick.vt_symbol}")
    print(f"  数据时间: {tick.datetime.strftime('%Y-%m-%d %H:%M:%S') if tick.datetime else 'N/A'}")
    print(f"  最新价: {tick.last_price:.2f}")
    print(f"  买一: {tick.bid_price_1:.2f} x {tick.bid_volume_1}")
    print(f"  卖一: {tick.ask_price_1:.2f} x {tick.ask_volume_1}")
    print(f"  成交量: {tick.volume} | 持仓量: {tick.open_interest}")
    print("=" * 80)


def process_log_event(event: Event):
    """处理日志事件"""
    log: LogData = event.data
    keywords = ["登录", "连接", "成功", "失败", "查询", "订阅", "行情", "成交", "委托"]
    if any(keyword in log.msg for keyword in keywords):
        print(f"[系统] {log.msg}")


def main():
    """主程序"""
    print("=" * 60)
    print("HLM5 策略模拟交易")
    print("=" * 60)
    
    # 1. 创建事件引擎和主引擎
    print("\n[1/8] 创建引擎...")
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    print("✓ 引擎创建成功")
    
    # 2. 注册事件监听
    print("\n[2/8] 注册事件监听...")
    event_engine.register(EVENT_TICK, process_tick_event)
    event_engine.register(EVENT_LOG, process_log_event)
    print("✓ 事件监听已注册")
    
    # 3. 检查 PaperAccountApp
    print("\n[3/8] 检查模拟账户...")
    use_paper_account = is_module_installed("vnpy_paperaccount")
    
    if use_paper_account:
        print("✓ 检测到 PaperAccountApp，将使用虚拟账户")
        from vnpy_paperaccount import PaperAccountApp
        main_engine.add_app(PaperAccountApp)
        gateway_name = "PAPER"
    else:
        print("⚠️ 未安装 vnpy_paperaccount，将使用 SimNow 模拟账户")
        print("  安装命令: pip install vnpy_paperaccount")
        gateway_name = "CTP_SIMNOW"
    
    # 4. 添加CTA策略应用
    print("\n[4/8] 添加 CTA 策略应用...")
    cta_engine = main_engine.add_app(CtaStrategyApp)
    print("✓ CTA 策略应用已添加")
    
    # 5. 如果使用 SimNow，添加并连接 CTP Gateway
    if not use_paper_account:
        print("\n连接 SimNow...")
        
        if not is_module_installed("vnpy_ctp"):
            print("✗ 未安装 vnpy_ctp，无法连接 SimNow")
            print("  安装命令: pip install vnpy_ctp")
            return
        
        from vnpy_ctp import CtpGateway
        main_engine.add_gateway(CtpGateway, gateway_name)
        print("✓ CTP Gateway 已添加")
        
        # 连接
        simnow_config = get_simnow_config()
        main_engine.connect(simnow_config, gateway_name)
        print("✓ 正在连接 SimNow...")
        time.sleep(5)  # 等待连接完成
    
    # 6. 注册策略类
    print("\n[5/8] 注册策略类...")
    cta_engine.classes["HLM5Strategy"] = HLM5Strategy
    print("✓ 策略类已注册")
    
    # 7. 添加策略实例
    print("\n[6/8] 添加策略实例...")
    
    strategy_name = "HLM5_OI888_Paper"
    vt_symbol = "OI888.CZCE"
    
    # 使用默认参数（从 hlm5_config.py 读取）
    strategy_setting = {
        "fixed_size": 1,
        "enable_bidirectional": True,
        "hold_overnight": False
    }
    
    cta_engine.add_strategy(
        "HLM5Strategy",
        strategy_name,
        vt_symbol,
        strategy_setting
    )
    print(f"✓ 策略实例已添加: {strategy_name}")
    
    # 8. 初始化并启动策略
    print("\n[7/8] 初始化策略...")
    cta_engine.init_engine()
    time.sleep(2)
    
    cta_engine.init_strategy(strategy_name)
    time.sleep(2)
    print("✓ 策略初始化完成")
    
    print("\n[8/8] 启动策略...")
    cta_engine.start_strategy(strategy_name)
    print("✓ 策略已启动")
    
    # 9. 订阅行情
    print("\n订阅行情...")
    req = SubscribeRequest(
        symbol="OI888",
        exchange=Exchange.CZCE
    )
    main_engine.subscribe(req, gateway_name)
    print(f"✓ 已订阅 {vt_symbol}")
    
    # 10. 打印策略配置
    print("\n" + "=" * 60)
    print("策略配置")
    print("=" * 60)
    print(f"合约: {vt_symbol}")
    print(f"下单手数: {strategy_setting['fixed_size']}")
    print(f"双向交易: {'启用' if strategy_setting['enable_bidirectional'] else '禁用'}")
    print(f"持仓过夜: {'允许' if strategy_setting['hold_overnight'] else '禁止'}")
    print(f"\nPrice MACD: ({HLM5Strategy.price_macd_long}, {HLM5Strategy.price_macd_mid}, {HLM5Strategy.price_macd_short})")
    print(f"Volume MACD: ({HLM5Strategy.volume_macd_long}, {HLM5Strategy.volume_macd_mid}, {HLM5Strategy.volume_macd_short})")
    print(f"HLBW: lookback={HLM5Strategy.hlbw_lookback}")
    print(f"止损: {HLM5Strategy.stop_loss_pct*100}% | 止盈: {HLM5Strategy.take_profit_pct*100}%")
    print("=" * 60)
    
    # 11. 保持运行并定期检查状态
    print("\n等待行情数据...")
    print("提示：行情数据会实时显示在下方")
    print("按 Ctrl+C 停止策略")
    
    last_status_check = time.time()
    
    try:
        while True:
            current_time = time.time()
            
            # 每30秒检查一次状态
            if current_time - last_status_check >= 30:
                print("\n" + "=" * 60)
                print(f"[状态检查] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 60)
                
                # 检查连接状态
                if not use_paper_account:
                    gateway = main_engine.get_gateway(gateway_name)
                    if gateway:
                        print(f"[连接] CTP Gateway: 已连接")
                    else:
                        print(f"[连接] CTP Gateway: 未连接")
                
                # 检查策略状态
                strategy = cta_engine.get_strategy(strategy_name)
                if strategy:
                    print(f"[策略] {strategy_name}: 运行中")
                    print(f"  持仓: {strategy.pos} 手")
                    print(f"  inited: {strategy.inited} | trading: {strategy.trading}")
                    print(f"  总交易: {strategy.total_trades} 次")
                else:
                    print(f"[策略] {strategy_name}: 未运行")
                
                print("=" * 60)
                last_status_check = current_time
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n收到停止信号...")
        
        # 12. 停止策略
        print("\n停止策略...")
        cta_engine.stop_strategy(strategy_name)
        time.sleep(1)
        
        # 13. 关闭引擎
        print("关闭引擎...")
        main_engine.close()
        
        print("\n" + "=" * 60)
        print("✅ HLM5 策略已停止")
        print("=" * 60)


if __name__ == "__main__":
    main()

