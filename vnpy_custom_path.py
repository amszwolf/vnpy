"""
VeighNa 自定义数据路径配置模块

使用方法：
    from vnpy_custom_path import set_custom_data_path
    set_custom_data_path(r"D:\Data\vnpy")
    
    然后正常导入和使用 vnpy 模块
"""
from pathlib import Path
from typing import Optional


def set_custom_data_path(custom_path: str | Path) -> None:
    """
    设置VeighNa的自定义数据存储路径
    
    参数:
        custom_path: 自定义数据目录路径（字符串或Path对象）
    
    注意: 此函数必须在导入 vnpy.trader 相关模块之前调用
    """
    custom_dir = Path(custom_path)
    
    # 创建目录（如果不存在）
    if not custom_dir.exists():
        custom_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ 创建数据目录: {custom_dir}")
    
    # 修改VeighNa的数据目录路径
    try:
        import vnpy.trader.utility as trader_utility
        trader_utility.TRADER_DIR = custom_dir
        trader_utility.TEMP_DIR = custom_dir
        print(f"✓ 数据存储路径已设置为: {custom_dir}")
    except ImportError:
        print("警告: 无法导入 vnpy.trader.utility，请确保已安装 vnpy")
        raise


# 默认路径（可以在导入时设置）
_DEFAULT_CUSTOM_PATH: Optional[Path] = None


def get_default_custom_path() -> Optional[Path]:
    """获取默认自定义路径"""
    return _DEFAULT_CUSTOM_PATH


def set_default_custom_path(path: str | Path) -> None:
    """设置默认自定义路径"""
    global _DEFAULT_CUSTOM_PATH
    _DEFAULT_CUSTOM_PATH = Path(path)

