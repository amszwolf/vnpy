"""
VeighNa Trader 自动加载账号配置启动脚本
自动检测并加载.vntrader文件夹中的账号配置
"""

import time
from pathlib import Path
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp
from vnpy.trader.utility import TEMP_DIR, load_json


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
        try:
            config = load_json(config_file.name)
            if config:  # 确保配置不为空
                gateway_name = _extract_gateway_name(config_file.name)
                configs.append({
                    "filename": config_file.name,
                    "gateway_name": gateway_name,
                    "setting": config
                })
                print(f"  ✓ 找到配置: {config_file.name}")
        except Exception as e:
            print(f"  ✗ 读取配置失败 {config_file.name}: {e}")
    
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
            print(f"     请在代码中添加: main_engine.add_gateway(CtpGateway, '{gateway_name}')")
            continue
        
        try:
            print(f"  → 正在连接: {gateway_name}")
            main_engine.connect(setting, gateway_name)
            time.sleep(0.5)  # 短暂延迟，避免连接过快
        except Exception as e:
            print(f"  ✗ 连接失败 {gateway_name}: {e}")


def main():
    """启动VeighNa Trader并自动加载账号"""
    print("=" * 60)
    print("VeighNa Trader - 自动加载账号版本")
    print("=" * 60)
    
    # 1. 加载账号配置
    print("\n[1/5] 加载账号配置...")
    configs = load_account_configs()
    if configs:
        print(f"✓ 成功加载 {len(configs)} 个账号配置")
    else:
        print("⚠ 未找到账号配置文件")
        print(f"  配置文件位置: {TEMP_DIR}")
        print("  请先运行 add_accounts.py 添加账号")
    
    # 2. 创建Qt应用
    print("\n[2/5] 创建Qt应用...")
    qapp = create_qapp()
    print("✓ Qt应用创建成功")
    
    # 3. 创建事件引擎
    print("\n[3/5] 创建事件引擎...")
    event_engine = EventEngine()
    print("✓ 事件引擎创建成功")
    
    # 4. 创建主引擎
    print("\n[4/5] 创建主引擎...")
    main_engine = MainEngine(event_engine)
    print("✓ 主引擎创建成功")
    
    # 尝试导入CTP Gateway（如果已安装）
    try:
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
    except ImportError:
        print("  ⚠ 未安装 vnpy_ctp 模块")
        print("    安装命令: pip install vnpy_ctp")
        print("    或者使用GUI界面手动连接账号")
    
    # 5. 创建主窗口
    print("\n[5/5] 创建主窗口...")
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    print("✓ 主窗口创建成功")
    
    # 6. 自动连接账号（如果已安装Gateway）
    try:
        from vnpy_ctp import CtpGateway
        if configs:
            print("\n" + "=" * 60)
            print("自动连接账号...")
            print("=" * 60)
            auto_connect_accounts(main_engine, configs)
            print("\n✓ 账号连接完成")
    except ImportError:
        pass
    
    print("\n" + "=" * 60)
    print("VeighNa Trader 已启动！")
    print("=" * 60)
    print("\n提示：")
    if configs:
        print(f"  - 已加载 {len(configs)} 个账号配置")
        if "vnpy_ctp" in str(main_engine.get_all_gateway_names()):
            print("  - 账号已自动连接，请查看日志确认连接状态")
        else:
            print("  - 请在GUI界面中手动连接账号")
    else:
        print("  - 未找到账号配置，请在GUI界面中手动配置")
    print("  - 按Ctrl+C或关闭窗口退出\n")
    
    # 7. 启动Qt事件循环
    qapp.exec()


if __name__ == "__main__":
    main()

