"""
数据源配置检查脚本（临时文件）
此文件已被其他脚本替代，保留仅用于兼容性
"""

from vnpy.trader.setting import SETTINGS

def check_datafeed():
    """检查数据源配置"""
    datafeed_name = SETTINGS.get("datafeed.name", "")
    
    if not datafeed_name:
        print("⚠ 数据源未配置")
        return False
    
    print(f"✓ 数据源已配置: {datafeed_name}")
    return True


if __name__ == "__main__":
    check_datafeed()


