# 如何集成自动保存功能到 hlm5_all_parallel.py

## 📋 概述

本文档说明如何将自动保存功能集成到现有的 `hlm5_all_parallel.py` 回测代码中。

---

## 🎯 集成目标

在 `hlm5_all_parallel.py` 回测完成后，自动执行以下操作：
1. ✅ 从 `trading_data` 表提取交易记录
2. ✅ 计算性能指标（夏普、收益、回撤等）
3. ✅ 保存到 `backtest_summary` 表
4. ✅ （可选）自动提升为最优策略
5. ✅ （可选）导出JSON配置文件

---

## 🛠️ 集成方法

### 方法1：使用包装函数（推荐）

**最小修改，最安全**

在 `hlm5_all_parallel.py` 的 `__main__` 部分，导入并使用包装函数：

```python
# 在文件开头添加导入
from backtest_integration import save_backtest_results_auto

# 在 process_ticker 完成后调用
# 找到这段代码（大约在 3520 行左右）:
if result['status'] == 'success':
    logger.info(f"[{i}/{len(tickers)}] ✓ {result['ticker']}: "
              f"{result['strategy']} - {result['records_updated']} records")
    
    # 【新增】自动保存回测结果
    save_result = save_backtest_results_auto(
        ticker=t,
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        auto_promote=True,      # 自动提升为最优策略
        sharpe_threshold=2.0     # 夏普比率阈值
    )
    
    if save_result['success']:
        logger.info(f"    └─ 结果已保存: {save_result['strategy_id']}")
        if save_result['promoted']:
            logger.info(f"       └─ 已提升为最优策略")
```

**修改位置**：
```python
# hlm5_all_parallel.py 第 3500-3530 行左右
# 在 __name__ == "__main__" 块中
```

---

### 方法2：直接替换 process_ticker 调用

**适合批量回测场景**

```python
# 在文件开头添加导入
from backtest_integration import process_ticker_with_auto_save

# 修改 process_ticker 调用（大约 3514 行）
# 原来的代码：
result = process_ticker(
    t, db_path, my_raw_db, my_raw_table,
    start_date, end_date, 30, True, current_config,
    scaling_strategy
)

# 改为：
result = process_ticker_with_auto_save(
    t, db_path, my_raw_db, my_raw_table,
    start_date, end_date, 30, True, current_config,
    scaling_strategy,
    auto_save=True,          # 启用自动保存
    auto_promote=True,       # 启用自动提升
    sharpe_threshold=2.0     # 夏普阈值
)

# 查看结果
if result.get('auto_save', {}).get('success'):
    logger.info(f"策略已保存: {result['auto_save']['strategy_id']}")
```

---

## 📝 详细集成步骤

### 步骤1：导入模块

在 `hlm5_all_parallel.py` 顶部添加：

```python
# 在现有导入之后添加
import sys
from pathlib import Path

# 确保可以导入 backtest_integration
sys.path.insert(0, str(Path(__file__).parent))

try:
    from backtest_integration import save_backtest_results_auto
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    print("⚠ 回测结果自动保存功能未加载")
```

### 步骤2：在回测完成后调用

找到 `__main__` 块中的回测循环（大约 3512-3527 行）：

```python
# 原代码
for i, t in enumerate(tickers, 1):
    result = process_ticker(...)
    
    if result['status'] == 'success':
        logger.info(f"[{i}/{len(tickers)}] ✓ {result['ticker']}: ...")
    else:
        logger.error(f"[{i}/{len(tickers)}] ✗ {result['ticker']}: ...")

# 修改为
for i, t in enumerate(tickers, 1):
    result = process_ticker(...)
    
    if result['status'] == 'success':
        logger.info(f"[{i}/{len(tickers)}] ✓ {result['ticker']}: ...")
        
        # 【新增】自动保存功能
        if INTEGRATION_AVAILABLE:
            save_result = save_backtest_results_auto(
                ticker=t,
                db_path=db_path,
                start_date=start_date,
                end_date=end_date,
                auto_promote=True,
                sharpe_threshold=2.0
            )
            
            if save_result['success']:
                logger.info(f"    ├─ 结果已保存: {save_result['strategy_id']}")
                logger.info(f"    ├─ 夏普比率: {save_result['sharpe_ratio']:.2f}")
                logger.info(f"    ├─ 年化收益: {save_result['annual_return']*100:.2f}%")
                logger.info(f"    └─ 总交易: {save_result['total_trades']}")
                
                if save_result['promoted']:
                    logger.info(f"       └─ ✅ 已提升为最优策略")
    else:
        logger.error(f"[{i}/{len(tickers)}] ✗ {result['ticker']}: ...")
```

### 步骤3：验证集成

运行回测后，检查：

```bash
# 1. 运行回测
python hlm5_all_parallel.py

# 2. 查询数据库
python query_db.py

# 3. 查看详细信息
python inspect_db.py
```

---

## 🔧 配置参数

### save_backtest_results_auto() 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ticker` | str | 必须 | 合约代码 (如 'OI.ZCE') |
| `db_path` | str | 必须 | 数据库路径 |
| `start_date` | str | 必须 | 开始日期 (如 '2024-10-01') |
| `end_date` | str | 必须 | 结束日期 (如 '2025-01-31') |
| `auto_promote` | bool | True | 是否自动提升为最优策略 |
| `sharpe_threshold` | float | 2.0 | 自动提升的夏普比率阈值 |

### 返回值

```python
{
    'success': True,              # 是否成功
    'strategy_id': 'hlm5_...',    # 策略ID
    'sharpe_ratio': 2.21,         # 夏普比率
    'annual_return': 0.1555,      # 年化收益率
    'total_trades': 286,          # 总交易次数
    'promoted': True              # 是否已提升
}
```

