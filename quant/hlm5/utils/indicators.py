# -*- coding: utf-8 -*-
"""
技术指标计算模块
从 hlm5_all_parallel.py 原样移植核心指标计算逻辑

包含：
- calculate_macd_signals: MACD-XLPL-CROSS 指标
- calculate_hlbw: HLBW 趋势指标
- calculate_prophet_forecast: Prophet 时间序列预测

⚠️ 关键：所有算法逻辑保持100%一致，不做修改
"""

import numpy as np
import pandas as pd
import talib
from prophet import Prophet

# 从配置文件读取参数
import sys
from pathlib import Path
# 添加父目录到路径，以便导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from hlm5_config import EQUITY_CONFIG

# ====================================================================
# HLBW 全局常量（从配置读取）
# ====================================================================

HLBW_CONFIG = EQUITY_CONFIG['INDICATORS']['HLBW']
HLBW_TOP_LINE = HLBW_CONFIG['levels']['top_line']          # 89
HLBW_MID_HIGH_LINE = HLBW_CONFIG['levels']['mid_high_line'] # 75
HLBW_MID_LINE = HLBW_CONFIG['levels']['mid_line']          # 50
HLBW_MID_LOW_LINE = HLBW_CONFIG['levels']['mid_low_line']  # 25
HLBW_BOTTOM_LINE = HLBW_CONFIG['levels']['bottom_line']    # 11

# ====================================================================
# 1. MACD-XLPL-CROSS 指标计算
# ====================================================================

