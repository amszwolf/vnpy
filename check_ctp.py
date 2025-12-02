"""检查CTP Gateway模块是否安装"""

import sys

print("=" * 60)
print("检查CTP Gateway模块")
print("=" * 60)

print(f"\nPython版本: {sys.version}")

try:
    from vnpy_ctp import CtpGateway
    print("✓ vnpy_ctp 模块已安装")
    print(f"  Gateway类: {CtpGateway}")
    print(f"  默认名称: {CtpGateway.default_name}")
except ImportError as e:
    print("✗ vnpy_ctp 模块未安装")
    print(f"  错误: {e}")
    print("\n请运行以下命令安装:")
    print("  conda activate vnpyenv")
    print("  pip install vnpy_ctp")

print("\n" + "=" * 60)

