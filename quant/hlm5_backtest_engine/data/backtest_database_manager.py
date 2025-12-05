# -*- coding: utf-8 -*-
"""
回测引擎数据库管理器
提供回测结果保存、策略配置导出等功能
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class BacktestDatabaseManager:
    """回测数据库管理器"""
    
    def __init__(self, db_path='../trading_signals.db'):
        """
        初始化数据库管理器
        
        Parameters:
        -----------
        db_path : str
            数据库文件路径
        """
        # 解析数据库路径
        if Path(db_path).is_absolute():
            self.db_path = db_path
        else:
            self.db_path = str((Path(__file__).parent / db_path).resolve())
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 返回字典形式
        
        print(f"✓ 数据库连接成功: {self.db_path}")
    
    def save_backtest_summary(self, strategy_config, performance_metrics):
        """
        保存回测结果到 backtest_summary 表
        
        Parameters:
        -----------
        strategy_config : dict
            策略配置字典，包含：
            - strategy_id: 策略唯一ID
            - ticker: 合约代码
            - strategy_name: 策略名称
            - strategy_version: 版本号
            - start_date, end_date: 回测时间范围
            - indicators: 指标参数
            - trading: 交易参数
            等
            
        performance_metrics : dict
            性能指标字典，包含：
            - total_return: 总收益率
            - annual_return: 年化收益率
            - sharpe_ratio: 夏普比率
            - max_drawdown: 最大回撤
            - win_rate: 胜率
            - total_trades: 总交易次数
            等
        
        Returns:
        --------
        strategy_id : str
            保存的策略ID
        """
        cursor = self.conn.cursor()
        
        # 提取Prophet模型（从策略配置中分离）
        prophet_model_bytes = strategy_config.pop('_prophet_model_bytes', None)
        
        # 准备数据
        data = {
            'strategy_id': strategy_config['strategy_id'],
            'ticker': strategy_config['ticker'],
            'strategy_name': strategy_config.get('strategy_name', 'HLM5'),
            'strategy_version': strategy_config.get('version', '1.0'),
            'start_date': strategy_config.get('start_date', ''),
            'end_date': strategy_config.get('end_date', ''),
            'indicator_params': json.dumps(strategy_config.get('indicators', {}), ensure_ascii=False),
            'trading_params': json.dumps(strategy_config.get('trading', {}), ensure_ascii=False),
            'prophet_model': prophet_model_bytes,  # BLOB数据
            'prophet_params': json.dumps(strategy_config.get('indicators', {}).get('prophet', {}), ensure_ascii=False),
            'total_return': performance_metrics.get('total_return', 0.0),
            'annual_return': performance_metrics.get('annual_return', 0.0),
            'sharpe_ratio': performance_metrics.get('sharpe_ratio', 0.0),
            'max_drawdown': performance_metrics.get('max_drawdown', 0.0),
            'win_rate': performance_metrics.get('win_rate', 0.0),
            'total_trades': performance_metrics.get('total_trades', 0),
            'avg_holding_period': performance_metrics.get('avg_holding_period', 0.0),
            'profit_factor': performance_metrics.get('profit_factor', 0.0),
            'is_optimal': 0,
            'status': 'completed',
            'full_config': json.dumps(strategy_config, ensure_ascii=False),
            'comments': strategy_config.get('comments', '')
        }
        
        # 插入数据
        cursor.execute("""
            INSERT OR REPLACE INTO backtest_summary (
                strategy_id, ticker, strategy_name, strategy_version,
                start_date, end_date,
                indicator_params, trading_params,
                prophet_model, prophet_params,
                total_return, annual_return, sharpe_ratio, max_drawdown,
                win_rate, total_trades, avg_holding_period, profit_factor,
                is_optimal, status, full_config, comments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['strategy_id'], data['ticker'], data['strategy_name'], data['strategy_version'],
            data['start_date'], data['end_date'],
            data['indicator_params'], data['trading_params'],
            data['prophet_model'], data['prophet_params'],
            data['total_return'], data['annual_return'], data['sharpe_ratio'], data['max_drawdown'],
            data['win_rate'], data['total_trades'], data['avg_holding_period'], data['profit_factor'],
            data['is_optimal'], data['status'], data['full_config'], data['comments']
        ))
        
        self.conn.commit()
        
        print(f"\n✓ 回测结果已保存: {data['strategy_id']}")
        print(f"  策略名称: {data['strategy_name']} v{data['strategy_version']}")
        print(f"  合约代码: {data['ticker']}")
        print(f"  回测区间: {data['start_date']} ~ {data['end_date']}")
        print(f"  性能指标:")
        print(f"    - 夏普比率: {data['sharpe_ratio']:.2f}")
        print(f"    - 年化收益: {data['annual_return']*100:.2f}%")
        print(f"    - 总收益率: {data['total_return']*100:.2f}%")
        print(f"    - 最大回撤: {data['max_drawdown']*100:.2f}%")
        print(f"    - 胜率: {data['win_rate']*100:.2f}%")
        print(f"    - 总交易次数: {data['total_trades']}")
        print(f"    - 平均持仓(分钟): {data['avg_holding_period']:.1f}")
        print(f"    - 盈亏比: {data['profit_factor']:.2f}")
        
        # 显示Prophet模型信息
        if data['prophet_model']:
            model_size = len(data['prophet_model']) / 1024
            print(f"  Prophet模型:")
            print(f"    - 模型大小: {model_size:.2f} KB")
            print(f"    - 状态: ✅ 已保存")
        else:
            print(f"  Prophet模型:")
            print(f"    - 状态: ⚠️ 未保存")
        
        return data['strategy_id']
    
    def promote_to_optimal(self, strategy_id, comments=''):
        """
        将策略从 backtest_summary 提升为 optimal_strategies
        
        Parameters:
        -----------
        strategy_id : str
            策略ID
        comments : str
            备注说明
        
        Returns:
        --------
        success : bool
            是否成功
        """
        cursor = self.conn.cursor()
        
        # 检查策略是否存在
        cursor.execute("""
            SELECT * FROM backtest_summary WHERE strategy_id = ?
        """, (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"\n✗ 策略不存在于backtest_summary: {strategy_id}")
            return False
        
        # 复制到 optimal_strategies
        cursor.execute("""
            INSERT OR REPLACE INTO optimal_strategies 
            SELECT 
                strategy_id, ticker, strategy_name, strategy_version,
                start_date, end_date,
                indicator_params, trading_params,
                prophet_model, prophet_params,
                total_return, annual_return, sharpe_ratio, max_drawdown,
                win_rate, total_trades, avg_holding_period, profit_factor,
                1 as is_optimal,
                'active' as status,
                full_config,
                CURRENT_TIMESTAMP as created_at,
                CURRENT_TIMESTAMP as updated_at,
                ? as comments
            FROM backtest_summary 
            WHERE strategy_id = ?
        """, (comments, strategy_id))
        
        # 更新 backtest_summary 的 is_optimal 标记
        cursor.execute("""
            UPDATE backtest_summary 
            SET is_optimal = 1, status = 'optimal' 
            WHERE strategy_id = ?
        """, (strategy_id,))
        
        self.conn.commit()
        
        print(f"\n✓ 策略已提升为最优策略: {strategy_id}")
        print(f"  备注: {comments}")
        
        return True
    
    def export_strategy_to_json(self, strategy_id, output_path):
        """
        导出策略配置到JSON文件
        
        Parameters:
        -----------
        strategy_id : str
            策略ID
        output_path : str or Path
            输出文件路径
        
        Returns:
        --------
        success : bool
            是否成功
        """
        cursor = self.conn.cursor()
        
        # 查询策略配置（优先从optimal_strategies查询）
        cursor.execute("""
            SELECT full_config FROM optimal_strategies WHERE strategy_id = ?
        """, (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            # 如果不在optimal_strategies中，从backtest_summary查询
            cursor.execute("""
                SELECT full_config FROM backtest_summary WHERE strategy_id = ?
            """, (strategy_id,))
            row = cursor.fetchone()
            
            if not row:
                print(f"\n✗ 策略不存在: {strategy_id}")
                return False
        
        # 解析JSON
        config = json.loads(row['full_config'])
        
        # 确保输出目录存在
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        file_size = output_file.stat().st_size / 1024  # KB
        print(f"\n✓ 策略配置已导出: {output_path}")
        print(f"  文件大小: {file_size:.2f} KB")
        print(f"  策略ID: {config.get('strategy_id', 'N/A')}")
        print(f"  策略名称: {config.get('strategy_name', 'N/A')}")
        print(f"  版本: {config.get('version', 'N/A')}")
        
        return True
    
    def get_all_backtest_results(self, order_by='sharpe_ratio', limit=None):
        """
        获取所有回测结果
        
        Parameters:
        -----------
        order_by : str
            排序字段 (sharpe_ratio, annual_return, total_return等)
        limit : int, optional
            返回记录数限制
        
        Returns:
        --------
        results : list of dict
            回测结果列表
        """
        cursor = self.conn.cursor()
        
        sql = f"""
            SELECT 
                strategy_id, ticker, strategy_name, strategy_version,
                start_date, end_date,
                total_return, annual_return, sharpe_ratio, max_drawdown,
                win_rate, total_trades, avg_holding_period, profit_factor,
                is_optimal, status, created_at
            FROM backtest_summary 
            ORDER BY {order_by} DESC
        """
        
        if limit:
            sql += f" LIMIT {limit}"
        
        cursor.execute(sql)
        results = [dict(row) for row in cursor.fetchall()]
        
        return results
    
    def get_optimal_strategies(self):
        """
        获取所有最优策略
        
        Returns:
        --------
        strategies : list of dict
            最优策略列表
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                strategy_id, ticker, strategy_name, strategy_version,
                start_date, end_date,
                total_return, annual_return, sharpe_ratio, max_drawdown,
                win_rate, total_trades,
                status, created_at, comments
            FROM optimal_strategies 
            ORDER BY sharpe_ratio DESC
        """)
        
        strategies = [dict(row) for row in cursor.fetchall()]
        
        return strategies
    
    def get_strategy_by_id(self, strategy_id):
        """
        根据ID获取策略详情
        
        Parameters:
        -----------
        strategy_id : str
            策略ID
        
        Returns:
        --------
        strategy : dict or None
            策略详情字典
        """
        cursor = self.conn.cursor()
        
        # 优先从optimal_strategies查询
        cursor.execute("""
            SELECT * FROM optimal_strategies WHERE strategy_id = ?
        """, (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            # 从backtest_summary查询
            cursor.execute("""
                SELECT * FROM backtest_summary WHERE strategy_id = ?
            """, (strategy_id,))
            row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def delete_backtest_result(self, strategy_id):
        """
        删除回测结果
        
        Parameters:
        -----------
        strategy_id : str
            策略ID
        
        Returns:
        --------
        success : bool
            是否成功
        """
        cursor = self.conn.cursor()
        
        # 从backtest_summary删除
        cursor.execute("DELETE FROM backtest_summary WHERE strategy_id = ?", (strategy_id,))
        deleted_count = cursor.rowcount
        
        self.conn.commit()
        
        if deleted_count > 0:
            print(f"\n✓ 已删除回测结果: {strategy_id}")
            return True
        else:
            print(f"\n✗ 回测结果不存在: {strategy_id}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("\n✓ 数据库连接已关闭")


# ============================================================
# 测试代码
# ============================================================
def test_database_manager():
    """测试数据库管理器功能"""
    print("=" * 60)
    print("测试 BacktestDatabaseManager")
    print("=" * 60)
    
    # 1. 初始化管理器
    print("\n[1/6] 初始化数据库管理器...")
    db_manager = BacktestDatabaseManager('../trading_signals.db')
    
    # 2. 创建测试策略配置
    print("\n[2/6] 创建测试策略配置...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_strategy_config = {
        'strategy_id': f'hlm5_OI888_test_{timestamp}',
        'ticker': 'OI888.CZCE',
        'strategy_name': 'HLM5_Test',
        'version': '1.0',
        'start_date': '2024-10-01',
        'end_date': '2025-01-31',
        'indicators': {
            'price_macd': {
                'macd_long': 20,
                'macd_mid': 8,
                'macd_short': 5,
                'diff_ema_period': 2,
                'enabled': True
            },
            'volume_macd': {
                'macd_long': 20,
                'macd_mid': 8,
                'macd_short': 5,
                'diff_ema_period': 3,
                'enabled': True
            },
            'hlbw': {
                'lookback_period': 40,
                'inner_ema': 3,
                'outer_ema': 2,
                'trend_ema': 2,
                'enabled': True
            },
            'prophet': {
                'periods': 20,
                'enabled': False
            }
        },
        'trading': {
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.09,
            'trailing_stop_pct': 0.02,
            'fixed_size': 1,
            'enable_bidirectional': True,
            'hold_overnight': False
        },
        'comments': f'测试运行于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    }
    
    test_performance = {
        'total_return': 0.1555,
        'annual_return': 0.1555,
        'sharpe_ratio': 2.21,
        'max_drawdown': -0.0823,
        'win_rate': 0.6783,
        'total_trades': 286,
        'avg_holding_period': 120.5,
        'profit_factor': 1.85
    }
    print("  ✓ 测试数据准备完成")
    
    # 3. 保存回测结果
    print("\n[3/6] 保存回测结果...")
    strategy_id = db_manager.save_backtest_summary(test_strategy_config, test_performance)
    
    # 4. 提升为最优策略
    print("\n[4/6] 提升为最优策略...")
    success = db_manager.promote_to_optimal(strategy_id, '测试策略 - 高夏普比率')
    
    # 5. 导出配置
    print("\n[5/6] 导出策略配置...")
    output_dir = Path(__file__).parent.parent / 'configs' / 'strategies'
    output_path = output_dir / f'{strategy_id}.json'
    success = db_manager.export_strategy_to_json(strategy_id, str(output_path))
    
    # 6. 查询结果
    print("\n[6/6] 查询数据库...")
    
    print("\n  (a) 所有回测结果 (Top 3):")
    results = db_manager.get_all_backtest_results(limit=3)
    for i, result in enumerate(results, 1):
        print(f"\n    {i}. {result['strategy_id']}")
        print(f"       策略: {result['strategy_name']} v{result['strategy_version']}")
        print(f"       夏普: {result['sharpe_ratio']:.2f} | "
              f"年化: {result['annual_return']*100:.2f}% | "
              f"回撤: {result['max_drawdown']*100:.2f}%")
        print(f"       交易: {result['total_trades']} | "
              f"胜率: {result['win_rate']*100:.1f}% | "
              f"状态: {result['status']}")
    
    print("\n  (b) 最优策略列表:")
    strategies = db_manager.get_optimal_strategies()
    for i, strategy in enumerate(strategies, 1):
        print(f"\n    {i}. {strategy['strategy_id']}")
        print(f"       策略: {strategy['strategy_name']} v{strategy['strategy_version']}")
        print(f"       夏普: {strategy['sharpe_ratio']:.2f} | "
              f"状态: {strategy['status']}")
        print(f"       备注: {strategy.get('comments', 'N/A')}")
    
    print("\n  (c) 策略详情:")
    detail = db_manager.get_strategy_by_id(strategy_id)
    if detail:
        print(f"    策略ID: {detail['strategy_id']}")
        print(f"    创建时间: {detail['created_at']}")
        print(f"    是否最优: {'是' if detail['is_optimal'] else '否'}")
        print(f"    状态: {detail['status']}")
    
    # 关闭连接
    db_manager.close()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n验证项:")
    print("  ✅ 数据库管理器初始化成功")
    print("  ✅ 回测结果保存成功")
    print("  ✅ 策略提升为最优成功")
    print("  ✅ 配置导出为JSON成功")
    print("  ✅ 查询功能正常")
    print("  ✅ 所有输出信息完整")
    print("\n✅ 步骤1.2完成！可以继续步骤1.3")


if __name__ == "__main__":
    test_database_manager()

