"""
检查加仓策略测试的数据状态
"""
import pandas as pd
import sqlite3
from trading_signal_database_manager import TradingSignalDatabaseManager

def check_data_for_scaling():
    """检查数据库中的信号数据"""
    db = TradingSignalDatabaseManager('trading_signals.db')
    
    # 测试品种和日期
    tickers = ['RB.SHF', 'OI.ZCE']
    start_date = '2025-01-01'
    end_date = '2025-06-30'
    
    for ticker in tickers:
        print(f"\n{'='*70}")
        print(f"检查 {ticker} 的数据")
        print(f"{'='*70}")
        
        # 查询数据
        query = """
        SELECT datetime, close, 
               Entry_Signal, Exit_Signal, Position,
               Entry_Price, Exit_Price, Profit_Loss
        FROM trading_data 
        WHERE ticker = ? 
          AND datetime >= date(?) 
          AND datetime < date(?, '+1 day')
        ORDER BY datetime
        """
        
        df = pd.read_sql(query, db.conn, params=[ticker, start_date, end_date])
        
        print(f"\n总数据行数: {len(df)}")
        print(f"日期范围: {df['datetime'].min()} 至 {df['datetime'].max()}")
        
        # 统计信号
        entry_signals = df[df['Entry_Signal'] != 0]
        exit_signals = df[df['Exit_Signal'] == True]
        
        print(f"\n入场信号数量: {len(entry_signals)}")
        print(f"出场信号数量: {len(exit_signals)}")
        
        # 统计持仓
        positions = df[df['Position'] != 0]
        print(f"持仓记录数量: {len(positions)}")
        print(f"  做多记录: {len(df[df['Position'] > 0])}")
        print(f"  做空记录: {len(df[df['Position'] < 0])}")
        
        # 统计盈亏
        trades = df[df['Profit_Loss'] != 0]
        print(f"\n交易次数: {len(trades)}")
        print(f"  盈利交易: {len(trades[trades['Profit_Loss'] > 0])}")
        print(f"  亏损交易: {len(trades[trades['Profit_Loss'] < 0])}")
        
        if len(trades) > 0:
            total_pnl = trades['Profit_Loss'].sum()
            print(f"  总盈亏: {total_pnl:.2f} 元")
            print(f"  胜率: {len(trades[trades['Profit_Loss'] > 0]) / len(trades):.2%}")
        
        # 显示前几条入场信号
        if len(entry_signals) > 0:
            print(f"\n前5条入场信号:")
            print(entry_signals[['datetime', 'Entry_Signal', 'Position', 'Entry_Price']].head())
        
        # 显示前几条出场信号
        if len(exit_signals) > 0:
            print(f"\n前5条出场信号:")
            print(exit_signals[['datetime', 'Exit_Signal', 'Position', 'Exit_Price', 'Profit_Loss']].head())
    
    db.close()
    print(f"\n{'='*70}")
    print("数据检查完成")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    check_data_for_scaling()

