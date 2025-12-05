"""
生成1分钟数据双向交易详细性能报告
"""
import sqlite3
import pandas as pd
import numpy as np

def analyze_bidirectional_trading(db_path='trading_signals.db', ticker=None):
    """分析双向交易性能"""
    conn = sqlite3.connect(db_path)
    
    # 如果没有指定ticker，默认分析RB.SHF和OI.ZCE
    if ticker:
        tickers_to_analyze = [ticker]
    else:
        tickers_to_analyze = ['RB.SHF', 'OI.ZCE']
    
    query = f"""
    SELECT * FROM trading_data 
    WHERE ticker IN ({','.join("'"+t+"'" for t in tickers_to_analyze)})
    ORDER BY ticker, datetime
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        print(f"❌ 没有找到数据")
        return
    
    # 获取所有期货代码
    tickers = df['ticker'].unique()
    
    print("=" * 80)
    print(f"📊 1分钟数据双向交易性能报告")
    print(f"数据源: {db_path}")
    print(f"期货品种: {len(tickers)} 个")
    print("=" * 80)
    
    for ticker in tickers:
        ticker_df = df[df['ticker'] == ticker].copy()
        
        print(f"\n{'='*80}")
        print(f"📈 {ticker} 详细分析")
        print(f"{'='*80}")
        
        # 基础统计
        total_records = len(ticker_df)
        date_range = f"{ticker_df['datetime'].min()} 到 {ticker_df['datetime'].max()}"
        
        print(f"\n【数据概况】")
        print(f"  总记录数: {total_records:,}")
        print(f"  日期范围: {date_range}")
        
        # 持仓分析
        position_counts = ticker_df['Position'].value_counts().sort_index()
        long_positions = ticker_df[ticker_df['Position'] > 0].shape[0]
        short_positions = ticker_df[ticker_df['Position'] < 0].shape[0]
        flat_positions = ticker_df[ticker_df['Position'] == 0].shape[0]
        
        print(f"\n【持仓分布】")
        print(f"  多头持仓: {long_positions:,} ({long_positions/total_records*100:.2f}%)")
        print(f"  空头持仓: {short_positions:,} ({short_positions/total_records*100:.2f}%)")
        print(f"  空仓: {flat_positions:,} ({flat_positions/total_records*100:.2f}%)")
        
        # 信号统计
        # Entry_Signal: 正值(1-6)=做多，负值(-1到-6)=做空
        long_entry = ticker_df[ticker_df['Entry_Signal'] > 0].shape[0]
        short_entry = ticker_df[ticker_df['Entry_Signal'] < 0].shape[0]
        exit_signals = ticker_df[ticker_df['Exit_Signal'] != 0].shape[0]
        
        print(f"\n【交易信号】")
        print(f"  做多入场信号: {long_entry:,}")
        print(f"  做空入场信号: {short_entry:,}")
        print(f"  出场信号: {exit_signals:,}")
        print(f"  总信号数: {long_entry + short_entry + exit_signals:,}")
        
        # 盈亏分析
        trades_df = ticker_df[ticker_df['Profit_Loss'] != 0].copy()
        if len(trades_df) > 0:
            profit_trades = trades_df[trades_df['Profit_Loss'] > 0]
            loss_trades = trades_df[trades_df['Profit_Loss'] < 0]
            
            total_trades = len(trades_df)
            win_trades = len(profit_trades)
            loss_trades_count = len(loss_trades)
            win_rate = win_trades / total_trades if total_trades > 0 else 0
            
            total_profit = profit_trades['Profit_Loss'].sum()
            total_loss = abs(loss_trades['Profit_Loss'].sum())
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            
            avg_profit = profit_trades['Profit_Loss'].mean() if len(profit_trades) > 0 else 0
            avg_loss = loss_trades['Profit_Loss'].mean() if len(loss_trades) > 0 else 0
            
            print(f"\n【盈亏统计】")
            print(f"  总交易次数: {total_trades:,}")
            print(f"  盈利次数: {win_trades:,}")
            print(f"  亏损次数: {loss_trades_count:,}")
            print(f"  胜率: {win_rate*100:.2f}%")
            print(f"  总盈利: {total_profit:.2f}%")
            print(f"  总亏损: {-total_loss:.2f}%")
            print(f"  净盈亏: {total_profit - total_loss:.2f}%")
            print(f"  盈亏比: {profit_factor:.2f}")
            print(f"  平均盈利: {avg_profit:.4f}%")
            print(f"  平均亏损: {avg_loss:.4f}%")
            
            # 做多vs做空分析（根据Entry_Signal判断）
            # 统计做多和做空的表现
            if long_positions > 0 or short_positions > 0:
                # 简化分析：根据持仓统计
                long_profit_loss = ticker_df[(ticker_df['Position'] > 0) & (ticker_df['Profit_Loss'] != 0)]['Profit_Loss']
                short_profit_loss = ticker_df[(ticker_df['Position'] < 0) & (ticker_df['Profit_Loss'] != 0)]['Profit_Loss']
                
                if len(long_profit_loss) > 0:
                    long_trades_count = len(long_profit_loss)
                    long_win = len(long_profit_loss[long_profit_loss > 0])
                    long_win_rate = long_win / long_trades_count if long_trades_count > 0 else 0
                    long_avg_profit = long_profit_loss.mean()
                    print(f"\n  【做多交易】")
                    print(f"    交易次数: {long_trades_count:,}")
                    print(f"    胜率: {long_win_rate*100:.2f}%")
                    print(f"    平均盈亏: {long_avg_profit:.4f}%")
                
                if len(short_profit_loss) > 0:
                    short_trades_count = len(short_profit_loss)
                    short_win = len(short_profit_loss[short_profit_loss > 0])
                    short_win_rate = short_win / short_trades_count if short_trades_count > 0 else 0
                    short_avg_profit = short_profit_loss.mean()
                    print(f"\n  【做空交易】")
                    print(f"    交易次数: {short_trades_count:,}")
                    print(f"    胜率: {short_win_rate*100:.2f}%")
                    print(f"    平均盈亏: {short_avg_profit:.4f}%")
        
        # 信号类型分布
        if long_entry > 0:
            print(f"\n【做多信号类型分布】")
            long_signal_types = ticker_df[ticker_df['Entry_Signal'] > 0]['Entry_Signal'].value_counts().sort_index()
            for signal_type, count in long_signal_types.items():
                print(f"  类型 {signal_type}: {count:,} ({count/long_entry*100:.2f}%)")
        
        if short_entry > 0:
            print(f"\n【做空信号类型分布】")
            short_signal_types = ticker_df[ticker_df['Entry_Signal'] < 0]['Entry_Signal'].value_counts().sort_index()
            for signal_type, count in short_signal_types.items():
                print(f"  类型 {signal_type}: {count:,} ({count/short_entry*100:.2f}%)")

if __name__ == "__main__":
    import sys
    
    ticker = sys.argv[1] if len(sys.argv) > 1 else None
    analyze_bidirectional_trading(ticker=ticker)

