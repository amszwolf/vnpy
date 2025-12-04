# HLM5 策略部署计划

## 📋 总体流程

从开发到实盘成功，共分为 **10个阶段**，每个阶段都有明确的验证标准。

```
阶段0: 环境验证 ✓
  ↓
阶段1: 数据准备验证 
  ↓
阶段2: 指标计算验证
  ↓
阶段3: 策略逻辑验证
  ↓
阶段4: 历史回测（固定仓位）
  ↓
阶段5: 历史回测（加仓策略）
  ↓
阶段6: 参数优化
  ↓
阶段7: SimNow模拟交易
  ↓
阶段8: 小资金实盘测试
  ↓
阶段9: 正式实盘部署
  ↓
阶段10: 监控和优化
```

---

## 🔍 阶段0: 环境验证

### 目标
确认所有依赖已安装，环境配置正确

### 验证步骤

#### 1. Python环境检查
```bash
# 激活环境
conda activate vnpyenv

# 检查Python版本
python --version  # 应该是 3.8+

# 检查关键包
python -c "import vnpy; print(f'VNPy: {vnpy.__version__}')"
python -c "import vnpy_ctastrategy; print('CTA策略模块: OK')"
python -c "import talib; print('TA-Lib: OK')"
python -c "import pandas; print('Pandas: OK')"
python -c "import numpy; print('NumPy: OK')"
```

#### 2. RQData配置检查
```bash
cd quant/hlm5
python -c "from vnpy.trader.setting import SETTINGS; print(f'数据源: {SETTINGS.get(\"datafeed.name\", \"未配置\")}'); print(f'License: {SETTINGS.get(\"datafeed.username\", \"未配置\")}')"
```

#### 3. 模块导入测试
```bash
python -c "from strategies.hlm5_strategy import HLM5Strategy; print('策略模块: OK')"
python -c "from utils.indicators import calculate_macd_signals; print('指标模块: OK')"
python -c "from utils.scaling_strategy import SCALING_CONFIGS; print('加仓模块: OK')"
python -c "from utils.trading_session import TradingSessionManager; print('时段管理: OK')"
python -c "from utils.cost_model import TradingCostCalculator; print('成本模块: OK')"
```

### ✅ 验证标准
- [ ] Python 3.8+
- [ ] 所有依赖包安装成功
- [ ] RQData 已配置
- [ ] 所有自定义模块可正常导入

### ❌ 失败处理
如果有任何失败，参考 `QUICKSTART.md` 的故障排查部分解决

---

## 📊 阶段1: 数据准备验证

### 目标
确认能够正确下载和存储历史数据

### 验证步骤

#### 1. 检查数据库
```bash
python data/download_oi_data.py --check
```

#### 2. 下载测试数据（1个月）
```bash
python data/download_oi_data.py --start 2025-01-01 --end 2025-01-31 --interval 5m
```

**预期输出：**
```
====================================
OI 期货数据下载
====================================
起始日期: 2025-01-01
结束日期: 2025-01-31
数据周期: 5m
✓ RQData 连接成功
✓ 成功下载 XXXX 条数据
✓ 数据已保存
```

#### 3. 验证数据质量
```bash
python -c "
from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval
from datetime import datetime

db = get_database()
bars = db.load_bar_data('OI888', Exchange.CZCE, Interval.MINUTE_5, 
                         datetime(2025, 1, 1), datetime(2025, 1, 31))
print(f'数据条数: {len(bars)}')
print(f'起始时间: {bars[0].datetime if bars else \"无数据\"}')
print(f'结束时间: {bars[-1].datetime if bars else \"无数据\"}')
print(f'价格范围: {min(b.close_price for b in bars):.2f} ~ {max(b.close_price for b in bars):.2f}')
"
```

### ✅ 验证标准
- [ ] 数据下载成功（至少1000条5分钟数据）
- [ ] 数据时间连续（无大段空白）
- [ ] 价格数据合理（无异常值）
- [ ] 成交量数据存在

### ⚠️ 注意事项
- 如果是周末/节假日，数据可能较少
- OI888 主力合约数据应该连续

