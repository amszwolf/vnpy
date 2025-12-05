"""
期货交易时段管理模块

提供开盘、收盘时间判断和数据缓冲期管理功能
支持国内商品期货的不同交易时段
"""

from datetime import datetime, time, timedelta
import pandas as pd


class TradingSessionManager:
    """
    交易时段管理器
    
    功能：
    1. 判断是否为交易时段开始（早盘9:00、午盘10:30、下午盘13:30、夜盘21:00）
    2. 判断是否在数据缓冲期内（开盘后N分钟）
    3. 判断是否临近收盘（收盘前N分钟）
    4. 检查数据充分性
    """
    
    # 定义各个交易所的交易时段
    TRADING_SESSIONS = {
        'day': [
            (time(9, 0), time(10, 15)),    # 早盘
            (time(10, 30), time(11, 30)),  # 午盘
            (time(13, 30), time(15, 0)),   # 下午盘
        ],
        'day_extended': [  # 上期所部分品种延长到15:15
            (time(9, 0), time(10, 15)),
            (time(10, 30), time(11, 30)),
            (time(13, 30), time(15, 15)),
        ],
        'night': [
            (time(21, 0), time(23, 0)),    # 夜盘（短）
        ],
        'night_extended': [
            (time(21, 0), time(23, 59, 59)),  # 夜盘跨日第一段
            (time(0, 0), time(2, 30)),         # 夜盘跨日第二段
        ]
    }
    
    # 各交易所的收盘时间
    CLOSE_TIMES = {
        'SHFE': time(15, 0),   # 上期所（大部分品种）
        'SHFE_EXT': time(15, 15),  # 上期所（延长品种）
        'DCE': time(15, 0),    # 大商所
        'CZCE': time(15, 0),   # 郑商所
        'INE': time(15, 0),    # 能源中心
    }
    
    def __init__(self, buffer_minutes=10, close_minutes=5, hold_overnight=False):
        """
        初始化交易时段管理器
        
        Parameters:
        -----------
        buffer_minutes : int
            缓冲期分钟数（开盘后多少分钟内不产生信号），默认10分钟
        close_minutes : int
            收盘前多少分钟开始平仓，默认5分钟
        hold_overnight : bool
            是否允许持仓过夜，默认False
        """
        self.buffer_minutes = buffer_minutes
        self.close_minutes = close_minutes
        self.hold_overnight = hold_overnight
        self.session_start_times = {}  # 记录每个交易日的开始时间
        
    def is_session_start(self, timestamp):
        """
        判断当前时间是否为交易时段的开始时刻
        
        Parameters:
        -----------
        timestamp : datetime or str
            当前时间戳
            
        Returns:
        --------
        bool
            是否为时段开始时刻
        """
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        current_time = timestamp.time()
        
        # 判断是否为各个时段的开始时刻（精确到分钟）
        session_starts = [
            time(9, 0),   # 早盘开始
            time(10, 30), # 午盘开始
            time(13, 30), # 下午盘开始
            time(21, 0),  # 夜盘开始
        ]
        
        # 允许1分钟的容差（考虑到1分钟K线的时间戳）
        for start_time in session_starts:
            if current_time.hour == start_time.hour and current_time.minute == start_time.minute:
                return True
        
        return False
    
    def is_in_buffer_period(self, timestamp, trading_date=None):
        """
        判断当前时间是否在缓冲期内
        
        Parameters:
        -----------
        timestamp : datetime or str
            当前时间戳
        trading_date : str
            交易日（格式：YYYY-MM-DD），用于跟踪每日的时段开始时间
            
        Returns:
        --------
        bool
            是否在缓冲期内
        """
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        if trading_date is None:
            trading_date = timestamp.strftime('%Y-%m-%d')
        
        current_time = timestamp.time()
        
        # 定义各时段的缓冲期（手动计算时间，避免溢出）
        # buffer_minutes = 10，所以缓冲期是开盘后10分钟
        buffer_periods = [
            (time(9, 0), time(9, 10)),      # 早盘缓冲期：9:00-9:10
            (time(10, 30), time(10, 40)),   # 午盘缓冲期：10:30-10:40
            (time(13, 30), time(13, 40)),   # 下午盘缓冲期：13:30-13:40
            (time(21, 0), time(21, 10)),    # 夜盘缓冲期：21:00-21:10
        ]
        
        # 检查是否在任一缓冲期内
        for start, end in buffer_periods:
            if self._time_in_range(current_time, start, end):
                return True
        
        return False
    
    def is_close_to_market_close(self, timestamp, exchange='DCE'):
        """
        判断是否临近收盘时间
        
        Parameters:
        -----------
        timestamp : datetime or str
            当前时间戳
        exchange : str
            交易所代码，默认'DCE'（大商所）
            
        Returns:
        --------
        bool
            是否临近收盘
        """
        if self.hold_overnight:
            return False  # 如果允许持仓过夜，则不进行收盘平仓
        
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        current_time = timestamp.time()
        
        # 定义各个时段的收盘时间和警告时间（手动计算避免时间溢出）
        # 格式：(警告开始时间, 收盘时间)
        close_periods = [
            (time(10, 10), time(10, 15)),   # 早盘收盘前5分钟
            (time(11, 25), time(11, 30)),   # 午盘收盘前5分钟
            (time(14, 55), time(15, 0)),    # 下午盘收盘前5分钟
            (time(14, 50), time(15, 15)),   # 上期所延长品种收盘前5分钟
            (time(22, 55), time(23, 0)),    # 夜盘收盘前5分钟（短）
            (time(2, 25), time(2, 30)),     # 夜盘收盘前5分钟（长）
        ]
        
        for start, end in close_periods:
            if self._time_in_range(current_time, start, end):
                return True
        
        return False
    
    def check_data_sufficiency(self, data_df, current_index, min_bars=10):
        """
        检查从时段开始到当前时刻是否有足够的数据
        
        Parameters:
        -----------
        data_df : pd.DataFrame
            完整的数据DataFrame
        current_index : int
            当前数据索引
        min_bars : int
            最小K线数量要求，默认10根
            
        Returns:
        --------
        bool
            数据是否充足
        """
        if current_index < min_bars:
            return False
        
        # 获取当前时间和交易日
        current_timestamp = pd.to_datetime(data_df.iloc[current_index]['datetime'])
        trading_date = current_timestamp.strftime('%Y-%m-%d')
        
        # 如果不在缓冲期内，则认为数据充足
        if not self.is_in_buffer_period(current_timestamp, trading_date):
            return True
        
        # 在缓冲期内，检查从时段开始到现在的K线数量
        # 找到当前时段的开始时间
        session_start = self._find_session_start(data_df, current_index)
        
        if session_start is None:
            return False
        
        # 计算从时段开始到当前的K线数量
        bars_since_start = current_index - session_start + 1
        
        return bars_since_start >= min_bars
    
    def get_session_data(self, data_df, current_index):
        """
        获取当前交易时段的数据（从时段开始到当前时刻）
        
        Parameters:
        -----------
        data_df : pd.DataFrame
            完整的数据DataFrame
        current_index : int
            当前数据索引
            
        Returns:
        --------
        pd.DataFrame
            当前时段的数据切片
        """
        session_start = self._find_session_start(data_df, current_index)
        
        if session_start is None:
            return data_df.iloc[:current_index + 1]
        
        return data_df.iloc[session_start:current_index + 1]
    
    def _find_session_start(self, data_df, current_index):
        """
        找到当前数据点所属交易时段的开始索引
        
        Parameters:
        -----------
        data_df : pd.DataFrame
            完整的数据DataFrame
        current_index : int
            当前数据索引
            
        Returns:
        --------
        int or None
            时段开始的索引，如果未找到则返回None
        """
        current_timestamp = pd.to_datetime(data_df.iloc[current_index]['datetime'])
        
        # 向前搜索，找到最近的时段开始时刻
        for i in range(current_index, -1, -1):
            timestamp = pd.to_datetime(data_df.iloc[i]['datetime'])
            
            if self.is_session_start(timestamp):
                return i
            
            # 防止搜索过远（最多搜索120根K线，约2小时）
            if current_index - i > 120:
                break
        
        return None
    
    def _time_in_range(self, current_time, start_time, end_time):
        """
        判断时间是否在指定范围内（处理跨午夜情况）
        
        Parameters:
        -----------
        current_time : time
            当前时间
        start_time : time
            开始时间
        end_time : time
            结束时间
            
        Returns:
        --------
        bool
            是否在范围内
        """
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # 跨午夜情况
            return current_time >= start_time or current_time <= end_time
    
    def should_generate_signal(self, timestamp, data_df, current_index):
        """
        综合判断当前时刻是否应该生成交易信号
        
        Parameters:
        -----------
        timestamp : datetime or str
            当前时间戳
        data_df : pd.DataFrame
            完整的数据DataFrame
        current_index : int
            当前数据索引
            
        Returns:
        --------
        tuple (bool, str)
            (是否应该生成信号, 原因说明)
        """
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        # 检查1：是否在缓冲期内
        if self.is_in_buffer_period(timestamp):
            # 在缓冲期内，检查数据是否充足
            if not self.check_data_sufficiency(data_df, current_index):
                return False, "数据缓冲期-数据不足"
        
        # 检查2：是否临近收盘
        if self.is_close_to_market_close(timestamp):
            return False, "临近收盘-禁止开新仓"
        
        return True, "正常交易时段"
    
    def should_force_close(self, timestamp):
        """
        判断是否应该强制平仓
        
        Parameters:
        -----------
        timestamp : datetime or str
            当前时间戳
            
        Returns:
        --------
        tuple (bool, str)
            (是否应该强制平仓, 原因说明)
        """
        if self.hold_overnight:
            return False, "允许持仓过夜"
        
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        if self.is_close_to_market_close(timestamp):
            return True, "临近收盘强制平仓"
        
        return False, ""


# 便捷函数
def create_session_manager(buffer_minutes=10, close_minutes=5, hold_overnight=False):
    """
    创建交易时段管理器的便捷函数
    
    Parameters:
    -----------
    buffer_minutes : int
        缓冲期分钟数，默认10分钟
    close_minutes : int
        收盘前平仓分钟数，默认5分钟
    hold_overnight : bool
        是否允许持仓过夜，默认False
        
    Returns:
    --------
    TradingSessionManager
        交易时段管理器实例
    """
    return TradingSessionManager(buffer_minutes, close_minutes, hold_overnight)

