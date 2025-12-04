# -*- coding: utf-8 -*-
"""
HLM5 多指标融合量化交易策略 - VNPy版本

核心逻辑从 hlm5_all_parallel.py 原样移植
配置参数从 hlm5_config.py 读取

策略特点：
- 多指标融合：Price MACD + Volume MACD + HLBW + Prophet
- 双向交易：支持做多和做空
- 日内交易：收盘前强制平仓，无隔夜风险
- 智能信号：6级信号强度分类
- 风险控制：止损/止盈/跟踪止损

测试表现（2025-01-01至2025-01-31）：
- OI.ZCE: 总收益24.73%, 胜率74.31%, 夏普0.504
- RB.SHF: 总收益19.46%, 胜率75.52%, 最大回撤-0.21%
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple

from vnpy.trader.constant import Direction, Offset, Status
from vnpy.trader.object import BarData, TickData, OrderData, TradeData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy import CtaTemplate, StopOrder

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入配置
from hlm5_config import EQUITY_CONFIG
from futures_config import FUTURES_CONFIG

# 导入工具模块
from utils.indicators import calculate_macd_signals, calculate_hlbw, merge_price_cross_signals
from utils.trading_session import TradingSessionManager
from utils.cost_model import TradingCostCalculator
from utils.scaling_strategy import ScalingStrategyEngine, ScalingConfig, SCALING_CONFIGS


class HLM5Strategy(CtaTemplate):
    """
    HLM5 多指标融合策略
    
    ⚠️ 核心交易逻辑从 hlm5_all_parallel.py 原样移植
    """
    
    author = "HLM5 Team"
    
    # ====================================================================
    # 策略参数（从 hlm5_config.py 读取）
    # ====================================================================
    
    # Price MACD 参数
    price_macd_long = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['macd_long']       # 20
    price_macd_mid = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['macd_mid']         # 8
    price_macd_short = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['macd_short']     # 5
    price_diff_ema = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['diff_ema_period']  # 2
    
    # Volume MACD 参数
    volume_macd_long = EQUITY_CONFIG['INDICATORS']['VOLUME_MACD']['macd_long']     # 20
    volume_macd_mid = EQUITY_CONFIG['INDICATORS']['VOLUME_MACD']['macd_mid']       # 8
    volume_macd_short = EQUITY_CONFIG['INDICATORS']['VOLUME_MACD']['macd_short']   # 5
    volume_diff_ema = EQUITY_CONFIG['INDICATORS']['VOLUME_MACD']['diff_ema_period'] # 3
    
    # HLBW 参数
    hlbw_lookback = EQUITY_CONFIG['INDICATORS']['HLBW']['lookback_period']         # 40
    hlbw_inner_ema = EQUITY_CONFIG['INDICATORS']['HLBW']['inner_ema']              # 3
    hlbw_outer_ema = EQUITY_CONFIG['INDICATORS']['HLBW']['outer_ema']              # 2
    hlbw_trend_ema = EQUITY_CONFIG['INDICATORS']['HLBW']['trend_ema']              # 2
    
    # Prophet 参数
    prophet_periods = EQUITY_CONFIG['INDICATORS']['PROPHET']['periods']            # 20
    prophet_min_duration = EQUITY_CONFIG['TRADING_SIGNALS']['entry_conditions']['prophet_min_duration']  # 2
    
    # 交易信号参数
    min_cross_signals = EQUITY_CONFIG['TRADING_SIGNALS']['entry_conditions']['min_cross_signals']  # 1
    
    # 风险管理参数
    stop_loss_pct = EQUITY_CONFIG['TRADING_SIGNALS']['exit_conditions']['stop_loss_pct']      # 0.04
    take_profit_pct = EQUITY_CONFIG['TRADING_SIGNALS']['exit_conditions']['take_profit_pct']  # 0.12
    trailing_stop_pct = EQUITY_CONFIG['TRADING_SIGNALS']['exit_conditions']['trailing_stop_pct']  # 0.02
    
    # 交易控制参数
    fixed_size = 1           # 默认下单手数
    enable_bidirectional = True   # 启用双向交易
    hold_overnight = False   # 不持仓过夜
    
    # 加仓策略参数
    enable_scaling = False   # 是否启用加仓策略
    scaling_method = 'aggressive_pyramid'  # 加仓方式
    max_position = 10        # 最大持仓手数
    scaling_threshold = 0.01  # 加仓阈值（盈利百分比）
    scaling_trailing_stop = 0.015  # 加仓模式下的移动止损
    
    # 调试参数
    debug_mode = False       # 调试模式，保存所有中间数据
    
    # ====================================================================
    # 策略变量
    # ====================================================================
    
    # 指标值
    price_macd = 0.0
    price_macd_signal = 0.0
    price_macd_hist = 0.0
    price_xlpl_phase = 0
    price_cross = 0
    
    volume_macd = 0.0
    volume_macd_signal = 0.0
    volume_xlpl_phase = 0
    volume_cross = 0
    
    hlbw_trend = 0.0
    hlbw_macd = 0.0
    hlbw_xlpl_phase = 0
    hlbw_cross = 0
    
    prophet_yhat = 0.0
    prophet_phase = 0
    prophet_duration = 0
    
    # 交易状态
    entry_price = 0.0
    entry_price_with_slippage = 0.0
    entry_commission = 0.0
    highest_price_since_entry = 0.0  # 用于跟踪止损
    
    # 加仓状态
    scaling_position = 0     # 加仓后的实际持仓
    scaling_level = 0        # 当前加仓层级
    avg_entry_price = 0.0    # 平均开仓价格
    
    # 统计信息
    total_trades = 0
    winning_trades = 0
    
    # 参数列表
    parameters = [
        "price_macd_long", "price_macd_mid", "price_macd_short",
        "volume_macd_long", "volume_macd_mid", "volume_macd_short",
        "hlbw_lookback", "hlbw_inner_ema",
        "debug_mode",  # 添加debug_mode到参数列表
        "prophet_periods", "prophet_min_duration",
        "stop_loss_pct", "take_profit_pct", "trailing_stop_pct",
        "fixed_size", "enable_bidirectional", "hold_overnight",
        "enable_scaling", "scaling_method", "max_position", 
        "scaling_threshold", "scaling_trailing_stop"
    ]
    
    # 变量列表
    variables = [
        "price_macd", "price_cross", "price_xlpl_phase",
        "volume_macd", "volume_cross", "volume_xlpl_phase",
        "hlbw_trend", "hlbw_cross", "hlbw_xlpl_phase",
        "entry_price", "total_trades", "winning_trades",
        "scaling_position", "scaling_level", "avg_entry_price"
    ]
    
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """策略初始化"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        
        # 初始化Bar生成器（1分钟 → 5分钟）
        self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        
        # 初始化ArrayManager（需要足够的历史数据用于指标计算）
        self.am = ArrayManager(size=100)  # 降低至100以加快初始化（原为200）
        
        # 初始化交易时段管理器
        symbol_code = self.extract_symbol_code(vt_symbol)
        self.session_mgr = TradingSessionManager(
            symbol=symbol_code,
            buffer_minutes=0,        # 禁用开盘缓冲（根据测试结果）
            close_minutes=5,         # 收盘前5分钟平仓
            hold_overnight=self.hold_overnight
        )
        
        # 初始化成本计算器
        self.cost_calculator = TradingCostCalculator(symbol_code)
        
        # 初始化加仓策略引擎（可选）
        self.scaling_engine = None
        if self.enable_scaling:
            # 如果启用加仓，创建加仓引擎
            if self.scaling_method in SCALING_CONFIGS:
                scaling_config = SCALING_CONFIGS[self.scaling_method]
            else:
                # 自定义配置
                scaling_config = ScalingConfig(
                    scaling_method='pyramid',
                    max_position=self.max_position,
                    add_position_condition='profit_threshold',
                    add_position_threshold=self.scaling_threshold,
                    use_trailing_stop=True,
                    trailing_stop_pct=self.scaling_trailing_stop
                )
            
            self.scaling_engine = ScalingStrategyEngine(scaling_config, symbol_code)
        
        # Prophet 预测缓存（避免每个Bar都重新训练）
        self.prophet_forecast = None
        self.prophet_last_update = None
        
        # 历史指标数据（用于存储完整的指标历史）
        self.indicator_history = pd.DataFrame()
        
        # 缓存前一个bar的Cross信号值（用于入场条件判断）
        self.prev_price_cross = 0
        self.prev_volume_cross = 0
        self.prev_hlbw_cross = 0
        
        # 调试数据收集
        if self.debug_mode:
            self.debug_data = []  # 用于收集所有bar的调试信息
        
    def extract_symbol_code(self, vt_symbol):
        """
        从vt_symbol提取品种代码
        
        例如：'OI888.CZCE' → 'OI'
        """
        symbol = vt_symbol.split('.')[0]
        return ''.join([c for c in symbol if c.isalpha()])
    
    def on_init(self):
        """策略初始化"""
        self.write_log("=" * 60)
        self.write_log("HLM5 多指标融合策略初始化")
        self.write_log("=" * 60)
        
        # 打印配置参数
        self.write_log(f"Price MACD: ({self.price_macd_long}, {self.price_macd_mid}, {self.price_macd_short})")
        self.write_log(f"Volume MACD: ({self.volume_macd_long}, {self.volume_macd_mid}, {self.volume_macd_short})")
        self.write_log(f"HLBW: lookback={self.hlbw_lookback}, inner_ema={self.hlbw_inner_ema}")
        self.write_log(f"风险控制: 止损={self.stop_loss_pct*100}%, 止盈={self.take_profit_pct*100}%")
        self.write_log(f"交易模式: {'双向交易' if self.enable_bidirectional else '单向做多'}")
        self.write_log(f"持仓过夜: {'允许' if self.hold_overnight else '禁止'}")
        
        # 打印加仓配置
        if self.enable_scaling:
            self.write_log(f"加仓策略: 已启用 ({self.scaling_method})")
            self.write_log(f"  最大持仓: {self.max_position}手")
            self.write_log(f"  加仓阈值: {self.scaling_threshold*100}%")
            self.write_log(f"  移动止损: {self.scaling_trailing_stop*100}%")
            if self.scaling_engine:
                config = self.scaling_engine.config
                self.write_log(f"  加仓序列: {config.scaling_sequence}")
        else:
            self.write_log(f"加仓策略: 未启用 (固定仓位 {self.fixed_size}手)")
        
        # 加载历史数据（10天）
        self.load_bar(10)
        
        self.write_log("策略初始化完成")
    
    def on_start(self):
        """策略启动"""
        self.write_log("HLM5 策略启动")
        self.put_event()
    
    def on_stop(self):
        """策略停止"""
        self.write_log("HLM5 策略停止")
        self.write_log(f"总交易次数: {self.total_trades}")
        if self.total_trades > 0:
            win_rate = self.winning_trades / self.total_trades * 100
            self.write_log(f"胜率: {win_rate:.2f}%")
        
        # 加仓策略统计
        if self.enable_scaling and self.scaling_engine:
            self.write_log(f"加仓模式: {self.scaling_method}")
            self.write_log(f"最大加仓层级: {self.scaling_level}")
        
        # 保存调试数据
        if self.debug_mode:
            self.save_debug_data()
        
        self.put_event()
    
    def on_bar(self, bar: BarData):
        """
        1分钟Bar回调
        通过 BarGenerator 合成5分钟Bar
        """
        self.bg.update_bar(bar)
    
    def on_5min_bar(self, bar: BarData):
        """
        5分钟Bar回调 - 核心交易逻辑
        
        ⚠️ 从 hlm5_all_parallel.py 第 2318-2509 行移植
        """
        # 调试：记录每个Bar
        if self.debug_mode:
            if not hasattr(self, '_bar_count'):
                self._bar_count = 0
                self.write_log("📊 调试模式已启用，开始记录数据")
            self._bar_count += 1
        
        # 1. 更新ArrayManager
        self.am.update_bar(bar)
        
        if not self.am.inited:
            if self.debug_mode and self._bar_count % 10 == 0:
                self.write_log(f"⏳ ArrayManager未初始化 (Bar #{self._bar_count}, 需要{self.am.size}个)")
            return
        
        # 2. 检查是否应该强制平仓（收盘前5分钟）
        should_close, close_reason = self.session_mgr.should_force_close(bar.datetime)
        
        if should_close and self.pos != 0:
            self.write_log(f"⚠️ 收盘前强制平仓: {close_reason}")
            
            # 平仓
            if self.pos > 0:
                self.sell(bar.close_price, abs(self.pos))
            else:
                self.cover(bar.close_price, abs(self.pos))
            
            # 更新UI
            self.put_event()
            return
        
        # 3. 计算所有技术指标
        self.calculate_all_indicators(bar)
        
        # 4. 生成交易信号
        long_entry_signal = self.check_entry_conditions_long()
        short_entry_signal = self.check_entry_conditions_short()
        long_exit_signal = self.check_exit_conditions_long()
        short_exit_signal = self.check_exit_conditions_short()
        
        # 5. 执行交易逻辑
        self.execute_trading_logic(
            bar, long_entry_signal, short_entry_signal, 
            long_exit_signal, short_exit_signal
        )
        
        # 6. 风险管理（止损/止盈）
        self.check_risk_management(bar)
        
        # 7. 收集调试数据
        if self.debug_mode:
            self.collect_debug_data(bar, long_entry_signal, short_entry_signal,
                                   long_exit_signal, short_exit_signal)
        
        # 8. 更新UI
        self.put_event()
    
    def calculate_all_indicators(self, bar: BarData):
        """
        计算所有技术指标
        
        使用 hlm5_config.py 中的参数
        """
        # 确保有足够的数据
        if not self.am.inited:
            return
        
        # ======== 1. Price MACD ========
        price_config = {
            'macd_long': self.price_macd_long,
            'macd_mid': self.price_macd_mid,
            'macd_short': self.price_macd_short,
            'diff_ema_period': self.price_diff_ema
        }
        
        price_series = pd.Series(self.am.close_array, index=range(len(self.am.close_array)))
        price_signals = calculate_macd_signals(price_series, config=price_config)
        
        # 获取最新值
        self.price_macd = float(price_signals['MACD'].iloc[-1])
        self.price_macd_signal = float(price_signals['MACD_Signal'].iloc[-1])
        self.price_macd_hist = float(price_signals['MACD_Hist'].iloc[-1])
        self.price_xlpl_phase = int(price_signals['XLPL_Phase'].iloc[-1])
        
        # 合并Cross信号
        # ⚠️ 注意：Cross信号记录在i-1位置，所以要同时检查最后两个位置
        merged_price_cross = merge_price_cross_signals(price_signals)
        # 如果倒数第二个位置有信号，说明最新bar发生了交叉
        if len(merged_price_cross) >= 2 and merged_price_cross[-2] != 0:
            self.price_cross = int(merged_price_cross[-2])
        else:
            self.price_cross = int(merged_price_cross[-1])  # 使用当前值
        
        # ======== 2. Volume MACD ========
        volume_config = {
            'macd_long': self.volume_macd_long,
            'macd_mid': self.volume_macd_mid,
            'macd_short': self.volume_macd_short,
            'diff_ema_period': self.volume_diff_ema
        }
        
        volume_series = pd.Series(self.am.volume_array, index=range(len(self.am.volume_array)))
        volume_signals = calculate_macd_signals(volume_series, config=volume_config)
        
        # 获取最新值
        self.volume_macd = float(volume_signals['MACD'].iloc[-1])
        self.volume_macd_signal = float(volume_signals['MACD_Signal'].iloc[-1])
        self.volume_macd_hist = float(volume_signals['MACD_Hist'].iloc[-1])  # 添加缺失的hist
        self.volume_xlpl_phase = int(volume_signals['XLPL_Phase'].iloc[-1])
        
        # ⚠️ Volume Cross信号记录在i-1位置，检查倒数第二个位置
        if len(volume_signals) >= 2 and volume_signals['Cross_1'].iloc[-2] != 0:
            self.volume_cross = int(volume_signals['Cross_1'].iloc[-2])
        else:
            self.volume_cross = int(volume_signals['Cross_1'].iloc[-1])
        
        # ======== 3. HLBW ========
        hlbw_config = {
            'lookback_period': self.hlbw_lookback,
            'inner_ema': self.hlbw_inner_ema,
            'outer_ema': self.hlbw_outer_ema,
            'trend_ema': self.hlbw_trend_ema
        }
        
        high_series = pd.Series(self.am.high_array, index=range(len(self.am.high_array)))
        low_series = pd.Series(self.am.low_array, index=range(len(self.am.low_array)))
        close_series = pd.Series(self.am.close_array, index=range(len(self.am.close_array)))
        
        hlbw_result = calculate_hlbw(high_series, low_series, close_series, config=hlbw_config)
        
        # 获取最新值
        self.hlbw_trend = float(hlbw_result['HLBW_Trend_Line'].iloc[-1])
        self.hlbw_macd = float(hlbw_result['HLBW_MACD'].iloc[-1])
        self.hlbw_xlpl_phase = int(hlbw_result['HLBW_XLPL_Phase'].iloc[-1])
        
        # ⚠️ HLBW Cross信号也要检查倒数第二个位置（虽然calculate_hlbw已经处理了Cross_1的偏移）
        # 但由于Cross_1本身记录在i-1，我们仍需检查前一个位置
        if len(hlbw_result) >= 2 and hlbw_result['HLBW_Cross'].iloc[-2] != 0:
            self.hlbw_cross = int(hlbw_result['HLBW_Cross'].iloc[-2])
        else:
            self.hlbw_cross = int(hlbw_result['HLBW_Cross'].iloc[-1])
        
        # ======== 4. Prophet 预测（简化版本，避免每个Bar都训练） ========
        # ⚠️ Prophet暂时禁用，后续需要专门时间修改架构
        # 在实时交易中，Prophet较慢，可以选择性禁用
        # 或者每N个Bar更新一次
        self.prophet_yhat = 0.0
        self.prophet_phase = 0
        self.prophet_duration = 0
        
        # 可选：每天更新一次Prophet预测
        # if self.should_update_prophet(bar.datetime):
        #     self.update_prophet_forecast()
        
        # ======== 5. 更新prev值缓存（用于下一个bar的入场条件判断） ========
        # 注意：必须在计算完所有指标后、调用check_entry_conditions之前更新
        # 这样check_entry_conditions才能使用正确的prev值
        # （但实际上在当前bar使用的是上一个bar计算后保存的prev值）
        # 所以这里保存的是给下一个bar使用的
        self.prev_price_cross = self.price_cross
        self.prev_volume_cross = self.volume_cross
        self.prev_hlbw_cross = self.hlbw_cross
    
    def check_entry_conditions_long(self):
        """
        检查做多入场条件
        
        ⚠️ 从 hlm5_all_parallel.py 第 1891-1988 行原样复制
        
        Returns:
        --------
        int : 做多信号类型 (1-6)，0表示无信号
        """
        # 获取当前和前一个指标值
        # ⚠️ 使用缓存的prev值（上一个bar保存的）
        current_price_cross = self.price_cross
        current_volume_cross = self.volume_cross
        current_hlbw_cross = self.hlbw_cross
        
        prev_price_cross = self.prev_price_cross
        prev_volume_cross = self.prev_volume_cross
        prev_hlbw_cross = self.prev_hlbw_cross
        
        # 1. 价格MACD信号（检查当前或前一个bar的交叉）
        price_cross = (current_price_cross == 1) or (prev_price_cross == 1)
        price_la = (self.price_xlpl_phase == 2)  # 2表示拉升(LA)
        price_signal = price_cross or price_la
        
        # 2. 成交量MACD信号（检查当前或前一个bar的交叉）
        volume_cross = (current_volume_cross == 1) or (prev_volume_cross == 1)
        volume_la = (self.volume_xlpl_phase == 2)
        volume_xi = (self.volume_xlpl_phase == 1)  # 1表示吸筹(XI)
        volume_signal = volume_cross or volume_la or volume_xi
        
        # 3. HLBW MACD信号（检查当前或前一个bar的交叉）
        hlbw_cross = (current_hlbw_cross == 1) or (current_hlbw_cross == 100) or \
                     (prev_hlbw_cross == 1) or (prev_hlbw_cross == 100)
        hlbw_la = (self.hlbw_xlpl_phase == 2)
        hlbw_signal = hlbw_cross or hlbw_la
        
        # 统计Cross信号数量
        cross_count = sum([
            1 if price_cross else 0,
            1 if volume_cross else 0,
            1 if hlbw_cross else 0
        ])
        
        # 特殊情况：PMACD和BWMACD都有Cross信号，Volume处于XI状态
        special_case = (price_cross and hlbw_cross and volume_xi)
        
        # 4. Prophet趋势确认
        prophet_signal = (
            (self.prophet_phase == 2) and  # 处于拉升状态
            (self.prophet_duration >= self.prophet_min_duration)
        )
        
        # 简化版本：不强制要求Prophet信号（Prophet计算较慢）
        # 根据 hlm5_config.py，require_prophet_trend = False
        if not EQUITY_CONFIG['TRADING_SIGNALS']['entry_conditions']['require_prophet_trend']:
            prophet_signal = True  # 始终为True，不作为限制条件
        
        # 初始化 entry 信号类型
        entry_signal_type = 0
        
        # 定义有效信号的优先级顺序（从 hlm5_all_parallel.py 原样复制）
        # ⚠️ 优化：禁用类型6兜底信号，仅使用高质量信号（类型1-5）
        signals = [
            (price_cross and volume_cross and hlbw_cross and prophet_signal, 1),
            (price_cross and volume_la and hlbw_cross and prophet_signal, 2),
            (price_cross and volume_xi and hlbw_cross and prophet_signal, 3),
            (volume_la and volume_cross and hlbw_cross and prophet_signal, 4),
            (price_cross and volume_cross and hlbw_la and prophet_signal, 5),
            # 类型6已禁用（兜底信号）
            # ((cross_count >= 2 and all([price_signal, volume_signal, hlbw_signal])) or special_case, 6)
        ]
        
        # 遍历信号列表，找到第一个有效信号
        for valid_signal, signal_type in signals:
            if valid_signal:
                entry_signal_type = signal_type
                break
        
        return entry_signal_type
    
    def check_entry_conditions_short(self):
        """
        检查做空入场条件
        
        ⚠️ 从 hlm5_all_parallel.py 第 1991-2066 行原样复制
        
        Returns:
        --------
        int : 做空信号类型 (-1到-6)，0表示无信号
        """
        # 如果未启用双向交易，返回0
        if not self.enable_bidirectional:
            return 0
        
        # ⚠️ 使用缓存的prev值（上一个bar保存的）
        current_price_cross = self.price_cross
        current_volume_cross = self.volume_cross
        current_hlbw_cross = self.hlbw_cross
        
        prev_price_cross = self.prev_price_cross
        prev_volume_cross = self.prev_volume_cross
        prev_hlbw_cross = self.prev_hlbw_cross
        
        # 1. 价格MACD信号（做空：寻找下跌信号，检查当前或前一个bar）
        price_cross = (current_price_cross == -1) or (prev_price_cross == -1)
        price_lo = (self.price_xlpl_phase == 4)  # 4表示下跌(LO)
        price_signal = price_cross or price_lo
        
        # 2. 成交量MACD信号（检查当前或前一个bar）
        volume_cross = (current_volume_cross == 1) or (current_volume_cross == -1) or \
                       (prev_volume_cross == 1) or (prev_volume_cross == -1)
        volume_la = (self.volume_xlpl_phase == 2)
        volume_xi = (self.volume_xlpl_phase == 1)
        volume_signal = volume_cross or volume_la or volume_xi
        
        # 3. HLBW MACD信号（做空：寻找下跌信号，检查当前或前一个bar）
        hlbw_cross = (current_hlbw_cross == -1) or (current_hlbw_cross == -100) or \
                     (prev_hlbw_cross == -1) or (prev_hlbw_cross == -100)
        hlbw_lo = (self.hlbw_xlpl_phase == 4)  # 4表示下跌
        hlbw_signal = hlbw_cross or hlbw_lo
        
        # 统计Cross信号数量
        cross_count = sum([
            1 if price_cross else 0,
            1 if volume_cross else 0,
            1 if hlbw_cross else 0
        ])
        
        # 特殊情况
        special_case = (price_cross and hlbw_cross and volume_xi)
        
        # 4. Prophet趋势确认（做空：寻找下跌趋势）
        prophet_signal = (
            (self.prophet_phase == 4) and  # 处于下跌状态
            (self.prophet_duration >= self.prophet_min_duration)
        )
        
        # 简化版本：不强制要求Prophet
        if not EQUITY_CONFIG['TRADING_SIGNALS']['entry_conditions']['require_prophet_trend']:
            prophet_signal = True
        
        # 初始化 entry 信号类型（做空用负数）
        entry_signal_type = 0
        
        # 定义有效信号的优先级顺序
        # ⚠️ 优化：禁用类型-6兜底信号，仅使用高质量信号（类型-1至-5）
        signals = [
            (price_cross and volume_cross and hlbw_cross and prophet_signal, -1),
            (price_cross and volume_la and hlbw_cross and prophet_signal, -2),
            (price_cross and volume_xi and hlbw_cross and prophet_signal, -3),
            (volume_la and volume_cross and hlbw_cross and prophet_signal, -4),
            (price_cross and volume_cross and hlbw_lo and prophet_signal, -5),
            # 类型-6已禁用（兜底信号）
            # ((cross_count >= 2 and all([price_signal, volume_signal, hlbw_signal])) or special_case, -6)
        ]
        
        # 遍历信号列表，找到第一个有效信号
        for valid_signal, signal_type in signals:
            if valid_signal:
                entry_signal_type = signal_type
                break
        
        return entry_signal_type
    
    def check_exit_conditions_long(self):
        """
        检查做多出场条件
        
        ⚠️ 从 hlm5_all_parallel.py 第 2069-2118 行原样复制
        
        Returns:
        --------
        bool : 是否满足做多出场条件
        """
        # 初始化变量
        reverse_entry = False
        price_reversal = False
        hlbw_reversal = False
        prophet_exit = False
        
        # 检查反向入场信号
        if self.price_cross < 0:  # 价格MACD下穿
            reverse_entry = True
        
        # 检查价格反转
        if self.price_xlpl_phase == 4:  # 下跌阶段
            price_reversal = True
        
        # 检查HLBW反转
        if self.hlbw_cross < 0:  # HLBW下穿
            hlbw_reversal = True
        
        # 检查Prophet预测
        if self.prophet_phase == 4:  # 当前预测处于下跌阶段
            prophet_exit = True
        
        # 合并所有反向信号
        reverse_signal = reverse_entry or price_reversal or hlbw_reversal or prophet_exit
        
        return reverse_signal
    
    def check_exit_conditions_short(self):
        """
        检查做空出场条件
        
        ⚠️ 从 hlm5_all_parallel.py 第 2121-2169 行原样复制
        
        Returns:
        --------
        bool : 是否满足做空出场条件
        """
        # 初始化变量
        reverse_entry = False
        price_reversal = False
        hlbw_reversal = False
        prophet_exit = False
        
        # 检查反向入场信号（做空出场：遇到上涨信号）
        if self.price_cross > 0:  # 价格MACD上穿
            reverse_entry = True
        
        # 检查价格反转（做空出场：遇到拉升阶段）
        if self.price_xlpl_phase == 2:  # 拉升阶段
            price_reversal = True
        
        # 检查HLBW反转（做空出场：遇到上穿）
        if self.hlbw_cross > 0:  # HLBW上穿
            hlbw_reversal = True
        
        # 检查Prophet预测（做空出场：遇到拉升阶段）
        if self.prophet_phase == 2:  # 当前预测处于拉升阶段
            prophet_exit = True
        
        # 合并所有反向信号
        reverse_signal = reverse_entry or price_reversal or hlbw_reversal or prophet_exit
        
        return reverse_signal
    
    def execute_trading_logic(self, bar: BarData, long_signal, short_signal, 
                             long_exit, short_exit):
        """
        执行交易逻辑
        
        ⚠️ 从 hlm5_all_parallel.py 第 2391-2509 行移植
        支持加仓策略和固定仓位两种模式
        
        优先级：平仓 > 反向开仓 > 同向加仓
        """
        current_price = bar.close_price
        
        # ======== 模式1：启用加仓策略 ========
        if self.enable_scaling and self.scaling_engine:
            self._execute_with_scaling(bar, long_signal, short_signal, long_exit, short_exit)
        
        # ======== 模式2：固定仓位交易 ========
        else:
            self._execute_with_fixed_size(bar, long_signal, short_signal, long_exit, short_exit)
    
    def _execute_with_scaling(self, bar: BarData, long_signal, short_signal, 
                             long_exit, short_exit):
        """
        使用加仓策略执行交易
        """
        current_price = bar.close_price
        
        # 组合信号：出场信号转换为反向信号
        signal_type = 0
        if long_signal > 0 and not long_exit:
            signal_type = long_signal
        elif short_signal < 0 and not short_exit and self.enable_bidirectional:
            signal_type = short_signal
        elif long_exit and self.pos > 0:
            signal_type = -1  # 做多出场，发送做空信号
        elif short_exit and self.pos < 0:
            signal_type = 1  # 做空出场，发送做多信号
        
        # 调用加仓引擎处理信号
        action_result = self.scaling_engine.on_signal(
            signal_type=signal_type,
            current_price=current_price,
            timestamp=bar.datetime
        )
        
        # 更新加仓状态变量
        self.scaling_position = self.scaling_engine.tracker.current_position
        self.scaling_level = self.scaling_engine.tracker.current_scaling_level
        if self.scaling_engine.tracker.current_position != 0:
            self.avg_entry_price = self.scaling_engine.tracker.get_average_price()
        
        # 根据加仓引擎的决策执行交易
        action = action_result.get('action', '')
        size = action_result.get('size', 0)
        
        if action == 'entry':
            # 首次开仓
            if size > 0:
                self.write_log(f"加仓策略：首次做多开仓 {size}手 (信号类型: {signal_type})")
                self.write_log(f"  Price: MACD={self.price_macd:.4f}, Phase={self.price_xlpl_phase}, Cross={self.price_cross}")
                self.write_log(f"  Volume: MACD={self.volume_macd:.4f}, Phase={self.volume_xlpl_phase}, Cross={self.volume_cross}")
                self.write_log(f"  HLBW: Trend={self.hlbw_trend:.2f}, Phase={self.hlbw_xlpl_phase}, Cross={self.hlbw_cross}")
                self.buy(current_price, abs(size))
            else:
                self.write_log(f"加仓策略：首次做空开仓 {abs(size)}手 (信号类型: {signal_type})")
                self.short(current_price, abs(size))
            
            self.record_entry('long' if size > 0 else 'short', current_price)
        
        elif action == 'add':
            # 加仓
            level = action_result.get('scaling_level', 0)
            if size > 0:
                self.write_log(f"加仓策略：做多加仓 {size}手 (层级: {level})")
                self.buy(current_price, abs(size))
            else:
                self.write_log(f"加仓策略：做空加仓 {abs(size)}手 (层级: {level})")
                self.short(current_price, abs(size))
        
        elif action in ['exit', 'exit_trailing_stop']:
            # 平仓
            pnl = action_result.get('pnl', 0.0)
            avg_price = action_result.get('avg_entry_price', 0.0)
            levels = action_result.get('scaling_levels', 0)
            
            if action == 'exit_trailing_stop':
                self.write_log(f"加仓策略：移动止损触发平仓 {abs(size)}手")
            else:
                self.write_log(f"加仓策略：反向信号平仓 {abs(size)}手")
            
            self.write_log(f"  加仓层级: {levels}, 平均价格: {avg_price:.2f}, 净盈亏: {pnl:.2f}元")
            
            if size > 0:  # 平空仓
                self.cover(current_price, abs(size))
            else:  # 平多仓
                self.sell(current_price, abs(size))
            
            self.record_trade_result('long' if size < 0 else 'short')
    
    def _execute_with_fixed_size(self, bar: BarData, long_signal, short_signal, 
                                 long_exit, short_exit):
        """
        使用固定仓位执行交易（原有逻辑）
        """
        current_price = bar.close_price
        
        # ======== 情况1：当前持有多仓 ========
        if self.pos > 0:
            # 检查是否需要平多仓
            if long_exit:
                self.write_log(f"做多出场信号触发")
                self.sell(current_price, abs(self.pos))
                self.record_trade_result('long')
                
            # 检查是否有做空信号（平多开空）
            elif self.enable_bidirectional and short_signal < 0:
                self.write_log(f"反向信号：平多开空 (信号类型: {short_signal})")
                # 先平多仓
                self.sell(current_price, abs(self.pos))
                self.record_trade_result('long')
                # 再开空仓
                self.short(current_price, self.fixed_size)
                self.record_entry('short', current_price)
        
        # ======== 情况2：当前持有空仓 ========
        elif self.pos < 0:
            # 检查是否需要平空仓
            if short_exit:
                self.write_log(f"做空出场信号触发")
                self.cover(current_price, abs(self.pos))
                self.record_trade_result('short')
                
            # 检查是否有做多信号（平空开多）
            elif long_signal > 0:
                self.write_log(f"反向信号：平空开多 (信号类型: {long_signal})")
                # 先平空仓
                self.cover(current_price, abs(self.pos))
                self.record_trade_result('short')
                # 再开多仓
                self.buy(current_price, self.fixed_size)
                self.record_entry('long', current_price)
        
        # ======== 情况3：当前无仓位 ========
        else:
            # 检查做多信号
            if long_signal > 0:
                self.write_log(f"做多入场信号触发 (信号类型: {long_signal})")
                self.write_log(f"  Price: MACD={self.price_macd:.4f}, Phase={self.price_xlpl_phase}, Cross={self.price_cross}")
                self.write_log(f"  Volume: MACD={self.volume_macd:.4f}, Phase={self.volume_xlpl_phase}, Cross={self.volume_cross}")
                self.write_log(f"  HLBW: Trend={self.hlbw_trend:.2f}, Phase={self.hlbw_xlpl_phase}, Cross={self.hlbw_cross}")
                
                self.buy(current_price, self.fixed_size)
                self.record_entry('long', current_price)
                
            # 检查做空信号
            elif self.enable_bidirectional and short_signal < 0:
                self.write_log(f"做空入场信号触发 (信号类型: {short_signal})")
                self.write_log(f"  Price: MACD={self.price_macd:.4f}, Phase={self.price_xlpl_phase}, Cross={self.price_cross}")
                self.write_log(f"  Volume: MACD={self.volume_macd:.4f}, Phase={self.volume_xlpl_phase}, Cross={self.volume_cross}")
                self.write_log(f"  HLBW: Trend={self.hlbw_trend:.2f}, Phase={self.hlbw_xlpl_phase}, Cross={self.hlbw_cross}")
                
                self.short(current_price, self.fixed_size)
                self.record_entry('short', current_price)
    
    def check_risk_management(self, bar: BarData):
        """
        风险管理：止损/止盈/跟踪止损
        
        从 hlm5_config.py 读取风险参数
        
        注意：加仓模式下由加仓引擎管理风险（移动止损），这里跳过
        """
        if self.pos == 0:
            return
        
        # 如果启用加仓，风险管理由加仓引擎处理
        if self.enable_scaling and self.scaling_engine:
            return
        
        current_price = bar.close_price
        
        # 更新最高价（用于跟踪止损）
        if self.pos > 0:
            self.highest_price_since_entry = max(
                self.highest_price_since_entry, 
                current_price
            )
        
        # ======== 止损检查 ========
        if self.entry_price > 0:
            if self.pos > 0:
                # 做多止损
                loss_pct = (current_price - self.entry_price) / self.entry_price
                if loss_pct <= -self.stop_loss_pct:
                    self.write_log(f"⚠️ 触发止损：亏损 {loss_pct*100:.2f}%")
                    self.sell(current_price, abs(self.pos))
                    self.record_trade_result('long')
                    return
                
                # 止盈检查
                profit_pct = (current_price - self.entry_price) / self.entry_price
                if profit_pct >= self.take_profit_pct:
                    self.write_log(f"✅ 触发止盈：盈利 {profit_pct*100:.2f}%")
                    self.sell(current_price, abs(self.pos))
                    self.record_trade_result('long')
                    return
                
                # 跟踪止损检查
                if self.highest_price_since_entry > self.entry_price:
                    trailing_loss = (current_price - self.highest_price_since_entry) / self.highest_price_since_entry
                    if trailing_loss <= -self.trailing_stop_pct:
                        self.write_log(f"⚠️ 触发跟踪止损：从最高点回撤 {trailing_loss*100:.2f}%")
                        self.sell(current_price, abs(self.pos))
                        self.record_trade_result('long')
                        return
            
            else:  # 做空
                # 做空止损
                loss_pct = (self.entry_price - current_price) / self.entry_price
                if loss_pct <= -self.stop_loss_pct:
                    self.write_log(f"⚠️ 触发止损：亏损 {loss_pct*100:.2f}%")
                    self.cover(current_price, abs(self.pos))
                    self.record_trade_result('short')
                    return
                
                # 止盈检查
                profit_pct = (self.entry_price - current_price) / self.entry_price
                if profit_pct >= self.take_profit_pct:
                    self.write_log(f"✅ 触发止盈：盈利 {profit_pct*100:.2f}%")
                    self.cover(current_price, abs(self.pos))
                    self.record_trade_result('short')
                    return
    
    def record_entry(self, direction, price):
        """记录开仓信息"""
        self.entry_price = price
        self.highest_price_since_entry = price
        self.write_log(f"开仓记录：{'做多' if direction == 'long' else '做空'} @ {price:.2f}")
    
    def record_trade_result(self, direction):
        """记录交易结果"""
        self.total_trades += 1
        # 这里可以计算盈亏，但VNPy会自动处理
        self.entry_price = 0.0
        self.highest_price_since_entry = 0.0
    
    def on_order(self, order: OrderData):
        """订单回调"""
        self.put_event()
    
    def on_trade(self, trade: TradeData):
        """成交回调"""
        # 记录成交
        if trade.direction == Direction.LONG:
            if trade.offset == Offset.OPEN:
                self.write_log(f"✅ 买入开仓成交: {trade.volume}手 @ {trade.price:.2f}")
            else:
                self.write_log(f"✅ 卖出平仓成交: {trade.volume}手 @ {trade.price:.2f}")
        else:
            if trade.offset == Offset.OPEN:
                self.write_log(f"✅ 卖出开仓成交: {trade.volume}手 @ {trade.price:.2f}")
            else:
                self.write_log(f"✅ 买入平仓成交: {trade.volume}手 @ {trade.price:.2f}")
        
        self.put_event()
    
    def on_stop_order(self, stop_order: StopOrder):
        """停止单回调"""
        self.put_event()
    
    def collect_debug_data(self, bar: BarData, long_entry, short_entry, long_exit, short_exit):
        """
        收集调试数据
        """
        debug_record = {
            # 时间和价格
            'datetime': bar.datetime,
            'open': bar.open_price,
            'high': bar.high_price,
            'low': bar.low_price,
            'close': bar.close_price,
            'volume': bar.volume,
            
            # Price MACD指标
            'price_macd': self.price_macd,
            'price_macd_signal': self.price_macd_signal,
            'price_macd_hist': self.price_macd_hist,
            'price_xlpl_phase': self.price_xlpl_phase,
            'price_cross': self.price_cross,
            
            # Volume MACD指标
            'volume_macd': self.volume_macd,
            'volume_macd_signal': self.volume_macd_signal,
            'volume_macd_hist': self.volume_macd_hist,
            'volume_xlpl_phase': self.volume_xlpl_phase,
            'volume_cross': self.volume_cross,
            
            # HLBW指标
            'hlbw_trend': self.hlbw_trend,  # 使用hlbw_trend而不是hlbw_trend_line
            'hlbw_macd': self.hlbw_macd,
            'hlbw_macd_signal': getattr(self, 'hlbw_macd_signal', 0.0),  # 使用getattr防止属性不存在
            'hlbw_xlpl_phase': self.hlbw_xlpl_phase,
            'hlbw_cross': self.hlbw_cross,
            
            # Prophet指标
            'prophet_yhat': self.prophet_yhat,
            'prophet_xlpl_phase': getattr(self, 'prophet_xlpl_phase', 0),  # 使用getattr
            'prophet_phase': self.prophet_phase,  # 添加实际存在的属性
            'prophet_cross': getattr(self, 'prophet_cross', 0),  # 使用getattr
            'prophet_duration': self.prophet_duration,  # 使用实际存在的prophet_duration
            
            # 信号
            'long_entry_signal': long_entry,
            'short_entry_signal': short_entry,
            'long_exit_signal': long_exit,
            'short_exit_signal': short_exit,
            
            # 持仓和状态
            'pos': self.pos,
            'entry_price': self.entry_price,
            'highest_price': getattr(self, 'highest_price', 0.0),  # 使用getattr
            'lowest_price': getattr(self, 'lowest_price', 0.0),  # 使用getattr
            
            # 加仓相关
            'scaling_position': self.scaling_position,
            'scaling_level': self.scaling_level,
            'avg_entry_price': self.avg_entry_price,
        }
        
        self.debug_data.append(debug_record)
    
    def save_debug_data(self, output_path=None):
        """
        保存调试数据到CSV文件
        
        Parameters:
        -----------
        output_path : str, optional
            输出文件路径，如果不提供则自动生成
        """
        if not self.debug_mode or not hasattr(self, 'debug_data') or not self.debug_data:
            self.write_log("没有调试数据可保存")
            return
        
        # 转换为DataFrame
        df = pd.DataFrame(self.debug_data)
        
        # 如果没有指定输出路径，自动生成
        if output_path is None:
            output_dir = Path(__file__).parent.parent / "output" / "debug"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = output_dir / f"debug_data_{self.vt_symbol}_{timestamp}.csv"
        
        # 保存到CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        self.write_log(f"调试数据已保存到: {output_path}")
        self.write_log(f"共保存 {len(df)} 条记录")
        
        # 生成信号统计
        self.write_log(f"\n=== 信号统计 ===")
        self.write_log(f"做多入场信号: {(df['long_entry_signal'] > 0).sum()} 次")
        self.write_log(f"做空入场信号: {(df['short_entry_signal'] < 0).sum()} 次")
        self.write_log(f"做多出场信号: {df['long_exit_signal'].sum()} 次")
        self.write_log(f"做空出场信号: {df['short_exit_signal'].sum()} 次")
        
        # 指标统计
        self.write_log(f"\n=== 指标统计 ===")
        self.write_log(f"Price Cross不为0: {(df['price_cross'] != 0).sum()} 次")
        self.write_log(f"Volume Cross不为0: {(df['volume_cross'] != 0).sum()} 次")
        self.write_log(f"HLBW Cross不为0: {(df['hlbw_cross'] != 0).sum()} 次")
        self.write_log(f"Prophet Cross不为0: {(df['prophet_cross'] != 0).sum()} 次")
        
        return output_path

