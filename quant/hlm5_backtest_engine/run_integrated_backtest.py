# -*- coding: utf-8 -*-
"""
集成回测测试脚本 - 带自动保存和图形显示
基于 hlm5_all_parallel.py，集成自动保存功能
"""

import sys
import logging
import copy
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from hlm5_config import EQUITY_CONFIG
from trading_signal_database_manager import TradingSignalDatabaseManager
from hlm5_all_parallel import process_ticker
from backtest_integration import save_backtest_results_auto

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_integrated_backtest_with_charts(
    ticker='OI.ZCE',
    start_date='2025-01-01',
    end_date='2025-12-31',
    scaling_strategy='aggressive_pyramid',
    my_raw_db='tushare',
    my_raw_table='tb_futures_rboi_5min',
    db_path='trading_signals.db',
    generate_charts=True,
    auto_save=True,
    auto_promote=True,
    sharpe_threshold=2.0
):
    """
    运行完整的集成回测流程
    
    Parameters:
    -----------
    ticker : str
        合约代码 (如 'OI.ZCE')
    start_date : str
        开始日期 (如 '2025-01-01')
    end_date : str
        结束日期 (如 '2025-12-31')
    scaling_strategy : str
        加仓策略 (aggressive_pyramid, pyramid, inverse_pyramid等)
    my_raw_db : str
        原始数据库名称
    my_raw_table : str
        原始数据表名称
    db_path : str
        信号数据库路径
    generate_charts : bool
        是否生成图形
    auto_save : bool
        是否自动保存结果
    auto_promote : bool
        是否自动提升为最优策略
    sharpe_threshold : float
        自动提升的夏普比率阈值
    """
    print("=" * 80)
    print("HLM5 集成回测测试")
    print("=" * 80)
    print(f"\n配置参数:")
    print(f"  合约: {ticker}")
    print(f"  时间范围: {start_date} ~ {end_date}")
    print(f"  数据表: {my_raw_table}")
    print(f"  加仓策略: {scaling_strategy}")
    print(f"  生成图形: {'是' if generate_charts else '否'}")
    print(f"  自动保存: {'是' if auto_save else '否'}")
    print(f"  自动提升: {'是' if auto_promote else '否'} (夏普>={sharpe_threshold})")
    print("=" * 80)
    
    # 创建主数据库连接
    main_db = TradingSignalDatabaseManager(db_path, enable_realtime=False)
    
    try:
        # 创建配置
        current_config = copy.deepcopy(EQUITY_CONFIG)
        current_config['UPDATE_STRATEGY']['force_full_update'] = True
        
        # ========================================
        # 步骤1: 运行回测
        # ========================================
        print(f"\n{'='*80}")
        print(f"步骤1: 运行回测")
        print(f"{'='*80}")
        
        logger.info(f"[启动] 处理期货: {ticker}")
        logger.info(f"  数据表: {my_raw_table}")
        logger.info(f"  日期范围: {start_date} 到 {end_date}")
        logger.info(f"  加仓策略: {scaling_strategy}")
        
        result = process_ticker(
            ticker, 
            db_path, 
            my_raw_db, 
            my_raw_table,
            start_date, 
            end_date, 
            30,  # forecast_days
            True,  # verbose
            current_config,
            scaling_strategy
        )
        
        # 检查回测结果
        if result['status'] != 'success':
            logger.error(f"✗ 回测失败: {result.get('error', 'Unknown error')}")
            return {
                'success': False,
                'stage': 'backtest',
                'error': result.get('error', 'Unknown error')
            }
        
        logger.info(f"✓ 回测完成: {result['strategy']} - {result['records_updated']} records")
        logger.info(f"  耗时: {result.get('duration', 0):.2f} 秒")
        
        # ========================================
        # 步骤2: 生成图形（如果启用）
        # ========================================
        if generate_charts:
            print(f"\n{'='*80}")
            print(f"步骤2: 生成分析图形")
            print(f"{'='*80}")
            
            try:
                from hlm5_all_parallel import plot_analysis
                
                logger.info("正在生成分析图表...")
                plot_analysis(main_db, ticker, start_date, end_date, output_type='bokeh')
                logger.info(f"✓ 图表已保存: output/{ticker}_analysis.html")
                
            except Exception as e:
                logger.warning(f"⚠ 图表生成失败: {e}")
        
        # ========================================
        # 步骤3: 自动保存结果（如果启用）
        # ========================================
        if auto_save:
            print(f"\n{'='*80}")
            print(f"步骤3: 自动保存回测结果")
            print(f"{'='*80}")
            
            logger.info("正在保存回测结果到数据库...")
            
            save_result = save_backtest_results_auto(
                ticker=ticker,
                db_path=db_path,
                start_date=start_date,
                end_date=end_date,
                auto_promote=auto_promote,
                sharpe_threshold=sharpe_threshold,
                save_prophet_model=True  # 启用Prophet模型保存
            )
            
            if save_result['success']:
                logger.info(f"✓ 策略ID: {save_result['strategy_id']}")
                logger.info(f"✓ 夏普比率: {save_result['sharpe_ratio']:.2f}")
                logger.info(f"✓ 年化收益: {save_result['annual_return']*100:.2f}%")
                logger.info(f"✓ 总交易: {save_result['total_trades']}")
                
                if save_result['promoted']:
                    logger.info(f"✓ 已提升为最优策略并导出配置")
                    logger.info(f"  配置文件: configs/strategies/{save_result['strategy_id']}.json")
                
                result['save_result'] = save_result
            else:
                logger.warning(f"⚠ 结果保存失败: {save_result.get('reason', 'unknown')}")
                result['save_result'] = save_result
        
        # ========================================
        # 步骤4: 显示摘要
        # ========================================
        print(f"\n{'='*80}")
        print(f"回测完成摘要")
        print(f"{'='*80}")
        print(f"\n回测信息:")
        print(f"  ✓ 合约: {ticker}")
        print(f"  ✓ 时间: {start_date} ~ {end_date}")
        print(f"  ✓ 更新策略: {result['strategy']}")
        print(f"  ✓ 记录数: {result['records_updated']}")
        print(f"  ✓ 耗时: {result.get('duration', 0):.2f} 秒")
        
        if generate_charts:
            print(f"\n图形输出:")
            print(f"  ✓ 分析图表: output/{ticker}_analysis.html")
        
        if auto_save and save_result['success']:
            print(f"\n数据库记录:")
            print(f"  ✓ 策略ID: {save_result['strategy_id']}")
            print(f"  ✓ 夏普比率: {save_result['sharpe_ratio']:.2f}")
            print(f"  ✓ 年化收益: {save_result['annual_return']*100:.2f}%")
            print(f"  ✓ 最大回撤: {save_result.get('max_drawdown', 0)*100:.2f}%")
            print(f"  ✓ 胜率: {save_result.get('win_rate', 0)*100:.2f}%")
            print(f"  ✓ 总交易: {save_result['total_trades']}")
            
            if save_result['promoted']:
                print(f"  ✓ 状态: 已提升为最优策略")
                print(f"  ✓ 配置: configs/strategies/{save_result['strategy_id']}.json")
        
        print(f"\n{'='*80}")
        print(f"✅ 全部完成！")
        print(f"{'='*80}")
        
        # 返回完整结果
        return {
            'success': True,
            'backtest_result': result,
            'save_result': save_result if auto_save else None
        }
        
    except Exception as e:
        logger.error(f"✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'stage': 'unknown',
            'error': str(e)
        }
    finally:
        main_db.close()
        logger.info("数据库连接已关闭")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='HLM5 集成回测测试 - 带自动保存和图形显示',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--ticker', default='OI.ZCE', help='合约代码 (默认: OI.ZCE)')
    parser.add_argument('--start-date', default='2025-01-01', help='开始日期 (默认: 2025-01-01)')
    parser.add_argument('--end-date', default='2025-12-31', help='结束日期 (默认: 2025-12-31)')
    parser.add_argument('--scaling-strategy', default='aggressive_pyramid', 
                       help='加仓策略 (默认: aggressive_pyramid)')
    parser.add_argument('--no-charts', action='store_true', help='禁用图形生成')
    parser.add_argument('--no-auto-save', action='store_true', help='禁用自动保存')
    parser.add_argument('--sharpe-threshold', type=float, default=2.0, 
                       help='自动提升的夏普比率阈值 (默认: 2.0)')
    
    args = parser.parse_args()
    
    print(f"\n启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行集成回测
    result = run_integrated_backtest_with_charts(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        scaling_strategy=args.scaling_strategy,
        generate_charts=not args.no_charts,
        auto_save=not args.no_auto_save,
        sharpe_threshold=args.sharpe_threshold
    )
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 退出码
    sys.exit(0 if result['success'] else 1)