### ❌ 失败处理
- RQData连接失败 → 检查 License 配置
- 数据为空 → 尝试下载更长时间段
- 价格异常 → 检查合约代码是否正确

---

## 🧮 阶段2: 指标计算验证

### 目标
验证技术指标计算的正确性

### 验证步骤

#### 1. 测试 Price MACD
```bash
python -c "
import pandas as pd
import numpy as np
from utils.indicators import calculate_macd_signals
from hlm5_config import EQUITY_CONFIG

# 生成测试数据
np.random.seed(42)
prices = 100 + np.cumsum(np.random.randn(200) * 2)
series = pd.Series(prices)

# 计算MACD
config = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']
result = calculate_macd_signals(series, config=config)

print('Price MACD 指标计算结果:')
print(f'  输出列: {list(result.columns)}')
print(f'  数据行数: {len(result)}')
print(f'  MACD范围: {result[\"MACD\"].min():.4f} ~ {result[\"MACD\"].max():.4f}')
print(f'  XLPL阶段分布:')
for phase in [1, 2, 3, 4]:
    count = (result['XLPL_Phase'] == phase).sum()
    print(f'    阶段{phase}: {count}次')
print('✓ Price MACD 计算正常')
"
```

#### 2. 测试 HLBW
```bash
python -c "
import pandas as pd
import numpy as np
from utils.indicators import calculate_hlbw
from hlm5_config import EQUITY_CONFIG

# 生成测试数据
np.random.seed(42)
base = 100 + np.cumsum(np.random.randn(200) * 2)
high = base + np.random.rand(200) * 5
low = base - np.random.rand(200) * 5
close = base

high_series = pd.Series(high)
low_series = pd.Series(low)
close_series = pd.Series(close)

# 计算HLBW
config = EQUITY_CONFIG['INDICATORS']['HLBW']
result = calculate_hlbw(high_series, low_series, close_series, config=config)

print('HLBW 指标计算结果:')
print(f'  输出列: {list(result.columns)}')
print(f'  趋势线范围: {result[\"HLBW_Trend_Line\"].min():.2f} ~ {result[\"HLBW_Trend_Line\"].max():.2f}')
print(f'  有效数据: {result[\"HLBW_Trend_Line\"].notna().sum()} / {len(result)}')
print('✓ HLBW 计算正常')
"
```

#### 3. 测试加仓策略
```bash
python utils/scaling_strategy.py
```

**预期输出：**
显示5种加仓策略的配置

### ✅ 验证标准
- [ ] Price MACD 计算成功，包含所有列
- [ ] XLPL 阶段分布合理（4个阶段都有）
- [ ] HLBW 趋势线在 0-100 范围内
- [ ] 加仓策略模块加载成功

### ❌ 失败处理
- 导入错误 → 检查模块路径
- 计算错误 → 检查配置参数
- NaN值过多 → 检查输入数据

---

## 🎯 阶段3: 策略逻辑验证

### 目标
验证入场/出场信号生成的正确性

### 验证步骤

#### 1. 创建最小测试脚本
创建 `test_strategy_logic.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from strategies.hlm5_strategy import HLM5Strategy

# 模拟策略实例（不需要完整的CTA引擎）
class MockCTAEngine:
    def write_log(self, msg):
        print(f"[Log] {msg}")

class MockStrategy(HLM5Strategy):
    def __init__(self):
        self.price_macd = 0.5
        self.price_macd_signal = 0.3
        self.price_xlpl_phase = 2  # 拉升
        self.price_cross = 1
        
        self.volume_macd = 100
        self.volume_macd_signal = 80
        self.volume_xlpl_phase = 2
        self.volume_cross = 1
        
        self.hlbw_trend = 60
        self.hlbw_macd = 0.2
        self.hlbw_xlpl_phase = 2
        self.hlbw_cross = 1
        
        self.prophet_yhat = 100
        self.prophet_phase = 2
        self.prophet_duration = 5
        
        self.enable_bidirectional = True
        self.prophet_min_duration = 2

# 测试做多信号
strategy = MockStrategy()
long_signal = strategy.check_entry_conditions_long()
print(f"做多信号: {long_signal}")
print(f"  预期: 1 (所有指标都符合最强信号)")

# 测试做空信号
strategy.price_cross = -1
strategy.price_xlpl_phase = 4  # 下跌
strategy.hlbw_cross = -1
strategy.prophet_phase = 4
short_signal = strategy.check_entry_conditions_short()
print(f"做空信号: {short_signal}")
print(f"  预期: -1 (所有指标都符合做空信号)")

print("\n✓ 策略逻辑验证通过")
```

