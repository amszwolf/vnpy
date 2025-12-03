"""
TuShare数据源配置脚本
用于快速配置TuShare数据源
"""

from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import TEMP_DIR
from pathlib import Path
import json

# TuShare Token
TUSHARE_TOKEN = "017347e4bfb6dd1cdaefb03897f528d339121c485a8bb0fb55a87f8c"

def configure_tushare(token: str):
    """
    配置TuShare数据源
    
    参数:
        token: 你的TuShare Token（从 https://tushare.pro/ 获取）
    """
    print("=" * 60)
    print("配置TuShare数据源")
    print("=" * 60)
    
    # 设置配置
    SETTINGS["datafeed.name"] = "tushare"
    SETTINGS["datafeed.username"] = "token"
    SETTINGS["datafeed.password"] = token
    
    # 保存配置到文件
    setting_file = Path(TEMP_DIR) / "vt_setting.json"
    
    # 读取现有配置（如果有）
    existing_settings = {}
    if setting_file.exists():
        with open(setting_file, 'r', encoding='utf-8') as f:
            existing_settings = json.load(f)
    
    # 更新数据源配置
    existing_settings["datafeed.name"] = "tushare"
    existing_settings["datafeed.username"] = "token"
    existing_settings["datafeed.password"] = token
    
    # 保存配置
    with open(setting_file, 'w', encoding='utf-8') as f:
        json.dump(existing_settings, f, ensure_ascii=False, indent=4)
    
    print(f"\n✓ 配置已保存到: {setting_file}")
    print("\n配置内容:")
    print(f"  datafeed.name: tushare")
    print(f"  datafeed.username: token")
    print(f"  datafeed.password: {token[:10]}...（已隐藏）")
    print("\n✓ TuShare数据源配置完成！")
    print("\n提示:")
    print("  - 重启VeighNa Trader使配置生效")
    print("  - 在DataManager中测试下载数据")
    print("  - 如果遇到积分不足，请访问 https://tushare.pro/ 查看积分")


if __name__ == "__main__":
    # 直接使用配置的Token
    configure_tushare(TUSHARE_TOKEN)

