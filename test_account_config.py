"""
测试账号配置加载功能
"""

from vnpy.trader.utility import TEMP_DIR, load_json
from pathlib import Path
import json


def test_load_configs():
    """测试加载配置"""
    print("=" * 60)
    print("测试账号配置加载")
    print("=" * 60)
    
    print(f"\n配置文件位置: {TEMP_DIR}")
    print(f"目录存在: {TEMP_DIR.exists()}")
    
    if not TEMP_DIR.exists():
        print("\n⚠ .vntrader 目录不存在")
        return
    
    # 查找所有配置文件
    config_files = list(TEMP_DIR.glob("connect_*.json"))
    print(f"\n找到 {len(config_files)} 个配置文件:")
    
    for config_file in config_files:
        print(f"\n  [{config_file.name}]")
        try:
            config = load_json(config_file.name)
            # 隐藏密码显示
            display_config = config.copy()
            if "密码" in display_config:
                display_config["密码"] = "******"
            
            print(f"    用户名: {display_config.get('用户名', 'N/A')}")
            print(f"    经纪商代码: {display_config.get('经纪商代码', 'N/A')}")
            print(f"    交易服务器: {display_config.get('交易服务器', 'N/A')}")
            print(f"    行情服务器: {display_config.get('行情服务器', 'N/A')}")
        except Exception as e:
            print(f"    ✗ 读取失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_load_configs()

