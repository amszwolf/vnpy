# VeighNa 量化交易框架 - 快速开始指南

## 一、环境准备

### 1. 安装依赖模块

```bash
pip install vnpy_ctastrategy
pip install vnpy_ctabacktester
pip install vnpy_paperaccount
pip install vnpy_ctp
```

### 2. 准备数据

确保数据库中有足够的历史数据，可以通过DataManager下载。

## 二、策略开发

### 1. 使用模板创建策略

复制 `strategies/template_strategy.py` 并重命名为你的策略文件。

### 2. 实现策略逻辑

参考 `strategies/ma_cross_strategy.py` 实现你的策略逻辑。

### 3. 注册参数和变量

在策略类中定义 `parameters` 和 `variables` 列表。

## 三、策略回测

### 1. 运行回测

```bash
cd quant/examples
python backtesting/run_backtest.py
```

### 2. 查看结果

回测完成后会显示：
- 统计指标
- 回测图表
- 保存结果到CSV文件

## 四、参数优化

### 1. 运行优化

```bash
python backtesting/optimizer.py
```

### 2. 选择最优参数

根据优化结果选择最优参数组合。

## 五、模拟交易

### 1. 运行模拟交易

```bash
python trading/paper_trading.py
```

### 2. 验证策略

在模拟环境中验证策略表现。

## 六、实盘交易

### 1. 准备账号配置

确保已配置CTP账号（运行 `add_accounts.py`）。

### 2. 运行实盘交易

```bash
python trading/live_trading.py
```

**⚠️ 警告：实盘交易涉及真实资金，请谨慎操作！**

## 七、复盘分析

### 1. 分析回测结果

```python
from analysis.performance_analyzer import PerformanceAnalyzer
from analysis.review_analyzer import ReviewAnalyzer
import pandas as pd

# 加载回测结果
result_df = pd.read_csv("backtest_result.csv", index_col=0, parse_dates=True)

# 绩效分析
analyzer = PerformanceAnalyzer(result_df)
analyzer.print_statistics()
analyzer.export_report("performance_report.txt")

# 复盘分析
reviewer = ReviewAnalyzer(result_df)
reviewer.generate_review_report("review_report.txt")
```

## 八、完整工作流

运行完整示例：

```bash
python complete_example.py
```

这会执行：
1. 策略回测
2. 绩效分析
3. 复盘分析

## 九、策略开发最佳实践

### 1. 策略设计原则

- **简单有效**：策略逻辑要简单清晰
- **风险控制**：必须设置止损止盈
- **参数合理**：参数范围要合理，避免过拟合
- **充分测试**：回测时间要足够长，覆盖不同市场环境

### 2. 回测注意事项

- **数据质量**：确保历史数据完整准确
- **滑点成本**：设置合理的滑点和手续费
- **样本外测试**：保留部分数据用于样本外测试
- **参数稳定性**：测试参数在不同市场环境下的稳定性

### 3. 实盘交易建议

- **小仓位开始**：先用小仓位测试
- **密切监控**：实时监控策略运行状态
- **设置止损**：设置合理的止损点
- **定期复盘**：定期分析策略表现，及时调整

## 十、常见问题

### Q1: 回测结果很好，但实盘表现不佳？

**可能原因：**
- 过拟合：参数过度优化
- 数据问题：回测数据与实盘数据不一致
- 滑点成本：实盘滑点比回测设置的大
- 市场环境变化：策略不适应当前市场

**解决方案：**
- 使用样本外数据测试
- 增加回测时间跨度
- 设置更保守的参数
- 添加更多风险控制

### Q2: 如何选择合适的参数？

**建议：**
- 使用参数优化工具
- 选择夏普比率高的参数组合
- 避免选择极端参数
- 测试参数在不同市场环境下的表现

### Q3: 策略运行中如何监控？

**方法：**
- 查看日志文件
- 监控持仓和资金变化
- 设置报警机制
- 定期生成报告

## 十一、进阶功能

### 1. 多策略组合

可以同时运行多个策略，分散风险。

### 2. 动态参数调整

根据市场环境动态调整策略参数。

### 3. 风险控制

添加更多风险控制机制，如：
- 最大回撤限制
- 单笔交易风险限制
- 总持仓限制

## 十二、参考资料

- VeighNa官方文档：https://www.vnpy.com/docs/cn/
- CTA策略开发指南：`docs/community/app/cta_strategy.md`
- 回测模块文档：`docs/community/app/cta_backtester.md`

---

**祝交易顺利！**

