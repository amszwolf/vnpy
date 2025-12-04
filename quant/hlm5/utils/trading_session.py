# -*- coding: utf-8 -*-
"""
交易时段管理模块
从 hlm5_all_parallel.py 移植

功能：
- 检查是否在交易时段
- 收盘前强制平仓逻辑
- 开盘缓冲期管理（可选）
"""

from datetime import datetime, time, timedelta
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from futures_config import FUTURES_TRADING_HOURS

class TradingSessionManager:
    """
    交易时段管理器
    
    基于 hlm5_all_parallel.py 的优化测试结果：
    - 收盘前5分钟强制平仓（必须）
    - 开盘缓冲期禁用（测试证明立即交易效果最佳）
    """
    
    def __init__(self, 
                 symbol='OI',
                 buffer_minutes=0,
                 close_minutes=5, 
                 hold_overnight=False):
        """
        初始化交易时段管理器
        
        Parameters:
        -----------
        symbol : str
            期货品种代码（如 'OI', 'RB'）
        buffer_minutes : int
            开盘后缓冲期（分钟），默认0（禁用）
        close_minutes : int
            收盘前平仓缓冲期（分钟），默认5
        hold_overnight : bool
            是否允许持仓过夜，默认False
        """
        self.symbol = symbol.upper()
        self.buffer_minutes = buffer_minutes
        self.close_minutes = close_minutes
        self.hold_overnight = hold_overnight
        
        # 从配置获取交易时段
        if self.symbol in FUTURES_TRADING_HOURS:
            self.trading_hours = FUTURES_TRADING_HOURS[self.symbol]
        else:
            # 默认使用OI的交易时段
            self.trading_hours = FUTURES_TRADING_HOURS['OI']
        
        # 解析交易时段
        self.day_sessions = self._parse_sessions(
            self.trading_hours['day_session']
        )
        self.night_sessions = self._parse_sessions(
            self.trading_hours.get('night_session', [])
        )
    
    def _parse_sessions(self, session_list):
        """
        解析交易时段字符串
        
        Parameters:
        -----------
        session_list : list of tuples
            时段列表，如 [('09:00:00', '11:30:00')]
            
        Returns:
        --------
        list of tuples : 解析后的时段列表 [(time, time), ...]
        """
        parsed_sessions = []
        for start_str, end_str in session_list:
            start_time = datetime.strptime(start_str, '%H:%M:%S').time()
            end_time = datetime.strptime(end_str, '%H:%M:%S').time()
            parsed_sessions.append((start_time, end_time))
        return parsed_sessions
    
    def is_trading_time(self, current_time):
        """
        检查当前时间是否在交易时段内
        
        Parameters:
        -----------
        current_time : datetime
            当前时间
            
        Returns:
        --------
        bool : 是否在交易时段
        """
        current_t = current_time.time()
        
        # 检查日盘时段
        for start_t, end_t in self.day_sessions:
            if start_t <= current_t <= end_t:
                return True
        
        # 检查夜盘时段
        for start_t, end_t in self.night_sessions:
            # 夜盘可能跨天
            if start_t > end_t:
                # 跨天情况：21:00 - 02:00
                if current_t >= start_t or current_t <= end_t:
                    return True
            else:
                # 正常情况
                if start_t <= current_t <= end_t:
                    return True
        
        return False
    
    def should_force_close(self, current_time):
        """
        检查是否应该强制平仓
        
        ⚠️ 核心逻辑：收盘前N分钟强制平仓
        
        Parameters:
        -----------
        current_time : datetime
            当前时间
            
        Returns:
        --------
        tuple : (should_close: bool, reason: str)
            是否应该平仓，以及原因
        """
        current_t = current_time.time()
        
        # 如果允许持仓过夜，则不需要强制平仓
        if self.hold_overnight:
            return False, ""
        
        # 检查每个交易时段的收盘时间
        all_sessions = self.day_sessions + self.night_sessions
        
        for start_t, end_t in all_sessions:
            # 计算收盘前N分钟的时间点
            close_dt = datetime.combine(datetime.today(), end_t)
            buffer_dt = close_dt - timedelta(minutes=self.close_minutes)
            buffer_t = buffer_dt.time()
            
            # 检查是否在收盘前缓冲期内
            if buffer_t <= current_t <= end_t:
                return True, f"Close in {self.close_minutes} minutes"
        
        return False, ""
    
    def should_open_trade(self, current_time):
        """
        检查是否允许开新仓
        
        根据测试结果：开盘缓冲期已禁用，始终允许交易
        
        Parameters:
        -----------
        current_time : datetime
            当前时间
            
        Returns:
        --------
        bool : 是否允许开仓
        """
        # 根据hlm5测试结果，开盘缓冲期禁用
        # 只要在交易时段内，就允许开仓
        if not self.is_trading_time(current_time):
            return False
        
        # 如果设置了缓冲期（虽然默认是0）
        if self.buffer_minutes > 0:
            current_t = current_time.time()
            
            # 检查每个交易时段的开盘时间
            all_sessions = self.day_sessions + self.night_sessions
            
            for start_t, end_t in all_sessions:
                # 计算开盘后N分钟的时间点
                open_dt = datetime.combine(datetime.today(), start_t)
                buffer_dt = open_dt + timedelta(minutes=self.buffer_minutes)
                buffer_t = buffer_dt.time()
                
                # 如果在开盘缓冲期内，不允许开仓
                if start_t <= current_t < buffer_t:
                    return False
        
        return True
    
    def get_next_close_time(self, current_time):
        """
        获取下一个收盘时间
        
        Parameters:
        -----------
        current_time : datetime
            当前时间
            
        Returns:
        --------
        datetime : 下一个收盘时间
        """
        current_t = current_time.time()
        
        # 检查所有交易时段
        all_sessions = self.day_sessions + self.night_sessions
        
        # 找到当前时段的收盘时间
        for start_t, end_t in all_sessions:
            if start_t <= current_t <= end_t:
                return datetime.combine(current_time.date(), end_t)
        
        # 如果不在交易时段，返回下一个交易时段的收盘时间
        for start_t, end_t in all_sessions:
            if current_t < start_t:
                return datetime.combine(current_time.date(), end_t)
        
        # 如果今天没有更多时段，返回明天第一个时段的收盘时间
        if all_sessions:
            next_day = current_time.date() + timedelta(days=1)
            return datetime.combine(next_day, all_sessions[0][1])
        
        return None


