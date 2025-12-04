# VeighNa 量化交易完整框架

这是一个基于VeighNa的完整量化交易框架，包含策略开发、回测、优化、模拟交易、实盘交易和复盘分析等完整功能。

## 目录结构

```
quant/examples/
├── README.md                    # 本文件
├── strategies/                  # 策略目录
│   ├── __init__.py
│   ├── template_strategy.py    # 策略开发模板
│   ├── ma_cross_strategy.py    # 均线交叉策略示例
│   └── dual_ma_strategy.py     # 双均线策略示例
├── backtesting/                # 回测模块
│   ├── __init__.py
│   ├── backtest_engine.py      # 回测引擎封装
│   ├── optimizer.py            # 参数优化工具
│   └── run_backtest.py         # 回测运行脚本
├── trading/                     # 交易模块
│   ├── __init__.py
│   ├── paper_trading.py        # 模拟交易
│   ├── live_trading.py         # 实盘交易
│   └── run_trading.py          # 交易运行脚本
└── analysis/                    # 分析模块
    ├── __init__.py
    ├── performance_analyzer.py # 绩效分析
    ├── report_generator.py     # 报告生成
    └── review_analyzer.py      # 复盘分析
```

## 快速开始

### 1. 策略开发

参考 `strategies/template_strategy.py` 开发自己的策略。

### 2. 策略回测

```python
python backtesting/run_backtest.py
```

### 3. 参数优化

```python
python backtesting/optimizer.py
```

### 4. 模拟交易

```python
python trading/paper_trading.py
```

### 5. 实盘交易

```python
python trading/live_trading.py
```

### 6. 复盘分析

```python
python analysis/review_analyzer.py
```

## 功能特性

- ✅ 策略开发：基于CtaTemplate的完整策略模板
- ✅ 回测引擎：封装BacktestingEngine，简化回测流程
- ✅ 参数优化：支持遗传算法和网格搜索优化
- ✅ 模拟交易：使用PaperAccount进行模拟交易
- ✅ 实盘交易：支持CTA策略实盘自动交易
- ✅ 复盘分析：完整的绩效分析和报告生成

## 依赖模块

```bash
pip install vnpy_ctastrategy
pip install vnpy_ctabacktester
pip install vnpy_paperaccount
```

## 使用说明

详细使用说明请参考各模块的文档和示例代码。