def calculate_macd_signals(series, 
                         macd_long=None, 
                         macd_mid=None, 
                         macd_short=None,
                         diff_ema_period=None,
                         config=None):
    """
    计算MACD及其相关信号，包含修正后的XLPL阶段判断
    
    ⚠️ 从 hlm5_all_parallel.py 第 763-937 行原样复制
    
    Parameters:
    -----------
    series : pandas.Series or numpy.ndarray
        输入数据序列（价格或成交量）
    macd_long : int, optional
        MACD长期EMA周期（默认从config读取）
    macd_mid : int, optional
        MACD中期EMA周期（默认从config读取）
    macd_short : int, optional
        MACD短期EMA周期/信号线（默认从config读取）
    diff_ema_period : int, optional
        MACD差值的EMA周期（默认从config读取）
    config : dict, optional
        配置字典，如果提供则覆盖默认配置
        
    Returns:
    --------
    pandas.DataFrame : 包含以下列的DataFrame:
        - MACD: MACD线(DIF), float64
        - MACD_Signal: MACD信号线(DEA), float64
        - MACD_Hist: MACD柱状图, float64
        - DIFDEA_DIFF: DIF-DEA的差值, float64
        - DDMA_DIFF: DIFDEA_DIFF的EMA, float64
        - XLPL_Phase: XLPL阶段 (1:吸筹, 2:拉升, 3:派发, 4:下跌), float64
        - Cross_1: DIF和DEA的交叉信号, float64
        - Cross_2: MACD差值与其EMA的交叉信号, float64
        - Cross_3: DEA与0轴的交叉信号, float64
        - Cross_4: DIF与0轴的交叉信号, float64
    """
    # 使用配置或默认参数
    if config is not None:
        macd_long = config.get('macd_long', 20)
        macd_mid = config.get('macd_mid', 8)
        macd_short = config.get('macd_short', 5)
        diff_ema_period = config.get('diff_ema_period', 2)
    else:
        # 从全局配置读取
        price_config = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']
        macd_long = macd_long or price_config['macd_long']
        macd_mid = macd_mid or price_config['macd_mid']
        macd_short = macd_short or price_config['macd_short']
        diff_ema_period = diff_ema_period or price_config['diff_ema_period']
    
    # 确保输入是pandas Series
    if isinstance(series, np.ndarray):
        series = pd.Series(series)
    
    # 1. 计算MACD基础值（使用 TA-Lib）
    dif, dea, hist = talib.MACD(
        series, 
        fastperiod=macd_mid,     # 中期
        slowperiod=macd_long,    # 长期
        signalperiod=macd_short  # 短期
    )
    
    # 转换为 Series 并保持索引对齐
    dif = pd.Series(dif, index=series.index)
    dea = pd.Series(dea, index=series.index)
    hist = pd.Series(hist, index=series.index)
    
    # 2. 计算MACD差值及其EMA
    difdea_diff = dif - dea
    ddma_diff = difdea_diff.ewm(span=diff_ema_period, adjust=False).mean()
    
    # 3. 计算所有交叉信号
    cross_1 = pd.Series(0, index=series.index, dtype='float64')
    cross_2 = pd.Series(0, index=series.index, dtype='float64')
    cross_3 = pd.Series(0, index=series.index, dtype='float64')
    cross_4 = pd.Series(0, index=series.index, dtype='float64')
    
    # DIF与DEA的交叉
    for i in range(1, len(series)):
        if dif.iloc[i] > dea.iloc[i] and dif.iloc[i-1] <= dea.iloc[i-1]:
            cross_1.iloc[i-1] = 1.0  # 上穿信号记录在前一位置
        elif dif.iloc[i] < dea.iloc[i] and dif.iloc[i-1] >= dea.iloc[i-1]:
            cross_1.iloc[i-1] = -1.0  # 下穿信号记录在前一位置
            
    # DIFDEA_DIFF与DDMA_DIFF的交叉
    for i in range(1, len(series)):
        if difdea_diff.iloc[i] > ddma_diff.iloc[i] and difdea_diff.iloc[i-1] <= ddma_diff.iloc[i-1]:
            cross_2.iloc[i-1] = 10.0  # 上穿信号
        elif difdea_diff.iloc[i] < ddma_diff.iloc[i] and difdea_diff.iloc[i-1] >= ddma_diff.iloc[i-1]:
            cross_2.iloc[i-1] = -10.0  # 下穿信号
            
    # DEA与0轴的交叉
    for i in range(1, len(series)):
        if dea.iloc[i] > 0 and dea.iloc[i-1] <= 0:
            cross_3.iloc[i-1] = 100.0  # 上穿0轴
        elif dea.iloc[i] < 0 and dea.iloc[i-1] >= 0:
            cross_3.iloc[i-1] = -100.0  # 下穿0轴
            
    # DIF与0轴的交叉
    for i in range(1, len(series)):
        if dif.iloc[i] > 0 and dif.iloc[i-1] <= 0:
            cross_4.iloc[i-1] = 1000.0  # 上穿0轴
        elif dif.iloc[i] < 0 and dif.iloc[i-1] >= 0:
            cross_4.iloc[i-1] = -1000.0  # 下穿0轴

    # 4. 计算XLPL阶段
    xlpl_phase = pd.Series(0, index=series.index, dtype='float64')
    for i in range(len(series)):
        if difdea_diff.iloc[i] <= 0 and ddma_diff.iloc[i] > 0:
            xlpl_phase.iloc[i] = 1.0  # 吸筹 (XI)
        elif difdea_diff.iloc[i] > 0 and ddma_diff.iloc[i] >= 0:
            xlpl_phase.iloc[i] = 2.0  # 拉升 (LA)
        elif difdea_diff.iloc[i] >= 0 and ddma_diff.iloc[i] < 0:
            xlpl_phase.iloc[i] = 3.0  # 派发 (PI)
        elif difdea_diff.iloc[i] < 0 and ddma_diff.iloc[i] <= 0:
            xlpl_phase.iloc[i] = 4.0  # 下跌 (LO)

    # 5. 创建结果DataFrame
    results = pd.DataFrame({
        'MACD': dif,
        'MACD_Signal': dea,
        'MACD_Hist': hist,
        'DIFDEA_DIFF': pd.to_numeric(difdea_diff, errors='coerce'),
        'DDMA_DIFF': pd.to_numeric(ddma_diff, errors='coerce'),
        'XLPL_Phase': xlpl_phase,
        'Cross_1': cross_1,
        'Cross_2': cross_2,
        'Cross_3': cross_3,
        'Cross_4': cross_4
    })
    
    return results