运行：
```bash
python test_strategy_logic.py
```

### ✅ 验证标准
- [ ] 做多信号正确生成（信号值 1-6）
- [ ] 做空信号正确生成（信号值 -1 到 -6）
- [ ] 出场信号正确判断
- [ ] 无异常错误

### ❌ 失败处理
- 信号错误 → 检查指标值设置
- 逻辑错误 → 对照 `hlm5_all_parallel.py` 检查移植

---

## 📈 阶段4: 历史回测（固定仓位）

### 目标
验证策略在历史数据上的基本表现

### 验证步骤

#### 1. 运行基础回测
```bash
cd quant/hlm5
python backtesting/run_backtest.py --start 2025-01-01 --end 2025-01-31 --capital 100000
```

#### 2. 检查回测结果

**预期输出示例：**
```
====================================
回测结果
====================================
起始资金: 100,000.00 元
结束资金: 124,730.00 元
总收益率: 24.73%
年化收益率: 98.92%

风险指标:
  最大回撤: -8.32%
  夏普比率: 0.504
  收益回撤比: 2.97

交易统计:
  总交易次数: 145
  胜率: 74.31%
  平均盈利: 856.23 元
====================================
```

#### 3. 验证关键指标

创建检查脚本 `check_backtest_result.py`:
```python
def validate_backtest_stats(stats):
    """验证回测结果的合理性"""
    checks = {
        '总收益': stats.get('total_return', 0) > 0.1,  # 至少10%
        '夏普比率': stats.get('sharpe_ratio', 0) > 0.3,  # 至少0.3
        '最大回撤': abs(stats.get('max_ddpercent', 1)) < 0.3,  # 小于30%
        '总交易次数': stats.get('total_trade_count', 0) > 10,  # 至少10笔
        '胜率': stats.get('winning_trade_count', 0) / max(stats.get('total_trade_count', 1), 1) > 0.4  # 至少40%
    }
    
    print("\n回测结果验证:")
    for name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
    
    return all(checks.values())
```

### ✅ 验证标准
- [ ] 回测成功完成，无错误
- [ ] 总收益率 > 10%
- [ ] 夏普比率 > 0.3
- [ ] 最大回撤 < 30%
- [ ] 总交易次数 > 10
- [ ] 胜率 > 40%
- [ ] 图表正常显示

### ⚠️ 如果指标不理想
不要灰心，这是正常的！进入阶段6进行参数优化

### ❌ 失败处理
- 无交易 → 检查信号生成逻辑
- 收益为负 → 检查出场条件
- 程序崩溃 → 检查数据完整性

---

## 🚀 阶段5: 历史回测（加仓策略）

### 目标
验证加仓策略是否能提升收益

### 验证步骤

#### 1. 运行对比测试
```bash
python examples/test_scaling_strategy.py
```

**预期输出：**
显示固定仓位 vs 加仓模式的对比结果

#### 2. 手动对比测试

**测试1：固定仓位**
```bash
# 修改 run_backtest.py，设置 enable_scaling = False
python backtesting/run_backtest.py
# 记录结果：总收益、夏普、回撤
```

**测试2：加仓模式**
```bash
# 修改 run_backtest.py，设置 enable_scaling = True
python backtesting/run_backtest.py
# 记录结果：总收益、夏普、回撤
```

### ✅ 验证标准
- [ ] 加仓模式回测成功
- [ ] 加仓模式收益 ≥ 固定仓位收益
- [ ] 加仓模式回撤在可接受范围（< 15%）
- [ ] 加仓层级正常工作（有加仓记录）

### 📊 决策标准

**如果加仓效果好（收益提升 > 20%，回撤增加 < 5%）：**
→ 采用加仓策略，进入阶段6

**如果加仓效果一般：**
→ 先优化固定仓位参数，再测试加仓

