"""
VeighNa Trader 自动加载账号配置启动脚本
自动检测并加载.vntrader文件夹中的账号配置
"""

import time
import importlib.util
from pathlib import Path
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp
from vnpy.trader.utility import TEMP_DIR, load_json


def is_module_installed(module_name: str) -> bool:
    """检查模块是否已安装"""
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def load_account_configs():
    """
    加载所有账号配置文件
    返回: 账号配置列表
    """
    configs = []
    
    if not TEMP_DIR.exists():
        return configs
    
    # 查找所有connect_*.json文件
    config_files = list(TEMP_DIR.glob("connect_*.json"))
    
    for config_file in config_files:
        config = load_json(config_file.name)
        if config:  # 确保配置不为空
            gateway_name = _extract_gateway_name(config_file.name)
            configs.append({
                "filename": config_file.name,
                "gateway_name": gateway_name,
                "setting": config
            })
            print(f"  ✓ 找到配置: {config_file.name}")
    
    return configs


def _extract_gateway_name(filename: str) -> str:
    """
    从配置文件名提取Gateway名称
    例如: connect_ctp.json -> CTP
         connect_ctp_账号1.json -> CTP_账号1
    """
    # 移除connect_前缀和.json后缀
    name = filename.replace("connect_", "").replace(".json", "")
    
    # 如果包含下划线，提取Gateway类型和账号名
    if "_" in name:
        parts = name.split("_", 1)
        gateway_type = parts[0].upper()
        account_name = parts[1]
        return f"{gateway_type}_{account_name}"
    else:
        return name.upper()


def add_data_manager_app(main_engine: MainEngine):
    """添加DataManager应用"""
    if not is_module_installed("vnpy_datamanager"):
        print("  ⚠ DataManager 未安装 (pip install vnpy_datamanager)")
        return False
    
    from vnpy_datamanager import DataManagerApp
    engine = main_engine.add_app(DataManagerApp)
    
    # 验证engine是否已创建
    engine_name = engine.engine_name if engine else None
    if engine_name and main_engine.get_engine(engine_name):
        print(f"  ✓ DataManager - 数据管理模块（数据查看、导入、导出）")
        print(f"    Engine名称: {engine_name}")
        return True
    else:
        print("  ⚠ DataManager Engine 创建失败")
        return False


def add_data_recorder_app(main_engine: MainEngine):
    """添加DataRecorder应用"""
    if not is_module_installed("vnpy_datarecorder"):
        print("  ⚠ DataRecorder 未安装 (pip install vnpy_datarecorder)")
        return False
    
    from vnpy_datarecorder import DataRecorderApp
    engine = main_engine.add_app(DataRecorderApp)
    
    # 验证engine是否已创建
    engine_name = engine.engine_name if engine else None
    if engine_name and main_engine.get_engine(engine_name):
        print(f"  ✓ DataRecorder - 数据采集模块（实时行情录制）")
        print(f"    Engine名称: {engine_name}")
        return True
    else:
        print("  ⚠ DataRecorder Engine 创建失败")
        return False


def add_chart_wizard_app(main_engine: MainEngine):
    """添加ChartWizard应用"""
    if not is_module_installed("vnpy_chartwizard"):
        print("  ⚠ ChartWizard 未安装 (pip install vnpy_chartwizard)")
        return False
    
    from vnpy_chartwizard import ChartWizardApp
    engine = main_engine.add_app(ChartWizardApp)
    
    # 验证engine是否已创建
    engine_name = engine.engine_name if engine else None
    if engine_name and main_engine.get_engine(engine_name):
        print(f"  ✓ ChartWizard - K线图表模块（实时K线显示）")
        print(f"    Engine名称: {engine_name}")
        return True
    else:
        print("  ⚠ ChartWizard Engine 创建失败")
        return False


