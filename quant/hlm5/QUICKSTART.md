# HLM5 策略快速入门指南

## 🎯 5分钟快速上手

### 步骤1: 环境准备

```bash
# 激活 vnpyenv 环境
conda activate vnpyenv

# 确认已安装必要依赖
pip list | grep vnpy
pip list | grep talib
pip list | grep prophet
```

### 步骤2: 配置数据源

编辑 VNPy 配置文件或在代码中设置：

```python
from vnpy.trader.setting import SETTINGS

# 使用 RQData (推荐)
SETTINGS["datafeed.name"] = "rqdata"
SETTINGS["datafeed.username"] = "your_rqdata_license"
SETTINGS["datafeed.password"] = ""
```

### 步骤3: 运行第一次回测

```bash
cd quant/hlm5
python backtesting/run_backtest.py
```

## 📖 详细步骤

### 1. 下载历史数据

```bash
# 下载 OI 主力合约数据
python data/download_oi_data.py
```

这将下载：
- **合约**: OI888 (菜油主力)
- **周期**: 5分钟
- **时间**: 2025-01-01 至最新
- **数据源**: RQData 或 TuShare

### 2. 回测策略

#### 基础回测

```bash
python backtesting/run_backtest.py
```

输出示例：
```
====================================
HLM5 策略回测结果
====================================
起始资金: 100,000.00
结束资金: 124,730.00
总收益率: 24.73%
夏普比率: 0.504
最大回撤: -8.32%
胜率: 74.31%
总交易次数: 145
```

#### 自定义回测参数

编辑 `backtesting/run_backtest.py`:

```python
# 修改回测时间段
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 3, 31)

# 修改初始资金
initial_capital = 200000

# 修改合约
vt_symbol = "OI888.CZCE"
```

### 3. 参数优化

```bash
python backtesting/optimizer.py
```

这将使用遗传算法优化以下参数：
- Price MACD 周期
- Volume MACD 周期
- HLBW 回望周期
- 止损/止盈比例

优化结果保存在 `output/optimization_results.csv`

### 4. 模拟交易

#### 使用 PaperAccount (推荐)

```bash
python trading/paper_trading.py
```

#### 使用 SimNow

修改 `trading/paper_trading.py` 中的配置：

```python
simnow_config = {
    "用户名": "your_account",
    "密码": "your_password",
    "经纪商代码": "9999",
    # ...
}
```

### 5. 查看分析报告

```bash
# 生成性能分析报告
python analysis/performance_analyzer.py

# 查看信号分析
python analysis/signal_analyzer.py
```

报告保存在 `output/` 目录：
- `performance_report.html`: 性能分析
- `signal_analysis.html`: 信号质量分析
- `OI888_analysis.html`: 完整回测图表

## 🔧 常见配置

### 修改策略参数

编辑 `hlm5_config.py`:

```python
EQUITY_CONFIG = {
    'INDICATORS': {
        'PRICE_MACD': {
            'macd_long': 20,   # 调整这个值
            'macd_mid': 8,     # 调整这个值
            # ...
        }
    }
}
```

### 修改期货合约

编辑 `futures_config.py`:

```python
FUTURES_SPECS = {
    'OI': {
        'multiplier': 10,      # 合约乘数
        'pricetick': 2,        # 最小变动
        'commission': {
            'open_ratio': 0.00002,  # 手续费率
        }
    }
}
```

### 修改回测周期

编辑 `backtesting/run_backtest.py`:

```python
engine.set_parameters(
    vt_symbol="OI888.CZCE",
    interval="5m",          # 修改为 "1m", "15m", "1h" 等
    start=datetime(2025, 1, 1),
    end=datetime(2025, 6, 30),
    # ...
)
```

## 📊 查看实时状态

### 模拟交易实时监控

运行模拟交易时，终端会实时显示：

```
============================================================
[状态检查] 2025-12-04 15:17:03
[连接] CTP Gateway 交易接口已连接
[连接] CTP Gateway 行情接口已连接
[策略] HLM5_OI888_Paper 运行中
[策略] 持仓: 2手 (多)
[策略] 当前盈亏: +1,234.56元
============================================================

[行情数据] OI888.CZCE
  时间: 2025-12-04 15:17:05
  价格: 9,856.00 (+24.00)
  成交量: 156,234
  持仓量: 234,567
============================================================
```

### 查看策略变量

在 VNPy Trader GUI 中：
1. 点击【功能】→【CTA策略】
2. 选择 HLM5_OI888_Paper
3. 查看实时指标值：
   - price_macd
   - volume_macd
   - hlbw_trend
   - 当前持仓
   - 盈亏情况

## 🐛 故障排查

### 问题1: 无法连接数据源

**症状**: `Unable to load datafeed module`

**解决**:
```bash
# 安装 RQData
pip install vnpy_rqdata

# 或安装 TuShare
pip install vnpy_tushare
```

### 问题2: 回测无数据

**症状**: `Warning: No data found for OI888.CZCE`

**解决**:
```bash
# 手动下载数据
python data/download_oi_data.py

# 检查数据库
python -c "from data.download_oi_data import check_database; check_database()"
```

### 问题3: 策略不生成信号

**症状**: 策略运行但无交易

**解决**:
1. 检查是否在交易时段内
2. 查看日志确认指标计算是否正常
3. 降低信号阈值：编辑 `hlm5_config.py`:
   ```python
   'min_cross_signals': 1  # 从 2 改为 1
   ```

### 问题4: Prophet 计算太慢

**症状**: 每个Bar计算超过1秒

**解决**:
1. 减少预测周期：
   ```python
   'periods': 10  # 从 20 改为 10
   ```
2. 或禁用 Prophet:
   ```python
   'PROPHET': {'enable': False}
   ```

## 📈 进阶使用

### 1. 批量回测多个合约

```python
# 创建 batch_backtest.py
symbols = ['OI888', 'RB888', 'M888']
for symbol in symbols:
    run_backtest(symbol)
```

### 2. 实时监控多策略

```python
# 在 paper_trading.py 中添加多个策略实例
strategies = [
    ('HLM5_OI', 'OI888.CZCE'),
    ('HLM5_RB', 'RB888.SHFE'),
]
```

### 3. 自定义信号逻辑

编辑 `strategies/hlm5_strategy.py`:

```python
def check_entry_conditions_long(self):
    # 添加自定义条件
    if self.price_macd > 0 and self.volume_macd > 0:
        return True
    return False
```

## 📚 下一步

- 📖 阅读 [README.md](README.md) 了解完整功能
- 🔧 查看 [策略详细文档](docs/strategy.md)
- 📊 研究 [回测结果分析](docs/backtest_analysis.md)
- 💰 准备 [实盘交易](docs/live_trading.md)

## ❓ 获取帮助

- 📧 Email: [your-email]
- 💬 GitHub Issues
- 📱 微信群: [QR code]

---

**开始你的量化交易之旅！** 🚀

