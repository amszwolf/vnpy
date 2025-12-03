"""
RQData数据源配置脚本
用于快速配置RQData数据源
"""

from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import TEMP_DIR
from pathlib import Path
import json

# RQData配置信息
RQDATA_USERNAME = "license"  # RQData固定为"license"
RQDATA_LICENSE = "DqAHX6WtHmnbcL5Haa6yFrJOJCElKSPTr339DvrbCY61LR1mXFy19fmsv5t6MPB25VjLSubzWjMRHa2Maqo6-35dAUC5SYe3QfNXXAAuNXt3O-xN-ooSKvFwgaJVOxUyR5q3MHGD26tldeymEiHOELLqDGtITB9GOezJGHtHLxM=doeF-hOW0dmHR2_BfG03DCSo7UAg4m_oRuUbJBAaWUN4tB9ZddEArW1SXOIkOSIVO9reBFIiGSvqbgpK9K4Fmrk_tAeVZtSMXmsXy8hSFrXSgZv8VFjs9w03_rKADTfHLFDNQ0x6Ls5dSvbfJFhNX6t087fVmQnX0B2jg57o5zI="

def configure_rqdata(username: str, license_key: str):
    """
    配置RQData数据源
    
    参数:
        username: RQData用户名（固定为"license"）
        license_key: 你的RQData License Key
    """
    print("=" * 60)
    print("配置RQData数据源")
    print("=" * 60)
    
    # 设置配置
    SETTINGS["datafeed.name"] = "rqdata"
    SETTINGS["datafeed.username"] = username
    SETTINGS["datafeed.password"] = license_key
    
    # 保存配置到文件
    setting_file = Path(TEMP_DIR) / "vt_setting.json"
    
    # 读取现有配置（如果有）
    existing_settings = {}
    if setting_file.exists():
        with open(setting_file, 'r', encoding='utf-8') as f:
            existing_settings = json.load(f)
    
    # 更新数据源配置
    existing_settings["datafeed.name"] = "rqdata"
    existing_settings["datafeed.username"] = username
    existing_settings["datafeed.password"] = license_key
    
    # 保存配置
    with open(setting_file, 'w', encoding='utf-8') as f:
        json.dump(existing_settings, f, ensure_ascii=False, indent=4)
    
    print(f"\n✓ 配置已保存到: {setting_file}")
    print("\n配置内容:")
    print(f"  datafeed.name: rqdata")
    print(f"  datafeed.username: {username}")
    print(f"  datafeed.password: {license_key[:20]}...（已隐藏）")
    print("\n✓ RQData数据源配置完成！")
    print("\n提示:")
    print("  - 重启VeighNa Trader使配置生效")
    print("  - 在DataManager中测试下载数据")
    print("  - RQData提供股票、期货、期权等多种数据")


if __name__ == "__main__":
    # 直接使用配置的License
    configure_rqdata(RQDATA_USERNAME, RQDATA_LICENSE)

