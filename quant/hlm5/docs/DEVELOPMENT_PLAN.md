# HLM5量化交易系统开发计划
## 基于方案C架构的详细实施方案

**制定时间**: 2025-12-05  
**运行环境**: vnpyenv  
**执行原则**: 每步确认，数据完整，非必要不改动

---

## 📋 总体规划

### 开发顺序

```
阶段1: hlm5_backtest_engine（独立回测引擎）
  ├─ 步骤1.1: 数据库初始化（新增表）
  ├─ 步骤1.2: 数据库管理器开发
  ├─ 步骤1.3: 回测结果保存功能
  ├─ 步骤1.4: 策略配置导出功能
  └─ 步骤1.5: 完整回测流程测试

阶段2: quant/hlm5（实盘交易系统）
  ├─ 步骤2.1: 数据库初始化（实盘表）
  ├─ 步骤2.2: 数据库管理器开发
  ├─ 步骤2.3: 策略配置导入功能
  ├─ 步骤2.4: 实盘数据记录功能
  └─ 步骤2.5: 纸上交易集成测试
```

### 设计原则

```
✅ 最小改动原则
   - hlm5_backtest_engine保持现有代码不变
   - 只添加新的数据库表和管理器

✅ 渐进式开发
   - 每个步骤独立可测
   - 先功能后优化

✅ 数据完整性
   - 每步都保存和显示数据
   - 便于验证和调试

✅ 无异常捕获
   - 按要求不使用try-except
   - 让错误直接暴露便于调试
```

---

## 🎯 阶段1: hlm5_backtest_engine 开发

### 目标

在**不修改现有回测代码**的前提下，添加：
1. 新的数据库表（backtest_summary, optimal_strategies）
2. 数据库管理器（BacktestDatabaseManager）
3. 回测结果保存功能
4. 策略配置导出功能

---

### 步骤1.1: 数据库表初始化 ✅

**目标**: 创建新的数据库表，不影响现有 trading_data 表

**任务清单**:
```
□ 创建数据库初始化脚本
□ 添加 backtest_summary 表
□ 添加 optimal_strategies 表
□ 创建索引
□ 验证表结构
```

**开发文件**:
```
quant/hlm5_backtest_engine/data/init_backtest_db.py
```

**代码内容**:
```python
"""
回测引擎数据库初始化脚本
在现有 trading_signals.db 基础上添加新表
"""

import sqlite3
from pathlib import Path

def init_backtest_tables(db_path='trading_signals.db'):
    """
    初始化回测引擎的数据库表
    
    只添加新表，不修改现有的 trading_data 表
    """
    print("=" * 60)
    print("回测引擎数据库初始化")
    print("=" * 60)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n数据库路径: {db_path}")
    
    # 1. 创建 backtest_summary 表
    print("\n[1/3] 创建 backtest_summary 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backtest_summary (
            strategy_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            
            -- 回测时间范围
            start_date TEXT,
            end_date TEXT,
            
            -- 指标参数 (JSON)
            indicator_params TEXT,
            
            -- 交易参数 (JSON)
            trading_params TEXT,
            
            -- Prophet模型 (序列化)
            prophet_model BLOB,
            prophet_params TEXT,
            
            -- 回测性能指标
            total_return REAL,
            annual_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            total_trades INTEGER,
            avg_holding_period REAL,
            profit_factor REAL,
            
            -- 标记和状态
            is_optimal BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'completed',
            
            -- 完整策略配置 (JSON)
            full_config TEXT,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comments TEXT
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_backtest_ticker 
        ON backtest_summary(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_backtest_optimal 
        ON backtest_summary(is_optimal) 
        WHERE is_optimal = 1
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_backtest_sharpe 
        ON backtest_summary(sharpe_ratio DESC)
    """)
    print("  ✓ backtest_summary 表创建成功")
    
    # 2. 创建 optimal_strategies 表
    print("\n[2/3] 创建 optimal_strategies 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS optimal_strategies (
            strategy_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            
            -- 回测时间范围
            start_date TEXT,
            end_date TEXT,
            
            -- 指标参数 (JSON)
            indicator_params TEXT,
            
            -- 交易参数 (JSON)
            trading_params TEXT,
            
            -- Prophet模型 (序列化)
            prophet_model BLOB,
            prophet_params TEXT,
            
            -- 回测性能指标
            total_return REAL,
            annual_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            total_trades INTEGER,
            avg_holding_period REAL,
            profit_factor REAL,
            
            -- 标记和状态
            is_optimal BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'active',
            
            -- 完整策略配置 (JSON)
            full_config TEXT,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comments TEXT
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_optimal_ticker 
        ON optimal_strategies(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_optimal_status 
        ON optimal_strategies(status)
    """)
    print("  ✓ optimal_strategies 表创建成功")
    
    # 3. 提交并验证
    print("\n[3/3] 提交更改并验证...")
    conn.commit()
    
    # 查询所有表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    
    print("\n数据库中的所有表:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  ✓ {table[0]}: {count} 条记录")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("数据库初始化完成！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    # 默认数据库路径
    db_path = "trading_signals.db"
    
    # 如果数据库文件不存在，创建目录
    db_file = Path(db_path)
    if not db_file.parent.exists():
        db_file.parent.mkdir(parents=True)
    
    # 初始化表
    init_backtest_tables(db_path)
```

