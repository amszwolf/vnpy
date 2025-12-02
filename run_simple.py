"""
VeighNa 简化运行示例
展示核心框架的基本使用方式，不依赖外部Gateway和App
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp


def main():
    """启动VeighNa Trader（简化版）"""
    print("=" * 60)
    print("VeighNa Trader 核心框架演示")
    print("=" * 60)
    
    # 1. 创建Qt应用
    print("\n[1/4] 创建Qt应用...")
    qapp = create_qapp()
    print("✓ Qt应用创建成功")
    
    # 2. 创建事件引擎
    print("\n[2/4] 创建事件引擎...")
    event_engine = EventEngine()
    print("✓ 事件引擎创建成功")
    
    # 3. 创建主引擎
    print("\n[3/4] 创建主引擎...")
    main_engine = MainEngine(event_engine)
    print("✓ 主引擎创建成功")
    print(f"  - 已注册的Gateway: {main_engine.get_all_gateway_names()}")
    print(f"  - 已注册的App: {[app.app_name for app in main_engine.get_all_apps()]}")
    
    # 4. 创建主窗口
    print("\n[4/4] 创建主窗口...")
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    print("✓ 主窗口创建成功")
    print("\n" + "=" * 60)
    print("VeighNa Trader 已启动！")
    print("=" * 60)
    print("\n提示：")
    print("  - 这是一个简化版本，没有加载外部Gateway和App")
    print("  - 要使用完整功能，需要安装相应的模块（如vnpy_ctp, vnpy_ctastrategy等）")
    print("  - 参考 examples/veighna_trader/run.py 查看完整示例")
    print("\n按Ctrl+C或关闭窗口退出\n")
    
    # 5. 启动Qt事件循环
    qapp.exec()


if __name__ == "__main__":
    main()