# ====================================================================
# 2. HLBW 趋势指标计算
# ====================================================================

def calculate_hlbw(high_series, low_series, close_series, config=None):
    """
    计算HLBW指标及其MACD信号
    
    ⚠️ 从 hlm5_all_parallel.py 第 1136-1253 行移植
    
    Parameters:
    -----------
    high_series : pandas.Series
        最高价序列
    low_series : pandas.Series
        最低价序列
    close_series : pandas.Series
        收盘价序列
    config : dict, optional
        配置字典
        
    Returns:
    --------
    pandas.DataFrame : 包含以下列:
        - HLBW_Trend_Line: HLBW趋势线, float64
        - HLBW_MACD: HLBW MACD线, float64
        - HLBW_MACD_Signal: HLBW MACD信号线, float64
        - HLBW_MACD_Hist: HLBW MACD柱状图, float64
        - HLBW_XLPL_Phase: XLPL阶段, float64
        - HLBW_Cross: 合并的交叉信号, float64
    """
    # 使用配置或默认参数
    if config is None:
        config = HLBW_CONFIG
    
    lookback_period = config['lookback_period']  # 40
    inner_ema = config['inner_ema']              # 3
    outer_ema = config['outer_ema']              # 2
    trend_ema = config['trend_ema']              # 2
    
    # 计算HLBW基础指标
    llv_low = pd.to_numeric(
        low_series.rolling(window=lookback_period).min(), 
        errors='coerce'
    )
    hhv_high = pd.to_numeric(
        high_series.rolling(window=lookback_period).max(), 
        errors='coerce'
    )
    
    # 计算基础比率
    basic_ratio = pd.to_numeric(
        (close_series - llv_low) / (hhv_high - llv_low) * 100, 
        errors='coerce'
    )
    
    # 计算趋势线
    sma_inner = pd.to_numeric(
        basic_ratio.ewm(span=inner_ema, adjust=False).mean(), 
        errors='coerce'
    )
    sma_outer = pd.to_numeric(
        sma_inner.ewm(span=outer_ema, adjust=False).mean(), 
        errors='coerce'
    )
    x_7 = pd.to_numeric(3 * sma_inner - 2 * sma_outer, errors='coerce')
    trend_line = pd.to_numeric(
        x_7.ewm(span=trend_ema, adjust=False).mean(), 
        errors='coerce'
    )
    
    # 计算MACD信号
    signals = calculate_macd_signals(trend_line, config=config)
    
    # 合并Cross信号（应用HLBW特定规则）
    merged_cross = np.zeros(len(signals))
    
    for i in range(len(signals)):
        trend_line_value = trend_line.iloc[i]
        cross_value = 0
        
        # 优先处理Cross_1信号
        if signals['Cross_1'].iloc[i] > 0 and trend_line_value >= HLBW_BOTTOM_LINE:
            cross_value = 1
        elif signals['Cross_1'].iloc[i] < 0 and trend_line_value <= HLBW_TOP_LINE:
            cross_value = -1
            
        # 如果没有Cross_1信号，检查Cross_2
        elif signals['Cross_2'].iloc[i] != 0:
            difdea_diff = signals['DIFDEA_DIFF'].iloc[i]
            if (signals['Cross_2'].iloc[i] > 0 and 
                difdea_diff > 0 and 
                trend_line_value > HLBW_MID_LOW_LINE):
                cross_value = 10
            elif (signals['Cross_2'].iloc[i] < 0 and 
                  difdea_diff < 0 and 
                  trend_line_value < HLBW_MID_HIGH_LINE):
                cross_value = -10
                
        # 如果既没有Cross_1也没有Cross_2信号，检查Cross_3
        elif signals['Cross_3'].iloc[i] != 0:
            if signals['Cross_3'].iloc[i] > 0:
                cross_value = 100
            else:
                cross_value = -100
        
        merged_cross[i] = cross_value
    
    # 准备返回数据
    hlbw_df = pd.DataFrame(index=close_series.index)
    hlbw_df['HLBW_Trend_Line'] = pd.to_numeric(trend_line, errors='coerce')
    hlbw_df['HLBW_MACD'] = pd.to_numeric(signals['MACD'], errors='coerce')
    hlbw_df['HLBW_MACD_Signal'] = pd.to_numeric(signals['MACD_Signal'], errors='coerce')
    hlbw_df['HLBW_MACD_Hist'] = pd.to_numeric(signals['MACD_Hist'], errors='coerce')
    hlbw_df['HLBW_XLPL_Phase'] = pd.to_numeric(signals['XLPL_Phase'], errors='coerce')
    hlbw_df['HLBW_Cross'] = pd.to_numeric(merged_cross, errors='coerce')
    
    return hlbw_df