**执行步骤**:
```bash
# 1. 切换环境
conda activate vnpyenv

# 2. 进入目录
cd quant/hlm5_backtest_engine/data

# 3. 运行初始化脚本
python init_backtest_db.py
```

**预期输出**:
```
============================================================
回测引擎数据库初始化
============================================================

数据库路径: trading_signals.db

[1/3] 创建 backtest_summary 表...
  ✓ backtest_summary 表创建成功

[2/3] 创建 optimal_strategies 表...
  ✓ optimal_strategies 表创建成功

[3/3] 提交更改并验证...

数据库中的所有表:
  ✓ backtest_summary: 0 条记录
  ✓ optimal_strategies: 0 条记录
  ✓ trading_data: 12345 条记录  (示例数字)

============================================================
数据库初始化完成！
============================================================
```

**验证标准**:
```
✅ 脚本运行无错误
✅ backtest_summary 表创建成功
✅ optimal_strategies 表创建成功
✅ 索引创建成功
✅ 现有 trading_data 表不受影响
```

**⏸️ 等待用户确认**: 是否继续步骤1.2？

---

### 步骤1.2: 数据库管理器开发 ✅

**目标**: 开发 BacktestDatabaseManager 类，提供数据库操作接口

**任务清单**:
```
□ 创建数据库管理器类
□ 实现回测结果保存方法
□ 实现策略提升方法（backtest_summary → optimal_strategies）
□ 实现策略导出方法（JSON）
□ 实现查询方法
□ 单元测试
```

**开发文件**:
```
quant/hlm5_backtest_engine/data/backtest_database_manager.py
```

