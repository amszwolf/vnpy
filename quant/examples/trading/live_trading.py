"""
实盘交易
使用真实交易接口进行实盘交易
需要先连接交易接口并订阅行情
"""

import sys
import time
from pathlib import Path
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.logger import INFO
from vnpy.trader.utility import TEMP_DIR, load_json

# 添加策略目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "strategies"))

from vnpy_ctp import CtpGateway
from vnpy_ctastrategy import CtaStrategyApp, CtaEngine
from vnpy_ctastrategy.base import EVENT_CTA_LOG
from strategies.ma_cross_strategy import MaCrossStrategy


def load_account_config():
    """
    加载账号配置
    """
    config_file = TEMP_DIR / "connect_ctp.json"
    if config_file.exists():
        return load_json("connect_ctp.json")
    return None


def main():
    """
    实盘交易主函数
    """
    print("=" * 60)
    print("实盘交易系统")
    print("=" * 60)
    print("\n⚠️  警告：这是实盘交易系统，将使用真实资金进行交易！")
    print("请确保：")
    print("1. 策略已经过充分回测和模拟交易验证")
    print("2. 已设置合理的风险控制参数")
    print("3. 已准备好监控和应急措施")
    
    confirm = input("\n确认继续？(yes/no): ")
    if confirm.lower() != "yes":
        print("已取消")
        return
    
    # 配置日志
    SETTINGS["log.active"] = True
    SETTINGS["log.level"] = INFO
    SETTINGS["log.console"] = True
    SETTINGS["log.file"] = True
    
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 创建主引擎
    main_engine = MainEngine(event_engine)
    
    # 添加CTP Gateway
    main_engine.add_gateway(CtpGateway)
    print("✓ CTP Gateway已添加")
    
    # 添加CTA策略模块
    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)
    print("✓ CTA策略模块已添加")
    
    # 注册CTA日志事件
    log_engine = main_engine.get_engine("log")
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    
    # 加载账号配置
    ctp_setting = load_account_config()
    if not ctp_setting:
        print("⚠ 未找到账号配置，请先运行 add_accounts.py 添加账号")
        return
    
    # 连接交易接口
    print("\n正在连接CTP接口...")
    main_engine.connect(ctp_setting, "CTP")
    print("✓ 连接请求已发送，等待连接建立...")
    
    # 等待连接建立
    time.sleep(10)
    
    # 初始化CTA引擎
    cta_engine.init_engine()
    print("✓ CTA引擎初始化完成")
    
    # 添加策略
    strategy_setting = {
        "fast_window": 10,
        "slow_window": 30,
        "fixed_size": 1,
        "sl_percent": 0.02,
        "tp_percent": 0.04
    }
    
    strategy_name = "MaCross_IF888"
    vt_symbol = "IF888.CFFEX"
    
    cta_engine.add_strategy(
        MaCrossStrategy,
        strategy_name,
        vt_symbol,
        strategy_setting
    )
    print(f"✓ 策略已添加: {strategy_name} on {vt_symbol}")
    
    # 订阅行情（重要！）
    from vnpy.trader.object import SubscribeRequest
    from vnpy.trader.constant import Exchange
    
    subscribe_req = SubscribeRequest(
        symbol="IF888",
        exchange=Exchange.CFFEX
    )
    main_engine.subscribe(subscribe_req, "CTP")
    print(f"✓ 已订阅行情: {vt_symbol}")
    
    # 初始化策略
    cta_engine.init_strategy(strategy_name)
    print("✓ 策略初始化完成")
    
    # 启动策略
    cta_engine.start_strategy(strategy_name)
    print("✓ 策略已启动")
    
    print("\n" + "=" * 60)
    print("实盘交易系统运行中...")
    print("=" * 60)
    print("\n提示：")
    print("1. 策略将根据实时行情自动交易")
    print("2. 所有交易都是真实的，涉及真实资金")
    print("3. 请密切监控策略运行状态")
    print("4. 按Ctrl+C停止策略并退出\n")
    
    # 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止策略...")
        cta_engine.stop_strategy(strategy_name)
        main_engine.close()
        print("系统已关闭")


if __name__ == "__main__":
    main()

