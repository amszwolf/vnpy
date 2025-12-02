"""
该程序使用VeighNa框架通过CTP接口连接到期货市场，并自动录制指定交易所和品种的行情数据。

适合初学者了解VeighNa框架的基本用法和数据录制流程。
"""

# 加载Python标准库
from logging import INFO
from time import sleep
from pathlib import Path

# ============================================================
# 设置自定义数据存储路径
# ============================================================
CUSTOM_DATA_DIR = Path(r"D:\Data\vnpy")
if not CUSTOM_DATA_DIR.exists():
    CUSTOM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ 创建数据目录: {CUSTOM_DATA_DIR}")

# 加载VeighNa核心框架
from vnpy.event import EventEngine, Event
from vnpy.trader.setting import SETTINGS
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.trader.object import ContractData
from vnpy.trader.constant import Exchange, Product
from vnpy.trader.event import EVENT_CONTRACT

# 修改VeighNa的数据目录路径
# 必须在数据库初始化之前修改
import vnpy.trader.utility as trader_utility
trader_utility.TRADER_DIR = CUSTOM_DATA_DIR
trader_utility.TEMP_DIR = CUSTOM_DATA_DIR

# 验证路径修改
print(f"✓ 数据存储路径已设置为: {CUSTOM_DATA_DIR}")
print(f"  验证: TEMP_DIR = {trader_utility.TEMP_DIR}")

# 加载VeighNa插件模块
from vnpy_ctp import CtpGateway
from vnpy_datarecorder import DataRecorderApp, RecorderEngine
from vnpy_datarecorder.engine import EVENT_RECORDER_LOG


# 开启日志记录功能
# 日志对于排查问题和监控系统运行状态非常重要
SETTINGS["log.active"] = True       # 激活日志功能
SETTINGS["log.level"] = INFO        # 设置日志级别为INFO，输出详细信息
SETTINGS["log.console"] = True      # 在控制台显示日志，方便实时查看


# CTP接口登录信息
# 以下使用的是SimNow模拟账户信息，初学者可以在SimNow官网申请
ctp_setting: dict[str, str] = {
    "用户名": "005442",                       # SimNow账户名
    "密码": "983311",                         # SimNow密码
    "经纪商代码": "9999",                     # SimNow经纪商代码固定为9999
    "交易服务器": "180.168.146.187:10201",    # SimNow交易服务器地址和端口
    "行情服务器": "180.168.146.187:10211",    # SimNow行情服务器地址和端口
    "产品名称": "simnow_client_test",         # 产品名称，用于区分不同的客户端
    "授权编码": "0000000000000000"            # 授权编码，SimNow模拟账户使用默认值即可
}


# 要录制数据的交易所列表
# 可以根据需要取消注释来添加更多交易所
recording_exchanges: list[Exchange] = [
    Exchange.CFFEX,          # 中国金融期货交易所
    Exchange.SHFE,         # 上海期货交易所
    Exchange.DCE,          # 大连商品交易所
    Exchange.CZCE,         # 郑州商品交易所
    # Exchange.GFEX,         # 广州期货交易所
    # Exchange.INE,          # 上海国际能源交易中心
]


# 要录制数据的品种类型
# 可以根据需要取消注释来添加更多品种
recording_products: list[Product] = [
    Product.FUTURES,        # 期货品种
    # Product.OPTION,       # 期权品种
]

# 要录制数据的合约代码前缀列表
# 合约代码前缀用于筛选特定品种，例如：
# - "IF" 表示沪深300股指期货（IF2506, IF2507等）
# - "IM" 表示中证2000股指期货（IM2506, IM2507等）
# - "OI" 表示菜籽油期货（OI2501, OI2502等）
# - "RB" 表示螺纹钢期货（RB2501, RB2502等）
# - "A" 表示豆1期货（A2501, A2502等）
# 如果 recording_symbols 为空列表 []，则录制所有符合交易所和品种类型的合约
recording_symbols: list[str] = [
    "IF",       # 沪深300股指期货
    "IM",       # 中证2000股指期货
    "OI",       # 菜籽油
    "RB",       # 螺纹钢
    "A",        # 豆1（大豆1号）
]