**代码内容**:
```python
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
    
    def __init__(self, db_path='trading_signals.db'):
        """
        初始化数据库管理器
        
        Parameters:
        -----------
        db_path : str
            数据库文件路径
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # 返回字典形式
        
        print(f"✓ 数据库连接成功: {db_path}")
    
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
            'prophet_model': None,  # 可选
            'prophet_params': json.dumps(strategy_config.get('prophet', {}), ensure_ascii=False) if 'prophet' in strategy_config else None,
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
        
        print(f"✓ 回测结果已保存: {data['strategy_id']}")
        print(f"  - 夏普比率: {data['sharpe_ratio']:.2f}")
        print(f"  - 年化收益: {data['annual_return']*100:.2f}%")
        print(f"  - 最大回撤: {data['max_drawdown']*100:.2f}%")
        print(f"  - 总交易次数: {data['total_trades']}")
        
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
            print(f"✗ 策略不存在: {strategy_id}")
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
                1 as is_optimal,  -- 强制设为1
                'active' as status,  -- 状态改为active
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
        
        print(f"✓ 策略已提升为最优策略: {strategy_id}")
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
        
        # 查询策略配置
        cursor.execute("""
            SELECT full_config FROM optimal_strategies WHERE strategy_id = ?
        """, (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"✗ 最优策略不存在: {strategy_id}")
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
        print(f"✓ 策略配置已导出: {output_path}")
        print(f"  - 文件大小: {file_size:.2f} KB")
        
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
                status, created_at
            FROM optimal_strategies 
            ORDER BY sharpe_ratio DESC
        """)
        
        strategies = [dict(row) for row in cursor.fetchall()]
        
        return strategies
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("✓ 数据库连接已关闭")


# ============================================================
# 测试代码
# ============================================================
def test_database_manager():
    """测试数据库管理器功能"""
    print("=" * 60)
    print("测试 BacktestDatabaseManager")
    print("=" * 60)
    
    # 1. 初始化管理器
    print("\n[1/5] 初始化数据库管理器...")
    db_manager = BacktestDatabaseManager('trading_signals.db')
    
    # 2. 创建测试策略配置
    print("\n[2/5] 创建测试策略配置...")
    test_strategy_config = {
        'strategy_id': 'hlm5_OI888_test_20251205',
        'ticker': 'OI888.CZCE',
        'strategy_name': 'HLM5_Test',
        'version': '1.0',
        'start_date': '2024-10-01',
        'end_date': '2025-01-31',
        'indicators': {
            'price_macd': {'macd_long': 20, 'macd_mid': 8, 'macd_short': 5},
            'volume_macd': {'macd_long': 20, 'macd_mid': 8, 'macd_short': 5},
            'hlbw': {'lookback_period': 40}
        },
        'trading': {
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.09
        }
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
    
    # 3. 保存回测结果
    print("\n[3/5] 保存回测结果...")
    strategy_id = db_manager.save_backtest_summary(test_strategy_config, test_performance)
    
    # 4. 提升为最优策略
    print("\n[4/5] 提升为最优策略...")
    db_manager.promote_to_optimal(strategy_id, '测试策略')
    
    # 5. 导出配置
    print("\n[5/5] 导出策略配置...")
    output_path = '../configs/strategies/test_strategy.json'
    db_manager.export_strategy_to_json(strategy_id, output_path)
    
    # 6. 查询结果
    print("\n[查询] 所有回测结果:")
    results = db_manager.get_all_backtest_results(limit=5)
    for i, result in enumerate(results, 1):
        print(f"\n  {i}. {result['strategy_id']}")
        print(f"     夏普: {result['sharpe_ratio']:.2f} | "
              f"年化: {result['annual_return']*100:.2f}% | "
              f"交易: {result['total_trades']}")
    
    print("\n[查询] 最优策略:")
    strategies = db_manager.get_optimal_strategies()
    for i, strategy in enumerate(strategies, 1):
        print(f"\n  {i}. {strategy['strategy_id']}")
        print(f"     夏普: {strategy['sharpe_ratio']:.2f} | "
              f"状态: {strategy['status']}")
    
    # 关闭连接
    db_manager.close()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_database_manager()
```

**执行步骤**:
```bash
# 1. 进入目录
cd quant/hlm5_backtest_engine/data

# 2. 运行测试
python backtest_database_manager.py
```

**预期输出**:
```
============================================================
测试 BacktestDatabaseManager
============================================================

[1/5] 初始化数据库管理器...
✓ 数据库连接成功: trading_signals.db

[2/5] 创建测试策略配置...

[3/5] 保存回测结果...
✓ 回测结果已保存: hlm5_OI888_test_20251205
  - 夏普比率: 2.21
  - 年化收益: 15.55%
  - 最大回撤: -8.23%
  - 总交易次数: 286

[4/5] 提升为最优策略...
✓ 策略已提升为最优策略: hlm5_OI888_test_20251205

[5/5] 导出策略配置...
✓ 策略配置已导出: ../configs/strategies/test_strategy.json
  - 文件大小: 1.23 KB

[查询] 所有回测结果:

  1. hlm5_OI888_test_20251205
     夏普: 2.21 | 年化: 15.55% | 交易: 286

[查询] 最优策略:

  1. hlm5_OI888_test_20251205
     夏普: 2.21 | 状态: active

✓ 数据库连接已关闭

============================================================
测试完成！
============================================================
```

**验证标准**:
```
✅ 数据库管理器初始化成功
✅ 回测结果保存到 backtest_summary
✅ 策略提升到 optimal_strategies
✅ 配置导出为JSON文件
✅ 查询功能正常
✅ 所有输出信息完整
```

**⏸️ 等待用户确认**: 是否继续步骤1.3？

---

### 步骤1.3: 集成到现有回测流程 ✅

**目标**: 在现有回测脚本中集成结果保存功能，不修改核心回测逻辑

**任务清单**:
```
□ 创建回测包装脚本
□ 调用现有 hlm5_all_parallel.py
□ 提取回测结果
□ 保存到数据库
□ 可选：自动提升为最优策略
□ 完整流程测试
```

