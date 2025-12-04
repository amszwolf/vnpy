# -*- coding: utf-8 -*-
"""
HLM5 策略回测执行脚本

基于 VNPy 的 BacktestingEngine
使用 hlm5_config.py 和 futures_config.py 中的配置参数
"""

import sys
from pathlib import Path
from datetime import datetime
import os

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "strategies"))

from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.optimize import OptimizationSetting

# 导入策略
from strategies.hlm5_strategy import HLM5Strategy

# 导入配置
from hlm5_config import EQUITY_CONFIG
from futures_config import FUTURES_CONFIG, get_contract_specs

# 导入可视化工具（可选）
try:
    from bokeh.plotting import figure, show, output_file
    from bokeh.layouts import column
    from bokeh.models import ColumnDataSource
    import pandas as pd
    import numpy as np
    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False
    print("Warning: Bokeh not installed. Advanced charts will not be available.")


def run_backtest(
    symbol='OI888',
    exchange=Exchange.CZCE,
    start_date=None,
    end_date=None,
    interval='5m',
    capital=100000,
    show_chart=True,
    show_advanced_chart=False,
    debug_mode=False
):
    """
    运行 HLM5 策略回测
    
    Parameters:
    -----------
    symbol : str
        合约代码（如 'OI888'）
    exchange : Exchange
        交易所
    start_date : datetime
        回测起始日期
    end_date : datetime
        回测结束日期
    interval : str
        回测周期
    capital : float
        初始资金
    show_chart : bool
        是否显示VNPy内置图表（默认: True）
    show_advanced_chart : bool
        是否生成详细的Bokeh交互图表（默认: False）
    debug_mode : bool
        是否启用调试模式，生成所有中间数据CSV（默认: False）
        
    Returns:
    --------
    dict : 回测统计结果
    """
    print("=" * 60)
    print("HLM5 策略回测")
    print("=" * 60)
    
    # 1. 设置默认参数
    if start_date is None:
        start_date_str = FUTURES_CONFIG['BACKTEST_CONFIG']['start_date']
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    if end_date is None:
        end_date = datetime.now()
    
    # 2. 获取合约规格
    specs = get_contract_specs(symbol)
    
    print(f"\n回测配置:")
    print(f"  合约: {symbol}.{exchange.value}")
    print(f"  时间: {start_date.date()} 至 {end_date.date()}")
    print(f"  周期: {interval}")
    print(f"  初始资金: {capital:,.0f} 元")
    print(f"\n合约规格:")
    print(f"  合约乘数: {specs['multiplier']} 吨/手")
    print(f"  最小变动: {specs['pricetick']} 元/吨")
    print(f"  保证金率: {specs['margin_rate']*100}%")
    print(f"  手续费率: 开{specs['commission']['open_ratio']*10000:.2f}万分之一")
    
    # 3. 创建回测引擎
    engine = BacktestingEngine()
    
    # 4. 设置回测参数
    # 转换interval字符串为Interval枚举
    interval_map = {
        '1m': Interval.MINUTE,
        '5m': Interval.MINUTE,  # VNPy只支持MINUTE，策略内部会聚合成5分钟
        '15m': Interval.MINUTE,
        '30m': Interval.MINUTE,
        '1h': Interval.HOUR,
        '1d': Interval.DAILY
    }
    interval_enum = interval_map.get(interval, Interval.MINUTE)
    
    engine.set_parameters(
        vt_symbol=f"{symbol}.{exchange.value}",
        interval=interval_enum,
        start=start_date,
        end=end_date,
        rate=specs['commission']['open_ratio'],        # 手续费率
        slippage=specs['slippage']['fixed_slippage'],  # 滑点（跳数）
        size=specs['multiplier'],                      # 合约乘数
        pricetick=specs['pricetick'],                  # 最小变动价位
        capital=capital                                # 初始资金
    )
    
    print(f"\n策略参数:")
    print(f"  Price MACD: ({HLM5Strategy.price_macd_long}, {HLM5Strategy.price_macd_mid}, {HLM5Strategy.price_macd_short})")
    print(f"  Volume MACD: ({HLM5Strategy.volume_macd_long}, {HLM5Strategy.volume_macd_mid}, {HLM5Strategy.volume_macd_short})")
    print(f"  HLBW: lookback={HLM5Strategy.hlbw_lookback}, inner_ema={HLM5Strategy.hlbw_inner_ema}")
    print(f"  风险控制: 止损={HLM5Strategy.stop_loss_pct*100}%, 止盈={HLM5Strategy.take_profit_pct*100}%")
    
    # 5. 添加策略
    strategy_setting = {
        # 使用默认参数（从 hlm5_config.py 读取）
        'debug_mode': debug_mode  # 启用调试模式
    }
    
    engine.add_strategy(HLM5Strategy, strategy_setting)
    
    # 6. 加载历史数据并运行回测
    print("\n" + "=" * 60)
    print("开始回测...")
    print("=" * 60)
    
    try:
        engine.load_data()
        print(f"✓ 数据加载完成")
        
        engine.run_backtesting()
        print(f"✓ 回测执行完成")
        
        # 7. 计算统计结果
        df = engine.calculate_result()
        stats = engine.calculate_statistics()
        
        # 7.5 如果启用调试模式，保存中间数据
        if debug_mode:
            try:
                # VNPy的BacktestingEngine使用strategy属性而不是strategies
                strategy = engine.strategy
                if strategy and hasattr(strategy, 'debug_data'):
                    import pandas as pd
                    from pathlib import Path
                    
                    if not strategy.debug_data:
                        print("⚠️ 没有收集到调试数据")
                    else:
                        # 转换为DataFrame
                        debug_df = pd.DataFrame(strategy.debug_data)
                        
                        # 准备输出路径
                        output_dir = Path(__file__).parent.parent / "output" / "debug"
                        output_dir.mkdir(parents=True, exist_ok=True)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        output_path = output_dir / f"debug_data_{symbol}_{timestamp}.csv"
                        
                        # 保存CSV
                        debug_df.to_csv(output_path, index=False, encoding='utf-8-sig')
                        
                        print(f"\n✅ 调试数据已保存: {output_path}")
                        print(f"   共 {len(debug_df)} 条记录")
                        
                        # 统计信号
                        print(f"\n=== 信号统计 ===")
                        print(f"   做多入场信号: {(debug_df['long_entry_signal'] > 0).sum()} 次")
                        print(f"   做空入场信号: {(debug_df['short_entry_signal'] < 0).sum()} 次")
                        print(f"   做多出场信号: {debug_df['long_exit_signal'].sum()} 次")
                        print(f"   做空出场信号: {debug_df['short_exit_signal'].sum()} 次")
                        
                        # 指标统计
                        print(f"\n=== 指标统计 ===")
                        print(f"   Price Cross不为0: {(debug_df['price_cross'] != 0).sum()} 次")
                        print(f"   Volume Cross不为0: {(debug_df['volume_cross'] != 0).sum()} 次")
                        print(f"   HLBW Cross不为0: {(debug_df['hlbw_cross'] != 0).sum()} 次")
                        print(f"   Prophet Cross不为0: {(debug_df['prophet_cross'] != 0).sum()} 次")
                        
                        # 验证文件
                        if output_path.exists():
                            print(f"\n✓ 文件已确认存在: {output_path}")
                        else:
                            print(f"\n✗ 警告: 文件不存在: {output_path}")
                else:
                    print("⚠️ 策略没有debug_data属性或策略实例为空")
            except Exception as e:
                import traceback
                print(f"⚠️ 保存调试数据失败: {e}")
                traceback.print_exc()
        
        # 8. 打印回测结果
        print("\n" + "=" * 60)
        print("回测结果")
        print("=" * 60)
        
        # 基础指标
        print(f"\n资金情况:")
        print(f"  起始资金: {capital:,.2f} 元")
        print(f"  结束资金: {stats.get('end_balance', 0):,.2f} 元")
        print(f"  总收益: {stats.get('total_return', 0)*100:.2f}%")
        print(f"  年化收益: {stats.get('annual_return', 0)*100:.2f}%")
        
        # 风险指标
        print(f"\n风险指标:")
        print(f"  最大回撤: {stats.get('max_ddpercent', 0)*100:.2f}%")
        print(f"  夏普比率: {stats.get('sharpe_ratio', 0):.3f}")
        print(f"  收益回撤比: {stats.get('return_drawdown_ratio', 0):.3f}")
        
        # 交易统计
        print(f"\n交易统计:")
        print(f"  总交易次数: {stats.get('total_trade_count', 0)}")
        print(f"  日均交易: {stats.get('daily_trade_count', 0):.2f} 次")
        print(f"  盈利次数: {stats.get('winning_trade_count', 0)}")
        print(f"  亏损次数: {stats.get('losing_trade_count', 0)}")
        
        # 胜率和盈亏
        if stats.get('total_trade_count', 0) > 0:
            win_rate = stats.get('winning_trade_count', 0) / stats.get('total_trade_count', 1) * 100
            print(f"  胜率: {win_rate:.2f}%")
        
        print(f"  总盈亏: {stats.get('total_net_pnl', 0):,.2f} 元")
        print(f"  手续费: {stats.get('total_commission', 0):,.2f} 元")
        print(f"  滑点成本: {stats.get('total_slippage', 0):,.2f} 元")
        
        # 9. 显示图表
        if show_chart:
            print("\n显示VNPy回测图表...")
            engine.show_chart()
        
        # 10. 生成详细的Bokeh交互图表（可选）
        if show_advanced_chart and BOKEH_AVAILABLE:
            print("\n生成详细的交互式图表...")
            try:
                _generate_advanced_chart(df, stats, symbol, start_date, end_date)
                print(f"✓ 详细图表已保存至: output/{symbol}_backtest_analysis.html")
            except Exception as e:
                print(f"⚠ 生成详细图表失败: {e}")
        elif show_advanced_chart and not BOKEH_AVAILABLE:
            print("\n⚠ Bokeh未安装，无法生成详细图表。请运行: pip install bokeh")
        
        print("\n" + "=" * 60)
        print("✅ 回测完成！")
        print("=" * 60)
        
        if debug_mode:
            print("\n💾 调试模式已启用")
            print("   详细的中间数据CSV文件将在策略停止时保存")
            print("   保存路径: output/debug/")
        
        return stats
        
    except Exception as e:
        print(f"\n✗ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def quick_backtest():
    """
    快速回测 - 使用默认配置
    """
    stats = run_backtest(
        symbol='OI888',
        exchange=Exchange.CZCE,
        interval='5m',
        capital=100000,
        show_chart=True,
        show_advanced_chart=False  # 默认不显示详细图表
    )
    
    return stats


def custom_backtest(
    start_date_str='2025-01-01',
    end_date_str=None,
    capital=100000,
    show_advanced_chart=False
):
    """
    自定义时间段回测
    
    Parameters:
    -----------
    start_date_str : str
        起始日期 'YYYY-MM-DD'
    end_date_str : str, optional
        结束日期 'YYYY-MM-DD'（默认为今天）
    capital : float
        初始资金
    show_advanced_chart : bool
        是否显示详细图表（默认: False）
    """
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    stats = run_backtest(
        symbol='OI888',
        exchange=Exchange.CZCE,
        start_date=start_date,
        end_date=end_date,
        interval='5m',
        capital=capital,
        show_chart=True,
        show_advanced_chart=show_advanced_chart
    )
    
    return stats


# ====================================================================
# 主程序
# ====================================================================

def main():
    """主程序"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HLM5 策略回测')
    parser.add_argument('--symbol', type=str, default='OI888', help='合约代码')
    parser.add_argument('--start', type=str, help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000, help='初始资金')
    parser.add_argument('--interval', type=str, default='5m', help='回测周期')
    parser.add_argument('--no-chart', action='store_true', help='不显示VNPy图表')
    parser.add_argument('--advanced-chart', action='store_true', help='生成详细的交互式图表')
    parser.add_argument('--debug', action='store_true', help='启用调试模式，生成所有中间数据CSV')
    
    args = parser.parse_args()
    
    # 解析日期
    start_date = None
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    
    end_date = None
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    
    # 运行回测
    stats = run_backtest(
        symbol=args.symbol,
        exchange=Exchange.CZCE,
        start_date=start_date,
        end_date=end_date,
        interval=args.interval,
        capital=args.capital,
        show_chart=not args.no_chart,
        show_advanced_chart=args.advanced_chart,
        debug_mode=args.debug
    )
    
    if stats:
        # 保存结果到文件
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("HLM5 策略回测结果\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"合约: {args.symbol}\n")
            f.write(f"回测周期: {args.interval}\n")
            f.write(f"初始资金: {args.capital:,.2f}\n\n")
            
            for key, value in stats.items():
                f.write(f"{key}: {value}\n")
        
        print(f"\n回测结果已保存到: {output_file}")


def _generate_advanced_chart(df, stats, symbol, start_date, end_date):
    """
    生成详细的Bokeh交互式图表
    
    Parameters:
    -----------
    df : pandas.DataFrame
        回测结果DataFrame
    stats : dict
        统计结果
    symbol : str
        合约代码
    start_date : datetime
        起始日期
    end_date : datetime
        结束日期
    """
    if not BOKEH_AVAILABLE:
        return
    
    # 确保输出目录存在
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # 设置输出文件
    output_file(str(output_dir / f"{symbol}_backtest_analysis.html"))
    
    # 准备数据
    df = df.copy()
    df['datetime'] = pd.to_datetime(df.index)
    df = df.reset_index(drop=True)
    
    # 配置图表参数
    tools = "pan,wheel_zoom,box_zoom,reset,save,crosshair"
    width = 1600
    height = 300
    
    # 1. 权益曲线图
    p1 = figure(width=width, height=height*2, tools=tools, x_axis_type="datetime",
               title=f"{symbol} 回测权益曲线 ({start_date.date()} 至 {end_date.date()})")
    
    # 绘制权益曲线
    p1.line(df['datetime'], df['balance'], line_color='blue', line_width=2, 
            legend_label='账户权益')
    
    # 绘制买卖点
    df_trades = df[df['trade_count'] > 0].copy()
    if not df_trades.empty:
        # 盈利交易（绿色）
        df_win = df_trades[df_trades['trade_profit'] > 0]
        if not df_win.empty:
            p1.circle(df_win['datetime'], df_win['balance'], size=8, 
                     color='green', alpha=0.6, legend_label='盈利交易')
        
        # 亏损交易（红色）
        df_loss = df_trades[df_trades['trade_profit'] < 0]
        if not df_loss.empty:
            p1.circle(df_loss['datetime'], df_loss['balance'], size=8, 
                     color='red', alpha=0.6, legend_label='亏损交易')
    
    # 添加统计信息文本
    stats_text = f"总收益: {stats.get('total_return', 0)*100:.2f}% | " \
                 f"最大回撤: {stats.get('max_ddpercent', 0)*100:.2f}% | " \
                 f"夏普比率: {stats.get('sharpe_ratio', 0):.3f} | " \
                 f"胜率: {stats.get('winning_trade_count', 0)}/{stats.get('total_trade_count', 0)}"
    p1.title.text = f"{symbol} 回测权益曲线 - {stats_text}"
    
    # 2. 回撤图
    p2 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
               x_range=p1.x_range, title="回撤曲线")
    
    # 计算回撤
    df['peak'] = df['balance'].expanding().max()
    df['drawdown'] = (df['balance'] - df['peak']) / df['peak'] * 100
    
    p2.line(df['datetime'], df['drawdown'], line_color='red', line_width=2)
    p2.line(df['datetime'], [0] * len(df), line_color='gray', 
            line_dash='dashed', line_width=1)
    
    # 3. 持仓图
    p3 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
               x_range=p1.x_range, title="持仓情况")
    
    if 'pos' in df.columns:
        # 多仓（正值，绿色）
        df_long = df[df['pos'] > 0]
        if not df_long.empty:
            p3.vbar(x=df_long['datetime'], top=df_long['pos'], bottom=0,
                   width=pd.Timedelta(minutes=5).value / 1e6, color='green', 
                   alpha=0.5, legend_label='多仓')
        
        # 空仓（负值，红色）
        df_short = df[df['pos'] < 0]
        if not df_short.empty:
            p3.vbar(x=df_short['datetime'], top=df_short['pos'], bottom=0,
                   width=pd.Timedelta(minutes=5).value / 1e6, color='red', 
                   alpha=0.5, legend_label='空仓')
    
    # 4. 收益分布图
    p4 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
               x_range=p1.x_range, title="单笔交易盈亏")
    
    if not df_trades.empty and 'trade_profit' in df_trades.columns:
        # 盈利柱（绿色）
        df_profit = df_trades[df_trades['trade_profit'] > 0]
        if not df_profit.empty:
            p4.vbar(x=df_profit['datetime'], top=df_profit['trade_profit'], bottom=0,
                   width=pd.Timedelta(minutes=5).value / 1e6, color='green', 
                   alpha=0.6, legend_label='盈利')
        
        # 亏损柱（红色）
        df_loss_trades = df_trades[df_trades['trade_profit'] < 0]
        if not df_loss_trades.empty:
            p4.vbar(x=df_loss_trades['datetime'], top=df_loss_trades['trade_profit'], bottom=0,
                   width=pd.Timedelta(minutes=5).value / 1e6, color='red', 
                   alpha=0.6, legend_label='亏损')
        
        # 0轴线
        p4.line(df['datetime'], [0] * len(df), line_color='gray', 
               line_dash='dashed', line_width=1)
    
    # 通用设置
    for p in [p1, p2, p3, p4]:
        p.legend.location = "top_left"
        p.legend.click_policy = "hide"
        p.grid.grid_line_alpha = 0.3
        p.xaxis.axis_label = "时间"
    
    p1.yaxis.axis_label = "账户权益（元）"
    p2.yaxis.axis_label = "回撤（%）"
    p3.yaxis.axis_label = "持仓（手）"
    p4.yaxis.axis_label = "盈亏（元）"
    
    # 显示图表
    show(column([p1, p2, p3, p4]))


if __name__ == "__main__":
    # 如果没有命令行参数，运行快速回测
    if len(sys.argv) == 1:
        print("\n使用默认配置运行快速回测...")
        print("提示：使用 --help 查看所有参数选项\n")
        quick_backtest()
    else:
        main()