**如果加仓效果差（收益下降或回撤显著增加）：**
→ 暂不使用加仓，专注优化基础策略

---

## 🔧 阶段6: 参数优化

### 目标
找到最优参数组合

### 验证步骤

#### 1. 运行参数优化
```bash
python backtesting/optimizer.py --start 2025-01-01 --end 2025-01-31
```

**预期运行时间：** 30分钟 - 2小时（取决于参数范围）

#### 2. 分析优化结果

查看 `output/optimization_*.txt`，寻找：
- 夏普比率最高的参数组合
- 总收益最高的参数组合
- 收益回撤比最高的参数组合

#### 3. 验证最优参数

选择一组参数，修改 `hlm5_config.py`:
```python
'PRICE_MACD': {
    'macd_long': 最优值,
    'macd_mid': 最优值,
    'macd_short': 最优值,
    # ...
}
```

重新运行回测验证：
```bash
python backtesting/run_backtest.py --start 2025-02-01 --end 2025-02-28
```

### ✅ 验证标准
- [ ] 优化成功完成
- [ ] 找到至少3组候选参数
- [ ] 最优参数在验证期表现良好
- [ ] 夏普比率提升 > 10%

### 📝 记录最优参数
在 `output/` 目录创建 `optimal_parameters.txt`，记录：
- 参数组合
- 训练期表现
- 验证期表现
- 选择理由

---

## 🎮 阶段7: SimNow模拟交易

### 目标
在SimNow模拟环境验证策略实时运行

### 验证步骤

#### 1. 准备模拟交易
```bash
# 确认 SimNow 账户可用
# 修改 trading/paper_trading.py 中的策略配置
```

配置示例：
```python
strategy_setting = {
    'enable_scaling': False,  # 先测试固定仓位
    'fixed_size': 1,
    'enable_bidirectional': True,
    'hold_overnight': False,
    # 使用优化后的参数
    'price_macd_long': 优化值,
    'price_macd_mid': 优化值,
    # ...
}
```

#### 2. 启动模拟交易
```bash
python trading/paper_trading.py
```

**预期输出：**
```
====================================
HLM5 策略模拟交易
====================================
✓ 引擎创建成功
✓ 事件监听已注册
✓ 正在连接 SimNow...
✓ CTP Gateway 已添加
✓ 策略类已注册
✓ 策略实例已添加
✓ 策略初始化完成
✓ 策略已启动
✓ 已订阅 OI888.CZCE

等待行情数据...
```

#### 3. 观察运行状态（至少2小时）

监控内容：
- [ ] 行情数据正常接收
- [ ] 指标计算正确
- [ ] 信号生成合理
- [ ] 订单执行成功
- [ ] 持仓管理正确
- [ ] 收盘前自动平仓

#### 4. 创建监控清单

**每30分钟检查：**
- 连接状态
- 持仓情况
- 当日盈亏
- 是否有错误日志

**交易发生时检查：**
- 开仓价格是否合理
- 开仓理由是否充分
- 仓位大小是否正确

### ✅ 验证标准（运行1-3天）
- [ ] 连接稳定，无频繁断线
- [ ] 信号生成符合预期
- [ ] 至少完成5笔完整交易
- [ ] 盈亏在预期范围内
- [ ] 无程序崩溃
- [ ] 收盘前成功平仓

### 📊 阶段7决策点

**如果模拟交易顺利（胜率 > 50%，盈亏合理）：**
→ 进入阶段8（小资金实盘）

**如果出现问题：**
- 信号频繁 → 调整信号阈值
- 止损频繁 → 放宽止损参数
- 无交易 → 检查信号生成
- 程序错误 → 修复bug，重新测试

**最低要求：**
- 模拟交易至少运行3天
- 至少完成10笔交易
- 总体盈利或盈亏平衡

---

## 💰 阶段8: 小资金实盘测试

### 目标
用最小资金验证策略在真实市场的表现

### ⚠️ 重要提示

**这是真实资金！**
- 建议初始资金：**1万元**
- 固定仓位：**1手**
- 不启用加仓
- 测试周期：**2-4周**

### 验证步骤

#### 1. 实盘前检查清单

