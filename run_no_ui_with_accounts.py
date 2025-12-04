"""
VeighNa Trader 无UI版本 - 自动加载账号配置
结合run.py和run_with_accounts.py的功能
支持自动加载账号配置、CTA策略等
"""

import multiprocessing
import sys
import time
import importlib.util
from datetime import datetime, time as dt_time
from pathlib import Path

from vnpy.event import EventEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.trader.logger import INFO, logger
from vnpy.trader.utility import TEMP_DIR, load_json


# 日志配置
SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True
SETTINGS["log.file"] = True


# 中国期货市场交易时间段
DAY_START = dt_time(8, 45)
DAY_END = dt_time(15, 0)
NIGHT_START = dt_time(20, 45)
NIGHT_END = dt_time(2, 45)


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
            logger.info(f"找到配置: {config_file.name}")
    
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


def add_ctp_gateway(main_engine: MainEngine, configs: list):
    """添加CTP Gateway并注册所有账号"""
    if not is_module_installed("vnpy_ctp"):
        logger.warning("vnpy_ctp 模块未安装，安装命令: pip install vnpy_ctp")
        return None
    
    from vnpy_ctp import CtpGateway
    logger.info("检测到 vnpy_ctp 模块")
    
    # 为每个账号创建Gateway实例
    if configs:
        for config in configs:
            gateway_name = config["gateway_name"]
            # 检查是否已添加
            if gateway_name not in main_engine.get_all_gateway_names():
                main_engine.add_gateway(CtpGateway, gateway_name)
                logger.info(f"已添加Gateway: {gateway_name}")
    else:
        # 如果没有配置，至少添加一个默认的CTP Gateway
        if "CTP" not in main_engine.get_all_gateway_names():
            main_engine.add_gateway(CtpGateway)
            logger.info("已添加默认CTP Gateway")
    
    return CtpGateway


def prepare_ctp_setting(setting: dict) -> dict:
    """
    准备CTP连接配置，补充缺失的字段
    """
    # 创建配置副本，避免修改原始配置
    prepared_setting = setting.copy()
    
    # 检查并补充缺失的字段
    if "柜台环境" not in prepared_setting:
        # 根据服务器地址判断：SimNow测试环境通常是10201/10211端口
        td_server = prepared_setting.get("交易服务器", "")
        if "10201" in td_server or "10211" in td_server:
            prepared_setting["柜台环境"] = "仿真"
        else:
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
        logger.warning("未找到任何账号配置文件，请先运行 add_accounts.py 添加账号配置")
        return
    
    logger.info(f"找到 {len(configs)} 个账号配置，开始连接...")
    
    for config in configs:
        gateway_name = config["gateway_name"]
        setting = config["setting"]
        
        # 检查是否已添加该Gateway
        if gateway_name not in main_engine.get_all_gateway_names():
            logger.warning(f"Gateway '{gateway_name}' 未注册，跳过连接")
            continue
        
        # 准备配置，补充缺失的字段
        prepared_setting = prepare_ctp_setting(setting)
        
        # 检查必要字段是否存在
        required_fields = ["用户名", "密码", "经纪商代码", "交易服务器", "行情服务器"]
        missing_fields = [field for field in required_fields if field not in prepared_setting]
        
        if missing_fields:
            logger.warning(f"Gateway '{gateway_name}' 配置不完整，缺少字段: {', '.join(missing_fields)}，跳过连接")
            continue
        
        logger.info(f"正在连接: {gateway_name}")
        main_engine.connect(prepared_setting, gateway_name)
        time.sleep(0.5)  # 短暂延迟，避免连接过快


def check_trading_period() -> bool:
    """检查当前是否在交易时间段内"""
    current_time = datetime.now().time()
    
    trading = False
    if (
        (current_time >= DAY_START and current_time <= DAY_END)
        or (current_time >= NIGHT_START)
        or (current_time <= NIGHT_END)
    ):
        trading = True
    
    return trading