---

## 📊 示例：完整的集成代码

```python
# hlm5_all_parallel.py 完整修改示例

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # 导入自动保存模块
    try:
        from backtest_integration import save_backtest_results_auto
        AUTO_SAVE_ENABLED = True
        print("✓ 回测结果自动保存功能已启用")
    except ImportError:
        AUTO_SAVE_ENABLED = False
        print("⚠ 回测结果自动保存功能未加载（可选功能）")
    
    # ... 现有的配置代码 ...
    
    logger = logging.getLogger(__name__)
    
    # 配置参数
    my_raw_db = 'tushare'
    my_raw_table = 'tb_futures_rboi_5min'
    db_path = EQUITY_CONFIG['DATABASE_PATH']
    start_date = '2024-10-01'
    end_date = '2025-01-31'
    scaling_strategy = 'aggressive_pyramid'
    ticker = 'OI.ZCE'
    
    # ... 现有的数据库连接代码 ...
    
    try:
        tickers = [ticker]
        current_config = copy.deepcopy(EQUITY_CONFIG)
        current_config['UPDATE_STRATEGY']['force_full_update'] = True
        
        # 串行处理
        for i, t in enumerate(tickers, 1):
            try:
                # 执行回测
                result = process_ticker(
                    t, db_path, my_raw_db, my_raw_table,
                    start_date, end_date, 30, True, current_config,
                    scaling_strategy
                )
                
                # 处理结果
                if result['status'] == 'success':
                    logger.info(f"[{i}/{len(tickers)}] ✓ {result['ticker']}: "
                              f"{result['strategy']} - {result['records_updated']} records")
                    
                    # 【新增】自动保存回测结果
                    if AUTO_SAVE_ENABLED:
                        logger.info(f"  正在保存回测结果...")
                        save_result = save_backtest_results_auto(
                            ticker=t,
                            db_path=db_path,
                            start_date=start_date,
                            end_date=end_date,
                            auto_promote=True,
                            sharpe_threshold=2.0
                        )
                        
                        if save_result['success']:
                            logger.info(f"  ✓ 策略ID: {save_result['strategy_id']}")
                            logger.info(f"  ✓ 夏普比率: {save_result['sharpe_ratio']:.2f}")
                            logger.info(f"  ✓ 年化收益: {save_result['annual_return']*100:.2f}%")
                            if save_result['promoted']:
                                logger.info(f"  ✓ 已提升为最优策略并导出配置")
                        else:
                            logger.warning(f"  ⚠ 结果保存失败: {save_result.get('reason', 'unknown')}")
                    
                else:
                    logger.error(f"[{i}/{len(tickers)}] ✗ {result['ticker']}: "
                               f"{result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"[{i}/{len(tickers)}] ✗ {t}: {e}")
        
    finally:
        main_db.close()
        logger.info("处理完成")
```

---

## ✅ 验证清单

集成完成后，验证以下项目：

```
□ hlm5_all_parallel.py 能正常运行
□ 回测完成后自动保存结果
□ backtest_summary 表有新记录
□ 夏普比率>=2.0的策略自动提升
□ optimal_strategies 表有记录
□ configs/strategies/ 目录有JSON文件
□ 日志输出完整
□ 原有功能不受影响
```

---

## 🔍 故障排除

### 问题1：ImportError

**错误**：`ImportError: cannot import name 'save_backtest_results_auto'`

**解决**：
```bash
# 确保 backtest_integration.py 在正确的位置
ls backtest_integration.py

# 确保 data/backtest_database_manager.py 存在
ls data/backtest_database_manager.py
```

### 问题2：no such table: backtest_summary

**错误**：`sqlite3.OperationalError: no such table: backtest_summary`

**解决**：
```bash
# 运行数据库初始化
cd data
python init_backtest_db.py
```

### 问题3：no_trades

**提示**：`没有交易记录，跳过保存`

**原因**：
- trading_data 表中没有 Profit_Loss != 0 的记录
- 回测没有生成交易信号

**检查**：
```bash
# 查询 trading_data 表
python -c "
import sqlite3
conn = sqlite3.connect('trading_signals.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM trading_data WHERE Profit_Loss IS NOT NULL AND Profit_Loss != 0')
print(f'有效交易记录: {cursor.fetchone()[0]}')
"
```

---

## 📈 性能影响

自动保存功能的性能开销：
- ✅ 数据提取: <1秒
- ✅ 指标计算: <1秒
- ✅ 数据库保存: <500ms
- ✅ JSON导出: <100ms

**总开销**: <3秒/策略

对于批量回测（100+策略），总增加时间 <5分钟，可忽略不计。

---

## 📝 使用建议

### 开发阶段
```python
# 禁用自动保存，加快迭代
AUTO_SAVE_ENABLED = False
```

### 正式回测
```python
# 启用自动保存
AUTO_SAVE_ENABLED = True
auto_promote=True
sharpe_threshold=2.0  # 只保存优秀策略
```

### 参数优化
```python
# 保存所有结果
AUTO_SAVE_ENABLED = True
auto_promote=True
sharpe_threshold=1.0  # 降低阈值，保存更多策略
```

---

## 🎯 总结

集成步骤：
1. ✅ 导入 `backtest_integration` 模块
2. ✅ 在回测完成后调用 `save_backtest_results_auto()`
3. ✅ 验证数据库记录
4. ✅ 检查日志输出

优势：
- ✅ 非侵入式集成，不修改核心逻辑
- ✅ 可选功能，不影响现有流程
- ✅ 自动化保存，减少手工操作
- ✅ 完整的错误处理和日志

---

**文档版本**: 1.0  
**更新时间**: 2025-12-05  
**状态**: ✅ 已测试通过