- [ ] 回测收益率 > 20%
- [ ] 夏普比率 > 0.5
- [ ] 模拟交易至少3天无重大问题
- [ ] 资金准备充足（考虑保证金和浮亏）
- [ ] 心理准备（接受可能的亏损）

#### 2. 配置实盘策略

```python
strategy_setting = {
    'enable_scaling': False,        # 禁用加仓
    'fixed_size': 1,                # 仅1手
    'enable_bidirectional': False,  # 仅做多（更保守）
    'hold_overnight': False,
    'stop_loss_pct': 0.03,         # 3%止损（比回测更严格）
    'take_profit_pct': 0.10,       # 10%止盈（比回测更保守）
}
```

#### 3. 启动实盘交易

```bash
# 修改 trading/paper_trading.py 连接实盘账户
python trading/live_trading.py  # 如果有实盘脚本
```

#### 4. 每日监控（必须做）

**开盘前（9:00前）：**
- 检查程序是否运行
- 检查网络连接
- 检查账户状态

**盘中（交易时段）：**
- 每小时检查一次持仓
- 观察信号是否合理
- 确认止损止盈正常

**收盘后（15:30后）：**
- 记录当日交易
- 计算当日盈亏
- 更新交易日志

#### 5. 创建交易日志

**Excel格式：**
| 日期 | 信号类型 | 开仓价 | 平仓价 | 手数 | 盈亏 | 盈亏% | 备注 |
|------|---------|--------|--------|------|------|-------|------|
| 2025-01-15 | 做多1 | 9850 | 9920 | 1 | +700 | +0.71% | 正常交易 |

### ✅ 验证标准（2周后评估）

**继续使用条件（满足任意一条）：**
- [ ] 总收益 > 0（盈利）
- [ ] 胜率 > 50%
- [ ] 最大单笔亏损 < 500元
- [ ] 按计划执行，无人为干预

**停止使用条件（任意一条）：**
- [ ] 累计亏损 > 10%（1000元）
- [ ] 连续亏损 > 5笔
- [ ] 单笔亏损 > 1000元
- [ ] 程序频繁出错

### 📊 阶段8决策点

**2周后评估：**

**情况A：盈利 > 5%，胜率 > 60%**
→ 策略表现优秀，进入阶段9

**情况B：微利或盈亏平衡，胜率 40-60%**
→ 继续观察2周，或回到阶段6优化参数

**情况C：亏损 < 5%，胜率 < 40%**
→ 停止实盘，回到阶段4-6重新优化

**情况D：亏损 > 10%**
→ 立即停止，全面检讨策略

---

## 🎯 阶段9: 正式实盘部署

### 目标
逐步放大资金规模，稳定盈利

### 前提条件

- [ ] 小资金测试至少1个月
- [ ] 总收益 > 10%
- [ ] 胜率 > 55%
- [ ] 连续无重大亏损
- [ ] 策略逻辑完全理解

### 资金管理策略

#### 第1-2月：保守期
- 资金：2万元
- 仓位：1手固定
- 加仓：禁用
- 目标：稳定盈利 > 5%/月

#### 第3-4月：成长期
- 资金：5万元
- 仓位：1-2手
- 加仓：可测试 pyramid（保守加仓）
- 目标：月收益 > 8%

#### 第5-6月：扩展期
- 资金：10万元
- 仓位：最大5手
- 加仓：可使用 aggressive_pyramid
- 目标：月收益 > 10%

### 风险控制规则

**单日止损：**
- 日亏损 > 3% → 停止交易当日
- 日亏损 > 5% → 停止交易3天
- 周亏损 > 10% → 停止交易1周

**回撤控制：**
- 总回撤 > 15% → 减少仓位50%
- 总回撤 > 25% → 停止交易，全面检讨

**盈利保护：**
- 每月盈利 > 15% → 提取盈利的50%
- 每季度盈利 > 50% → 提取盈利的70%

### 每周评估

**周日晚上复盘：**
1. 本周交易回顾
2. 盈亏分析
3. 策略表现评估
4. 下周交易计划

**记录内容：**
- 周收益率
- 胜率
- 最大单笔盈亏
- 交易次数
- 是否按计划执行