def run_recorder() -> None:
    """
    运行行情录制程序

    该函数是程序的主体，按照以下步骤工作：
    1. 创建VeighNa核心组件（事件引擎、主引擎）
    2. 添加交易接口和应用模块
    3. 设置数据录制规则
    4. 连接到交易所并开始录制数据
    """
    print("\n" + "=" * 60)
    print("启动数据录制程序")
    print("=" * 60)
    
    # 验证数据路径
    from vnpy.trader.utility import TEMP_DIR, get_file_path
    from vnpy.trader.setting import SETTINGS
    print(f"\n[配置信息]")
    print(f"  数据存储路径: {TEMP_DIR}")
    print(f"  数据库文件: {get_file_path(SETTINGS['database.database'])}")
    print(f"  筛选品种: {recording_symbols}")
    print(f"  筛选交易所: {[e.value for e in recording_exchanges]}")
    
    # 创建事件引擎，负责系统内各模块间的通信
    print(f"\n[1/5] 创建事件引擎...")
    event_engine: EventEngine = EventEngine()
    print(f"  ✓ 事件引擎创建成功")

    # 创建主引擎，管理系统功能模块，包括底层接口、上层应用等
    print(f"\n[2/5] 创建主引擎...")
    main_engine: MainEngine = MainEngine(event_engine)
    print(f"  ✓ 主引擎创建成功")

    # 添加CTP接口，连接到期货市场
    print(f"\n[3/5] 添加CTP Gateway...")
    main_engine.add_gateway(CtpGateway)
    print(f"  ✓ CTP Gateway 已注册")

    # 添加数据录制引擎，用于录制Tick行情入库
    print(f"\n[4/5] 添加数据录制引擎...")
    recorder_engine: RecorderEngine = main_engine.add_app(DataRecorderApp)
    print(f"  ✓ 数据录制引擎已加载")

    # 定义合约订阅函数
    def subscribe_data(event: Event) -> None:
        """
        处理合约推送并订阅行情

        当系统接收到合约信息后，根据预设的交易所和品种过滤条件，
        自动为符合条件的合约添加行情录制任务。

        参数:
            event: 包含合约信息的事件对象
        """
        # 从事件对象中获取合约数据
        contract: ContractData = event.data

        # 判断合约是否符合录制条件
        # 1. 检查交易所
        exchange_match = contract.exchange in recording_exchanges
        # 2. 检查品种类型
        product_match = contract.product in recording_products
        # 3. 检查合约代码前缀（如果 recording_symbols 不为空）
        symbol_match = True
        if recording_symbols:  # 如果指定了合约代码列表，则进行筛选
            # 提取合约代码的品种前缀
            # 期货合约代码格式：品种代码（1-2个字符）+ 年月（4个数字）
            # 例如：IF2506（IF是品种代码），RB2501（RB是品种代码），A2501（A是品种代码）
            # 先尝试匹配2个字符的前缀（如 IF, RB, OI, IM）
            symbol_prefix_2 = contract.symbol[:2] if len(contract.symbol) >= 2 else ""
            # 再尝试匹配1个字符的前缀（如 A）
            symbol_prefix_1 = contract.symbol[0] if len(contract.symbol) >= 1 else ""
            
            # 优先匹配2字符前缀，如果不在列表中，再匹配1字符前缀
            if symbol_prefix_2 in recording_symbols:
                symbol_match = True
            elif symbol_prefix_1 in recording_symbols:
                symbol_match = True
            else:
                symbol_match = False
        
        # 如果所有条件都满足，则添加录制任务
        if exchange_match and product_match and symbol_match:
            # 添加该合约的行情录制任务，vt_symbol是VeighNa中的唯一标识符，格式为"代码.交易所"
            print(f"开始录制: {contract.vt_symbol} ({contract.name})")
            recorder_engine.add_tick_recording(contract.vt_symbol)      # 录制Tick数据
            recorder_engine.add_bar_recording(contract.vt_symbol)       # 录制分钟K线

    # 注册合约事件处理函数，当有新合约信息推送时，会自动调用subscribe_data函数
    event_engine.register(EVENT_CONTRACT, subscribe_data)

    # 获取日志引擎并设置日志处理
    log_engine: LogEngine = main_engine.get_engine("log")

    def print_log(event: Event) -> None:
        """
        处理数据录制模块的日志事件

        将数据录制模块产生的日志信息输出到控制台和日志文件中，
        便于监控录制过程和排查问题。

        参数:
            event: 包含日志信息的事件对象
        """
        log_engine.logger.log(INFO, event.data)

    # 注册日志事件处理函数，当有新的日志推送时，会自动调用print_log函数
    event_engine.register(EVENT_RECORDER_LOG, print_log)

    # 连接CTP接口并登录，第一个参数是接口设置，第二个参数是接口名称
    print(f"\n[5/5] 连接CTP服务器...")
    print(f"  用户名: {ctp_setting['用户名']}")
    print(f"  经纪商代码: {ctp_setting['经纪商代码']}")
    print(f"  交易服务器: {ctp_setting['交易服务器']}")
    print(f"  行情服务器: {ctp_setting['行情服务器']}")
    main_engine.connect(ctp_setting, CtpGateway.default_name)
    print(f"  ✓ 连接请求已发送")

    # 等待30秒，CTP接口连接后需要一段时间来完成初始化
    print(f"\n等待CTP连接初始化（30秒）...")
    print(f"  正在查询合约信息...")
    sleep(30)
    print(f"  ✓ 初始化完成")

    # 提示用户程序已经开始运行，用户可以根据需要随时退出
    input(">>>>>> 高频行情数据录制已启动，正在记录数据。按回车键退出程序 <<<<<<")

    # 关闭主引擎实现安全退出，避免出现内存中未入库数据的丢失
    main_engine.close()


# Python程序的标准入口写法，直接运行此脚本时会执行run_recorder函数
if __name__ == "__main__":
    run_recorder()