def load_data_apps(main_engine: MainEngine):
    """
    逐个加载数据相关的应用模块
    返回: 已加载的模块列表
    """
    modules_loaded = []
    
    print("\n  正在加载数据相关应用模块...")
    
    # 逐个添加app并验证
    if add_data_manager_app(main_engine):
        modules_loaded.append("DataManager (数据管理)")
    
    if add_data_recorder_app(main_engine):
        modules_loaded.append("DataRecorder (数据采集)")
    
    if add_chart_wizard_app(main_engine):
        modules_loaded.append("ChartWizard (K线图表)")
    
    return modules_loaded


def add_ctp_gateway(main_engine: MainEngine, configs: list):
    """添加CTP Gateway并注册所有账号"""
    if not is_module_installed("vnpy_ctp"):
        print("  ⚠ vnpy_ctp 模块未安装")
        print("    安装命令: pip install vnpy_ctp")
        return None
    
    from vnpy_ctp import CtpGateway
    print("  ✓ 检测到 vnpy_ctp 模块")
    
    # 为每个账号创建Gateway实例
    if configs:
        for config in configs:
            gateway_name = config["gateway_name"]
            # 检查是否已添加
            if gateway_name not in main_engine.get_all_gateway_names():
                main_engine.add_gateway(CtpGateway, gateway_name)
                print(f"  ✓ 已添加Gateway: {gateway_name}")
    else:
        # 如果没有配置，至少添加一个默认的CTP Gateway
        if "CTP" not in main_engine.get_all_gateway_names():
            main_engine.add_gateway(CtpGateway)
            print("  ✓ 已添加默认CTP Gateway")
    
    return CtpGateway


def prepare_ctp_setting(setting: dict) -> dict:
    """
    准备CTP连接配置，补充缺失的字段
    """
    # 创建配置副本，避免修改原始配置
    prepared_setting = setting.copy()
    
    # 检查并补充缺失的字段
    # 如果缺少"柜台环境"，根据服务器地址判断或使用默认值
    if "柜台环境" not in prepared_setting:
        # 根据服务器地址判断：SimNow测试环境通常是10201/10211端口
        td_server = prepared_setting.get("交易服务器", "")
        if "10201" in td_server or "10211" in td_server:
            prepared_setting["柜台环境"] = "仿真"
        else:
            # 默认使用实盘环境
            prepared_setting["柜台环境"] = "实盘"
    
    # 确保其他可选字段存在
    if "产品名称" not in prepared_setting:
        prepared_setting["产品名称"] = ""
    
    if "授权编码" not in prepared_setting:
        prepared_setting["授权编码"] = ""
    
    if "产品信息" not in prepared_setting:
        prepared_setting["产品信息"] = ""
    
    return prepared_setting


def auto_connect_accounts(main_engine: MainEngine, configs: list):
    """
    自动连接所有配置的账号
    """
    if not configs:
        print("\n⚠ 未找到任何账号配置文件")
        print("  请先运行 add_accounts.py 添加账号配置")
        return
    
    print(f"\n[自动连接] 找到 {len(configs)} 个账号配置")
    
    for config in configs:
        gateway_name = config["gateway_name"]
        setting = config["setting"]
        
        # 检查是否已添加该Gateway
        if gateway_name not in main_engine.get_all_gateway_names():
            print(f"  ⚠ Gateway '{gateway_name}' 未注册，跳过连接")
            continue
        
        # 准备配置，补充缺失的字段
        prepared_setting = prepare_ctp_setting(setting)
        
        # 检查必要字段是否存在
        required_fields = ["用户名", "密码", "经纪商代码", "交易服务器", "行情服务器"]
        missing_fields = [field for field in required_fields if field not in prepared_setting]
        
        if missing_fields:
            print(f"  ⚠ Gateway '{gateway_name}' 配置不完整，缺少字段: {', '.join(missing_fields)}")
            print(f"     跳过连接")
            continue
        
        print(f"  → 正在连接: {gateway_name}")
        main_engine.connect(prepared_setting, gateway_name)
        time.sleep(0.5)  # 短暂延迟，避免连接过快


