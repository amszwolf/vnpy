"""
双均线交叉策略示例
快速均线上穿慢速均线买入，下穿卖出
"""

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager
)


class MaCrossStrategy(CtaTemplate):
    """
    双均线交叉策略
    
    策略逻辑：
    - 快速均线上穿慢速均线：买入
    - 快速均线下穿慢速均线：卖出
    - 支持止损止盈
    """
    
    author = "VeighNa量化框架"
    
    # 策略参数
    fast_window = 10      # 快速均线周期
    slow_window = 30      # 慢速均线周期
    fixed_size = 1        # 每次交易数量
    sl_percent = 0.02     # 止损百分比（2%）
    tp_percent = 0.04     # 止盈百分比（4%）
    
    # 策略变量
    fast_ma = 0.0
    slow_ma = 0.0
    long_stop = 0.0       # 多头止损价
    short_stop = 0.0      # 空头止损价
    long_target = 0.0     # 多头止盈价
    short_target = 0.0    # 空头止盈价
    
    parameters = [
        "fast_window",
        "slow_window",
        "fixed_size",
        "sl_percent",
        "tp_percent"
    ]
    
    variables = [
        "fast_ma",
        "slow_ma",
        "long_stop",
        "short_stop",
        "long_target",
        "short_target"
    ]
    
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        
        # K线生成器：将1分钟K线合成5分钟K线
        self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am = ArrayManager()
    
    def on_init(self):
        """
        策略初始化
        """
        self.write_log("双均线交叉策略初始化")
        self.load_bar(100)
    
    def on_start(self):
        """
        策略启动
        """
        self.write_log("双均线交叉策略启动")
    
    def on_stop(self):
        """
        策略停止
        """
        self.write_log("双均线交叉策略停止")
    
    def on_tick(self, tick: TickData):
        """
        Tick数据回调
        """
        self.bg.update_tick(tick)
    
    def on_bar(self, bar: BarData):
        """
        1分钟K线数据回调
        """
        # 将1分钟K线合成5分钟K线
        self.bg.update_bar(bar)
    
    def on_5min_bar(self, bar: BarData):
        """
        5分钟K线数据回调（策略主要逻辑在这里）
        """
        # 更新K线序列
        self.am.update_bar(bar)
        
        if not self.am.inited:
            return
        
        # 计算均线（基于5分钟K线）
        self.fast_ma = self.am.sma(self.fast_window, array=False)
        self.slow_ma = self.am.sma(self.slow_window, array=False)
        
        # 计算止损止盈
        if self.pos > 0:
            # 多头持仓，更新止损止盈
            if self.long_stop == 0:
                self.long_stop = bar.close_price * (1 - self.sl_percent)
                self.long_target = bar.close_price * (1 + self.tp_percent)
            else:
                # 移动止损（跟踪止损）
                new_stop = bar.close_price * (1 - self.sl_percent)
                if new_stop > self.long_stop:
                    self.long_stop = new_stop
            
            # 检查止损
            if bar.low_price <= self.long_stop:
                self.sell(bar.close_price, abs(self.pos))
                self.write_log(f"触发止损: {self.long_stop}")
                self.long_stop = 0
                self.long_target = 0
                return
            
            # 检查止盈
            if bar.high_price >= self.long_target:
                self.sell(bar.close_price, abs(self.pos))
                self.write_log(f"触发止盈: {self.long_target}")
                self.long_stop = 0
                self.long_target = 0
                return
        
        elif self.pos < 0:
            # 空头持仓，更新止损止盈
            if self.short_stop == 0:
                self.short_stop = bar.close_price * (1 + self.sl_percent)
                self.short_target = bar.close_price * (1 - self.tp_percent)
            else:
                # 移动止损
                new_stop = bar.close_price * (1 + self.sl_percent)
                if new_stop < self.short_stop:
                    self.short_stop = new_stop
            
            # 检查止损
            if bar.high_price >= self.short_stop:
                self.cover(bar.close_price, abs(self.pos))
                self.write_log(f"触发止损: {self.short_stop}")
                self.short_stop = 0
                self.short_target = 0
                return
            
            # 检查止盈
            if bar.low_price <= self.short_target:
                self.cover(bar.close_price, abs(self.pos))
                self.write_log(f"触发止盈: {self.short_target}")
                self.short_stop = 0
                self.short_target = 0
                return
        
        # 交易信号
        # 快速均线上穿慢速均线
        if self.fast_ma > self.slow_ma:
            if self.pos == 0:
                self.buy(bar.close_price, self.fixed_size)
                self.write_log(f"买入信号: 快速均线={self.fast_ma:.2f}, 慢速均线={self.slow_ma:.2f}")
            elif self.pos < 0:
                # 平空开多
                self.cover(bar.close_price, abs(self.pos))
                self.buy(bar.close_price, self.fixed_size)
                self.write_log(f"平空开多: 快速均线={self.fast_ma:.2f}, 慢速均线={self.slow_ma:.2f}")
        
        # 快速均线下穿慢速均线
        elif self.fast_ma < self.slow_ma:
            if self.pos == 0:
                self.short(bar.close_price, self.fixed_size)
                self.write_log(f"卖出信号: 快速均线={self.fast_ma:.2f}, 慢速均线={self.slow_ma:.2f}")
            elif self.pos > 0:
                # 平多开空
                self.sell(bar.close_price, abs(self.pos))
                self.short(bar.close_price, self.fixed_size)
                self.write_log(f"平多开空: 快速均线={self.fast_ma:.2f}, 慢速均线={self.slow_ma:.2f}")
    
    def on_order(self, order: OrderData):
        """
        委托回报
        """
        pass
    
    def on_trade(self, trade: TradeData):
        """
        成交回报
        """
        self.write_log(
            f"成交: {trade.direction.value} {trade.volume}@{trade.price:.2f}, "
            f"当前持仓: {self.pos}"
        )
    
    def on_stop_order(self, stop_order: StopOrder):
        """
        停止单回报
        """
        pass

