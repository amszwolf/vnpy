"""
VeighNa Trader - 完整功能启动脚本（包含行情显示模块）
自动加载CTP Gateway和所有可以显示行情的模块
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp
from vnpy.trader.utility import TEMP_DIR, load_json
import time


def load_ctp_configs():
    """加载所有CTP账号配置"""
    configs = []
    if not TEMP_DIR.exists():
        return configs
    
    config_files = list(TEMP_DIR.glob("connect_ctp*.json"))
    for config_file in config_files:
        try:
            config = load_json(config_file.name)
            if config and config.get("用户名"):
                if config_file.name == "connect_ctp.json":
                    account_name = "CTP"
                else:
                    account_name = config_file.name.replace("connect_ctp_", "").replace(".json", "")
                    account_name = f"CTP_{account_name}"
                
                configs.append({
                    "filename": config_file.name,
                    "account_name": account_name,
                    "setting": config
                })
        except Exception:
            pass
    return configs


def main():
    """启动VeighNa Trader with 完整功能模块"""
    print("=" * 60)
    print("VeighNa Trader - 完整功能版本（包含行情显示）")
    print("=" * 60)
    
    # 1. 检查CTP Gateway
    print("\n[1/7] 检查CTP Gateway模块...")
    ctp_available = False
    CtpGateway = None
    try:
        from vnpy_ctp import CtpGateway
        print("✓ vnpy_ctp 模块已安装")
        ctp_available = True
    except ImportError:
        print("⚠ vnpy_ctp 模块未安装（无法连接实盘接口）")
        print("  但可以使用其他功能模块")
    
    # 2. 加载账号配置
    print("\n[2/7] 加载CTP账号配置...")
    configs = load_ctp_configs()
    if configs:
        print(f"✓ 找到 {len(configs)} 个CTP账号配置")
    else:
        print("⚠ 未找到CTP账号配置")
    
    # 3. 创建Qt应用
    print("\n[3/7] 创建Qt应用...")
    qapp = create_qapp()
    print("✓ Qt应用创建成功")
    
    # 4. 创建事件引擎
    print("\n[4/7] 创建事件引擎...")
    event_engine = EventEngine()
    print("✓ 事件引擎创建成功")
    
    # 5. 创建主引擎
    print("\n[5/7] 创建主引擎...")
    main_engine = MainEngine(event_engine)
    print("✓ 主引擎创建成功")
    
    # 6. 添加Gateway
    print("\n[6/7] 注册Gateway...")
    if ctp_available:
        if configs:
            for config in configs:
                account_name = config["account_name"]
                if account_name not in main_engine.get_all_gateway_names():
                    main_engine.add_gateway(CtpGateway, account_name)
                    print(f"  ✓ 已注册Gateway: {account_name}")
        else:
            main_engine.add_gateway(CtpGateway)
            print("  ✓ 已注册默认CTP Gateway")
    else:
        print("  ⚠ 跳过CTP Gateway注册（模块未安装）")
    
    # 7. 添加功能模块（可以显示行情的模块）
    print("\n[7/7] 加载功能模块...")
    
    # 尝试加载各种可以显示行情的模块
    modules_loaded = []
    
    # ChartWizard - K线图表（需要连接接口）
    try:
        from vnpy_chartwizard import ChartWizardApp
        main_engine.add_app(ChartWizardApp)
        modules_loaded.append("ChartWizard (K线图表)")
        print("  ✓ ChartWizard - 实时K线图表模块")
    except ImportError:
        print("  ⚠ ChartWizard 未安装 (pip install vnpy_chartwizard)")
    
    # DataRecorder - 行情记录（需要连接接口）
    try:
        from vnpy_datarecorder import DataRecorderApp
        main_engine.add_app(DataRecorderApp)
        modules_loaded.append("DataRecorder (行情记录)")
        print("  ✓ DataRecorder - 行情记录模块")
    except ImportError:
        print("  ⚠ DataRecorder 未安装 (pip install vnpy_datarecorder)")
    
    # PaperAccount - 模拟交易（需要连接接口获取行情）
    try:
        from vnpy_paperaccount import PaperAccountApp
        main_engine.add_app(PaperAccountApp)
        modules_loaded.append("PaperAccount (模拟交易)")
        print("  ✓ PaperAccount - 本地模拟交易模块")
    except ImportError:
        print("  ⚠ PaperAccount 未安装 (pip install vnpy_paperaccount)")
    
    # CTA Strategy - 策略模块
    try:
        from vnpy_ctastrategy import CtaStrategyApp
        main_engine.add_app(CtaStrategyApp)
        modules_loaded.append("CtaStrategy (CTA策略)")
        print("  ✓ CtaStrategy - CTA策略模块")
    except ImportError:
        print("  ⚠ CtaStrategy 未安装 (pip install vnpy_ctastrategy)")
    
    # CTA Backtester - 回测模块
    try:
        from vnpy_ctabacktester import CtaBacktesterApp
        main_engine.add_app(CtaBacktesterApp)
        modules_loaded.append("CtaBacktester (回测)")
        print("  ✓ CtaBacktester - CTA回测模块")
    except ImportError:
        print("  ⚠ CtaBacktester 未安装 (pip install vnpy_ctabacktester)")
    
    # DataManager - 数据管理
    try:
        from vnpy_datamanager import DataManagerApp
        main_engine.add_app(DataManagerApp)
        modules_loaded.append("DataManager (数据管理)")
        print("  ✓ DataManager - 数据管理模块")
    except ImportError:
        print("  ⚠ DataManager 未安装 (pip install vnpy_datamanager)")
    
    # 8. 创建主窗口
    print("\n创建主窗口...")
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    print("✓ 主窗口创建成功")
    
    # 9. 自动连接账号
    if configs and ctp_available:
        print("\n" + "=" * 60)
        print("自动连接CTP账号...")
        print("=" * 60)
        
        for config in configs:
            account_name = config["account_name"]
            setting = config["setting"]
            
            try:
                print(f"\n  → 正在连接: {account_name}")
                main_engine.connect(setting, account_name)
                time.sleep(1)
                print(f"  ✓ 连接请求已发送: {account_name}")
            except Exception as e:
                print(f"  ✗ 连接失败: {e}")
        
        print("\n✓ 账号连接请求已发送")
        print("  等待连接成功后，可以在主界面订阅行情查看实时数据")
    
    # 10. 使用说明
    print("\n" + "=" * 60)
    print("VeighNa Trader 已启动！")
    print("=" * 60)
    print("\n【如何查看行情】")
    print("=" * 60)
    
    if ctp_available and configs:
        print("\n方法1：在主界面订阅行情（推荐）")
        print("  1. 等待CTP连接成功（查看日志窗口）")
        print("  2. 在【交易】组件中：")
        print("     - 选择交易所（如CFFEX）")
        print("     - 输入合约代码（如IF2506）")
        print("     - 按回车键订阅")
        print("  3. 订阅后，【行情】组件会显示实时Tick数据")
        print("  4. 点击【功能】->【K线图表】可以查看K线图")
        
        print("\n方法2：使用ChartWizard查看K线")
        print("  1. 点击【功能】->【K线图表】")
        print("  2. 输入合约代码（如rb2510.SHFE）")
        print("  3. 点击【新建图表】")
        
    elif ctp_available:
        print("\n⚠ CTP Gateway已加载，但未找到账号配置")
        print("  1. 点击【系统】->【连接CTP】手动配置")
        print("  2. 或运行 add_accounts.py 添加账号")
        print("  3. 连接成功后，按照方法1订阅行情")
        
    else:
        print("\n⚠ CTP Gateway未安装，无法连接实盘接口")
        print("  但可以使用以下功能：")
        print("  - 查看界面布局")
        print("  - 使用回测功能（如果有历史数据）")
        print("  - 查看数据管理功能")
        print("\n  要查看实时行情，需要：")
        print("  1. 安装 vnpy_ctp: pip install vnpy_ctp")
        print("  2. 配置账号信息")
        print("  3. 连接并订阅行情")
    
    print("\n【主界面组件说明】")
    print("=" * 60)
    print("  - 【行情】组件：显示订阅合约的实时Tick数据")
    print("  - 【交易】组件：手动下单和订阅行情")
    print("  - 【委托】组件：显示所有委托记录")
    print("  - 【成交】组件：显示所有成交记录")
    print("  - 【持仓】组件：显示当前持仓")
    print("  - 【资金】组件：显示账户资金")
    print("  - 【日志】组件：显示系统运行日志")
    
    print("\n【功能模块】")
    print("=" * 60)
    if modules_loaded:
        for module in modules_loaded:
            print(f"  ✓ {module}")
    else:
        print("  ⚠ 未加载任何功能模块")
        print("  请安装相应模块：")
        print("    pip install vnpy_chartwizard vnpy_datarecorder vnpy_paperaccount")
        print("    pip install vnpy_ctastrategy vnpy_ctabacktester vnpy_datamanager")
    
    print("\n按Ctrl+C或关闭窗口退出\n")
    
    # 11. 启动Qt事件循环
    qapp.exec()


if __name__ == "__main__":
    main()


