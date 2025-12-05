"""
双向交易性能报告 - 详细统计
"""
import sqlite3
import pandas as pd
import numpy as np

# 连接数据库
conn = sqlite3.connect('trading_signals.db')

# 查询所有期货的交易数据
tickers = ['RB.SHF', 'OI.ZCE']

print("="*100)
print(" " * 35 + "双向交易性能报告")
print("="*100)

for ticker in tickers:
    query = f"""
    SELECT datetime, close, Position, Entry_Signal, Exit_Signal, 
           Entry_Price, Exit_Price, Profit_Loss
    FROM trading_data
    WHERE ticker = '{ticker}' AND datetime >= '2025-01-01'
    ORDER BY datetime
    """
    
    df = pd.read_sql(query, conn)
    
    if df.empty:
        print(f"\n{ticker}: 无数据")
        continue
    
    print(f"\n{'='*100}")
    print(f"期货合约: {ticker}")
    print(f"{'='*100}")
    
    # 1. Position 分布统计
    print("\n【1. 持仓分布】")
    position_counts = df['Position'].value_counts().sort_index()
    total_positions = len(df[df['Position'] != 0])
    
    long_count = len(df[df['Position'] > 0])
    short_count = len(df[df['Position'] < 0])
    no_position = len(df[df['Position'] == 0])
    
    print(f"  做多持仓: {long_count:>6} ({long_count/len(df)*100:>5.1f}%)")
    print(f"  做空持仓: {short_count:>6} ({short_count/len(df)*100:>5.1f}%)")
    print(f"  空仓位置: {no_position:>6} ({no_position/len(df)*100:>5.1f}%)")
    print(f"  总数据点: {len(df):>6}")
    
    # 2. 信号统计
    print("\n【2. 交易信号统计】")
    long_entries = len(df[df['Entry_Signal'] > 0])
    long_exits = len(df[df['Exit_Signal'] == True])
    
    # 通过Position变化识别做空入场
    df['Prev_Position'] = df['Position'].shift(1).fillna(0)
    short_entry_count = len(df[(df['Position'] < 0) & (df['Prev_Position'] >= 0)])
    short_exit_count = len(df[(df['Position'] == 0) & (df['Prev_Position'] < 0)])
    
    print(f"  做多入场信号: {long_entries:>6}")
    print(f"  做空入场信号: {short_entry_count:>6}")
    print(f"  做多出场信号: {long_exits:>6}")
    print(f"  做空出场信号: {short_exit_count:>6}")
    
    # 3. 盈亏统计
    print("\n【3. 盈亏统计】")
    profit_trades = df[df['Profit_Loss'] > 0]
    loss_trades = df[df['Profit_Loss'] < 0]
    total_trades = len(profit_trades) + len(loss_trades)
    
    if total_trades > 0:
        win_rate = len(profit_trades) / total_trades * 100
        total_profit = df['Profit_Loss'].sum()
        
        print(f"  总交易次数: {total_trades:>6}")
        print(f"  盈利次数:   {len(profit_trades):>6} ({len(profit_trades)/total_trades*100:>5.1f}%)")
        print(f"  亏损次数:   {len(loss_trades):>6} ({len(loss_trades)/total_trades*100:>5.1f}%)")
        print(f"  胜率:       {win_rate:>6.2f}%")
        print(f"  总盈亏:     {total_profit:>6.2f}%")
        
        if len(profit_trades) > 0:
            avg_profit = profit_trades['Profit_Loss'].mean()
            max_profit = profit_trades['Profit_Loss'].max()
            print(f"  平均盈利:   {avg_profit:>6.2f}%")
            print(f"  最大盈利:   {max_profit:>6.2f}%")
        
        if len(loss_trades) > 0:
            avg_loss = loss_trades['Profit_Loss'].mean()
            max_loss = loss_trades['Profit_Loss'].min()
            print(f"  平均亏损:   {avg_loss:>6.2f}%")
            print(f"  最大亏损:   {max_loss:>6.2f}%")
        
        if len(profit_trades) > 0 and len(loss_trades) > 0:
            profit_factor = abs(profit_trades['Profit_Loss'].sum() / loss_trades['Profit_Loss'].sum())
            print(f"  盈亏比:     {profit_factor:>6.2f}")
    
    # 4. 信号类型分布
    print("\n【4. 做多信号类型分布】")
    long_signal_counts = df[df['Entry_Signal'] > 0]['Entry_Signal'].value_counts().sort_index()
    for signal_type, count in long_signal_counts.items():
        print(f"  类型 {signal_type:>2}: {count:>4} 次")
    
    # 5. 最近交易
    print("\n【5. 最近5笔交易】")
    recent_trades = df[(df['Profit_Loss'] != 0)].tail(5)
    if not recent_trades.empty:
        for idx, row in recent_trades.iterrows():
            position_type = "做多" if row['Exit_Signal'] else "做空"
            print(f"  {row['datetime'][:16]} | {position_type} | "
                  f"入场:{row['Entry_Price']:>7.1f} | 出场:{row['Exit_Price']:>7.1f} | "
                  f"盈亏:{row['Profit_Loss']:>6.2f}%")

print("\n" + "="*100)
print(" " * 40 + "报告生成完成")
print("="*100)

conn.close()