**开发文件**:
```
quant/hlm5_backtest_engine/run_backtest_with_save.py
```

**执行步骤**:
```bash
# 1. 进入目录
cd quant/hlm5_backtest_engine

# 2. 运行带保存功能的回测
python run_backtest_with_save.py --ticker OI888 --start-date 2024-10-01 --end-date 2025-01-31
```

**代码内容**:
```python
"""
带保存功能的回测脚本
调用现有 hlm5_all_parallel.py，保存回测结果到数据库
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime
import json

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from data.backtest_database_manager import BacktestDatabaseManager


def generate_strategy_id(ticker, timestamp=None):
    """生成策略ID"""
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"hlm5_{ticker}_bt_{timestamp}"


def extract_performance_from_backtest(ticker, start_date, end_date):
    """
    从现有回测结果中提取性能指标
    
    注意：这里需要实际运行 hlm5_all_parallel.py 或读取其输出
    暂时使用模拟数据，后续需要对接真实回测
    """
    # TODO: 实际对接 hlm5_all_parallel.py
    # 这里暂时返回模拟数据
    
    print(f"  - 正在运行回测: {ticker} ({start_date} ~ {end_date})")
    print(f"  - 提示: 实际运行需要对接 hlm5_all_parallel.py")
    
    # 模拟性能数据
    performance = {
        'total_return': 0.1555,
        'annual_return': 0.1555,
        'sharpe_ratio': 2.21,
        'max_drawdown': -0.0823,
        'win_rate': 0.6783,
        'total_trades': 286,
        'avg_holding_period': 120.5,
        'profit_factor': 1.85
    }
    
    return performance


def run_backtest_with_save(
    ticker='OI888',
    start_date='2024-10-01',
    end_date='2025-01-31',
    auto_promote=False
):
    """
    运行回测并保存结果
    
    Parameters:
    -----------
    ticker : str
        合约代码
    start_date : str
        开始日期
    end_date : str
        结束日期
    auto_promote : bool
        是否自动提升为最优策略（夏普>2.0）
    """
    print("=" * 60)
    print("HLM5 回测引擎 - 带结果保存")
    print("=" * 60)
    
    # 1. 生成策略ID
    strategy_id = generate_strategy_id(ticker)
    print(f"\n策略ID: {strategy_id}")
    
    # 2. 准备策略配置
    print("\n[1/4] 准备策略配置...")
    strategy_config = {
        'strategy_id': strategy_id,
        'ticker': ticker,
        'strategy_name': 'HLM5',
        'version': '1.2',
        'start_date': start_date,
        'end_date': end_date,
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
                'enabled': False  # 当前禁用
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
        'comments': f'回测运行于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    }
    print("  ✓ 策略配置准备完成")
    
    # 3. 运行回测（调用现有逻辑或提取结果）
    print("\n[2/4] 运行回测...")
    performance = extract_performance_from_backtest(ticker, start_date, end_date)
    print("  ✓ 回测完成")
    
    # 4. 保存到数据库
    print("\n[3/4] 保存回测结果到数据库...")
    db_manager = BacktestDatabaseManager('data/trading_signals.db')
    db_manager.save_backtest_summary(strategy_config, performance)
    
    # 5. 自动提升（可选）
    if auto_promote or performance['sharpe_ratio'] > 2.0:
        print("\n[4/4] 提升为最优策略...")
        db_manager.promote_to_optimal(strategy_id, '自动提升：夏普比率>2.0')
        
        # 导出配置
        output_path = f'../configs/strategies/{strategy_id}.json'
        db_manager.export_strategy_to_json(strategy_id, output_path)
    else:
        print(f"\n[4/4] 跳过提升（夏普比率={performance['sharpe_ratio']:.2f} < 2.0）")
    
    db_manager.close()
    
    print("\n" + "=" * 60)
    print("回测流程完成！")
    print("=" * 60)
    
    return strategy_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HLM5回测引擎 - 带结果保存')
    parser.add_argument('--ticker', default='OI888', help='合约代码')
    parser.add_argument('--start-date', default='2024-10-01', help='开始日期')
    parser.add_argument('--end-date', default='2025-01-31', help='结束日期')
    parser.add_argument('--auto-promote', action='store_true', help='自动提升为最优策略')
    
    args = parser.parse_args()
    
    run_backtest_with_save(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        auto_promote=args.auto_promote
    )
```

