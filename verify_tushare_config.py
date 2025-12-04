"""
TuShare 数据源配置检查脚本（临时文件）
此文件已被其他脚本替代，保留仅用于兼容性

相关配置已转移到：
D:\01_OneDrive\N8TL\OneDrive - Neon Eight Management\10_Work\vnpy.hl\run\.vntrader
"""

from vnpy.trader.setting import SETTINGS

def verify_tushare():
    """验证 TuShare 配置"""
    datafeed_name = SETTINGS.get("datafeed.name", "")
    
    if datafeed_name == "tushare":
        print("✓ TuShare 数据源已配置")
        username = SETTINGS.get("datafeed.username", "")
        if username:
            print(f"  Token: {username[:10]}...")
        return True
    else:
        print("⚠ TuShare 数据源未配置")
        return False


if __name__ == "__main__":
    verify_tushare()

