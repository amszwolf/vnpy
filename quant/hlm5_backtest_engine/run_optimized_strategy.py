#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HLM5 优化策略运行器
=================

根据交易频率优化报告，运行优化后的策略：
- 目标：年收益率 > 200%
- 回撤：< 5%
- 交易频率：每日 > 2次
- 股票数量：30-100只

运行步骤：
1. 股票筛选（优化后的宽松标准）
2. 技术指标计算（优化后的敏感参数）
3. 策略优化（扩大股票池，多层次信号）
4. 投资组合构建（动态仓位管理）

Author: HLM5 Team
Date: 2024-12
"""

import os
import sys
import time
import logging
from datetime import datetime
import argparse
import webbrowser
import tempfile

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hlm5_finscreener import FinancialScreener
from hlm5_all_parallel import main as run_indicators
from hlm5_stock_optimize import StrategyOptimizer, OptimizationConfig
from hlm5_portfolio_signal_driven import PortfolioConstructor, WeightMethod
from hlm5_config import EQUITY_CONFIG

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/optimized_strategy.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def run_optimized_finscreener(account: str = 'hfzq_real', 
                             screening_level: str = 'moderate', 
                             target_stocks: int = 100) -> list:
    """
    步骤1: 运行优化后的股票筛选器
    """
    logger = logging.getLogger(__name__)
    logger.info("🎯 步骤1: 开始股票筛选（优化参数）")
    
    # 使用优化后的筛选标准
    screener = FinancialScreener(qmt_account=account, screening_level=screening_level)
    
    # 连接QMT
    if not screener.connect_qmt():
        logger.error("❌ QMT连接失败")
        return []
    
    # 检查数据有效性，如果需要则更新
    if not screener.is_data_cache_valid():
        logger.info("📊 数据过期，开始更新...")
        screener.update_all_stock_data(force_update=True)
    
    # 执行筛选，获取更多股票
    selected_stocks = screener.screen_stocks_from_db(top_n=target_stocks)
    
    if not selected_stocks:
        logger.error("❌ 未找到符合条件的股票")
        return []
    
    stock_codes = [stock['stock_code'] for stock in selected_stocks]
    logger.info(f"✅ 筛选完成，获得 {len(stock_codes)} 只股票")
    logger.info(f"📋 股票列表: {', '.join(stock_codes[:10])}...")
    
    return stock_codes

def run_optimized_indicators(stock_codes: list) -> bool:
    """
    步骤2: 运行优化后的技术指标计算
    """
    logger = logging.getLogger(__name__)
    logger.info("🎯 步骤2: 开始技术指标计算（优化参数）")
    
    try:
        # 使用优化后的配置运行技术指标计算
        run_indicators(
            update_mode='smart',
            enable_realtime=False,
            max_tickers=len(stock_codes),
            verbose=True,
            start_date=None,
            end_date=None,
            raw_db='tushare',
            raw_table='tb_szsh_day_2024'
        )
        
        logger.info("✅ 技术指标计算完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 技术指标计算失败: {e}")
        return False

def run_optimized_strategy_optimization(stock_codes: list, experiment_name: str) -> dict:
    """
    步骤3: 运行优化后的策略优化
    """
    logger = logging.getLogger(__name__)
    logger.info("🎯 步骤3: 开始策略优化（优化参数）")
    
    # 使用优化后的配置
    config = OptimizationConfig(
        max_stocks=min(100, len(stock_codes)),  # 最多100只股票
        min_stocks=min(30, len(stock_codes)//2),  # 最少30只股票
        n_calls=100,  # 优化迭代次数
        optimization_method='bayesian',
        
        # 优化后的权重配置
        return_weight=0.4,
        drawdown_weight=0.25,
        sharpe_weight=0.15,
        win_rate_weight=0.1,
        trade_frequency_weight=0.1,
        
        # 更积极的替换策略
        replacement_threshold=0.02,
        min_optimization_rounds=1,
        replacement_candidate_pool=100
    )
    
    try:
        # 创建优化器
        optimizer = StrategyOptimizer(config, 'trading_signals.db', 'finscreener.db')
        
        # 执行优化
        logger.info(f"📈 开始优化 {len(stock_codes)} 只股票...")
        results = optimizer.optimize_strategy(
            tickers=stock_codes,
            experiment_name=experiment_name
        )
        
        logger.info("✅ 策略优化完成")
        return results
        
    except Exception as e:
        logger.error(f"❌ 策略优化失败: {e}")
        return {}

def run_optimized_portfolio_construction(optimization_results: dict, 
                                       experiment_name: str) -> str:
    """
    步骤4: 运行优化后的投资组合构建
    """
    logger = logging.getLogger(__name__)
    logger.info("🎯 步骤4: 开始投资组合构建（优化参数）")
    
    try:
        # 使用优化后的权重方法
        portfolio_constructor = PortfolioConstructor(
            optimization_results=optimization_results,
            weight_method=WeightMethod.ENHANCED_TOP_PERFORMERS,  # 使用增强权重方法
            experiment_name=experiment_name
        )
        
        # 构建投资组合
        portfolio_result = portfolio_constructor.construct_portfolio()
        
        if portfolio_result:
            logger.info("✅ 投资组合构建完成")
            
            # 生成HTML报告
            html_content = generate_optimization_report(
                optimization_results, 
                portfolio_result, 
                experiment_name
            )
            
            # 保存并在浏览器中打开
            html_file = save_and_open_report(html_content, experiment_name)
            logger.info(f"📊 详细报告已生成: {html_file}")
            
            return html_file
        else:
            logger.error("❌ 投资组合构建失败")
            return ""
            
    except Exception as e:
        logger.error(f"❌ 投资组合构建失败: {e}")
        return ""

def generate_optimization_report(optimization_results: dict, 
                               portfolio_result: dict, 
                               experiment_name: str) -> str:
    """生成优化报告HTML"""
    
    # 计算关键指标
    total_stocks = len(optimization_results.get('stock_performances', {}))
    avg_return = sum(stock['annual_return'] for stock in optimization_results.get('stock_performances', {}).values()) / max(total_stocks, 1)
    avg_drawdown = sum(abs(stock['max_drawdown']) for stock in optimization_results.get('stock_performances', {}).values()) / max(total_stocks, 1)
    total_trades = sum(stock['total_trades'] for stock in optimization_results.get('stock_performances', {}).values())
    avg_trades_per_stock = total_trades / max(total_stocks, 1)
    
    # 筛选高收益股票
    high_return_stocks = []
    if 'stock_performances' in optimization_results:
        for ticker, perf in optimization_results['stock_performances'].items():
            if perf['annual_return'] > 0.5:  # 50%以上收益
                high_return_stocks.append((ticker, perf))
    
    high_return_stocks.sort(key=lambda x: x[1]['annual_return'], reverse=True)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HLM5 优化策略报告 - {experiment_name}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
        .metric-label {{ font-size: 0.9em; opacity: 0.9; }}
        .success {{ background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%); }}
        .warning {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .info {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }}
        .stocks-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .stocks-table th, .stocks-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        .stocks-table th {{ background-color: #f8f9fa; font-weight: bold; }}
        .stocks-table tr:hover {{ background-color: #f5f5f5; }}
        .positive {{ color: #27ae60; font-weight: bold; }}
        .negative {{ color: #e74c3c; font-weight: bold; }}
        .timestamp {{ color: #7f8c8d; font-size: 0.9em; margin-top: 20px; }}
        .target-progress {{ margin: 20px 0; }}
        .progress-bar {{ width: 100%; height: 25px; background: #ecf0f1; border-radius: 12px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #56ab2f, #a8e6cf); transition: width 0.3s ease; }}
        .progress-text {{ text-align: center; line-height: 25px; font-weight: bold; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 HLM5 优化策略执行报告</h1>
        <p><strong>实验名称:</strong> {experiment_name}</p>
        <p><strong>生成时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>📊 核心指标概览</h2>
        <div class="metrics-grid">
            <div class="metric-card {'success' if avg_return > 2.0 else 'warning' if avg_return > 1.0 else 'info'}">
                <div class="metric-value">{avg_return:.1%}</div>
                <div class="metric-label">平均年化收益率</div>
                <div class="metric-label">目标: >200%</div>
            </div>
            <div class="metric-card {'success' if avg_drawdown < 0.05 else 'warning' if avg_drawdown < 0.08 else 'info'}">
                <div class="metric-value">{avg_drawdown:.1%}</div>
                <div class="metric-label">平均最大回撤</div>
                <div class="metric-label">目标: <5%</div>
            </div>
            <div class="metric-card {'success' if avg_trades_per_stock > 50 else 'warning' if avg_trades_per_stock > 20 else 'info'}">
                <div class="metric-value">{avg_trades_per_stock:.0f}</div>
                <div class="metric-label">平均交易次数/股票</div>
                <div class="metric-label">目标: >2次/日</div>
            </div>
            <div class="metric-card info">
                <div class="metric-value">{total_stocks}</div>
                <div class="metric-label">总股票数量</div>
                <div class="metric-label">目标: 30-100只</div>
            </div>
        </div>
        
        <h2>🎯 目标达成度</h2>
        <div class="target-progress">
            <p><strong>收益率目标 (200%):</strong></p>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {min(100, avg_return*100/2):.1f}%">
                    <div class="progress-text">{avg_return:.1%} / 200%</div>
                </div>
            </div>
        </div>
        
        <div class="target-progress">
            <p><strong>回撤控制目标 (<5%):</strong></p>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {max(0, min(100, (0.05-avg_drawdown)*100/0.05)):.1f}%">
                    <div class="progress-text">{avg_drawdown:.1%} (目标 <5%)</div>
                </div>
            </div>
        </div>
        
        <h2>🏆 表现优异股票 (收益率 >50%)</h2>
        <table class="stocks-table">
            <thead>
                <tr>
                    <th>股票代码</th>
                    <th>年化收益率</th>
                    <th>最大回撤</th>
                    <th>交易次数</th>
                    <th>胜率</th>
                    <th>夏普比率</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # 添加高收益股票表格
    for ticker, perf in high_return_stocks[:20]:  # 只显示前20只
        return_class = "positive" if perf['annual_return'] > 0 else "negative"
        drawdown_class = "positive" if abs(perf['max_drawdown']) < 0.05 else "negative"
        
        html_content += f"""
                <tr>
                    <td><strong>{ticker}</strong></td>
                    <td class="{return_class}">{perf['annual_return']:.1%}</td>
                    <td class="{drawdown_class}">{abs(perf['max_drawdown']):.1%}</td>
                    <td>{perf['total_trades']}</td>
                    <td>{perf['win_rate']:.1%}</td>
                    <td>{perf['sharpe_ratio']:.2f}</td>
                </tr>
        """
    
    html_content += f"""
            </tbody>
        </table>
        
        <h2>📈 策略优化总结</h2>
        <ul>
            <li><strong>技术指标优化:</strong> MACD参数缩短(20/8/5)，HLBW回望期缩短(40)，Prophet敏感性提升</li>
            <li><strong>筛选标准放宽:</strong> 扩大股票池，降低ROE要求，提升PE容忍度</li>
            <li><strong>信号生成优化:</strong> 多层次信号强度(3-10级)，动态仓位管理</li>
            <li><strong>风险控制:</strong> 紧密止损(4%)，快速止盈(12%)，跟踪止损(2%)</li>
        </ul>
        
        <h2>💡 优化建议</h2>
        <ul>
            <li>{'✅ 收益率目标已达成' if avg_return > 2.0 else '📈 建议进一步优化信号敏感性以提升收益率'}</li>
            <li>{'✅ 回撤控制良好' if avg_drawdown < 0.05 else '⚠️ 建议加强风险控制，调整止损策略'}</li>
            <li>{'✅ 交易频率充足' if avg_trades_per_stock > 50 else '🔄 建议降低信号门槛，增加交易机会'}</li>
        </ul>
        
        <div class="timestamp">
            <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>HLM5 智能股票交易系统 - 优化版本 v2.0</p>
        </div>
    </div>