**预期输出**:
```
============================================================
HLM5 回测引擎 - 带结果保存
============================================================

策略ID: hlm5_OI888_bt_20251205_103000

[1/4] 准备策略配置...
  ✓ 策略配置准备完成

[2/4] 运行回测...
  - 正在运行回测: OI888 (2024-10-01 ~ 2025-01-31)
  - 提示: 实际运行需要对接 hlm5_all_parallel.py
  ✓ 回测完成

[3/4] 保存回测结果到数据库...
✓ 数据库连接成功: data/trading_signals.db
✓ 回测结果已保存: hlm5_OI888_bt_20251205_103000
  - 夏普比率: 2.21
  - 年化收益: 15.55%
  - 最大回撤: -8.23%
  - 总交易次数: 286

[4/4] 提升为最优策略...
✓ 策略已提升为最优策略: hlm5_OI888_bt_20251205_103000
✓ 策略配置已导出: ../configs/strategies/hlm5_OI888_bt_20251205_103000.json
  - 文件大小: 1.23 KB

✓ 数据库连接已关闭

============================================================
回测流程完成！
============================================================
```

**验证标准**:
```
✅ 回测运行成功
✅ 结果保存到 backtest_summary
✅ 自动提升到 optimal_strategies
✅ 配置导出为JSON
✅ 所有信息显示完整
```

**⏸️ 等待用户确认**: 是否继续步骤1.4？

---

### 步骤1.4: 策略查询和管理工具 ✅

**目标**: 开发CLI工具，方便查询和管理策略

**任务清单**:
```
□ 创建策略查询工具
□ 显示所有回测结果
□ 显示最优策略列表
□ 对比多个策略
□ 导出指定策略
```

**开发文件**:
```
quant/hlm5_backtest_engine/tools/strategy_manager.py
```

**执行步骤**:
```bash
# 查询所有回测结果
python tools/strategy_manager.py list-all

# 查询最优策略
python tools/strategy_manager.py list-optimal

# 导出策略
python tools/strategy_manager.py export --id=xxx --output=configs/

# 对比策略
python tools/strategy_manager.py compare --ids=xxx,yyy,zzz
```

**⏸️ 等待用户确认**: 是否需要此步骤？

---

### 步骤1.5: 阶段1完整测试 ✅

**目标**: 验证回测引擎所有功能正常

**测试场景**:
```
1. 运行一次完整回测
2. 结果自动保存到数据库
3. 提升为最优策略
4. 导出配置JSON
5. 查询和验证数据
```

**执行步骤**:
```bash
cd quant/hlm5_backtest_engine

# 完整流程测试
python run_backtest_with_save.py \
    --ticker OI888 \
    --start-date 2024-10-01 \
    --end-date 2025-01-31 \
    --auto-promote
```

**验证清单**:
```
✅ 回测运行成功
✅ backtest_summary 有新记录
✅ optimal_strategies 有新记录
✅ JSON文件导出成功
✅ 所有字段数据完整
```

**⏸️ 等待用户确认**: 阶段1全部完成后，是否开始阶段2？

---

## 🎯 阶段2: quant/hlm5 实盘交易系统开发

### 目标

开发实盘交易系统，集成策略配置和交易记录功能。

---

### 步骤2.1: 实盘数据库初始化 ✅

**目标**: 创建实盘数据库表

**任务清单**:
```
□ 创建数据库初始化脚本
□ 创建 trading_data 表（与回测相同）
□ 创建 live_strategies 表
□ 创建 live_trades 表
□ 创建 live_performance_daily 表
□ 创建索引
□ 验证表结构
```

**开发文件**:
```
quant/hlm5/data/init_live_db.py
```