# ====================================================================
# 3. Prophet 时间序列预测
# ====================================================================

def calculate_prophet_forecast(close_series, forecast_periods=None, config=None):
    """
    使用Prophet模型进行预测并处理MACD-XLPL-CROSS信号
    
    ⚠️ 从 hlm5_all_parallel.py 第 1258-1406 行移植
    
    Parameters:
    -----------
    close_series : pandas.Series
        收盘价序列（需要有datetime index）
    forecast_periods : int, optional
        预测周期数（默认从config读取）
    config : dict, optional
        配置字典
        
    Returns:
    --------
    pandas.DataFrame : 包含以下列:
        - PH_yhat: Prophet预测值, float64
        - PH_yhat_lower: 预测下限, float64
        - PH_yhat_upper: 预测上限, float64
        - PH_MACD: Prophet MACD线, float64
        - PH_MACD_Signal: Prophet MACD信号线, float64
        - PH_MACD_Hist: Prophet MACD柱状图, float64
        - PH_XLPL_Phase: XLPL阶段, float64
        - PH_Cross: 交叉信号, float64
        - PH_Trend_Duration: 趋势持续时间, float64
        - PH_Trend_Change: 趋势变化幅度, float64
    """
    # 使用配置或默认参数
    if config is None:
        config = EQUITY_CONFIG['INDICATORS']['PROPHET']
    
    forecast_periods = forecast_periods or config['periods']
    
    # 准备Prophet训练数据
    train_df = close_series.reset_index()
    train_df = train_df.rename(columns={'datetime': 'ds', 'close': 'y'})
    
    # 检查数据有效性
    if train_df['y'].isnull().sum() >= len(train_df) - 1:
        raise ValueError("数据集中有效数据不足")
        
    # 训练Prophet模型
    model = Prophet(
        daily_seasonality=config.get('daily_seasonality', False),
        weekly_seasonality=config.get('weekly_seasonality', True),
        yearly_seasonality=config.get('yearly_seasonality', False),
        changepoint_prior_scale=config.get('changepoint_prior_scale', 0.08)
    )
    model.fit(train_df)
    
    # 生成预测
    future = model.make_future_dataframe(periods=forecast_periods, freq='D')
    forecast = model.predict(future)
    
    # 计算MACD信号
    price_macd_config = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']
    signals = calculate_macd_signals(
        pd.to_numeric(forecast['yhat'], errors='coerce'),
        macd_long=price_macd_config['macd_long'],
        macd_mid=price_macd_config['macd_mid'],
        macd_short=price_macd_config['macd_short'],
        diff_ema_period=price_macd_config['diff_ema_period']
    )
    
    # 合并Cross信号
    merged_cross = np.zeros(len(signals))
    for i in range(len(signals)):
        if signals['Cross_1'].iloc[i] != 0:
            merged_cross[i] = signals['Cross_1'].iloc[i]
    
    # 计算趋势持续时间和变化幅度
    trend_duration = np.zeros(len(forecast))
    trend_change = np.zeros(len(forecast))
    
    current_phase = 0
    phase_start_idx = 0
    phase_start_price = 0
    
    for i in range(len(forecast)):
        phase = signals['XLPL_Phase'].iloc[i]
        
        # 检测阶段变化
        if phase != current_phase:
            current_phase = phase
            phase_start_idx = i
            phase_start_price = forecast['yhat'].iloc[i]
        
        # 只关注拉升(2)和下跌(4)阶段
        if phase in [2, 4]:
            trend_duration[i] = i - phase_start_idx + 1
            
            current_price = forecast['yhat'].iloc[i]
            if phase_start_price != 0:
                change = ((current_price - phase_start_price) / phase_start_price) * 100
                trend_change[i] = change if phase == 2 else -change
    
    # 准备返回数据
    prophet_df = pd.DataFrame()
    prophet_df['ds'] = forecast['ds']
    prophet_df['PH_yhat'] = forecast['yhat']
    prophet_df['PH_yhat_lower'] = forecast['yhat_lower']
    prophet_df['PH_yhat_upper'] = forecast['yhat_upper']
    prophet_df['PH_MACD'] = signals['MACD']
    prophet_df['PH_MACD_Signal'] = signals['MACD_Signal']
    prophet_df['PH_MACD_Hist'] = signals['MACD_Hist']
    prophet_df['PH_XLPL_Phase'] = signals['XLPL_Phase']
    prophet_df['PH_Cross'] = merged_cross
    prophet_df['PH_Trend_Duration'] = trend_duration
    prophet_df['PH_Trend_Change'] = trend_change
    
    prophet_df.set_index('ds', inplace=True)
    
    return prophet_df


