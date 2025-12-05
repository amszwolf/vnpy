# -*- coding: utf-8 -*-
"""
回测结果自动保存集成模块
用于集成到 hlm5_all_parallel.py
"""

import sys
import pickle
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from data.backtest_database_manager import BacktestDatabaseManager


def train_and_serialize_prophet_model(db_path, ticker, start_date, end_date):
    """
    训练Prophet模型并序列化
    
    Parameters:
    -----------
    db_path : str
        数据库路径
    ticker : str
        合约代码
    start_date : str
        开始日期
    end_date : str
        结束日期
    
    Returns:
    --------
    model_bytes : bytes or None
        序列化的模型数据
    prophet_params : dict
        Prophet配置参数
    """
    import sqlite3
    import pandas as pd
    
    # 检查Prophet是否可用
    prophet_available = False
    prophet_model = None
    prophet_params = {
        'periods': 20,
        'daily_seasonality': False,
        'weekly_seasonality': True,
        'yearly_seasonality': True,
        'changepoint_prior_scale': 0.05,
        'enabled': False
    }
    
    try:
        from prophet import Prophet
        prophet_available = True
    except ImportError:
        print("  ⚠ Prophet未安装，跳过模型训练")
        return None, prophet_params
    
    # 从数据库获取close价格数据
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT datetime, close
        FROM trading_data
        WHERE ticker = '{ticker}'
          AND datetime >= '{start_date}'
          AND datetime <= '{end_date}'
          AND close IS NOT NULL
        ORDER BY datetime
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if len(df) < 100:
        print(f"  ⚠ 数据不足({len(df)}条)，跳过Prophet训练")
        return None, prophet_params
    
    # 准备Prophet训练数据
    df['datetime'] = pd.to_datetime(df['datetime'])
    train_df = df[['datetime', 'close']].copy()
    train_df.columns = ['ds', 'y']
    
    print(f"  正在训练Prophet模型... (数据量: {len(train_df)})")
    
    # 训练模型
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05
    )
    model.fit(train_df)
    
    # 序列化模型
    model_bytes = pickle.dumps(model)
    
    prophet_params['enabled'] = True
    prophet_params['training_samples'] = len(train_df)
    prophet_params['training_date_range'] = f"{train_df['ds'].min()} ~ {train_df['ds'].max()}"
    
    print(f"  ✓ Prophet模型训练完成")
    print(f"    训练样本: {len(train_df)}")
    print(f"    模型大小: {len(model_bytes)/1024:.2f} KB")
    
    return model_bytes, prophet_params