**代码内容**:
```python
"""
实盘交易数据库初始化脚本
创建实盘所需的所有表
"""

import sqlite3
from pathlib import Path


def init_live_tables(db_path='data/trading_signals.db'):
    """
    初始化实盘交易数据库表
    """
    print("=" * 60)
    print("实盘交易数据库初始化")
    print("=" * 60)
    
    # 确保目录存在
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n数据库路径: {db_path}")
    
    # 1. 创建 trading_data 表（与回测引擎相同）
    print("\n[1/4] 创建 trading_data 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trading_data (
            ticker TEXT,
            datetime TIMESTAMP,
            
            -- OHLCV
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            
            -- Price MACD
            Price_MACD REAL,
            Price_MACD_Signal REAL,
            Price_MACD_Hist REAL,
            Price_XLPL_Phase INTEGER,
            Price_Cross INTEGER,
            
            -- Volume MACD
            Volume_MACD REAL,
            Volume_MACD_Signal REAL,
            Volume_MACD_Hist REAL,
            Volume_XLPL_Phase INTEGER,
            Volume_Cross INTEGER,
            
            -- HLBW
            HLBW_Trend_Line REAL,
            HLBW_MACD REAL,
            HLBW_MACD_Signal REAL,
            HLBW_MACD_Hist REAL,
            HLBW_XLPL_Phase INTEGER,
            HLBW_Cross INTEGER,
            
            -- Prophet
            PH_yhat REAL,
            PH_yhat_lower REAL,
            PH_yhat_upper REAL,
            PH_MACD REAL,
            PH_MACD_Signal REAL,
            PH_MACD_Hist REAL,
            PH_XLPL_Phase INTEGER,
            PH_Cross INTEGER,
            PH_Trend_Duration INTEGER,
            PH_Trend_Change REAL,
            
            -- 交易信号
            Entry_Signal BOOLEAN,
            Exit_Signal BOOLEAN,
            Position INTEGER,
            Entry_Price REAL,
            Exit_Price REAL,
            Profit_Loss REAL,
            
            -- 加仓策略
            Scaling_Signal INTEGER DEFAULT 0,
            Scaling_Position INTEGER DEFAULT 0,
            Scaling_Level INTEGER DEFAULT 0,
            Scaling_Strategy TEXT,
            
            -- 数据质量标记
            is_realtime BOOLEAN DEFAULT 1,
            data_quality INTEGER DEFAULT 1,
            
            PRIMARY KEY (ticker, datetime)
        )
    """)
    
    # 创建索引（优化实盘查询）
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticker_datetime 
        ON trading_data(ticker, datetime)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_live_latest 
        ON trading_data(ticker, datetime DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_entry_signal 
        ON trading_data(ticker, Entry_Signal) 
        WHERE Entry_Signal = 1
    """)
    print("  ✓ trading_data 表创建成功")
    
    # 2. 创建 live_strategies 表
    print("\n[2/4] 创建 live_strategies 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_strategies (
            strategy_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            
            -- 回测时间范围
            start_date TEXT,
            end_date TEXT,
            
            -- 指标参数 (JSON)
            indicator_params TEXT,
            
            -- 交易参数 (JSON)
            trading_params TEXT,
            
            -- Prophet模型
            prophet_model BLOB,
            prophet_params TEXT,
            
            -- 回测性能指标
            total_return REAL,
            annual_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            total_trades INTEGER,
            avg_holding_period REAL,
            profit_factor REAL,
            
            -- 标记和状态
            is_optimal BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'testing',
            
            -- 完整配置
            full_config TEXT,
            
            -- 实盘控制参数
            max_position INTEGER DEFAULT 10,
            max_daily_loss REAL,
            max_daily_trades INTEGER DEFAULT 50,
            is_paper_trading BOOLEAN DEFAULT 1,
            
            -- 实盘性能追踪
            live_total_trades INTEGER DEFAULT 0,
            live_win_trades INTEGER DEFAULT 0,
            live_total_pnl REAL DEFAULT 0,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deployed_at TIMESTAMP,
            last_trade_at TIMESTAMP,
            comments TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_live_strategy_ticker 
        ON live_strategies(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_live_strategy_status 
        ON live_strategies(status)
    """)
    print("  ✓ live_strategies 表创建成功")
    
    # 3. 创建 live_trades 表
    print("\n[3/4] 创建 live_trades 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_trades (
            trade_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            
            -- 订单信息
            order_id TEXT,
            vt_orderid TEXT,
            direction TEXT,
            offset TEXT,
            
            -- 入场信息
            entry_datetime TIMESTAMP,
            entry_price REAL,
            entry_volume INTEGER,
            entry_signal_type INTEGER,
            entry_signal_strength INTEGER,
            
            -- 出场信息
            exit_datetime TIMESTAMP,
            exit_price REAL,
            exit_volume INTEGER,
            exit_reason TEXT,
            
            -- 盈亏计算
            gross_pnl REAL,
            commission REAL,
            slippage_cost REAL,
            net_pnl REAL,
            return_pct REAL,
            
            -- 持仓信息
            holding_period INTEGER,
            max_profit REAL,
            max_loss REAL,
            
            -- 状态
            status TEXT DEFAULT 'OPEN',
            
            -- 回测对比
            expected_pnl REAL,
            actual_vs_expected REAL,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comments TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_ticker 
        ON live_trades(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_strategy 
        ON live_trades(strategy_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_datetime 
        ON live_trades(entry_datetime)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_status 
        ON live_trades(status)
    """)
    print("  ✓ live_trades 表创建成功")
    
    # 4. 创建 live_performance_daily 表
    print("\n[4/4] 创建 live_performance_daily 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_performance_daily (
            date DATE,
            ticker TEXT,
            strategy_id TEXT,
            
            -- 交易统计
            total_trades INTEGER DEFAULT 0,
            win_trades INTEGER DEFAULT 0,
            loss_trades INTEGER DEFAULT 0,
            
            -- 盈亏
            gross_pnl REAL DEFAULT 0,
            net_pnl REAL DEFAULT 0,
            total_commission REAL DEFAULT 0,
            total_slippage REAL DEFAULT 0,
            
            -- 风险指标
            max_drawdown REAL,
            daily_return REAL,
            cumulative_return REAL,
            
            -- 回测对比
            expected_pnl REAL,
            tracking_error REAL,
            
            PRIMARY KEY (date, ticker, strategy_id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_date 
        ON live_performance_daily(date DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_strategy 
        ON live_performance_daily(strategy_id)
    """)
    print("  ✓ live_performance_daily 表创建成功")
    
    # 5. 提交并验证
    print("\n[验证] 提交更改并验证表结构...")
    conn.commit()
    
    # 查询所有表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    
    print("\n实盘数据库中的所有表:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  ✓ {table[0]}: {count} 条记录")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("实盘数据库初始化完成！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    init_live_tables()
```

