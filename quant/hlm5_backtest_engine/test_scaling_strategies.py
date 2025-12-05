"""
加仓策略对比测试脚本 (Scaling Strategy Comparison Test)

并行测试多种加仓策略，生成详细的对比报告和可视化图表。

Python环境：aidata311
"""

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
import os
import sys
from typing import Dict, List
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import json

from trading_signal_database_manager import TradingSignalDatabaseManager
from scaling_strategy import (
    ScalingConfig, 
    generate_scaling_signals,
    calculate_scaling_performance,
    SCALING_CONFIGS
)
from scaling_strategy_visualizer import visualize_all_strategies

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_strategy(ticker: str,
                        start_date: str,
                        end_date: str,
                        strategy_name: str,
                        config: ScalingConfig,
                        db_path: str = 'trading_signals.db') -> Dict:
    """
    测试单个加仓策略
    
    Parameters:
    -----------
    ticker : str
        期货代码
    start_date : str
        开始日期
    end_date : str
        结束日期
    strategy_name : str
        策略名称
    config : ScalingConfig
        加仓配置
    db_path : str
        数据库路径
    
    Returns:
    --------
    Dict : 测试结果
    """
    logger.info(f"Testing {strategy_name} for {ticker}")
    
    # 创建数据库连接
    db = TradingSignalDatabaseManager(db_path)
    
    # 生成加仓信号
    signals_df = generate_scaling_signals(
        db, ticker, start_date, end_date, config
    )
    
    # 关闭数据库
    db.close()
    
    if signals_df.empty:
        logger.warning(f"No signals generated for {ticker} with {strategy_name}")
        return {
            'ticker': ticker,
            'strategy': strategy_name,
            'status': 'no_data',
            'metrics': {}
        }
    
    # 计算性能指标
    metrics = calculate_scaling_performance(signals_df)
    
    return {
        'ticker': ticker,
        'strategy': strategy_name,
        'status': 'success',
        'metrics': metrics,
        'signals_df': signals_df
    }


def compare_all_strategies(tickers: List[str],
                          start_date: str,
                          end_date: str,
                          strategies: Dict[str, ScalingConfig] = None,
                          db_path: str = 'trading_signals.db',
                          parallel: bool = True) -> Dict:
    """
    对比测试所有加仓策略
    
    Parameters:
    -----------
    tickers : List[str]
        期货代码列表
    start_date : str
        开始日期
    end_date : str
        结束日期
    strategies : Dict[str, ScalingConfig]
        策略配置字典
    db_path : str
        数据库路径
    parallel : bool
        是否并行处理
    
    Returns:
    --------
    Dict : 所有策略的测试结果
    """
    if strategies is None:
        strategies = SCALING_CONFIGS
    
    logger.info(f"Comparing {len(strategies)} strategies for {len(tickers)} tickers")
    logger.info(f"Date range: {start_date} to {end_date}")
    
    results = {}
    
    if parallel:
        # 并行测试
        with ProcessPoolExecutor(max_workers=min(4, os.cpu_count())) as executor:
            futures = []
            
            for ticker in tickers:
                for strategy_name, config in strategies.items():
                    future = executor.submit(
                        test_single_strategy,
                        ticker, start_date, end_date,
                        strategy_name, config, db_path
                    )
                    futures.append((ticker, strategy_name, future))
            
            for ticker, strategy_name, future in futures:
                result = future.result()
                
                if ticker not in results:
                    results[ticker] = {}
                
                results[ticker][strategy_name] = result
                
                if result['status'] == 'success':
                    metrics = result['metrics']
                    logger.info(f"✓ {ticker} - {strategy_name}: "
                              f"Return={metrics['total_return_pct']:.2f}%, "
                              f"Trades={metrics['total_trades']}, "
                              f"WinRate={metrics['win_rate']:.2%}")
    else:
        # 串行测试
        for ticker in tickers:
            results[ticker] = {}
            
            for strategy_name, config in strategies.items():
                result = test_single_strategy(
                    ticker, start_date, end_date,
                    strategy_name, config, db_path
                )
                results[ticker][strategy_name] = result
                
                if result['status'] == 'success':
                    metrics = result['metrics']
                    logger.info(f"✓ {ticker} - {strategy_name}: "
                              f"Return={metrics['total_return_pct']:.2f}%, "
                              f"Trades={metrics['total_trades']}")
    
    return results