# ====================================================================
# 测试代码
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("交易时段管理器测试")
    print("=" * 60)
    
    # 创建OI期货的交易时段管理器
    session_mgr = TradingSessionManager(
        symbol='OI',
        buffer_minutes=0,   # 禁用开盘缓冲
        close_minutes=5,    # 收盘前5分钟平仓
        hold_overnight=False
    )
    
    # 测试时间点
    test_times = [
        datetime(2025, 1, 15, 9, 0, 0),   # 开盘时刻
        datetime(2025, 1, 15, 9, 30, 0),  # 开盘后30分钟
        datetime(2025, 1, 15, 10, 10, 0), # 日盘第一节结束前5分钟
        datetime(2025, 1, 15, 10, 20, 0), # 休息时间
        datetime(2025, 1, 15, 13, 30, 0), # 下午开盘
        datetime(2025, 1, 15, 14, 56, 0), # 收盘前4分钟
        datetime(2025, 1, 15, 15, 10, 0), # 收盘后
        datetime(2025, 1, 15, 21, 0, 0),  # 夜盘开盘
        datetime(2025, 1, 15, 22, 56, 0), # 夜盘收盘前4分钟
    ]
    
    print("\n时间点测试：")
    print("-" * 60)
    for test_time in test_times:
        is_trading = session_mgr.is_trading_time(test_time)
        should_close, reason = session_mgr.should_force_close(test_time)
        can_open = session_mgr.should_open_trade(test_time)
        
        print(f"\n时间: {test_time.strftime('%H:%M:%S')}")
        print(f"  交易时段: {'是' if is_trading else '否'}")
        print(f"  允许开仓: {'是' if can_open else '否'}")
        print(f"  强制平仓: {'是' if should_close else '否'} {reason}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

