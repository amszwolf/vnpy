"""
添加期货账号配置工具
支持批量添加多个账号到VeighNa项目
"""

import json
from pathlib import Path
from vnpy.trader.utility import get_file_path, save_json, load_json


def add_ctp_account(
    account_name: str,
    username: str,
    password: str,
    broker_id: str,
    md_address: str,
    td_address: str,
    product_name: str = "",
    auth_code: str = ""
) -> None:
    """
    添加CTP账号配置（根据gateway.md文档格式）
    
    参数:
        account_name: 账号名称（用于区分多个账号，如"账号1"、"账号2"）
                     如果为空或"CTP"，则使用默认文件名connect_ctp.json
        username: 用户名
        password: 密码
        broker_id: 经纪商代码
        md_address: 行情服务器地址（格式：tcp://IP:端口）
        td_address: 交易服务器地址（格式：tcp://IP:端口）
        product_name: 产品名称（可选）
        auth_code: 授权编码（可选）
    """
    # CTP Gateway的配置文件名
    if not account_name or account_name.upper() == "CTP":
        filename = "connect_ctp.json"
    else:
        # 支持多个账号：使用不同的文件名
        filename = f"connect_ctp_{account_name}.json"
    
    # 构建配置字典（按照gateway.md文档的字段名）
    setting = {
        "用户名": username,
        "密码": password,
        "经纪商代码": broker_id,
        "交易服务器": td_address,
        "行情服务器": md_address,
        "产品名称": product_name,
        "授权编码": auth_code
    }
    
    # 保存配置
    save_json(filename, setting)
    
    print(f"✓ CTP账号配置已保存: {filename}")
    print(f"  用户名: {username}")
    print(f"  经纪商代码: {broker_id}")
    print(f"  交易服务器: {td_address}")
    print(f"  行情服务器: {md_address}")
    if product_name:
        print(f"  产品名称: {product_name}")
    if auth_code:
        print(f"  授权编码: {auth_code}")
    print()


def add_accounts_from_dict(accounts: list[dict]) -> None:
    """
    从字典列表批量添加账号
    
    参数:
        accounts: 账号信息列表，每个字典包含账号配置信息
    """
    for i, account in enumerate(accounts, 1):
        account_name = account.get("account_name", f"账号{i}")
        
        # 根据gateway_type选择不同的添加方法
        gateway_type = account.get("gateway_type", "CTP").upper()
        
        if gateway_type == "CTP":
            add_ctp_account(
                account_name=account_name,
                username=account.get("username", ""),
                password=account.get("password", ""),
                broker_id=account.get("broker_id", ""),
                md_address=account.get("md_address", ""),
                td_address=account.get("td_address", ""),
                product_name=account.get("product_name", account.get("product_info", "")),
                auth_code=account.get("auth_code", "")
            )
        else:
            print(f"⚠ 暂不支持的Gateway类型: {gateway_type}")


def show_config_location() -> None:
    """显示配置文件位置"""
    from vnpy.trader.utility import TEMP_DIR
    print(f"配置文件存储位置: {TEMP_DIR}")
    print()


def list_all_accounts() -> None:
    """列出所有已配置的账号"""
    from vnpy.trader.utility import TEMP_DIR
    
    print("=" * 60)
    print("已配置的账号列表")
    print("=" * 60)
    
    config_files = list(TEMP_DIR.glob("connect_*.json"))
    
    if not config_files:
        print("未找到任何账号配置文件")
        return
    
    for config_file in config_files:
        print(f"\n配置文件: {config_file.name}")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 隐藏密码
                if "密码" in config:
                    config["密码"] = "******"
                print(json.dumps(config, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"  读取失败: {e}")
    
    print()


# ============================================================================
# 示例：添加账号配置
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VeighNa 账号配置工具")
    print("=" * 60)
    print()
    
    # 显示配置文件位置
    show_config_location()
    
    # ========================================================================
    # 在这里添加您的账号信息
    # ========================================================================
    # 请将C#代码中的账号信息转换为以下格式并填入
    
    accounts = [
        {
            "account_name": "账号1",  # 账号标识名称（用于多账号区分）
            "gateway_type": "CTP",    # Gateway类型
            "username": "您的用户名",  # 6位纯数字（实盘）或SimNow账号
            "password": "您的密码",    # 交易密码
            "broker_id": "9999",      # 经纪商代码（SimNow为9999，实盘为4位数字）
            "md_address": "tcp://180.168.146.187:10131",  # 行情服务器（格式：tcp://IP:端口）
            "td_address": "tcp://180.168.146.187:10130",  # 交易服务器（格式：tcp://IP:端口）
            "product_name": "",       # 产品名称（可选）
            "auth_code": ""           # 授权编码（可选）
        },
        # 添加更多账号示例：
        # {
        #     "account_name": "账号2",
        #     "gateway_type": "CTP",
        #     "username": "789012",
        #     "password": "your_password",
        #     "broker_id": "9999",
        #     "md_address": "tcp://180.168.146.187:10131",
        #     "td_address": "tcp://180.168.146.187:10130",
        #     "product_name": "",
        #     "auth_code": ""
        # },
    ]
    
    # 如果accounts列表为空，提示用户
    if not accounts or accounts[0].get("username") == "您的用户名":
        print("⚠ 请先编辑此脚本，填入您的账号信息")
        print()
        print("账号信息格式示例：")
        print("""
        accounts = [
            {
                "account_name": "账号1",
                "gateway_type": "CTP",
                "username": "123456",
                "password": "your_password",
                "broker_id": "9999",
                "md_address": "tcp://180.168.146.187:10131",
                "td_address": "tcp://180.168.146.187:10130",
                "product_info": "",
                "auth_code": ""
            },
            {
                "account_name": "账号2",
                "gateway_type": "CTP",
                "username": "789012",
                "password": "your_password",
                "broker_id": "9999",
                "md_address": "tcp://180.168.146.187:10131",
                "td_address": "tcp://180.168.146.187:10130",
                "product_info": "",
                "auth_code": ""
            }
        ]
        """)
    else:
        # 批量添加账号
        print("开始添加账号配置...")
        print()
        add_accounts_from_dict(accounts)
        print("=" * 60)
        print("✓ 所有账号配置完成！")
        print("=" * 60)
        print()
        print("使用方法：")
        print("1. 在VeighNa Trader中，点击【系统】->【连接CTP】")
        print("2. 如果配置了多个账号，需要修改run.py，为每个账号创建不同的Gateway实例")
        print()
    
    # 列出所有已配置的账号
    list_all_accounts()

