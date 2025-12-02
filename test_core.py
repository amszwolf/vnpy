"""
测试VeighNa核心框架功能（非GUI）
"""

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import LogData
from vnpy.trader.event import EVENT_LOG
import time


def test_event_engine():
    """测试事件引擎"""
    print("\n" + "=" * 60)
    print("测试1: 事件引擎")
    print("=" * 60)
    
    event_engine = EventEngine()
    event_engine.start()
    
    # 注册事件处理器
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
        print(f"  收到事件: {event.type}, 数据: {event.data}")
    
    event_engine.register(EVENT_LOG, handler)
    
    # 发送测试事件
    log_data = LogData(msg="测试日志消息", gateway_name="test")
    event = Event(EVENT_LOG, log_data)
    event_engine.put(event)
    
    # 等待事件处理
    time.sleep(0.5)
    
    print(f"  事件处理结果: 收到 {len(received_events)} 个事件")
    assert len(received_events) > 0, "事件引擎未正常工作"
    print("  ✓ 事件引擎测试通过")
    
    event_engine.stop()
    return True


def test_main_engine():
    """测试主引擎"""
    print("\n" + "=" * 60)
    print("测试2: 主引擎")
    print("=" * 60)
    
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    
    print(f"  Gateway列表: {main_engine.get_all_gateway_names()}")
    print(f"  App列表: {[app.app_name for app in main_engine.get_all_apps()]}")
    print(f"  交易所列表: {[e.value for e in main_engine.get_all_exchanges()]}")
    
    # 测试日志功能
    main_engine.write_log("测试主引擎日志功能", "TestEngine")
    
    # 测试获取引擎
    log_engine = main_engine.get_engine("log")
    assert log_engine is not None, "日志引擎未找到"
    print("  ✓ 主引擎测试通过")
    
    main_engine.close()
    return True


def test_data_objects():
    """测试数据对象"""
    print("\n" + "=" * 60)
    print("测试3: 数据对象")
    print("=" * 60)
    
    from vnpy.trader.object import (
        TickData, OrderData, TradeData, 
        PositionData, AccountData, ContractData
    )
    from vnpy.trader.constant import Exchange, Direction, Status, OrderType
    
    # 测试TickData
    tick = TickData(
        symbol="rb2310",
        exchange=Exchange.SHFE,
        datetime=time.time(),
        gateway_name="test"
    )
    print(f"  TickData.vt_symbol: {tick.vt_symbol}")
    assert tick.vt_symbol == "rb2310.SHFE", "vt_symbol生成错误"
    
    # 测试OrderData
    from datetime import datetime
    order = OrderData(
        symbol="rb2310",
        exchange=Exchange.SHFE,
        orderid="12345",
        type=OrderType.LIMIT,
        direction=Direction.LONG,
        offset=None,
        price=3500.0,
        volume=10,
        status=Status.SUBMITTING,
        datetime=datetime.now(),
        gateway_name="test"
    )
    print(f"  OrderData.vt_orderid: {order.vt_orderid}")
    assert order.is_active(), "订单状态判断错误"
    
    print("  ✓ 数据对象测试通过")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("VeighNa 核心框架功能测试")
    print("=" * 60)
    
    try:
        test_event_engine()
        test_main_engine()
        test_data_objects()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        print("\n核心框架运行正常，可以开始使用VeighNa进行开发。")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    import time
    main()