**执行步骤**:
```bash
# 1. 进入目录
cd quant/hlm5/data

# 2. 运行初始化
python init_live_db.py
```

**预期输出**:
```
============================================================
实盘交易数据库初始化
============================================================

数据库路径: data/trading_signals.db

[1/4] 创建 trading_data 表...
  ✓ trading_data 表创建成功

[2/4] 创建 live_strategies 表...
  ✓ live_strategies 表创建成功

[3/4] 创建 live_trades 表...
  ✓ live_trades 表创建成功

[4/4] 创建 live_performance_daily 表...
  ✓ live_performance_daily 表创建成功

[验证] 提交更改并验证表结构...

实盘数据库中的所有表:
  ✓ live_performance_daily: 0 条记录
  ✓ live_strategies: 0 条记录
  ✓ live_trades: 0 条记录
  ✓ trading_data: 0 条记录

============================================================
实盘数据库初始化完成！
============================================================
```

**⏸️ 等待用户确认**: 是否继续步骤2.2？

---

### 步骤2.2: 实盘数据库管理器开发 ✅

**目标**: 开发 LiveDatabaseManager 类

**任务清单**:
```
□ 创建实盘数据库管理器类
□ 实现策略导入方法
□ 实现市场数据保存方法
□ 实现交易记录方法
□ 实现查询方法
□ 单元测试
```

**开发文件**:
```
quant/hlm5/data/live_database_manager.py
```

**执行步骤**:
```bash
# 测试实盘数据库管理器
cd quant/hlm5/data
python live_database_manager.py
```

**⏸️ 等待用户确认**: 是否继续步骤2.3？

---

### 步骤2.3: 策略配置导入工具 ✅

**目标**: 开发策略导入CLI工具

**任务清单**:
```
□ 创建策略导入工具
□ 读取JSON配置
□ 验证配置完整性
□ 导入到 live_strategies
□ 显示导入结果
```

**开发文件**:
```
quant/hlm5/tools/import_strategy.py
```

**执行步骤**:
```bash
cd quant/hlm5

# 导入策略
python tools/import_strategy.py \
    --config=../hlm5_backtest_engine/configs/strategies/hlm5_OI888_xxx.json \
    --paper-trading
```

**⏸️ 等待用户确认**: 是否继续步骤2.4？

