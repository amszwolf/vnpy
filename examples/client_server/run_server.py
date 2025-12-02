from time import sleep
from threading import Event as ThreadEvent

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp
from vnpy.trader.event import EVENT_LOG, EVENT_ACCOUNT
from vnpy.trader.object import LogData, AccountData

# Try to import CTP Gateway (optional, requires C++ compiler)
try:
    from vnpy_ctp import CtpGateway  # type: ignore
    CTP_AVAILABLE = True
except ImportError:
    CTP_AVAILABLE = False
    CtpGateway = None  # type: ignore
    print("警告: vnpy_ctp 模块未安装，CTP Gateway 功能不可用。")
    print("如需使用CTP Gateway，请先安装: pip install vnpy_ctp")
    print("注意: vnpy_ctp 需要 C++ 编译器（Windows上需要 Visual Studio Build Tools）")
    print("")

try:
    from vnpy_rpcservice import RpcServiceApp  # type: ignore
    from vnpy_rpcservice.rpc_service.engine import RpcEngine, EVENT_RPC_LOG  # type: ignore
    RPC_AVAILABLE = True
except ImportError:
    RPC_AVAILABLE = False
    RpcServiceApp = None  # type: ignore
    RpcEngine = None  # type: ignore
    EVENT_RPC_LOG = None  # type: ignore
    print("错误: vnpy_rpcservice 模块未安装，RPC服务功能不可用。")
    print("请先安装: pip install vnpy_rpcservice")
    raise


def main_ui() -> None:
    """"""
    if not RPC_AVAILABLE:
        print("错误: RPC服务模块未安装，无法启动。")
        return
    
    qapp = create_qapp()

    event_engine = EventEngine()

    main_engine = MainEngine(event_engine)

    if CTP_AVAILABLE:
        main_engine.add_gateway(CtpGateway)
    else:
        print("提示: 由于 vnpy_ctp 未安装，未加载CTP Gateway。")
        print("      RPC服务仍可运行，但无法连接CTP接口。")
    
    main_engine.add_app(RpcServiceApp)

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()


def process_log_event(event: Event) -> None:
    """"""
    log: LogData = event.data
    msg: str = f"{log.time}\t{log.msg}"
    print(msg)


# 全局变量用于跟踪登录状态
login_status = {"success": False, "error": None, "account_received": ThreadEvent()}


def process_account_event(event: Event) -> None:
    """处理账户事件，表示登录成功"""
    account: AccountData = event.data
    if not login_status["success"]:
        login_status["success"] = True
        login_status["account_received"].set()
        print(f"\n{'='*60}")
        print(f"✓ CTP登录成功！")
        print(f"  账户ID: {account.accountid}")
        print(f"  账户余额: {account.balance:,.2f}")
        print(f"  可用资金: {account.available:,.2f}")
        print(f"{'='*60}\n")


def check_login_status(event_engine: EventEngine, gateway_name: str, timeout: int = 10) -> bool:
    """
    检查登录状态
    返回: True表示登录成功，False表示登录失败
    """
    global login_status
    
    # 重置状态
    login_status = {"success": False, "error": None, "account_received": ThreadEvent()}
    
    # 注册账户事件监听器
    event_engine.register(EVENT_ACCOUNT, process_account_event)
    
    # 注册日志事件监听器，检查错误信息
    def check_error_log(event: Event):
        log: LogData = event.data
        if log.gateway_name == gateway_name:
            msg_lower = log.msg.lower()
            # 检查常见的错误关键词
            error_keywords = ["错误", "失败", "error", "failed", "拒绝", "reject", "认证失败", "登录失败", "认证", "auth"]
            if any(keyword in msg_lower for keyword in error_keywords):
                if not login_status["success"] and not login_status["error"]:
                    login_status["error"] = log.msg
                    login_status["account_received"].set()  # 触发事件，结束等待
    
    event_engine.register(EVENT_LOG, check_error_log)
    
    # 等待登录结果（最多等待timeout秒）
    print(f"\n等待登录结果（最多{timeout}秒）...")
    received = login_status["account_received"].wait(timeout=timeout)
    
    # 取消注册事件监听器
    event_engine.unregister(EVENT_ACCOUNT, process_account_event)
    event_engine.unregister(EVENT_LOG, check_error_log)
    
    if login_status["success"]:
        return True
    elif login_status["error"]:
        print(f"\n{'='*60}")
        print(f"✗ CTP登录失败")
        print(f"  错误信息: {login_status['error']}")
        print(f"{'='*60}\n")
        return False
    else:
        print(f"\n{'='*60}")
        print(f"✗ CTP登录超时（{timeout}秒内未收到账户信息）")
        print(f"  可能的原因：")
        print(f"    1. 用户名或密码错误")
        print(f"    2. 服务器地址不正确")
        print(f"    3. 网络连接问题")
        print(f"    4. 账号未激活或已过期")
        print(f"{'='*60}\n")
        return False


def main_terminal() -> None:
    """"""
    if not RPC_AVAILABLE:
        print("错误: RPC服务模块未安装，无法启动。")
        return
    
    if not CTP_AVAILABLE:
        print("错误: vnpy_ctp 模块未安装，无法连接CTP接口。")
        print("请先安装 vnpy_ctp: pip install vnpy_ctp")
        print("注意: vnpy_ctp 需要 C++ 编译器（Windows上需要 Visual Studio Build Tools）")
        return
    
    event_engine: EventEngine = EventEngine()
    event_engine.register(EVENT_LOG, process_log_event)
    event_engine.register(EVENT_RPC_LOG, process_log_event)

    main_engine: MainEngine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)
    rpc_engine: RpcEngine = main_engine.add_app(RpcServiceApp)

    setting: dict[str, str] = {
        "用户名": "144632",
        "密码": "983311",
        "经纪商代码": "9999",
        "交易服务器": "180.168.146.187:10101",
        "行情服务器": "180.168.146.187:10111",
        "产品名称": "simnow_client_test",
        "授权编码": "0000000000000000",
        "产品信息": ""
    }
    
    print(f"\n{'='*60}")
    print("正在连接CTP服务器...")
    print(f"  用户名: {setting['用户名']}")
    print(f"  经纪商代码: {setting['经纪商代码']}")
    print(f"  交易服务器: {setting['交易服务器']}")
    print(f"  行情服务器: {setting['行情服务器']}")
    print(f"{'='*60}")
    
    # 发起连接
    main_engine.connect(setting, "CTP")
    
    # 检查登录状态
    login_success = check_login_status(event_engine, "CTP", timeout=10)
    
    if not login_success:
        print("登录失败，RPC服务将无法正常工作。")
        print("请检查账号配置后重新运行。")
        return
    
    print("CTP连接成功，启动RPC服务...")

    rep_address: str = "tcp://127.0.0.1:2014"
    pub_address: str = "tcp://127.0.0.1:4102"
    rpc_engine.start(rep_address, pub_address)

    while True:
        sleep(1)


if __name__ == "__main__":
    # Run in GUI mode
    # main_ui()

    # Run in CLI mode
    main_terminal()