def save_backtest_results_auto(
    ticker, 
    db_path, 
    start_date, 
    end_date,
    auto_promote=True,
    sharpe_threshold=2.0,
    save_prophet_model=True
):
    """
    自动保存回测结果到数据库
    
    这个函数在 process_ticker 完成后调用
    
    Parameters:
    -----------
    ticker : str
        合约代码
    db_path : str
        数据库路径
    start_date : str
        开始日期
    end_date : str  
        结束日期
    auto_promote : bool
        是否自动提升为最优策略
    sharpe_threshold : float
        自动提升的夏普比率阈值
    
    Returns:
    --------
    result : dict
        保存结果
    """
    import sqlite3
    import pandas as pd
    import numpy as np
    
    print(f"\n{'='*60}")
    print(f"自动保存回测结果: {ticker}")
    print(f"{'='*60}")
    
    # 生成策略ID
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    strategy_id = f"hlm5_{ticker.replace('.', '_')}_bt_{timestamp}"
    
    # 1. 从trading_data提取交易记录
    print(f"\n[1/3] 提取交易记录...")
    conn = sqlite3.connect(db_path)
    
    query = f"""
        SELECT 
            datetime,
            Entry_Price,
            Exit_Price,
            Profit_Loss,
            Position
        FROM trading_data
        WHERE ticker = '{ticker}'
          AND datetime >= '{start_date}'
          AND datetime <= '{end_date}'
          AND Profit_Loss IS NOT NULL
          AND Profit_Loss != 0
        ORDER BY datetime
    """
    
    trades_df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"  ✓ 提取了 {len(trades_df)} 笔交易")
    
    if len(trades_df) == 0:
        print("  ⚠ 没有交易记录，跳过保存")
        return {
            'success': False,
            'reason': 'no_trades',
            'strategy_id': None
        }
    
    # 2. 计算性能指标
    print(f"\n[2/3] 计算性能指标...")
    
    total_trades = len(trades_df)
    total_pnl = trades_df['Profit_Loss'].sum()
    wins = trades_df[trades_df['Profit_Loss'] > 0]
    losses = trades_df[trades_df['Profit_Loss'] < 0]
    
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    
    # 盈亏比
    total_win = wins['Profit_Loss'].sum() if len(wins) > 0 else 0.0
    total_loss = abs(losses['Profit_Loss'].sum()) if len(losses) > 0 else 0.0
    profit_factor = total_win / total_loss if total_loss > 0 else 0.0
    
    # 收益率
    initial_capital = 100000
    total_return = total_pnl / initial_capital
    annual_return = total_return * 4  # 假设3个月
    
    # 夏普比率
    if len(trades_df) > 1:
        returns = trades_df['Profit_Loss'] / initial_capital
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0
    else:
        sharpe_ratio = 0.0
    
    # 最大回撤
    cumulative_pnl = trades_df['Profit_Loss'].cumsum()
    running_max = cumulative_pnl.expanding().max()
    drawdown = (cumulative_pnl - running_max) / initial_capital
    max_drawdown = drawdown.min() if len(drawdown) > 0 else 0.0
    
    performance = {
        'total_return': float(total_return),
        'annual_return': float(annual_return),
        'sharpe_ratio': float(sharpe_ratio),
        'max_drawdown': float(max_drawdown),
        'win_rate': float(win_rate),
        'total_trades': int(total_trades),
        'avg_holding_period': 120.0,  # 默认值
        'profit_factor': float(profit_factor)
    }
    
    print(f"  性能指标:")
    print(f"    - 夏普比率: {performance['sharpe_ratio']:.2f}")
    print(f"    - 年化收益: {performance['annual_return']*100:.2f}%")
    print(f"    - 最大回撤: {performance['max_drawdown']*100:.2f}%")
    print(f"    - 胜率: {performance['win_rate']*100:.2f}%")
    print(f"    - 总交易: {performance['total_trades']}")
    
    # 3. 训练和保存Prophet模型
    print(f"\n[3/4] 训练Prophet模型...")
    
    prophet_model_bytes = None
    prophet_params = {'periods': 20, 'enabled': False}
    
    if save_prophet_model:
        prophet_model_bytes, prophet_params = train_and_serialize_prophet_model(
            db_path, ticker, start_date, end_date
        )
    else:
        print("  ⚠ Prophet模型保存已禁用")
    
    # 4. 保存到数据库
    print(f"\n[4/4] 保存到数据库...")
    
    strategy_config = {
        'strategy_id': strategy_id,
        'ticker': ticker,
        'strategy_name': 'HLM5',
        'version': '1.2',
        'start_date': start_date,
        'end_date': end_date,
        'indicators': {
            'price_macd': {'macd_long': 20, 'macd_mid': 8, 'macd_short': 5, 'enabled': True},
            'volume_macd': {'macd_long': 20, 'macd_mid': 8, 'macd_short': 5, 'enabled': True},
            'hlbw': {'lookback_period': 40, 'enabled': True},
            'prophet': prophet_params
        },
        'trading': {
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.09,
            'fixed_size': 1,
            'slippage': 2.5
        },
        'comments': f'自动保存于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    }
    
    # Prophet模型单独传递（不放入JSON）
    if prophet_model_bytes:
        strategy_config['_prophet_model_bytes'] = prophet_model_bytes
    
    # 使用绝对路径
    db_manager = BacktestDatabaseManager(str(Path(db_path).resolve()))
    db_manager.save_backtest_summary(strategy_config, performance)
    
    # 自动提升
    promoted = False
    if auto_promote and performance['sharpe_ratio'] >= sharpe_threshold:
        print(f"\n  夏普比率 {performance['sharpe_ratio']:.2f} >= {sharpe_threshold}，自动提升...")
        db_manager.promote_to_optimal(strategy_id, f'自动提升：夏普 {performance["sharpe_ratio"]:.2f}')
        
        # 导出配置
        output_dir = Path(db_path).parent / 'configs' / 'strategies'
        output_path = output_dir / f'{strategy_id}.json'
        db_manager.export_strategy_to_json(strategy_id, str(output_path))
        promoted = True
    
    db_manager.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 自动保存完成")
    print(f"{'='*60}")
    
    return {
        'success': True,
        'strategy_id': strategy_id,
        'sharpe_ratio': performance['sharpe_ratio'],
        'annual_return': performance['annual_return'],
        'total_trades': performance['total_trades'],
        'promoted': promoted
    }


# 用于集成到 hlm5_all_parallel.py 的包装函数
def process_ticker_with_auto_save(
    ticker, db_path, my_raw_db, my_raw_table, 
    start_date, end_date, forecast_days, verbose, 
    config=None, scaling_strategy_name='aggressive_pyramid',
    auto_save=True, auto_promote=True, sharpe_threshold=2.0
):
    """
    包装原有的 process_ticker 函数，增加自动保存功能
    
    这个函数可以直接替换 hlm5_all_parallel.py 中的 process_ticker 调用
    
    Parameters:
    -----------
    ... (与原 process_ticker 相同)
    auto_save : bool
        是否自动保存回测结果
    auto_promote : bool
        是否自动提升为最优策略
    sharpe_threshold : float
        自动提升的夏普比率阈值
    
    Returns:
    --------
    result : dict
        包含回测结果和保存结果
    """
    from hlm5_all_parallel import process_ticker
    
    # 调用原有的 process_ticker
    result = process_ticker(
        ticker, db_path, my_raw_db, my_raw_table,
        start_date, end_date, forecast_days, verbose,
        config, scaling_strategy_name
    )
    
    # 如果成功且启用自动保存
    if result.get('status') == 'success' and auto_save:
        save_result = save_backtest_results_auto(
            ticker, db_path, start_date, end_date,
            auto_promote, sharpe_threshold
        )
        
        # 合并结果
        result['auto_save'] = save_result
    
    return result


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试回测集成模块")
    print("=" * 60)
    
    # 使用现有的测试数据
    result = save_backtest_results_auto(
        ticker='OI.ZCE',
        db_path='trading_signals.db',
        start_date='2024-10-01',
        end_date='2025-01-31',
        auto_promote=True,
        sharpe_threshold=2.0
    )
    
    print(f"\n测试结果:")
    print(f"  成功: {result['success']}")
    if result['success']:
        print(f"  策略ID: {result['strategy_id']}")
        print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
        print(f"  年化收益: {result['annual_return']*100:.2f}%")
        print(f"  总交易: {result['total_trades']}")
        print(f"  已提升: {result['promoted']}")