---

## 📊 阶段10: 监控和优化

### 目标
持续监控策略表现，及时优化调整

### 日常监控

#### 1. 实时监控（交易时段）

**自动化监控脚本** `monitor_strategy.py`:
```python
# 每5分钟检查一次
while True:
    # 检查连接状态
    # 检查持仓情况
    # 检查当日盈亏
    # 检查是否异常
    time.sleep(300)
```

#### 2. 每日总结

**晚上记录：**
- 当日交易明细
- 盈亏金额和百分比
- 信号质量评估
- 是否有改进点

#### 3. 每周分析

**分析内容：**
- 周收益曲线
- 交易频率是否正常
- 止损止盈是否合理
- 参数是否需要调整

#### 4. 每月优化

**优化检查：**
- 重新运行回测（最近3个月数据）
- 对比实盘表现 vs 回测表现
- 如果差异 > 20% → 需要优化参数
- 测试新的加仓策略

### 持续改进

#### 市场环境变化适应

**震荡市：**
- 提高信号阈值
- 收紧止损
- 减少交易频率

**趋势市：**
- 放宽信号条件
- 启用加仓
- 适当放宽止损

#### 参数漂移检测

每月运行：
```bash
python backtesting/optimizer.py --start 最近3个月
```

如果新的最优参数与当前参数差异 > 20%：
→ 考虑调整参数

### 预警机制

**自动预警条件：**
- 连续亏损 3 笔
- 单日亏损 > 3%
- 连接断开 > 10分钟
- 程序异常退出

**预警方式：**
- 邮件通知
- 微信/钉钉通知
- 手机短信（重要预警）

---

## 📋 检查清单总结

### 各阶段通过标准

| 阶段 | 关键指标 | 最低标准 | 建议标准 |
|------|---------|----------|----------|
| 0.环境 | 依赖安装 | 100% | 100% |
| 1.数据 | 数据完整性 | > 90% | > 95% |
| 2.指标 | 计算正确 | 100% | 100% |
| 3.逻辑 | 信号正确 | 100% | 100% |
| 4.回测 | 夏普比率 | > 0.3 | > 0.5 |
| 5.加仓 | 收益提升 | > 0% | > 20% |
| 6.优化 | 夏普提升 | > 10% | > 30% |
| 7.模拟 | 运行稳定 | 3天 | 7天 |
| 8.小资金 | 盈亏 | >= 0 | > 5% |
| 9.实盘 | 月收益 | > 3% | > 10% |

---

## 🚨 紧急情况处理

### 情况1：程序崩溃
1. 立即手动平仓
2. 保存日志文件
3. 分析崩溃原因
4. 修复后重启

### 情况2：网络断线
1. 检查持仓
2. 确认订单状态
3. 如有必要，手动交易
4. 恢复连接后重启程序

### 情况3：异常亏损
1. 立即停止策略
2. 检查交易记录
3. 分析亏损原因
4. 决定是否继续使用

### 情况4：重大利好/利空
1. 暂停自动交易
2. 评估市场影响
3. 决定是否手动干预
4. 市场稳定后恢复

---

## 📞 支持资源

### 技术支持
- 查看文档：`README.md`, `QUICKSTART.md`, `SCALING_STRATEGY_GUIDE.md`
- GitHub Issues
- 技术交流群

### 学习资源
- VNPy官方文档
- RQData文档
- 量化交易书籍推荐

---

## ✅ 最后检查

在进入实盘前，确认：

- [ ] 完全理解策略逻辑
- [ ] 回测数据充分（至少3个月）
- [ ] 模拟交易成功（至少1周）
- [ ] 风险承受能力充足
- [ ] 止损规则明确
- [ ] 资金管理计划清晰
- [ ] 应急预案准备好

---

**⚠️ 记住：量化交易不是稳赚不赔！**
- 历史表现不代表未来
- 市场在不断变化
- 风险控制永远第一
- 保持学习和改进

**🎯 祝您交易顺利，稳定盈利！**

---

**下一步：从阶段0开始执行计划**

运行第一个验证命令：
```bash
conda activate vnpyenv
python --version
```

完成后向我报告结果，我们继续下一步！

