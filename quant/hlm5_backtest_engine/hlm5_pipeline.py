#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
HLM5 智能股票交易流水线系统
集成完整的股票分析和交易流程，支持模块化执行

主要功能:
1. 股票筛选 (FinScreener)
2. 技术指标计算 (All Parallel)
3. 策略优化 (Stock Optimize)
4. 投资组合构建 (Portfolio)
5. 实盘交易执行 (QMT)

Author: HLM5 Team
Version: 2.0 - Pipeline Integration
"""

import sys
import io
import numpy as np
import pandas as pd
import sqlite3
import os
import json
import time
import warnings
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import webbrowser
import tempfile
import codecs

# Force UTF-8 encoding for stdout and stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set environment encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 导入优化相关
try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    from skopt.acquisition import gaussian_ei
except ImportError:
    print("请先安装scikit-optimize包:")
    print("pip install scikit-optimize")

# 导入可视化相关
import plotly.graph_objects as go
import plotly.subplots as sp
from plotly.offline import plot

# 导入现有模块
try:
    from hlm5_all_parallel import (
        calculate_macd_signals, 
        check_entry_conditions, 
        check_exit_conditions,
        generate_performance_metrics,
        main as run_all_parallel
    )
    print("[OK] Successfully imported hlm5_all_parallel")
except ImportError as e:
    print(f"[WARNING] hlm5_all_parallel import failed: {e}")
    run_all_parallel = None

try:
    from trading_signal_database_manager import TradingSignalDatabaseManager
    print("[OK] Successfully imported TradingSignalDatabaseManager")
except ImportError as e:
    print(f"[WARNING] TradingSignalDatabaseManager import failed: {e}")

try:
    from finscreener_database_manager import FinScreenerDBManager
    print("[OK] Successfully imported FinScreenerDBManager")
except ImportError as e:
    print(f"[WARNING] FinScreenerDBManager import failed: {e}")

try:
    from hlm5_finscreener import FinancialScreener
    print("[OK] Successfully imported FinancialScreener")
except Exception as e:
    print(f"[WARNING] FinancialScreener import failed: {e}")
    FinancialScreener = None

try:
    from hlm5_config import EQUITY_CONFIG
    print("[OK] Successfully imported hlm5_config")
except ImportError as e:
    print(f"[WARNING] hlm5_config import failed: {e}")
    EQUITY_CONFIG = {}

# 导入原有的优化类
from hlm5_stock_optimize import (
    OptimizationConfig, OptimizationVisualizer, StockReplacementManager,
    StockOptimizeDatabase, VectorizedBacktester, StrategyOptimizer
)

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/hlm5_pipeline.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')

@dataclass
class PipelineConfig:
    """流水线配置参数"""
    # 基础配置
    experiment_name: str = "pipeline_run"
    account: str = "hfzq_sim"
    
    # 步骤控制
    run_finscreener: bool = True
    run_all_parallel: bool = True
    run_optimization: bool = True
    run_portfolio: bool = True
    run_trading: bool = False  # 默认不执行实盘交易
    
    # FinScreener参数
    finscreener_account: str = "hfzq_sim"
    
    # All Parallel参数
    update_mode: str = "smart"  # 'smart', 'force', 'incremental'
    max_workers: int = 4
    tickers: List[str] = None
    
    # 性能优化参数
    force_full_update: bool = False
    quiet_mode: bool = True
    
    # 优化参数
    max_stocks: int = 15
    n_calls: int = 80
    optimization_method: str = 'bayesian'
    auto_select: bool = True
    
    # 投资组合参数
    n_portfolio_stocks: int = 10
    weight_method: str = "score_weighted"  # 'profit_weighted', 'score_weighted', 'equal_weight'
    start_date: str = "2023-01-01"
    end_date: str = None
    initial_capital: float = 1000000
    min_weight: float = 0.02
    max_weight: float = 0.15
    
    # 其他参数
    parallel_jobs: int = -1
    verbose: bool = True
    force_update: bool = False
    
    def __post_init__(self):
        if self.end_date is None:
            self.end_date = datetime.now().strftime('%Y-%m-%d')
        if self.tickers is None:
            self.tickers = []

class HLM5Pipeline:
    """HLM5完整流水线系统"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.results = {}
        self.start_time = time.time()
        
        # 初始化各个组件
        self.finscreener = None
        self.trading_db = None
        self.optimizer = None
        
        logger.info(f"初始化HLM5 Pipeline: {config.experiment_name}")
        
    def run_pipeline(self):
        """运行完整流水线"""
        logger.info("="*80)
        logger.info("开始执行HLM5完整流水线")
        logger.info("="*80)
        
        # 步骤1: 股票筛选
        if self.config.run_finscreener:
            self.run_step_finscreener()
        
        # 步骤2: 技术指标计算
        if self.config.run_all_parallel:
            self.run_step_all_parallel()
        
        # 步骤3: 策略优化
        if self.config.run_optimization:
            self.run_step_optimization()
        
        # 步骤4: 投资组合构建
        if self.config.run_portfolio:
            self.run_step_portfolio()
        
        # 步骤5: 实盘交易
        if self.config.run_trading:
            self.run_step_trading()
        
        # 生成最终报告
        self.generate_final_report()
        
        logger.info("="*80)
        logger.info("HLM5流水线执行完成")
        logger.info("="*80)
        
        return self.results
    
    def run_step_finscreener(self):
        """步骤1: 股票筛选"""
        print("\n" + "="*80)
        print("🔍 步骤1: 股票筛选 (FinScreener)")
        print("="*80)
        logger.info("开始执行基础股票筛选...")
        
        screener_start = time.time()
        
        if FinancialScreener is None:
            logger.warning("FinancialScreener未导入，执行替代方案...")
            # 执行替代的finscreener命令 - 使用当前Python环境
            import subprocess
            import sys
            python_path = sys.executable
            cmd = [python_path, 'hlm5_finscreener.py']
            logger.info(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                raise RuntimeError(f"FinScreener执行失败: {result.stderr}")
            
            logger.info("✅ FinScreener执行成功")
            print("✅ 股票筛选完成，结果已保存到finscreener.db")
        else:
            # 初始化筛选器
            logger.info("初始化FinancialScreener...")
            self.finscreener = FinancialScreener(qmt_account=self.config.finscreener_account)
            
            logger.info("正在执行基本面筛选...")
            print("🔍 正在分析股票基本面数据...")
            print("📈 应用技术指标筛选条件...")
            print("💰 检查北向资金流入情况...")
            
            # 连接QMT - 任何错误都会直接抛出
            self.finscreener.connect_qmt()
            
            # 执行筛选逻辑 - 任何错误都会直接抛出
            logger.info("正在执行股票筛选...")
            
            # 清理数据库中的重复数据
            logger.info("检查并清理数据库重复数据...")
            db_manager = self.finscreener.get_db_manager()
            db_manager.cleanup_duplicate_data()
            
            # 下载板块数据
            logger.info("下载板块数据...")
            self.finscreener.qmt_client.download_sector_data()
            
            # 获取沪深全部股票数据
            logger.info("获取沪深全部股票数据...")
            all_stocks = self.finscreener.qmt_client.get_stock_list_in_sector('沪深A股')
            
            # 如果本地没有数据，则重新下载
            if not all_stocks:
                logger.info("本地无数据，从服务器下载...")
                self.finscreener.qmt_client.download_sector_data()
                all_stocks = self.finscreener.qmt_client.get_stock_list_in_sector('沪深A股')
            
            logger.info(f"获取到 {len(all_stocks)} 只股票")
            
            # 执行股票筛选
            if all_stocks:
                logger.info(f"开始筛选股票 - 使用{len(all_stocks)}只股票...")
                print(f"📊 正在筛选 {len(all_stocks)} 只股票...")
                
                # 筛选股票，获取前50只符合条件的股票
                selected_stocks = self.finscreener.screen_stocks(all_stocks, top_n=50)
                logger.info(f"筛选完成，获得 {len(selected_stocks)} 只符合条件的股票")
                
                if selected_stocks:
                    print(f"✅ 股票筛选完成，筛选出 {len(selected_stocks)} 只股票")
                    # 输出前几只股票信息
                    for i, stock in enumerate(selected_stocks[:5]):
                        print(f"   {i+1}. {stock['stock_code']} - 得分: {stock['score']:.3f}")
                else:
                    print("⚠️ 未找到符合筛选条件的股票")
                    logger.warning("筛选完成但未找到符合条件的股票")
            else:
                logger.error("无法获取股票列表")
                raise RuntimeError("无法获取股票列表")
            
            logger.info("筛选完成，结果保存到finscreener.db")
        
        # 记录成功结果
        duration = time.time() - screener_start
        self.results['finscreener'] = {
            'status': 'completed',
            'duration': duration,
            'message': '股票筛选完成'
        }
        
        logger.info(f"[步骤1] 股票筛选完成，耗时: {duration:.2f}秒")
    
    def run_step_all_parallel(self):
        """步骤2: 技术指标计算和信号生成"""
        print("\n" + "="*80)
        print("🔧 步骤2: 技术指标计算和信号生成 (All Parallel)")
        print("="*80)
        logger.info("开始执行技术指标计算和交易信号生成...")
        
        # 强制检查导入 - 失败就停止
        if run_all_parallel is None:
            raise ImportError("hlm5_all_parallel模块导入失败，无法继续执行技术指标计算")
        
        parallel_start = time.time()
        
        # 调用hlm5_all_parallel主函数
        logger.info(f"运行模式: {self.config.update_mode}")
        logger.info(f"最大工作进程: {self.config.max_workers}")
        
        # 准备参数
        enable_realtime = (self.config.update_mode == 'realtime')
        
        # 执行技术指标计算 - 任何错误都会直接抛出
        run_all_parallel(
            update_mode=self.config.update_mode,
            enable_realtime=enable_realtime,
            max_tickers=None,
            verbose=self.config.verbose,
            start_date=None,
            end_date=None,
            raw_db='tushare',
            raw_table='tb_szsh_day_2024'
        )
        
        # 记录成功结果
        duration = time.time() - parallel_start
        self.results['all_parallel'] = {
            'status': 'completed',
            'duration': duration,
            'message': '技术指标计算完成'
        }
        
        logger.info(f"[步骤2] 技术指标计算完成，耗时: {duration:.2f}秒")
    
    def run_step_optimization(self):
        """步骤3: 策略优化"""
        print("\n" + "="*80)
        print("⚡ 步骤3: 策略优化 (Stock Optimize)")
        print("="*80)
        logger.info("开始执行贝叶斯策略参数优化...")
        
        opt_start = time.time()
        
        # 创建优化配置
        opt_config = OptimizationConfig(
            max_stocks=self.config.max_stocks,
            min_stocks=max(1, self.config.max_stocks // 4),
            n_calls=self.config.n_calls,
            optimization_method=self.config.optimization_method,
            parallel_jobs=self.config.parallel_jobs
        )
        
        # 创建策略优化器
        self.optimizer = StrategyOptimizer(opt_config)
        
        # 选择股票
        if self.config.auto_select:
            logger.info(f"自动选择{self.config.max_stocks}只股票进行优化...")
            tickers = self.optimizer.select_stocks_from_finscreener(self.config.max_stocks)
            logger.info(f"股票选择完成，共选择{len(tickers)}只股票")
            
            if not tickers:
                raise ValueError("自动选择股票失败，没有找到符合条件的股票")
        else:
            tickers = self.config.tickers
            if not tickers:
                raise ValueError("未指定股票列表且未启用自动选择")
        
        logger.info(f"选择的股票: {tickers}")
        
        # 执行优化 - 任何错误都会直接抛出
        logger.info("开始执行策略优化...")
        optimization_result = self.optimizer.optimize_strategy(
            tickers, 
            self.config.experiment_name
        )
        
        if not optimization_result:
            raise RuntimeError("策略优化返回空结果")
        
        logger.info("策略优化执行完成")
        
        # 记录成功结果
        duration = time.time() - opt_start
        self.results['optimization'] = {
            'status': 'completed',
            'duration': duration,
            'result': optimization_result,
            'selected_stocks': tickers,
            'message': '策略优化完成'
        }
        
        logger.info(f"[步骤3] 策略优化完成，耗时: {duration:.2f}秒")
        
        # 确保资源清理
        if self.optimizer:
            self.optimizer.close()
    
    def run_step_portfolio(self):
        """步骤4: 投资组合构建"""
        print("\n" + "="*80)
        print("📊 步骤4: 投资组合构建 (Portfolio Signal Driven)")
        print("="*80)
        logger.info("开始执行信号驱动的投资组合构建和回测...")
        
        portfolio_start = time.time()
        
        # 构建命令 - 使用当前Python环境
        import sys
        python_path = sys.executable
        cmd = [
            python_path, 
            'hlm5_portfolio_signal_driven.py',
            '--n-stocks', str(self.config.n_portfolio_stocks),
            '--weight-method', self.config.weight_method,
            '--start-date', self.config.start_date,
            '--end-date', self.config.end_date,
            '--initial-capital', str(self.config.initial_capital),
            '--min-weight', str(self.config.min_weight),
            '--max-weight', str(self.config.max_weight),
            '--portfolio-name', f"{self.config.experiment_name}_portfolio"
        ]
        
        # 如果有优化结果配置文件，使用它
        if (self.results.get('optimization', {}).get('status') == 'completed' and 
            self.results['optimization']['result'].get('config_file')):
            config_file = self.results['optimization']['result']['config_file']
            cmd.extend(['--use-config', '--config-file', config_file])
            logger.info(f"使用优化配置文件: {config_file}")
        
        logger.info(f"执行投资组合构建: {' '.join(cmd)}")
        
        # 执行命令 - 任何错误都会直接抛出
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            raise RuntimeError(f"投资组合构建失败，返回码: {result.returncode}, 错误信息: {result.stderr}")
        
        # 记录成功结果
        duration = time.time() - portfolio_start
        self.results['portfolio'] = {
            'status': 'completed',
            'duration': duration,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'message': '投资组合构建完成'
        }
        
        logger.info(f"[步骤4] 投资组合构建完成，耗时: {duration:.2f}秒")
    
    def run_step_trading(self):
        """步骤5: 实盘交易执行"""
        print("\n" + "="*80)
        print("💼 步骤5: 实盘交易执行 (QMT Trading)")
        print("="*80)
        logger.info("开始执行QMT实盘交易系统连接和测试...")
        
        trading_start = time.time()
        
        # 构建QMT测试命令 - 使用当前Python环境
        import sys
        python_path = sys.executable
        cmd = [
            python_path,
            'hlm5_qmt.py',
            self.config.account
        ]
        
        logger.info(f"执行QMT连接测试: {' '.join(cmd)}")
        
        # 执行命令 - 任何错误都会直接抛出
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            raise RuntimeError(f"QMT连接测试失败，返回码: {result.returncode}, 错误信息: {result.stderr}")
        
        # 记录成功结果
        duration = time.time() - trading_start
        self.results['trading'] = {
            'status': 'completed',
            'duration': duration,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'message': 'QMT连接测试完成'
        }
        
        logger.info(f"[步骤5] QMT连接测试完成，耗时: {duration:.2f}秒")
        logger.info("注意: 实盘交易需要手动执行，请谨慎操作")
    
    def generate_final_report(self):
        """生成最终报告"""
        logger.info("\n[最终报告] 生成流水线执行报告...")
        
        total_duration = time.time() - self.start_time
        
        # 创建报告
        report = {
            'experiment_name': self.config.experiment_name,
            'execution_time': datetime.now().isoformat(),
            'total_duration': total_duration,
            'config': self.config.__dict__,
            'results': self.results,
            'summary': self._generate_summary()
        }
        
        # 保存报告
        report_filename = f"pipeline_report_{self.config.experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"流水线报告已保存: {report_filename}")
        
        # 打印摘要
        self._print_summary()
        
        self.results['final_report'] = {
            'status': 'completed',
            'report_file': report_filename,
            'total_duration': total_duration
        }
    
    def _generate_summary(self):
        """生成执行摘要"""
        summary = {
            'total_steps': 0,
            'completed_steps': 0,
            'failed_steps': 0,
            'step_status': {}
        }
        
        steps = ['finscreener', 'all_parallel', 'optimization', 'portfolio', 'trading']
        
        for step in steps:
            if step in self.results:
                summary['total_steps'] += 1
                status = self.results[step].get('status', 'unknown')
                summary['step_status'][step] = status
                
                if status == 'completed':
                    summary['completed_steps'] += 1
                elif status == 'failed':
                    summary['failed_steps'] += 1
        
        summary['success_rate'] = (summary['completed_steps'] / summary['total_steps'] * 100) if summary['total_steps'] > 0 else 0
        
        return summary
    
    def _print_summary(self):
        """打印执行摘要"""
        print("\n" + "="*80)
        print("HLM5 流水线执行摘要")
        print("="*80)
        
        summary = self._generate_summary()
        
        print(f"实验名称: {self.config.experiment_name}")
        total_duration = time.time() - self.start_time
        print(f"总执行时间: {total_duration:.2f}秒")
        print(f"执行步骤: {summary['completed_steps']}/{summary['total_steps']}")
        print(f"成功率: {summary['success_rate']:.1f}%")
        
        print(f"\n步骤执行状态:")
        step_names = {
            'finscreener': '股票筛选',
            'all_parallel': '技术指标计算',
            'optimization': '策略优化',
            'portfolio': '投资组合构建',
            'trading': '交易系统测试'
        }
        
        for step, status in summary['step_status'].items():
            name = step_names.get(step, step)
            status_icon = "✅" if status == 'completed' else "❌" if status == 'failed' else "⚠️"
            duration = self.results[step].get('duration', 0)
            print(f"  {status_icon} {name}: {status} ({duration:.2f}秒)")
        
        # 显示关键结果
        if 'optimization' in self.results and self.results['optimization']['status'] == 'completed':
            opt_result = self.results['optimization']['result']
            if opt_result:
                print(f"\n策略优化结果:")
                print(f"  选择股票: {self.results['optimization']['selected_stocks']}")
                print(f"  最佳评分: {opt_result.get('best_score', 'N/A')}")
                if opt_result.get('config_file'):
                    print(f"  配置文件: {opt_result['config_file']}")
        
        print("\n" + "="*80)

def parse_steps(steps_str):
    """解析步骤参数"""
    if not steps_str:
        return None
    
    step_map = {
        # 数字映射
        '1': 'finscreener',
        '2': 'all_parallel', 
        '3': 'optimization',
        '4': 'portfolio',
        '5': 'trading',
        # 完整名称
        'finscreener': 'finscreener',
        'all_parallel': 'all_parallel',
        'optimization': 'optimization',
        'portfolio': 'portfolio',
        'trading': 'trading',
        # 简化名称
        'parallel': 'all_parallel',
        'optimize': 'optimization',
        'screen': 'finscreener',
        'screener': 'finscreener',
        'technical': 'all_parallel',
        'signals': 'all_parallel',
        'backtest': 'portfolio',
        'trade': 'trading'
    }
    
    steps = []
    for step in steps_str.split(','):
        step = step.strip().lower()
        if step in step_map:
            mapped_step = step_map[step]
            if mapped_step not in steps:  # 避免重复
                steps.append(mapped_step)
        else:
            print(f"警告: 未知步骤 '{step}'，将被忽略")
            print(f"支持的步骤: 1-5, finscreener, parallel, optimize, portfolio, trading")
    
    return steps

def show_pipeline_help():
    """显示流水线帮助信息"""
    help_text = """
HLM5 智能股票交易流水线系统 - 详细使用指南
===============================================

🚀 预设运行模式：
----------------

1️⃣  日常分析流程（每日交易日下午2:30运行）：
   python hlm5_pipeline.py --mode daily
   等同于：--steps 1,2,3,4 --max-stocks 15 --n-calls 50

2️⃣  仅交易执行（根据需要运行）：
   python hlm5_pipeline.py --mode trading
   等同于：--steps 5 --account hfzq_sim

3️⃣  完整优化模式（周末或需要时运行）：
   python hlm5_pipeline.py --mode full-optimize
   等同于：--steps 1,2,3,4 --max-stocks 20 --n-calls 100

4️⃣  快速测试模式：
   python hlm5_pipeline.py --mode quick-test
   等同于：--steps 2,4 --max-stocks 5 --n-calls 20

📝 单步运行模式：
----------------

🔍 步骤1：股票筛选
   python hlm5_pipeline.py --step 1
   python hlm5_pipeline.py --steps finscreener

🔧 步骤2：技术指标计算  
   python hlm5_pipeline.py --step 2
   python hlm5_pipeline.py --steps parallel

⚡ 步骤3：策略优化
   python hlm5_pipeline.py --step 3 --max-stocks 15 --n-calls 80
   python hlm5_pipeline.py --steps optimize --max-stocks 15 --n-calls 80

📊 步骤4：投资组合构建
   python hlm5_pipeline.py --step 4 --n-portfolio-stocks 10
   python hlm5_pipeline.py --steps portfolio --n-portfolio-stocks 10

💼 步骤5：实盘交易
   python hlm5_pipeline.py --step 5 --account hfzq_sim
   python hlm5_pipeline.py --steps trading --account hfzq_sim

🎯 常用参数组合：
----------------

• 轻量级日常运行：
  python hlm5_pipeline.py --mode daily-light
  （10只股票，30次优化，适合快速运行）

• 深度优化运行：
  python hlm5_pipeline.py --mode daily-deep
  （20只股票，100次优化，适合充分优化）

• 更新技术指标：
  python hlm5_pipeline.py --step 2 --update-mode force

• 重建投资组合：
  python hlm5_pipeline.py --step 4 --weight-method profit_weighted --n-portfolio-stocks 15

• 测试交易连接：
  python hlm5_pipeline.py --step 5 --test-only

📅 推荐运行计划：
----------------

交易日下午2:30（数据更新后）：
→ python hlm5_pipeline.py --mode daily

交易日早盘前（如需要）：  
→ python hlm5_pipeline.py --mode trading

周末或需要深度优化时：
→ python hlm5_pipeline.py --mode full-optimize

⚙️  高级参数：
----------------
--experiment NAME        实验名称
--max-stocks NUM         优化股票数量 (1-50)
--n-calls NUM           优化迭代次数 (10-1000)  
--n-portfolio-stocks NUM 投资组合股票数量
--weight-method METHOD   权重方法 (score_weighted/profit_weighted/equal_weight)
--update-mode MODE      更新模式 (smart/force/incremental)
--start-date DATE       回测开始日期
--end-date DATE         回测结束日期
--account ACCOUNT       交易账号
--no-plot              跳过图表生成
--verbose              详细输出
"""
    print(help_text)

def show_pipeline_examples():
    """显示流水线使用示例"""
    examples = """
HLM5 流水线实用示例
==================

🔥 最常用命令：
--------------

# 每日例行分析（推荐）
python hlm5_pipeline.py --mode daily
python hlm5_pipeline.py --mode daily-light    # 快速版本
python hlm5_pipeline.py --mode daily-deep     # 深度版本

# 单独交易执行  
python hlm5_pipeline.py --mode trading
python hlm5_pipeline.py --step 5 --test-only  # 仅测试连接

📋 分步执行示例：
----------------

# 每日分析 - 分步执行
python hlm5_pipeline.py --step 1              # 股票筛选
python hlm5_pipeline.py --step 2 --force      # 强制更新技术指标  
python hlm5_pipeline.py --step 3 --max-stocks 15 --n-calls 60  # 策略优化
python hlm5_pipeline.py --step 4 --n-portfolio-stocks 10       # 组合构建

# 重新优化特定部分
python hlm5_pipeline.py --step 3 --max-stocks 20 --n-calls 100  # 增加优化强度
python hlm5_pipeline.py --step 4 --weight-method profit_weighted # 改变权重方法

🎯 特殊场景：
-------------

# 新股票池筛选
python hlm5_pipeline.py --step 1 --experiment new_stocks

# 强制全量更新
python hlm5_pipeline.py --steps 2,3,4 --update-mode force

# 高频交易优化
python hlm5_pipeline.py --steps 3,4 --max-stocks 25 --n-calls 150 --experiment high_freq

# 回测特定时间段
python hlm5_pipeline.py --step 4 --start-date 2023-01-01 --end-date 2024-12-31

# 测试不同权重方法
python hlm5_pipeline.py --step 4 --weight-method equal_weight --n-portfolio-stocks 12

⏰ 自动化脚本示例：
------------------

# Windows批处理文件 (daily_analysis.bat)
@echo off
cd /d "D:\\Your\\Project\\Path"
"D:\\Install\\anaconda\\envs\\aidata311_new\\python.exe" hlm5_pipeline.py --mode daily
pause

# Linux/Mac定时任务 (crontab)
# 每个交易日下午2:30运行
30 14 * * 1-5 cd /path/to/project && python hlm5_pipeline.py --mode daily

🔧 故障排除：
-------------

# 跳过问题步骤继续执行
python hlm5_pipeline.py --steps 2,4  # 跳过筛选和优化

# 调试模式
python hlm5_pipeline.py --step 3 --max-stocks 5 --n-calls 10 --verbose

# 仅生成报告，不执行交易
python hlm5_pipeline.py --step 4 --no-plot
"""
    print(examples)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='HLM5 智能股票交易流水线系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='使用 --help-pipeline 查看详细帮助, --help-examples 查看实用示例'
    )
    
    # 预设运行模式
    parser.add_argument('--mode', type=str, 
                       choices=['daily', 'daily-light', 'daily-deep', 'trading', 'full-optimize', 'quick-test'],
                       help='预设运行模式')
    
    # 基础参数
    parser.add_argument('--experiment', type=str, default=f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}", 
                       help='实验名称')
    parser.add_argument('--account', type=str, default='hfzq_sim', help='交易账号')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    # 步骤控制（新增简化参数）
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4, 5], help='运行单个步骤')
    parser.add_argument('--steps', type=str, help='指定运行步骤 (1-5或名称，逗号分隔)')
    parser.add_argument('--skip-finscreener', action='store_true', help='跳过股票筛选')
    parser.add_argument('--skip-parallel', action='store_true', help='跳过技术指标计算')
    parser.add_argument('--skip-optimization', action='store_true', help='跳过策略优化')
    parser.add_argument('--skip-portfolio', action='store_true', help='跳过投资组合构建')
    parser.add_argument('--skip-trading', action='store_true', help='跳过交易系统测试')
    
    # 简化参数
    parser.add_argument('--force', action='store_true', help='强制全量更新（等同于--update-mode force）')
    parser.add_argument('--test-only', action='store_true', help='仅测试连接，不执行实际交易')
    
    # All Parallel参数
    parser.add_argument('--update-mode', type=str, default='smart', 
                       choices=['smart', 'force', 'incremental'], help='更新模式')
    parser.add_argument('--max-workers', type=int, default=4, help='最大工作进程数')
    parser.add_argument('--tickers', nargs='+', help='指定股票代码列表')
    
    # 性能优化参数
    parser.add_argument('--force-full', action='store_true', 
                       help='强制全量更新（忽略增量检查）')
    parser.add_argument('--quiet', action='store_true', default=True,
                       help='安静模式（只显示进度和错误）')
    
    # 优化参数
    parser.add_argument('--max-stocks', type=int, default=15, help='最大股票数量 (1-50)')
    parser.add_argument('--n-calls', type=int, default=50, help='优化迭代次数 (10-1000)')
    parser.add_argument('--parallel-jobs', type=int, default=-1, help='并行任务数')
    parser.add_argument('--auto-select', action='store_true', default=True, help='自动选择股票')
    
    # 投资组合参数
    parser.add_argument('--n-portfolio-stocks', type=int, default=10, help='投资组合股票数量')
    parser.add_argument('--weight-method', type=str, default='score_weighted',
                       choices=['profit_weighted', 'score_weighted', 'equal_weight'],
                       help='权重分配方法')
    parser.add_argument('--start-date', type=str, default='2023-01-01', help='回测开始日期')
    parser.add_argument('--end-date', type=str, help='回测结束日期')
    parser.add_argument('--initial-capital', type=float, default=1000000, help='初始资金')
    parser.add_argument('--min-weight', type=float, default=0.02, help='最小权重')
    parser.add_argument('--max-weight', type=float, default=0.15, help='最大权重')
    
    # 其他参数
    parser.add_argument('--no-plot', action='store_true', help='跳过图表生成')
    
    # 帮助参数
    parser.add_argument('--help-pipeline', action='store_true', help='显示流水线详细帮助')
    parser.add_argument('--help-examples', action='store_true', help='显示实用示例')
    
    args = parser.parse_args()
    
    # 显示帮助信息
    if args.help_pipeline:
        show_pipeline_help()
        return
    elif args.help_examples:
        show_pipeline_examples()
        return
    
    # 处理预设模式
    if args.mode:
        if args.mode == 'daily':
            # 日常分析流程：1,2,3,4步，15只股票，50次优化
            args.steps = '1,2,3,4'
            args.max_stocks = 15
            args.n_calls = 50
            args.experiment = f"daily_{datetime.now().strftime('%Y%m%d')}"
            print(f"🔄 运行模式: 日常分析流程")
            
        elif args.mode == 'daily-light':
            # 轻量级日常运行：1,2,3,4步，10只股票，30次优化
            args.steps = '1,2,3,4'
            args.max_stocks = 10
            args.n_calls = 30
            args.experiment = f"daily_light_{datetime.now().strftime('%Y%m%d')}"
            print(f"🚀 运行模式: 轻量级日常运行")
            
        elif args.mode == 'daily-deep':
            # 深度优化运行：1,2,3,4步，20只股票，100次优化
            args.steps = '1,2,3,4'
            args.max_stocks = 20
            args.n_calls = 100
            args.experiment = f"daily_deep_{datetime.now().strftime('%Y%m%d')}"
            print(f"⚡ 运行模式: 深度优化运行")
            
        elif args.mode == 'trading':
            # 仅交易执行：第5步
            args.steps = '5'
            args.experiment = f"trading_{datetime.now().strftime('%Y%m%d_%H%M')}"
            print(f"💼 运行模式: 交易执行")
            
        elif args.mode == 'full-optimize':
            # 完整优化模式：1,2,3,4步，20只股票，100次优化
            args.steps = '1,2,3,4'
            args.max_stocks = 20
            args.n_calls = 100
            args.update_mode = 'full'
            args.experiment = f"full_optimize_{datetime.now().strftime('%Y%m%d')}"
            print(f"🔥 运行模式: 完整优化模式")
            
        elif args.mode == 'quick-test':
            # 快速测试模式：2,4步，5只股票，20次优化
            args.steps = '2,4'
            args.max_stocks = 5
            args.n_calls = 20
            args.experiment = f"quick_test_{datetime.now().strftime('%Y%m%d_%H%M')}"
            print(f"🧪 运行模式: 快速测试")
    
    # 处理单步参数
    if args.step:
        args.steps = str(args.step)
        print(f"📍 单步运行: 步骤{args.step}")
    
    # 处理简化参数
    if args.force:
        args.update_mode = 'full'
        print(f"🔄 强制全量更新模式")
    
    # 处理性能优化参数
    if args.force_full:
        args.force_full_update = True
        print(f"🔄 强制全量更新（忽略增量检查）")
    else:
        args.force_full_update = False
    
    if args.verbose:
        args.quiet_mode = False
        print(f"📝 详细日志模式")
    else:
        args.quiet_mode = getattr(args, 'quiet', True)
    
    # 参数验证
    if args.max_stocks < 1 or args.max_stocks > 50:
        print("Error: max-stocks must be between 1-50")
        return
    
    if args.n_calls < 10 or args.n_calls > 1000:
        print("Error: n-calls must be between 10-1000")
        return
    
    # 创建配置
    config = PipelineConfig(
        experiment_name=args.experiment,
        account=args.account,
        
        # 步骤控制
        run_finscreener=not args.skip_finscreener,
        run_all_parallel=not args.skip_parallel,
        run_optimization=not args.skip_optimization,
        run_portfolio=not args.skip_portfolio,
        run_trading=not args.skip_trading,
        
        # 参数配置
        update_mode=args.update_mode,
        max_workers=args.max_workers,
        tickers=args.tickers or [],
        force_full_update=getattr(args, 'force_full_update', False),
        quiet_mode=getattr(args, 'quiet_mode', True),
        max_stocks=args.max_stocks,
        n_calls=args.n_calls,
        parallel_jobs=args.parallel_jobs,
        auto_select=args.auto_select,
        n_portfolio_stocks=args.n_portfolio_stocks,
        weight_method=args.weight_method,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        min_weight=args.min_weight,
        max_weight=args.max_weight,
        verbose=args.verbose
    )
    
    # 处理步骤参数
    if args.steps:
        selected_steps = parse_steps(args.steps)
        if selected_steps:
            config.run_finscreener = 'finscreener' in selected_steps
            config.run_all_parallel = 'all_parallel' in selected_steps
            config.run_optimization = 'optimization' in selected_steps
            config.run_portfolio = 'portfolio' in selected_steps
            config.run_trading = 'trading' in selected_steps
    
    # 特殊处理：测试模式
    if args.test_only:
        print(f"🧪 测试模式: 仅测试连接，不执行实际操作")
        # 这里可以添加测试专用的逻辑
    
    # 显示配置摘要
    if args.verbose or args.mode:
        print(f"\n📋 运行配置摘要:")
        print(f"   实验名称: {config.experiment_name}")
        print(f"   运行步骤: {get_enabled_steps(config)}")
        print(f"   股票数量: {config.max_stocks}")
        print(f"   优化次数: {config.n_calls}")
        print(f"   更新模式: {config.update_mode}")
        print(f"   投资组合: {config.n_portfolio_stocks}只股票，{config.weight_method}权重")
    
    # 确保logs目录存在
    os.makedirs('logs', exist_ok=True)
    
    # 创建并运行流水线
    pipeline = HLM5Pipeline(config)
    
    # 直接运行，任何错误都会导致程序停止
    results = pipeline.run_pipeline()
    
    # 最终状态检查
    summary = pipeline._generate_summary()
    if summary['failed_steps'] == 0:
        print("\n🎉 流水线执行完全成功!")
        return 0
    elif summary['completed_steps'] > 0:
        print(f"\n⚠️ 流水线部分成功: {summary['completed_steps']}/{summary['total_steps']} 步骤完成")
        return 0
    else:
        print("\n❌ 流水线执行失败")
        return 1

def get_enabled_steps(config):
    """获取启用的步骤列表"""
    steps = []
    if config.run_finscreener:
        steps.append("1.筛选")
    if config.run_all_parallel:
        steps.append("2.指标")
    if config.run_optimization:
        steps.append("3.优化")
    if config.run_portfolio:
        steps.append("4.组合")
    if config.run_trading:
        steps.append("5.交易")
    return ", ".join(steps) if steps else "无"

if __name__ == "__main__":
    exit(main()) 