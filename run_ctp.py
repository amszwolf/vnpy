"""
VeighNa Trader - CTP Gateway 完整启动脚本
根据 gateway.md 文档配置，自动加载CTP账号
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp
from vnpy.trader.utility import TEMP_DIR, load_json
import time


def load_ctp_configs():
    """
    加载所有CTP账号配置文件
    返回: 账号配置列表
    """
    configs = []
    
    if not TEMP_DIR.exists():
        return configs
    
    # 查找所有CTP配置文件
    # connect_ctp.json 或 connect_ctp_账号名.json
    config_files = list(TEMP_DIR.glob("connect_ctp*.json"))
    
    for config_file in config_files:
        try:
            config = load_json(config_file.name)
            if config and config.get("用户名"):  # 确保配置有效
                # 从文件名提取账号名称
                if config_file.name == "connect_ctp.json":
                    account_name = "CTP"
                else:
                    # connect_ctp_账号1.json -> 账号1
                    account_name = config_file.name.replace("connect_ctp_", "").replace(".json", "")
                    account_name = f"CTP_{account_name}"
                
                configs.append({
                    "filename": config_file.name,
                    "account_name": account_name,
                    "setting": config
                })
                print(f"  ✓ 找到CTP配置: {config_file.name} -> {account_name}")
        except Exception as e:
            print(f"  ✗ 读取配置失败 {config_file.name}: {e}")
    
    return configs


def main():
    """启动VeighNa Trader with CTP Gateway"""
    print("=" * 60)
    print("VeighNa Trader - CTP Gateway 启动")
    print("=" * 60)
    
    # 1. 检查并导入CTP Gateway
    print("\n[1/6] 检查CTP Gateway模块...")
    ctp_available = False
    CtpGateway = None
    try:
        from vnpy_ctp import CtpGateway
        print("✓ vnpy_ctp 模块已安装")
        ctp_available = True
    except ImportError:
        print("⚠ vnpy_ctp 模块未安装")
        print("  UI界面仍会启动，但无法使用CTP Gateway功能")
        print("\n安装说明：")
        print("  vnpy_ctp需要C++编译器，Windows上需要安装Visual Studio Build Tools")
        print("  或者使用预编译的wheel包（如果有）")
        print("  安装命令: pip install vnpy_ctp")
    
    # 2. 加载账号配置
    print("\n[2/6] 加载CTP账号配置...")
    configs = load_ctp_configs()
    if configs:
        print(f"✓ 成功加载 {len(configs)} 个CTP账号配置")
        for config in configs:
            username = config["setting"].get("用户名", "N/A")
            broker_id = config["setting"].get("经纪商代码", "N/A")
            print(f"  - {config['account_name']}: 用户名={username}, 经纪商={broker_id}")
    else:
        print("⚠ 未找到CTP账号配置文件")
        print(f"  配置文件位置: {TEMP_DIR}")
        print("  请先运行 add_accounts.py 添加账号，或手动创建配置文件")
        print("\n配置文件格式示例（connect_ctp.json）：")
        print("""
{
    "用户名": "您的用户名",
    "密码": "您的密码",
    "经纪商代码": "9999",
    "交易服务器": "tcp://180.168.146.187:10130",
    "行情服务器": "tcp://180.168.146.187:10131",
    "产品名称": "",
    "授权编码": ""
}
        """)
    
    # 3. 创建Qt应用
    print("\n[3/6] 创建Qt应用...")
    qapp = create_qapp()
    print("✓ Qt应用创建成功")
    
    # 4. 创建事件引擎
    print("\n[4/6] 创建事件引擎...")
    event_engine = EventEngine()
    print("✓ 事件引擎创建成功")
    
    # 5. 创建主引擎
    print("\n[5/6] 创建主引擎...")
    main_engine = MainEngine(event_engine)
    print("✓ 主引擎创建成功")
    
    # 6. 添加CTP Gateway
    print("\n[6/6] 注册CTP Gateway...")
    if ctp_available:
        if configs:
            # 为每个账号创建独立的Gateway实例
            for config in configs:
                account_name = config["account_name"]
                if account_name not in main_engine.get_all_gateway_names():
                    main_engine.add_gateway(CtpGateway, account_name)
                    print(f"  ✓ 已注册Gateway: {account_name}")
        else:
            # 如果没有配置，至少添加一个默认的CTP Gateway
            main_engine.add_gateway(CtpGateway)
            print("  ✓ 已注册默认CTP Gateway（可在GUI中手动配置）")
    else:
        print("  ⚠ 跳过CTP Gateway注册（模块未安装）")
    
    # 7. 创建主窗口
    print("\n创建主窗口...")
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    print("✓ 主窗口创建成功")
    
    # 8. 自动连接账号
    if configs and ctp_available:
        print("\n" + "=" * 60)
        print("自动连接CTP账号...")
        print("=" * 60)
        
        for config in configs:
            account_name = config["account_name"]
            setting = config["setting"]
            
            try:
                print(f"\n  → 正在连接: {account_name}")
                print(f"     用户名: {setting.get('用户名', 'N/A')}")
                print(f"     经纪商: {setting.get('经纪商代码', 'N/A')}")
                
                main_engine.connect(setting, account_name)
                time.sleep(1)  # 延迟1秒，避免连接过快
                
                print(f"  ✓ 连接请求已发送: {account_name}")
            except Exception as e:
                print(f"  ✗ 连接失败 {account_name}: {e}")
        
        print("\n✓ 所有账号连接请求已发送")
        print("  请查看VeighNa Trader的日志窗口确认连接状态")
    elif configs and not ctp_available:
        print("\n⚠ 找到账号配置，但CTP Gateway模块未安装，无法自动连接")
        print("  请先安装vnpy_ctp模块后再运行")
    
    print("\n" + "=" * 60)
    print("VeighNa Trader 已启动！")
    print("=" * 60)
    print("\n提示：")
    if configs:
        print(f"  - 已加载 {len(configs)} 个CTP账号配置")
        print("  - 账号已自动连接，请查看日志确认状态")
    else:
        print("  - 未找到账号配置")
        print("  - 请在GUI界面中点击【系统】->【连接CTP】手动配置")
    print("  - 按Ctrl+C或关闭窗口退出\n")
    
    # 9. 启动Qt事件循环
    qapp.exec()


if __name__ == "__main__":
    main()