---

### 步骤2.4: 集成到HLM5Strategy ✅

**目标**: 在策略中集成数据库记录功能

**任务清单**:
```
□ 修改 hlm5_strategy.py
□ 添加数据库管理器
□ 保存实时市场数据
□ 记录交易
□ 测试集成
```

**修改文件**:
```
quant/hlm5/strategies/hlm5_strategy.py
```

**修改内容**:
```python
# 在 __init__ 中添加
from ..data.live_database_manager import LiveDatabaseManager

class HLM5Strategy(CtaTemplate):
    
    # 添加参数
    enable_db_logging = False  # 是否启用数据库记录
    
    def __init__(self, ...):
        super().__init__(...)
        
        # 初始化数据库管理器（可选）
        self.db_manager = None
        if self.enable_db_logging:
            self.db_manager = LiveDatabaseManager()
    
    def on_5min_bar(self, bar):
        # 原有逻辑
        ...
        
        # 保存市场数据（可选）
        if self.db_manager:
            signals = self._get_current_signals()
            self.db_manager.save_market_data(bar, signals)
```

**⏸️ 等待用户确认**: 是否需要此步骤？

---

### 步骤2.5: 阶段2完整测试 ✅

**目标**: 验证实盘系统所有功能

**测试场景**:
```
1. 从回测引擎导入策略配置
2. 启动纸上交易
3. 记录实时数据和信号
4. 记录模拟交易
5. 查询和验证数据
```

**⏸️ 等待用户确认**: 阶段2全部完成后，是否进入纸上交易验证？

---

## 📋 完整执行流程总结

### 阶段1: hlm5_backtest_engine（3-5步）

```
步骤1.1: 数据库初始化 ✅ 必做
  └─ 创建 backtest_summary, optimal_strategies 表

步骤1.2: 数据库管理器 ✅ 必做
  └─ 开发 BacktestDatabaseManager

步骤1.3: 集成到回测流程 ✅ 必做
  └─ 创建 run_backtest_with_save.py

步骤1.4: 策略管理工具 ⚠️ 可选
  └─ 创建 strategy_manager.py CLI工具

步骤1.5: 完整测试 ✅ 必做
  └─ 验证所有功能
```

### 阶段2: quant/hlm5（4-5步）

```
步骤2.1: 数据库初始化 ✅ 必做
  └─ 创建实盘数据库表

步骤2.2: 数据库管理器 ✅ 必做
  └─ 开发 LiveDatabaseManager

步骤2.3: 策略导入工具 ✅ 必做
  └─ 创建 import_strategy.py

步骤2.4: 集成到策略 ⚠️ 可选
  └─ 修改 hlm5_strategy.py

步骤2.5: 完整测试 ✅ 必做
  └─ 纸上交易验证
```

---

## 🎯 执行建议

### 最小可行方案（必做步骤）

```
阶段1必做:
  ✅ 步骤1.1: 数据库初始化
  ✅ 步骤1.2: 数据库管理器
  ✅ 步骤1.3: 集成回测流程

阶段2必做:
  ✅ 步骤2.1: 数据库初始化
  ✅ 步骤2.2: 数据库管理器
  ✅ 步骤2.3: 策略导入工具
```

**总计**: 6个必做步骤

### 完整方案（包含可选）

```
阶段1: 5个步骤
阶段2: 5个步骤
```

**总计**: 10个步骤

---

## 📝 关键说明

### 为什么这样设计

1. **最小改动**
   - 不修改 hlm5_all_parallel.py
   - 只添加新表和管理器
   - 现有回测流程不受影响

2. **每步可验证**
   - 每个步骤都有独立的测试
   - 输出信息详细完整
   - 便于调试和确认

3. **渐进式开发**
   - 先数据库，再管理器，再集成
   - 循序渐进，风险可控

### 下一步

完成步骤1.1后，请告诉我：
- ✅ "步骤1.1完成，继续1.2" - 继续下一步
- ⚠️ "步骤1.1有问题：[具体问题]" - 我会协助解决
- 🔄 "需要修改步骤1.1：[修改需求]" - 我会调整方案

**当前状态**: 📋 计划制定完成，等待执行步骤1.1

---

**制定人**: AI Assistant  
**制定时间**: 2025-12-05  
**状态**: 等待用户确认启动步骤1.1

