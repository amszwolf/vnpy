# HLM5 多指标融合量化交易策略

## 📖 项目简介

HLM5 是一个基于 VNPy 框架的多指标融合量化交易策略，专为期货市场（特别是菜油OI合约）设计。

该策略整合了以下核心技术指标：
- **Price MACD**: 价格动量分析
- **Volume MACD**: 成交量动量分析  
- **HLBW**: 高低带宽趋势分析
- **Prophet**: 时间序列预测

## ✨ 核心特性

### 🎯 策略特点
- ✅ **多指标融合**: 4大核心指标协同判断
- ✅ **双向交易**: 支持做多和做空
- ✅ **日内交易**: 收盘前强制平仓，无隔夜风险
- ✅ **智能信号**: 6级信号强度分类
- ✅ **加仓策略**: 支持5种加仓模式（金字塔、激进、线性等） ⭐ **新增**
- ✅ **风险控制**: 止损/止盈/移动止损

### 📊 测试表现
基于2025年1月实测数据：
- **OI.ZCE（菜油）**: 总收益24.73%, 胜率74.31%, 夏普0.504
- **RB.SHF（螺纹钢）**: 总收益19.46%, 胜率75.52%, 最大回撤-0.21%

### 🔧 技术架构
```
quant/hlm5/
├── hlm5_config.py          # 核心配置（已优化参数）
├── futures_config.py       # 期货专用配置
├── strategies/             # 策略实现
│   └── hlm5_strategy.py   # HLM5核心策略
├── backtesting/            # 回测系统
├── data/                   # 数据管理
├── trading/                # 实盘/模拟交易
├── analysis/               # 分析工具
└── utils/                  # 工具模块
```

## 🚀 快速开始

### 🎯 推荐：使用自动化部署测试

我们提供了完整的自动化测试脚本，帮助您从开发到实盘逐步验证：

```bash
# 切换到项目目录
cd quant/hlm5

# 运行阶段0：环境验证
python run_deployment_tests.py --stage 0

# 按照提示逐步执行阶段1-10
```

**详细流程请查看：[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)**

---

### 环境要求
- Python 3.8+
- VNPy 框架
- vnpy_ctastrategy
- vnpy_rqdata (推荐) 或 vnpy_tushare

### 手动安装
```bash
# 激活 vnpyenv 环境
conda activate vnpyenv

# 安装依赖
pip install vnpy vnpy_ctastrategy vnpy_rqdata
pip install talib prophet
```

### 配置数据源

#### 使用 RQData (推荐)
```python
from vnpy.trader.setting import SETTINGS

SETTINGS["datafeed.name"] = "rqdata"
SETTINGS["datafeed.username"] = "your_license_key"
SETTINGS["datafeed.password"] = ""
```

#### 使用 TuShare
```python
SETTINGS["datafeed.name"] = "tushare"
SETTINGS["datafeed.username"] = "your_token"
```

### 运行回测
```bash
cd quant/hlm5
python backtesting/run_backtest.py
```

### 运行模拟交易
```bash
python trading/paper_trading.py
```

## 📋 配置说明

### 核心参数 (`hlm5_config.py`)

#### Price MACD (已优化)
```python
'PRICE_MACD': {
    'macd_long': 20,      # 长期EMA (优化: 26→20)
    'macd_mid': 8,        # 中期EMA (优化: 12→8)
    'macd_short': 5,      # 短期EMA (优化: 9→5)
    'diff_ema_period': 2, # DIFF EMA (优化: 3→2)
}
```

#### Volume MACD (已优化)
```python
'VOLUME_MACD': {
    'macd_long': 20,      # 优化: 26→20
    'macd_mid': 8,        # 优化: 12→8
    'macd_short': 5,      # 优化: 9→5
    'diff_ema_period': 3, # 优化: 5→3
}
```

#### HLBW (已优化)
```python
'HLBW': {
    'lookback_period': 40,  # 回望周期 (优化: 55→40)
    'inner_ema': 3,         # 内层EMA (优化: 5→3)
    'outer_ema': 2,         # 外层EMA (优化: 3→2)
    'trend_ema': 2,         # 趋势EMA (优化: 3→2)
}
```

### 期货配置 (`futures_config.py`)

#### OI 合约规格
- **交易所**: 郑州商品交易所 (CZCE)
- **合约乘数**: 10吨/手
- **最小变动**: 2元/吨
- **保证金率**: 8%
- **手续费率**: 开平各万分之2

