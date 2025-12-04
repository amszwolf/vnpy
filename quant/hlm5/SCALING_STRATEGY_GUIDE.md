# HLM5 加仓策略使用指南

## 📖 概述

HLM5 策略现已集成完整的加仓策略功能，支持5种不同的加仓模式。加仓策略可以在趋势明确时逐步增加仓位，提高盈利潜力。

## ✨ 功能特性

### 支持的加仓模式

1. **pyramid** (金字塔加仓)
   - 序列: [4, 3, 2, 1]
   - 特点: 逐步减少加仓手数，降低风险
   
2. **inverse_pyramid** (倒金字塔加仓)
   - 序列: [1, 2, 3, 4]
   - 特点: 逐步增加加仓手数，激进策略

3. **linear** (线性加仓)
   - 序列: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
   - 特点: 每次固定1手，稳定均衡

4. **fixed_fraction** (固定比例加仓)
   - 序列: [2, 2, 2, 2, 2]
   - 特点: 每次固定2手

5. **aggressive_pyramid** (激进金字塔) ⭐ **推荐**
   - 序列: [5, 3, 2]
   - 特点: 盈利1%后加仓，移动止损1.5%
   - 适合: OI等趋势性品种

### 加仓条件

1. **price_move** (价格移动)
   - 价格朝有利方向移动超过阈值时加仓
   - pyramid, inverse_pyramid, linear, fixed_fraction 使用

2. **signal_confirm** (信号确认)
   - 出现新的同向信号时加仓

3. **profit_threshold** (盈利阈值) ⭐ **推荐**
   - 未实现盈亏达到阈值时加仓
   - aggressive_pyramid 使用
   - 更保守，确保盈利后再加仓

### 风险控制

- **移动止损**: 回撤超过设定百分比时强制平仓
- **最大持仓**: 限制总持仓手数，防止过度交易
- **加仓层级限制**: 控制加仓次数

---

## 🚀 快速开始

### 1. 启用加仓策略（回测）

```python
from strategies.hlm5_strategy import HLM5Strategy
from vnpy_ctastrategy.backtesting import BacktestingEngine

# 创建回测引擎
engine = BacktestingEngine()

# 设置回测参数
engine.set_parameters(
    vt_symbol="OI888.CZCE",
    interval=Interval.MINUTE_5,
    start=datetime(2025, 1, 1),
    end=datetime(2025, 1, 31),
    # ... 其他参数
)

# 策略配置：启用加仓
strategy_setting = {
    'enable_scaling': True,              # 启用加仓
    'scaling_method': 'aggressive_pyramid',  # 加仓方式
    'max_position': 10,                  # 最大持仓10手
    'scaling_threshold': 0.01,           # 盈利1%后加仓
    'scaling_trailing_stop': 0.015,      # 移动止损1.5%
}

# 添加策略并运行
engine.add_strategy(HLM5Strategy, strategy_setting)
engine.load_data()
engine.run_backtesting()
```

### 2. 启用加仓策略（模拟交易）

```python
# 在 paper_trading.py 中修改策略配置

strategy_setting = {
    'enable_scaling': True,
    'scaling_method': 'aggressive_pyramid',
    'max_position': 10,
    'scaling_threshold': 0.01,
    'scaling_trailing_stop': 0.015,
    'fixed_size': 1,
    'enable_bidirectional': True,
    'hold_overnight': False
}

cta_engine.add_strategy(
    "HLM5Strategy",
    strategy_name,
    vt_symbol,
    strategy_setting
)
```

### 3. 固定仓位模式（默认）

如果不想使用加仓，保持默认配置即可：

```python
strategy_setting = {
    'enable_scaling': False,    # 不启用加仓
    'fixed_size': 1,            # 固定1手
    # ... 其他参数
}
```

---

## 📊 加仓策略参数说明

### 核心参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_scaling` | bool | False | 是否启用加仓策略 |
| `scaling_method` | str | 'aggressive_pyramid' | 加仓方式 |
| `max_position` | int | 10 | 最大持仓手数 |
| `scaling_threshold` | float | 0.01 | 加仓阈值（盈利百分比）|
| `scaling_trailing_stop` | float | 0.015 | 移动止损百分比 |

### 预定义配置

使用预定义配置：

```python
from utils.scaling_strategy import SCALING_CONFIGS

# 查看所有预定义配置
for name, config in SCALING_CONFIGS.items():
    print(f"{name}: {config}")

# 使用预定义配置
strategy_setting = {
    'enable_scaling': True,
    'scaling_method': 'aggressive_pyramid',  # 使用预定义
    # ... 其他参数
}
```

---

## 💡 使用建议

### 1. aggressive_pyramid 适用场景

**推荐用于：**
- OI、RB 等趋势性强的期货品种
- 日内交易（强制平仓前收盘）
- 有明确趋势的市场环境