def add_cta_strategy_app(main_engine: MainEngine):
    """添加CTA策略应用"""
    if not is_module_installed("vnpy_ctastrategy"):
        logger.warning("vnpy_ctastrategy 模块未安装，安装命令: pip install vnpy_ctastrategy")
        return None
    
    from vnpy_ctastrategy import CtaStrategyApp, CtaEngine
    from vnpy_ctastrategy.base import EVENT_CTA_LOG
    
    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)
    logger.info("CTA策略模块加载成功")
    
    # 注册CTA日志事件
    log_engine: LogEngine = main_engine.get_engine("log")  # type: ignore
    main_engine.event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    logger.info("注册CTA日志事件监听")
    
    return cta_engine


def run_child() -> None:
    """
    在子进程中运行
    """
    logger.info("=" * 60)
    logger.info("VeighNa Trader - 无UI版本（子进程）")
    logger.info("=" * 60)
    
    # 1. 加载账号配置
    logger.info("\n[1/6] 加载账号配置...")
    configs = load_account_configs()
    if configs:
        logger.info(f"成功加载 {len(configs)} 个账号配置")
    else:
        logger.warning("未找到账号配置文件")
        logger.info(f"配置文件位置: {TEMP_DIR}")
        logger.info("请先运行 add_accounts.py 添加账号")
    
    # 2. 创建事件引擎
    logger.info("\n[2/6] 创建事件引擎...")
    event_engine: EventEngine = EventEngine()
    logger.info("事件引擎创建成功")
    
    # 3. 创建主引擎
    logger.info("\n[3/6] 创建主引擎...")
    main_engine: MainEngine = MainEngine(event_engine)
    logger.info("主引擎创建成功")
    
    # 4. 添加CTP Gateway
    logger.info("\n[4/6] 注册CTP Gateway...")
    ctp_gateway = add_ctp_gateway(main_engine, configs)
    
    # 5. 添加CTA策略应用（可选）
    logger.info("\n[5/6] 加载CTA策略模块...")
    cta_engine = add_cta_strategy_app(main_engine)
    
    # 6. 自动连接账号
    logger.info("\n[6/6] 自动连接账号...")
    if ctp_gateway and configs:
        auto_connect_accounts(main_engine, configs)
        logger.info("账号连接完成，等待连接建立...")
        time.sleep(10)  # 等待连接建立
    else:
        logger.warning("未找到CTP Gateway或账号配置，跳过自动连接")
    
    # 7. 初始化CTA策略（如果已加载）
    if cta_engine:
        logger.info("\n初始化CTA策略...")
        cta_engine.init_engine()
        logger.info("CTA策略引擎初始化完成")
        
        cta_engine.init_all_strategies()
        logger.info("等待策略初始化...")
        time.sleep(60)  # 留足够时间完成策略初始化
        logger.info("CTA策略全部初始化完成")
        
        cta_engine.start_all_strategies()
        logger.info("CTA策略全部启动")
    
    # 8. 主循环
    logger.info("\n" + "=" * 60)
    logger.info("系统运行中，按Ctrl+C退出")
    logger.info("=" * 60)
    
    while True:
        time.sleep(10)
        
        trading = check_trading_period()
        if not trading:
            logger.info("当前不在交易时间段，关闭子进程")
            main_engine.close()
            sys.exit(0)


def run_parent() -> None:
    """
    在父进程中运行（守护进程）
    """
    print("=" * 60)
    print("VeighNa Trader - 无UI版本守护进程")
    print("=" * 60)
    print("\n启动CTA策略守护父进程")
    print("系统将根据交易时间段自动启动/关闭子进程")
    print("\n交易时间段：")
    print(f"  日盘: {DAY_START.strftime('%H:%M')} - {DAY_END.strftime('%H:%M')}")
    print(f"  夜盘: {NIGHT_START.strftime('%H:%M')} - {NIGHT_END.strftime('%H:%M')}")
    print("\n按Ctrl+C退出守护进程\n")
    
    child_process = None
    
    while True:
        trading = check_trading_period()
        
        # 在交易时间段启动子进程
        if trading and child_process is None:
            print("检测到交易时间段，启动子进程...")
            child_process = multiprocessing.Process(target=run_child)
            child_process.start()
            print("子进程启动成功")
        
        # 非交易时间段则退出子进程
        if not trading and child_process is not None:
            if not child_process.is_alive():
                child_process = None
                print("子进程已关闭")
        
        time.sleep(5)


if __name__ == "__main__":
    # 检查是否直接运行子进程（用于调试）
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        run_child()
    else:
        run_parent()