</body>
</html>
    """
    
    return html_content

def save_and_open_report(html_content: str, experiment_name: str) -> str:
    """保存HTML报告并在浏览器中打开"""
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"optimization_report_{experiment_name}_{timestamp}.html"
    filepath = os.path.join('output', filename)
    
    # 保存文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # 在浏览器中打开
    abs_path = os.path.abspath(filepath)
    try:
        webbrowser.open(f'file://{abs_path}')
    except Exception as e:
        print(f"无法自动打开浏览器: {e}")
        print(f"请手动打开文件: {abs_path}")
    
    return abs_path

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='HLM5 优化策略运行器')
    parser.add_argument('--account', default='hfzq_real', 
                       choices=['hfzq_sim', 'hfzq_real'],
                       help='QMT账户类型')
    parser.add_argument('--screening-level', default='moderate',
                       choices=['strict', 'moderate', 'loose'],
                       help='筛选严格程度')
    parser.add_argument('--target-stocks', type=int, default=100,
                       help='目标股票数量')
    parser.add_argument('--experiment', default=None,
                       help='实验名称')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging()
    
    # 生成实验名称
    if not args.experiment:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        args.experiment = f"optimized_strategy_{timestamp}"
    
    logger.info("🚀 HLM5 优化策略开始执行")
    logger.info(f"📊 实验参数: {args}")
    logger.info("🎯 目标: 200%+收益率, <5%回撤, 每日2+交易, 30-100只股票")
    
    start_time = time.time()
    
    try:
        # 步骤1: 股票筛选
        stock_codes = run_optimized_finscreener(
            account=args.account,
            screening_level=args.screening_level,
            target_stocks=args.target_stocks
        )
        
        if not stock_codes:
            logger.error("❌ 股票筛选失败，终止执行")
            return
        
        # 步骤2: 技术指标计算
        if not run_optimized_indicators(stock_codes):
            logger.error("❌ 技术指标计算失败，终止执行")
            return
        
        # 步骤3: 策略优化
        optimization_results = run_optimized_strategy_optimization(
            stock_codes, args.experiment
        )
        
        if not optimization_results:
            logger.error("❌ 策略优化失败，终止执行")
            return
        
        # 步骤4: 投资组合构建
        report_file = run_optimized_portfolio_construction(
            optimization_results, args.experiment
        )
        
        if not report_file:
            logger.error("❌ 投资组合构建失败")
            return
        
        # 执行完成
        elapsed_time = time.time() - start_time
        logger.info(f"🎉 优化策略执行完成!")
        logger.info(f"⏱️ 总耗时: {elapsed_time:.1f} 秒")
        logger.info(f"📊 详细报告: {report_file}")
        
    except Exception as e:
        logger.error(f"❌ 执行过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    main() 