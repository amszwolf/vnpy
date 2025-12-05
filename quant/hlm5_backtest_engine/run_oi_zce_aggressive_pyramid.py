"""
使用 hlm5_all_parallel.py 运行 OI.ZCE 的 aggressive_pyramid 策略回测
Python环境：aidata311
"""

import sys
import os

# 导入 hlm5_all_parallel 的模块
from hlm5_all_parallel import (
    TradingSignalDatabaseManager,
    SmartDataUpdateManager,
    plot_analysis,
    EQUITY_CONFIG
)
import copy
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """运行 OI.ZCE 的 aggressive_pyramid 策略回测"""
    
    # 配置参数
    ticker = 'OI.ZCE'
    start_date = '2025-01-01'
    end_date = '2025-07-31'
    raw_db = 'tushare'
    raw_table = 'tb_futures_rboi_5min'  # 5分钟数据
    scaling_strategy = 'aggressive_pyramid'
    
    # 从配置文件获取数据库路径
    db_path = EQUITY_CONFIG['DATABASE_PATH']
    
    logger.info("="*70)
    logger.info("运行 OI.ZCE aggressive_pyramid 策略回测")
    logger.info("="*70)
    logger.info(f"品种: {ticker}")
    logger.info(f"数据周期: {raw_table}")
    logger.info(f"测试期间: {start_date} 至 {end_date}")
    logger.info(f"加仓策略: {scaling_strategy}")
    logger.info("="*70)
    
    # 创建数据库连接
    db = TradingSignalDatabaseManager(db_path)
    
    try:
        # 创建配置
        current_config = copy.deepcopy(EQUITY_CONFIG)
        current_config['UPDATE_STRATEGY']['force_full_update'] = True  # 强制全量更新
        current_config['UPDATE_STRATEGY']['skip_existing'] = False
        
        # 创建智能更新管理器
        smart_manager = SmartDataUpdateManager(db, current_config)
        
        # 执行智能更新（含加仓策略）
        logger.info(f"\n开始处理 {ticker}...")
        start_time = time.time()
        
        result = smart_manager.update_ticker_data(
            ticker, raw_db, raw_table, start_date, end_date,
            scaling_strategy_name=scaling_strategy
        )
        
        duration = time.time() - start_time
        
        if result.get('records_updated', 0) > 0:
            logger.info(f"\n✓ 成功处理 {ticker}")
            logger.info(f"  更新记录数: {result.get('records_updated', 0)}")
            logger.info(f"  处理耗时: {duration:.2f}秒")
            
            # 生成可视化图表
            logger.info(f"\n生成分析图表...")
            plot_analysis(db, ticker, start_date, end_date, output_type='bokeh')
            logger.info(f"✓ 图表已保存: output/{ticker}_analysis.html")
            
            # 打开图表
            import webbrowser
            chart_path = os.path.abspath(f'output/{ticker}_analysis.html')
            webbrowser.open(f'file://{chart_path}')
            logger.info(f"✓ 已在浏览器中打开图表")
        else:
            logger.warning(f"未更新任何记录，可能数据已存在或数据源无数据")
        
        logger.info("\n" + "="*70)
        logger.info("回测完成！")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()
        logger.info("数据库连接已关闭")

if __name__ == "__main__":
    main()