**参数建议：**
```python
{
    'enable_scaling': True,
    'scaling_method': 'aggressive_pyramid',
    'max_position': 10,           # 10手限制
    'scaling_threshold': 0.01,    # 盈利1%加仓
    'scaling_trailing_stop': 0.015  # 1.5%移动止损
}
```

### 2. pyramid 适用场景

**推荐用于：**
- 波动较大的品种
- 需要更保守的风险控制
- 市场趋势不明确时

**参数建议：**
```python
{
    'enable_scaling': True,
    'scaling_method': 'pyramid',
    'max_position': 10,
    'scaling_threshold': 0.005,   # 0.5%价格移动
    'scaling_trailing_stop': 0.02   # 2%移动止损
}
```

### 3. linear 适用场景

**推荐用于：**
- 小资金账户
- 测试和学习阶段
- 希望平均成本的场景

**参数建议：**
```python
{
    'enable_scaling': True,
    'scaling_method': 'linear',
    'max_position': 10,
    'scaling_threshold': 0.003,   # 0.3%频繁加仓
    'scaling_trailing_stop': 0.02
}
```

---

## 🧪 测试对比

运行测试脚本对比加仓 vs 固定仓位：

```bash
cd quant/hlm5
python examples/test_scaling_strategy.py
```

输出示例：
```
====================================
性能对比：加仓 vs 固定仓位
====================================

指标                 加仓模式              固定仓位              差异
--------------------------------------------------------------------------------
总收益率             32.45%               24.73%               +7.72%
夏普比率             0.612                0.504                +0.108
最大回撤             -10.23%              -8.32%               -1.91%
总交易次数           145                  145

====================================
✅ 加仓策略表现更优：收益更高且风险调整后收益更好
```

---

## ⚠️ 风险提示

### 1. 加仓策略风险

- **放大亏损**: 如果趋势判断错误，加仓会放大亏损
- **资金占用**: 最大持仓10手需要足够的保证金
- **滑点成本**: 多次交易会增加滑点和手续费

### 2. 使用建议

✅ **推荐做法：**
- 先在回测中充分测试
- 使用 SimNow 模拟账户验证
- 小资金实盘测试
- 根据品种特性调整参数

❌ **避免做法：**
- 不经测试直接实盘
- 在震荡市场使用激进加仓
- 超过风险承受能力的最大持仓
- 忽略移动止损

### 3. 资金管理

以10万元资金为例：

- **固定仓位 (1手)**
  - OI保证金: ~8,000元
  - 仓位占比: ~8%
  - 风险: 低

- **加仓策略 (最大10手)**
  - OI保证金: ~80,000元
  - 仓位占比: ~80%
  - 风险: 高

**建议:** 根据账户资金调整 `max_position` 参数。

---

## 📈 性能优化

### 1. 优化加仓阈值

```python
# 更保守（盈利2%才加仓）
'scaling_threshold': 0.02

# 更激进（盈利0.5%就加仓）
'scaling_threshold': 0.005
```

### 2. 优化移动止损

```python
# 更紧的止损（1%）
'scaling_trailing_stop': 0.01

# 更宽松的止损（3%）
'scaling_trailing_stop': 0.03
```

### 3. 自定义加仓序列

```python
from utils.scaling_strategy import ScalingConfig

# 创建自定义配置
custom_config = ScalingConfig(
    scaling_method='custom',
    max_position=15,
    scaling_sequence=[6, 4, 3, 2],  # 自定义序列
    add_position_condition='profit_threshold',
    add_position_threshold=0.015,    # 1.5%
    use_trailing_stop=True,
    trailing_stop_pct=0.02
)
```

---

## 🔧 故障排查

### 问题1: 加仓策略未生效

**检查：**
```python
# 确认 enable_scaling = True
strategy_setting = {
    'enable_scaling': True,  # 必须设为 True
    # ...
}
```

### 问题2: 加仓频率过高/过低

**调整加仓阈值：**
```python
# 频率过高 → 提高阈值
'scaling_threshold': 0.02  # 从0.01改为0.02

# 频率过低 → 降低阈值
'scaling_threshold': 0.005  # 从0.01改为0.005
```

### 问题3: 回撤过大

**收紧移动止损：**
```python
# 从1.5%改为1%
'scaling_trailing_stop': 0.01
```

---

## 📚 相关文档

- [README.md](README.md) - 项目完整说明
- [QUICKSTART.md](QUICKSTART.md) - 快速入门
- [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - 实施指南

---

## 💬 技术支持

如有问题，请：
1. 查看本文档的故障排查部分
2. 运行测试脚本验证功能
3. 提交 GitHub Issue

---

**⚡ 享受加仓策略带来的增强收益！记住：风险与收益并存。**