def generate_comparison_report(results: Dict,
                              output_file: str = None) -> str:
    """
    生成对比报告
    
    Parameters:
    -----------
    results : Dict
        测试结果字典
    output_file : str
        输出文件路径
    
    Returns:
    --------
    str : 报告内容
    """
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'加仓策略对比报告_{timestamp}.md'
    
    report_lines = []
    report_lines.append("# 加仓策略对比测试报告")
    report_lines.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 遍历每个品种
    for ticker, strategies in results.items():
        report_lines.append(f"\n## {ticker} 策略对比\n")
        
        # 收集所有成功的策略数据
        strategy_data = []
        for strategy_name, result in strategies.items():
            if result['status'] == 'success':
                metrics = result['metrics']
                strategy_data.append({
                    'strategy': strategy_name,
                    'metrics': metrics
                })
        
        if not strategy_data:
            report_lines.append("❌ 无有效数据\n")
            continue
        
        # 创建对比表格
        report_lines.append("### 核心性能指标对比\n")
        report_lines.append("| 策略 | 总收益率 | 年化收益 | 夏普比率 | 最大回撤 | 交易次数 | 胜率 | 盈亏比 | 平均加仓层级 |")
        report_lines.append("|------|---------|---------|---------|---------|---------|------|-------|--------------|")
        
        # 找出各指标的最优值
        best_return = max(d['metrics']['total_return_pct'] for d in strategy_data)
        best_sharpe = max(d['metrics']['sharpe_ratio'] for d in strategy_data)
        best_drawdown = max(d['metrics']['max_drawdown'] for d in strategy_data)  # 最大回撤是负数，最接近0最好
        best_win_rate = max(d['metrics']['win_rate'] for d in strategy_data)
        best_pf = max(d['metrics']['profit_factor'] for d in strategy_data if d['metrics']['profit_factor'] != float('inf'))
        
        for data in strategy_data:
            strategy_name = data['strategy']
            m = data['metrics']
            
            # 标记最优值
            return_str = f"{m['total_return_pct']:.2f}%"
            if abs(m['total_return_pct'] - best_return) < 0.01:
                return_str = f"**{return_str}** ⭐"
            
            sharpe_str = f"{m['sharpe_ratio']:.4f}"
            if abs(m['sharpe_ratio'] - best_sharpe) < 0.001:
                sharpe_str = f"**{sharpe_str}** ⭐"
            
            drawdown_str = f"{m['max_drawdown_pct']:.2f}%"
            if abs(m['max_drawdown'] - best_drawdown) < 0.01:
                drawdown_str = f"**{drawdown_str}** ⭐"
            
            win_rate_str = f"{m['win_rate']:.2%}"
            if abs(m['win_rate'] - best_win_rate) < 0.001:
                win_rate_str = f"**{win_rate_str}** ⭐"
            
            pf_str = f"{m['profit_factor']:.2f}" if m['profit_factor'] != float('inf') else "∞"
            if m['profit_factor'] == best_pf or m['profit_factor'] == float('inf'):
                pf_str = f"**{pf_str}** ⭐"
            
            report_lines.append(
                f"| {strategy_name} | {return_str} | "
                f"{m['annual_return_pct']:.2f}% | {sharpe_str} | {drawdown_str} | "
                f"{m['total_trades']} | {win_rate_str} | {pf_str} | "
                f"{m['avg_scaling_levels']:.2f} |"
            )
        
        # 添加详细分析
        report_lines.append("\n### 详细分析\n")
        
        # 找出最佳策略
        best_strategy = max(strategy_data, 
                          key=lambda x: x['metrics']['sharpe_ratio'])
        
        report_lines.append(f"**推荐策略**: {best_strategy['strategy']}\n")
        report_lines.append(f"- **理由**: 夏普比率最高 ({best_strategy['metrics']['sharpe_ratio']:.4f})，"
                          f"风险调整后收益最优\n")
        
        bm = best_strategy['metrics']
        report_lines.append(f"- **总收益**: {bm['total_return_pct']:.2f}%")
        report_lines.append(f"- **年化收益**: {bm['annual_return_pct']:.2f}%")
        report_lines.append(f"- **最大回撤**: {bm['max_drawdown_pct']:.2f}%")
        report_lines.append(f"- **胜率**: {bm['win_rate']:.2%}")
        report_lines.append(f"- **平均加仓层级**: {bm['avg_scaling_levels']:.2f}\n")
        
        # 策略特点分析
        report_lines.append("### 策略特点\n")
        
        for data in strategy_data:
            name = data['strategy']
            m = data['metrics']
            
            report_lines.append(f"\n**{name}**:")
            
            if 'pyramid' in name:
                report_lines.append("- 特点: 首次重仓，后续递减")
                report_lines.append("- 优势: 降低平均成本，风险控制较好")
            elif 'inverse' in name:
                report_lines.append("- 特点: 逐步加大仓位")
                report_lines.append("- 优势: 趋势确认后收益更大")
            elif 'linear' in name:
                report_lines.append("- 特点: 每次固定加仓")
                report_lines.append("- 优势: 简单稳定，适合震荡市")
            elif 'fixed_fraction' in name:
                report_lines.append("- 特点: 固定比例加仓")
                report_lines.append("- 优势: 资金管理更科学")
            
            report_lines.append(f"- 实际表现: 收益率{m['total_return_pct']:.2f}%, "
                              f"胜率{m['win_rate']:.2%}, "
                              f"平均{m['avg_scaling_levels']:.1f}层加仓")
    
    # 综合结论
    report_lines.append("\n## 综合结论\n")
    
    # 统计各策略在各品种上的表现
    strategy_rankings = {}
    for ticker, strategies in results.items():
        for strategy_name, result in strategies.items():
            if result['status'] != 'success':
                continue
            
            if strategy_name not in strategy_rankings:
                strategy_rankings[strategy_name] = {
                    'total_sharpe': 0,
                    'total_return': 0,
                    'count': 0
                }
            
            metrics = result['metrics']
            strategy_rankings[strategy_name]['total_sharpe'] += metrics['sharpe_ratio']
            strategy_rankings[strategy_name]['total_return'] += metrics['total_return_pct']
            strategy_rankings[strategy_name]['count'] += 1
    
    # 计算平均值并排序
    strategy_scores = []
    for name, data in strategy_rankings.items():
        if data['count'] > 0:
            avg_sharpe = data['total_sharpe'] / data['count']
            avg_return = data['total_return'] / data['count']
            strategy_scores.append({
                'name': name,
                'avg_sharpe': avg_sharpe,
                'avg_return': avg_return
            })
    
    strategy_scores.sort(key=lambda x: x['avg_sharpe'], reverse=True)
    
    report_lines.append("### 综合排名（按平均夏普比率）\n")
    for i, score in enumerate(strategy_scores, 1):
        report_lines.append(f"{i}. **{score['name']}**: "
                          f"平均夏普比率 {score['avg_sharpe']:.4f}, "
                          f"平均收益率 {score['avg_return']:.2f}%")
    
    report_lines.append("\n### 使用建议\n")
    
    if strategy_scores:
        best = strategy_scores[0]
        report_lines.append(f"1. **推荐策略**: {best['name']}")
        report_lines.append(f"   - 在测试的所有品种上表现最稳定")
        report_lines.append(f"   - 平均夏普比率: {best['avg_sharpe']:.4f}")
        report_lines.append(f"   - 平均收益率: {best['avg_return']:.2f}%")
    
    report_lines.append("\n2. **策略选择原则**:")
    report_lines.append("   - **趋势明显的品种**: 推荐倒金字塔加仓")
    report_lines.append("   - **震荡市场**: 推荐金字塔加仓或线性加仓")
    report_lines.append("   - **风险厌恶**: 推荐金字塔加仓（首次重仓）")
    report_lines.append("   - **激进风格**: 推荐倒金字塔或aggressive_pyramid")
    
    report_lines.append("\n3. **风险提示**:")
    report_lines.append("   - 加仓策略会放大收益，同时也会放大风险")
    report_lines.append("   - 建议配合移动止损使用")
    report_lines.append("   - 实盘使用前需要充分测试")
    report_lines.append("   - 注意资金管理，避免过度杠杆")
    
    report_lines.append("\n---")
    report_lines.append(f"\n**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"**Python环境**: aidata311")
    
    # 写入文件
    report_content = '\n'.join(report_lines)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    logger.info(f"Comparison report saved to: {output_file}")
    
    return report_content


def save_results_to_json(results: Dict, output_file: str = None):
    """保存结果到JSON文件"""
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'scaling_test_results_{timestamp}.json'
    
    # 转换DataFrame为可序列化格式
    serializable_results = {}
    for ticker, strategies in results.items():
        serializable_results[ticker] = {}
        for strategy_name, result in strategies.items():
            # 移除DataFrame
            clean_result = {
                'ticker': result['ticker'],
                'strategy': result['strategy'],
                'status': result['status'],
                'metrics': result['metrics']
            }
            serializable_results[ticker][strategy_name] = clean_result
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Results saved to JSON: {output_file}")


def save_strategy_to_database(ticker: str,
                              start_date: str,
                              end_date: str,
                              strategy_name: str,
                              config: ScalingConfig,
                              db_path: str = 'trading_signals.db'):
    """
    将选定的加仓策略信号保存到数据库
    
    Parameters:
    -----------
    ticker : str
        期货代码
    start_date : str
        开始日期
    end_date : str
        结束日期
    strategy_name : str
        策略名称
    config : ScalingConfig
        加仓配置
    db_path : str
        数据库路径
    """
    logger.info(f"Saving {strategy_name} signals to database for {ticker}")
    
    # 创建数据库连接
    db = TradingSignalDatabaseManager(db_path)
    
    # 生成加仓信号
    signals_df = generate_scaling_signals(
        db, ticker, start_date, end_date, config
    )
    
    if signals_df.empty:
        logger.warning(f"No signals to save for {ticker} with {strategy_name}")
        db.close()
        return
    
    # 准备更新数据
    update_count = 0
    for idx, row in signals_df.iterrows():
        data_dict = {
            'Scaling_Signal': int(row.get('Scaling_Action_Code', 0)),
            'Scaling_Position': int(row.get('Scaling_Position', 0)),
            'Scaling_Level': int(row.get('Scaling_Level', 0)),
            'Scaling_Strategy': strategy_name
        }
        
        # 更新数据库
        db.update_data(ticker, row['datetime'], data_dict)
        update_count += 1
    
    # 关闭数据库
    db.close()
    
    logger.info(f"Successfully saved {update_count} records for {ticker} - {strategy_name}")
    print(f"\n✓ 已保存 {strategy_name} 策略信号到数据库：{ticker}")
    print(f"  - 更新记录数: {update_count}")
    print(f"  - 日期范围: {start_date} 至 {end_date}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='加仓策略对比测试')
    parser.add_argument('--tickers', nargs='+', default=['RB.SHF', 'OI.ZCE'],
                       help='期货代码列表')
    parser.add_argument('--start-date', type=str, default='2025-01-01',
                       help='开始日期')
    parser.add_argument('--end-date', type=str, default='2025-01-31',
                       help='结束日期')
    parser.add_argument('--db-path', type=str, default='trading_signals.db',
                       help='数据库路径')
    parser.add_argument('--parallel', action='store_true', default=True,
                       help='是否并行处理')
    parser.add_argument('--strategies', nargs='+',
                       help='指定测试的策略（不指定则测试所有）')
    parser.add_argument('--save-strategy', type=str,
                       help='将指定策略的信号保存到数据库（例如：pyramid）')
    
    args = parser.parse_args()
    
    # 选择要测试的策略
    if args.strategies:
        strategies = {k: v for k, v in SCALING_CONFIGS.items() 
                     if k in args.strategies}
    else:
        strategies = SCALING_CONFIGS
    
    logger.info("="*70)
    logger.info("加仓策略对比测试系统")
    logger.info("="*70)
    logger.info(f"测试品种: {args.tickers}")
    logger.info(f"测试周期: {args.start_date} 至 {args.end_date}")
    logger.info(f"测试策略: {list(strategies.keys())}")
    logger.info(f"并行处理: {args.parallel}")
    logger.info("="*70)
    
    # 运行测试
    results = compare_all_strategies(
        tickers=args.tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        strategies=strategies,
        db_path=args.db_path,
        parallel=args.parallel
    )
    
    # 生成报告
    report = generate_comparison_report(results)
    
    # 保存JSON结果
    save_results_to_json(results)
    
    # 生成可视化图表
    logger.info("="*70)
    logger.info("生成可视化图表...")
    logger.info("="*70)
    
    chart_files = visualize_all_strategies(results, output_dir='output')
    
    logger.info("\n生成的图表文件:")
    for ticker, files in chart_files.items():
        logger.info(f"\n{ticker}:")
        for file_path in files:
            logger.info(f"  - {os.path.basename(file_path)}")
    
    logger.info("="*70)
    logger.info("测试完成！")
    logger.info("="*70)
    
    # 自动打开对比图表
    import webbrowser
    import time
    
    logger.info("\n打开图表...")
    charts_opened = []
    
    for ticker, files in chart_files.items():
        for file_path in files:
            if 'comparison' in file_path.lower():
                try:
                    abs_path = os.path.abspath(file_path)
                    logger.info(f"  打开: {os.path.basename(file_path)}")
                    webbrowser.open(f'file:///{abs_path}')
                    charts_opened.append(file_path)
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"  无法打开 {file_path}: {e}")
    
    if charts_opened:
        logger.info(f"\n✓ 已在浏览器中打开 {len(charts_opened)} 个对比图表")
    
    # 打开output目录
    try:
        import subprocess
        if os.name == 'nt':  # Windows
            os.startfile('output')
            logger.info(f"✓ 已打开output目录")
    except:
        pass
    
    # 打印简要结果
    print("\n" + "="*70)
    print("测试结果摘要")
    print("="*70)
    
    for ticker, strategies_result in results.items():
        print(f"\n{ticker}:")
        for strategy_name, result in strategies_result.items():
            if result['status'] == 'success':
                m = result['metrics']
                print(f"  {strategy_name:20s}: "
                      f"收益 {m['total_return_pct']:6.2f}%, "
                      f"夏普 {m['sharpe_ratio']:6.4f}, "
                      f"胜率 {m['win_rate']:5.2%}, "
                      f"交易 {m['total_trades']:3d}次")
    
    # 如果指定了保存策略，则将其信号保存到数据库
    if args.save_strategy:
        if args.save_strategy not in strategies:
            logger.error(f"指定的策略 '{args.save_strategy}' 不存在！")
            logger.error(f"可用策略: {list(strategies.keys())}")
            return
        
        print("\n" + "="*70)
        print(f"保存策略 '{args.save_strategy}' 到数据库...")
        print("="*70)
        
        config = strategies[args.save_strategy]
        
        for ticker in args.tickers:
            save_strategy_to_database(
                ticker=ticker,
                start_date=args.start_date,
                end_date=args.end_date,
                strategy_name=args.save_strategy,
                config=config,
                db_path=args.db_path
            )
        
        print("\n✓ 所有品种的加仓信号已保存到数据库！")
        print(f"  策略: {args.save_strategy}")
        print(f"  品种: {', '.join(args.tickers)}")
        print(f"  数据库: {args.db_path}")


if __name__ == "__main__":
    main()

