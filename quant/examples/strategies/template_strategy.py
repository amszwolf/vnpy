"""
CTA策略开发模板
基于vnpy_ctastrategy的CtaTemplate开发
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


class TemplateStrategy(CtaTemplate):
    """
    策略开发模板
    
    使用方法：
    1. 复制本文件并重命名（如：my_strategy.py）
    2. 修改类名为你的策略名称（如：MyStrategy）
    3. 实现策略逻辑
    4. 在parameters和variables中注册参数和变量
    """
    
    author = "Your Name"
    
    # 策略参数（可在UI界面修改）
    fast_window = 10      # 快速均线周期
    slow_window = 30     # 慢速均线周期
    fixed_size = 1       # 每次交易数量
    
    # 策略变量（运行时变化）
    fast_ma = 0.0        # 快速均线值
    slow_ma = 0.0        # 慢速均线值
    
    # 参数列表（用于UI显示和保存）
    parameters = [
        "fast_window",
        "slow_window",
        "fixed_size"
    ]
    
    # 变量列表（用于UI显示和保存）
    variables = [
        "fast_ma",
        "slow_ma"
    ]
    
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """
        策略初始化
        
        参数:
            cta_engine: CTA策略引擎
            strategy_name: 策略名称
            vt_symbol: 交易合约（格式：symbol.exchange）
            setting: 策略参数字典
        """
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        
        # K线生成器（将Tick合成1分钟K线）
        self.bg = BarGenerator(self.on_bar)
        
        # K线时间序列管理器（用于计算技术指标）
        self.am = ArrayManager()
    
    def on_init(self):
        """
        策略初始化回调
        在策略启动时调用一次
        """
        self.write_log("策略初始化")
        
        # 加载历史数据（用于计算技术指标）
        self.load_bar(100)  # 加载最近100根K线
    
    def on_start(self):
        """
        策略启动回调
        """
        self.write_log("策略启动")
    
    def on_stop(self):
        """
        策略停止回调
        """
        self.write_log("策略停止")
    
    def on_tick(self, tick: TickData):
        """
        Tick数据回调
        
        参数:
            tick: Tick行情数据
        """
        # 将Tick数据合成K线
        self.bg.update_tick(tick)
    
    def on_bar(self, bar: BarData):
        """
        1分钟K线数据回调
        
        参数:
            bar: K线数据
        """
        # 更新K线时间序列
        self.am.update_bar(bar)
        
        # 如果K线数量不足，不进行交易
        if not self.am.inited:
            return
        
        # 计算技术指标
        self.fast_ma = self.am.sma(self.fast_window, array=False)
        self.slow_ma = self.am.sma(self.slow_window, array=False)
        
        # 策略逻辑
        # 快速均线上穿慢速均线，买入信号
        if self.fast_ma > self.slow_ma:
            if self.pos == 0:
                self.buy(bar.close_price, self.fixed_size)
            elif self.pos < 0:
                self.cover(bar.close_price, abs(self.pos))
                self.buy(bar.close_price, self.fixed_size)
        
        # 快速均线下穿慢速均线，卖出信号
        elif self.fast_ma < self.slow_ma:
            if self.pos == 0:
                self.short(bar.close_price, self.fixed_size)
            elif self.pos > 0:
                self.sell(bar.close_price, abs(self.pos))
                self.short(bar.close_price, self.fixed_size)
    
    def on_order(self, order: OrderData):
        """
        委托回报回调
        
        参数:
            order: 委托数据
        """
        pass
    
    def on_trade(self, trade: TradeData):
        """
        成交回报回调
        
        参数:
            trade: 成交数据
        """
        # 记录成交信息
        self.write_log(
            f"成交: {trade.direction.value} {trade.volume}@{trade.price}, "
            f"当前持仓: {self.pos}"
        )
    
    def on_stop_order(self, stop_order: StopOrder):
        """
        停止单回调
        
        参数:
            stop_order: 停止单数据
        """
        pass