#### 交易时段
- **日盘**: 09:00-10:15, 10:30-11:30, 13:30-15:00
- **夜盘**: 21:00-23:00
- **收盘平仓**: 收盘前5分钟强制平仓
- **开盘缓冲**: 禁用（测试证明立即交易效果最佳）

## 📈 策略逻辑

### 入场信号（做多）

策略使用6级入场信号系统，优先级如下：

1. **信号1**: Price↑ + Volume↑ + HLBW↑ + Prophet↑
2. **信号2**: Price↑ + Volume拉升 + HLBW↑ + Prophet↑
3. **信号3**: Price↑ + Volume吸筹 + HLBW↑ + Prophet↑
4. **信号4**: Volume拉升 + Volume↑ + HLBW↑ + Prophet↑
5. **信号5**: Price↑ + Volume↑ + HLBW拉升 + Prophet↑
6. **信号6**: 至少2个Cross信号 + 其他指标配合

### 出场信号

- **反向信号**: 出现反向入场信号
- **止损**: 亏损达到4%
- **止盈**: 盈利达到12%
- **趋势反转**: XLPL阶段转为派发/下跌
- **收盘平仓**: 收盘前5分钟强制平仓

### 双向交易

策略支持完整的双向交易逻辑：
- **持有多仓时**: 检查做多出场 或 反向开空
- **持有空仓时**: 检查做空出场 或 反向开多
- **无持仓时**: 检查做多入场 或 做空入场

## 📊 性能分析

### 关键指标
- **总收益率**: 策略整体收益
- **夏普比率**: 风险调整后收益
- **最大回撤**: 最大资金回撤比例
- **胜率**: 盈利交易占比
- **盈亏比**: 平均盈利/平均亏损

### 查看回测报告
```bash
# 生成性能报告
python analysis/performance_analyzer.py

# 查看可视化图表
# 报告保存在 output/ 目录
```

## 🔧 高级功能

### 参数优化
```bash
# 运行遗传算法优化
python backtesting/optimizer.py
```

### 加仓策略 ⭐ 新增功能

HLM5 策略现已支持完整的加仓策略功能，可在趋势明确时逐步增加仓位。

#### 支持的加仓模式

| 模式 | 加仓序列 | 适用场景 |
|------|----------|----------|
| `pyramid` | [4, 3, 2, 1] | 保守，逐步减仓 |
| **`aggressive_pyramid`** ⭐ | [5, 3, 2] | **推荐**，盈利1%后加仓 |
| `linear` | [1×10] | 稳定，均衡成本 |
| `inverse_pyramid` | [1, 2, 3, 4] | 激进，逐步加仓 |
| `fixed_fraction` | [2×5] | 固定比例 |

#### 启用加仓（回测）

```python
# 在 backtesting/run_backtest.py 中
strategy_setting = {
    'enable_scaling': True,              # 启用加仓
    'scaling_method': 'aggressive_pyramid',  # 加仓方式
    'max_position': 10,                  # 最大持仓10手
    'scaling_threshold': 0.01,           # 盈利1%后加仓
    'scaling_trailing_stop': 0.015,      # 移动止损1.5%
}
```

#### 启用加仓（模拟交易）

```python
# 在 trading/paper_trading.py 中
strategy_setting = {
    'enable_scaling': True,
    'scaling_method': 'aggressive_pyramid',
    'max_position': 10,
    'fixed_size': 1,                     # 固定仓位（未启用加仓时）
}
```

#### 测试加仓效果

```bash
# 运行对比测试
python examples/test_scaling_strategy.py
```

详细说明请参考：[加仓策略使用指南](SCALING_STRATEGY_GUIDE.md)

### 实盘交易
```bash
# 连接实盘账户
python trading/live_trading.py
```

## ⚠️ 风险提示

1. **历史表现不代表未来收益**
2. **期货交易存在杠杆风险**
3. **建议先进行充分回测和模拟交易**
4. **实盘前务必小资金测试**
5. **严格遵守风险管理原则**

## 📚 相关文档

- **[部署计划](DEPLOYMENT_PLAN.md)** 🚀 **推荐！从开发到实盘的完整流程**
- [快速入门指南](QUICKSTART.md)
- [实施指南](IMPLEMENTATION_GUIDE.md)
- [加仓策略使用指南](SCALING_STRATEGY_GUIDE.md) ⭐ **新增**

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📧 联系方式

如有问题，请通过以下方式联系：
- GitHub Issues
- Email: [your-email]

---

**⚡ 基于 VNPy 框架 | 🚀 HLM5 量化团队出品**