def main():
    """启动VeighNa Trader并自动加载账号"""
    print("=" * 60)
    print("VeighNa Trader - 自动加载账号版本")
    print("=" * 60)
    
    # 1. 加载账号配置
    print("\n[1/7] 加载账号配置...")
    configs = load_account_configs()
    if configs:
        print(f"✓ 成功加载 {len(configs)} 个账号配置")
    else:
        print("⚠ 未找到账号配置文件")
        print(f"  配置文件位置: {TEMP_DIR}")
        print("  请先运行 add_accounts.py 添加账号")
    
    # 2. 创建Qt应用
    print("\n[2/7] 创建Qt应用...")
    qapp = create_qapp()
    print("✓ Qt应用创建成功")
    
    # 3. 创建事件引擎
    print("\n[3/7] 创建事件引擎...")
    event_engine = EventEngine()
    print("✓ 事件引擎创建成功")
    
    # 4. 创建主引擎
    print("\n[4/7] 创建主引擎...")
    main_engine = MainEngine(event_engine)
    print("✓ 主引擎创建成功")
    
    # 5. 添加CTP Gateway
    print("\n[5/7] 注册CTP Gateway...")
    ctp_gateway = add_ctp_gateway(main_engine, configs)
    
    # 6. 加载数据相关的应用模块
    print("\n[6/7] 加载数据相关应用模块...")
    modules_loaded = load_data_apps(main_engine)
    if modules_loaded:
        print(f"\n✓ 成功加载 {len(modules_loaded)} 个数据相关模块")
    else:
        print("\n⚠ 未加载任何数据模块")
        print("  安装命令:")
        print("    pip install vnpy_datamanager vnpy_datarecorder vnpy_chartwizard")
    
    # 7. 创建主窗口
    print("\n[7/7] 创建主窗口...")
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    print("✓ 主窗口创建成功")
    
    # 8. 自动连接账号（如果已安装Gateway且有配置）
    if ctp_gateway and configs:
        print("\n" + "=" * 60)
        print("自动连接账号...")
        print("=" * 60)
        auto_connect_accounts(main_engine, configs)
        print("\n✓ 账号连接完成")
    
    print("\n" + "=" * 60)
    print("VeighNa Trader 已启动！")
    print("=" * 60)
    print("\n【功能模块】")
    print("=" * 60)
    if modules_loaded:
        print("已加载的数据相关模块：")
        for module in modules_loaded:
            print(f"  ✓ {module}")
    else:
        print("  ⚠ 未加载任何数据模块")
        print("  要使用数据功能，请安装：")
        print("    pip install vnpy_datamanager vnpy_datarecorder vnpy_chartwizard")
    
    print("\n【使用说明】")
    print("=" * 60)
    print("数据相关功能：")
    print("  - 数据管理：点击【功能】->【数据管理】查看、导入、导出历史数据")
    print("  - 数据采集：点击【功能】->【行情记录】录制实时Tick和K线数据")
    print("  - K线图表：点击【功能】->【K线图表】查看实时和历史K线图")
    print("  - 合约查看：点击【系统】->【合约查询】查看所有可用合约")
    
    if configs:
        print(f"\n账号配置：")
        print(f"  - 已加载 {len(configs)} 个账号配置")
        if ctp_gateway:
            print("  - CTP Gateway已注册，账号已自动连接")
            print("  - 请查看日志确认连接状态")
        else:
            print("  - CTP Gateway未安装，请在GUI界面中手动连接账号")
    else:
        print("\n账号配置：")
        print("  - 未找到账号配置，请在GUI界面中手动配置")
        print("  - 或运行 add_accounts.py 添加账号")
    
    print("\n按Ctrl+C或关闭窗口退出\n")
    
    # 9. 启动Qt事件循环
    qapp.exec()


if __name__ == "__main__":
    main()