# ====================================================================
# 辅助函数
# ====================================================================

def merge_price_cross_signals(signals):
    """
    合并Price MACD的交叉信号
    
    规则：
    - 首先检查Cross_1信号
    - 然后在特定条件下检查Cross_2信号
    
    ⚠️ 从 hlm5_all_parallel.py 第 1006-1026 行移植
    """
    merged_cross = np.zeros(len(signals))
    for i in range(len(signals)):
        # 首先检查Cross_1信号
        if signals['Cross_1'].iloc[i] != 0:
            merged_cross[i] = signals['Cross_1'].iloc[i]
        
        # 然后在特定条件下检查Cross_2信号
        if signals['Cross_2'].iloc[i] != 0:
            dea = signals['MACD_Signal'].iloc[i]
            dif = signals['MACD'].iloc[i]
            
            # 当DEA>0且DIF>DEA时，保留上穿信号
            if dea > 0 and dif > dea and signals['Cross_2'].iloc[i] > 0:
                merged_cross[i] = 2
            # 当DEA<0且DIF<DEA时，保留下穿信号
            elif dea < 0 and dif < dea and signals['Cross_2'].iloc[i] < 0:
                merged_cross[i] = -2
    
    return merged_cross


# ====================================================================
# 测试代码
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("技术指标模块测试")
    print("=" * 60)
    
    # 生成测试数据
    np.random.seed(42)
    dates = pd.date_range('2025-01-01', periods=200, freq='D')
    prices = 100 + np.cumsum(np.random.randn(200) * 2)
    volumes = 1000000 + np.random.randint(-100000, 100000, 200)
    
    test_series = pd.Series(prices, index=dates)
    
    print("\n1. 测试 Price MACD 计算...")
    price_macd = calculate_macd_signals(test_series)
    print(f"✓ Price MACD 计算完成，输出列: {list(price_macd.columns)}")
    print(f"  最新XLPL阶段: {int(price_macd['XLPL_Phase'].iloc[-1])}")
    
    print("\n2. 测试 HLBW 计算...")
    high_series = test_series + np.random.rand(200) * 5
    low_series = test_series - np.random.rand(200) * 5
    hlbw = calculate_hlbw(high_series, low_series, test_series)
    print(f"✓ HLBW 计算完成，输出列: {list(hlbw.columns)}")
    print(f"  最新趋势线: {hlbw['HLBW_Trend_Line'].iloc[-1]:.2f}")
    
    print("\n3. 配置参数验证...")
    print(f"  Price MACD: ({EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['macd_long']}, "
          f"{EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['macd_mid']}, "
          f"{EQUITY_CONFIG['INDICATORS']['PRICE_MACD']['macd_short']})")
    print(f"  HLBW lookback: {HLBW_CONFIG['lookback_period']}")
    
    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)

