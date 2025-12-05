# HLM5策略架构差异分析及解决方案

**创建时间**: 2025-12-05  
**状态**: 分析完成，待讨论方案

---

## 📋 问题概述

用户发现从 `hlm5-standalone` 移植到 `hlm5 (VNPy)` 时存在根本性的数据架构差异，导致指标计算结果可能不一致。

---

## 🔍 核心差异对比

### 1. **hlm5-standalone 架构 (批量向量化)**

#### 数据流向
```
MySQL数据库 
  ↓ (一次性加载全部历史数据)
SQLite (trading_signals.db)
  ↓ (pandas.DataFrame, 全部历史)
指标计算 (pandas向量化操作)
  ↓ (一次性计算全部)
入场/出场信号 (pandas向量化操作)
  ↓ (一次性计算全部)
回测结果 (pandas向量化计算盈亏)
```

#### 核心特点
✅ **优点**:
- **向量化计算**: 使用`pandas`和`talib`的向量化操作，一次性计算全部历史数据
- **全局视野**: 所有指标都能看到完整的历史数据
- **计算精度高**: Prophet可以使用完整历史数据训练一次模型，然后一次性预测
- **易于优化**: 数据存储在SQLite中，可随时查询中间结果
- **快速回测**: 向量化操作比逐bar循环快得多

⚠️ **限制**:
- **内存占用大**: 所有数据都在内存中
- **不适合实盘**: 无法处理流式数据
- **难以实时更新**: 每次新增数据需要重新计算

#### 代码示例
```python
# hlm5_all_parallel.py 的工作方式

# 1. 一次性加载数据
df = db.get_data(ticker, start_date, end_date, columns=['close'])
# df 是完整的 DataFrame，包含所有历史数据

# 2. 一次性计算MACD (向量化)
dif, dea, hist = talib.MACD(df['close'], 
                             fastperiod=8, slowperiod=20, signalperiod=5)
# 结果是完整的Series，与df同长度

# 3. 一次性计算交叉信号 (向量化循环)
for i in range(1, len(series)):
    if dif.iloc[i] > dea.iloc[i] and dif.iloc[i-1] <= dea.iloc[i-1]:
        cross_1.iloc[i-1] = 1.0  # 可以回看i-1
# 可以随时访问任意历史数据点

# 4. Prophet一次性训练和预测
prophet_df = df[['datetime', 'close']].rename(columns={'datetime': 'ds', 'close': 'y'})
model = Prophet()
model.fit(prophet_df)  # 使用全部历史数据训练
forecast = model.predict(future)  # 一次性预测未来
```

---

### 2. **hlm5 (VNPy) 架构 (流式事件驱动)**

#### 数据流向
```
VNPy数据库 / RQData
  ↓ (load_data: 一次性加载)
BacktestingEngine.history_data
  ↓ (逐bar回放)
on_bar() / on_5min_bar()
  ↓ (ArrayManager缓存固定长度历史)
calculate_all_indicators()
  ↓ (基于am的最新N根bar计算)
check_entry_conditions()
  ↓ (基于当前bar的指标值)
交易执行
```

#### 核心特点
✅ **优点**:
- **事件驱动**: 适合实盘交易，每个bar触发一次
- **内存高效**: 只缓存固定长度的历史数据（如100或200根bar）
- **实盘回测一致**: 回测和实盘使用相同的代码逻辑
- **易于调试**: 可以在每个bar打印当前状态
- **风险控制**: 无法"未卜先知"（look-ahead bias）

⚠️ **限制**:
- **逐bar计算**: 每个bar都要重新计算指标，效率低
- **历史数据受限**: ArrayManager只保留最近N根bar
- **复杂模型困难**: Prophet这样的模型需要大量历史数据训练

#### 代码示例
```python
# hlm5_strategy.py 的工作方式

# 1. 初始化时ArrayManager为空
self.am = ArrayManager(size=200)  # 只保留最近200根bar

# 2. 每个bar触发on_5min_bar
def on_5min_bar(self, bar: BarData):
    self.am.update_bar(bar)  # 只添加当前bar，丢弃最老的bar
    
    if not self.am.inited:  # 前200根bar只是初始化
        return
    
    # 3. 基于am的200根bar计算指标
    self.calculate_all_indicators()  # 只能看到最近200根
    
    # 4. 立即根据当前指标做交易决策
    self.execute_trading_logic()

# 5. 指标计算限制
def calculate_all_indicators(self):
    # 只能访问am中的200根bar
    close = self.am.close  # ndarray, shape=(200,)
    
    # MACD计算 - 只基于最近200根
    price_signals = calculate_macd_signals(
        pd.Series(close[-60:]),  # 只用最近60根计算
        ...
    )
    
    # Prophet? - 无法使用，需要至少几百根甚至上千根bar
    # 且每个bar都要重新训练，效率极低
```

---

## 🎯 关键差异汇总表

| 维度 | hlm5-standalone | hlm5 (VNPy) |
|------|----------------|------------|
| **数据加载** | 一次性加载全部 | 逐bar流式传入 |
| **数据视野** | 全部历史数据 | 最近N根bar (100-200) |
| **计算方式** | 向量化（pandas） | 逐bar事件驱动 |
| **指标计算** | 一次性计算全部 | 每bar重新计算 |
| **Prophet** | 一次训练，全局预测 | ❌ 几乎不可行 |
| **Cross信号** | 可回看任意历史 | 只能回看am范围内 |
| **计算效率** | ⚡ 极快（向量化） | 🐢 较慢（循环） |
| **内存占用** | 📈 高（全部数据） | 📊 低（固定大小） |
| **实盘适用** | ❌ 不适合 | ✅ 完全适合 |
| **回测速度** | ⚡ 快（分钟级） | 🐢 慢（可能需要小时） |

---

## 🔧 已发现的具体差异点

### 差异1: Cross信号计算

**Standalone版本**:
```python
# 可以在i位置回看i-1
for i in range(1, len(series)):
    if dif.iloc[i] > dea.iloc[i] and dif.iloc[i-1] <= dea.iloc[i-1]:
        cross_1.iloc[i-1] = 1.0  # 信号记录在i-1位置
```

**VNPy版本 (之前的BUG)**:
```python
# 只能看到最新的值
self.price_cross = price_signals['Cross_1'].iloc[-1]  # ❌ 总是0
```

**VNPy版本 (修复后)**:
```python
# 需要缓存前一个bar的信号
self.price_cross = price_signals['Cross_1'].iloc[-1]
self.prev_price_cross = price_signals['Cross_1'].iloc[-2]  # 实际信号在这里
```

### 差异2: Prophet预测

**Standalone版本**:
```python
# 可以使用全部历史数据训练一次
def process_prophet(db, ticker, start_date=None, end_date=None):
    df = db.get_data(ticker)  # 全部数据
    
    prophet_df = df[['datetime', 'close']].rename(...)
    model = Prophet(...)
    model.fit(prophet_df)  # 一次训练，用全部历史
    
    forecast = model.predict(future)  # 一次性预测
    # 将预测结果写回数据库
    db.update_data(...)
```

**VNPy版本 (当前状态)**:
```python
# ❌ 无法实现
# 1. ArrayManager只有200根bar，不够训练
# 2. 每个bar都训练一次太慢
# 3. Prophet需要DataFrame格式，am只提供ndarray

# 临时解决方案：禁用Prophet
self.prophet_yhat = 0.0
self.prophet_phase = 0
self.prophet_cross = 0
```

### 差异3: 指标计算窗口

**Standalone版本**:
```python
# MACD可以使用任意长度的历史数据
signals = calculate_macd_signals(
    df['close'],  # 可能是几千根bar
    macd_long=20, macd_mid=8, macd_short=5
)
```

**VNPy版本**:
```python
# 受限于ArrayManager的大小
close = self.am.close  # 最多200根
signals = calculate_macd_signals(
    pd.Series(close[-60:]),  # 只用60根，因为MACD需要的历史有限
    macd_long=20, macd_mid=8, macd_short=5
)
```

---

## 💡 解决方案

### 方案A: **保持当前架构（推荐用于实盘）** ⭐

**适用场景**: 实盘交易、纸上交易、常规回测

**核心思路**: 接受VNPy的事件驱动架构，优化算法适应流式数据

#### A1. 简化指标系统
```python
✅ 保留：Price MACD (需要历史较短)
✅ 保留：Volume MACD (需要历史较短)
✅ 保留：HLBW (lookback=40根足够)
❌ 移除：Prophet (需要太多历史数据)
```

#### A2. 增加ArrayManager大小
```python
# 当前: size=100 (不够)
self.am = ArrayManager(size=100)

# 建议: size=300-500
self.am = ArrayManager(size=500)  # 足够容纳MACD+HLBW的历史需求
```

#### A3. 优化指标计算频率
```python
# 不是每个bar都重新计算全部指标
# 只在必要时更新

def on_5min_bar(self, bar: BarData):
    self.am.update_bar(bar)
    
    # 增量更新指标
    self._update_macd_incremental()  # 只计算最新一根bar的MACD
    self._update_hlbw_incremental()  # 只计算最新一根bar的HLBW
```

#### A4. 预计算策略
```python
# 在on_init时批量加载历史数据
def on_init(self):
    self.write_log("策略初始化")
    
    # 加载足够的历史数据（如10天）
    self.load_bar(10)
    
    # 此时am已经填充了历史数据
    # 初始计算一次完整指标
    self.calculate_all_indicators()
```

#### 优点
- ✅ 完全兼容VNPy框架
- ✅ 实盘和回测逻辑一致
- ✅ 无look-ahead bias
- ✅ 易于调试和监控

#### 缺点
- ⚠️ 无法使用Prophet
- ⚠️ 回测速度较慢
- ⚠️ 历史数据有限

---

### 方案B: **混合架构（推荐用于高级回测）** ⭐⭐

**适用场景**: 需要Prophet、大量历史数据、快速回测、参数优化

**核心思路**: 回测时预计算所有指标，实盘时使用事件驱动

#### B1. 回测模式：预计算指标
```python
class HLM5Strategy(CtaTemplate):
    def __init__(self, ...):
        self.backtest_mode = False  # 是否回测模式
        self.precomputed_indicators = None  # 预计算的指标DataFrame
    
    def on_init(self):
        if self.is_backtesting():  # 检测是否在回测
            self.backtest_mode = True
            self._precompute_all_indicators()  # 预计算
    
    def _precompute_all_indicators(self):
        """预计算所有指标（仅回测时）"""
        # 1. 从数据库加载全部历史数据
        bars = self.load_all_historical_bars()
        df = pd.DataFrame(bars)
        
        # 2. 使用standalone的向量化方法计算指标
        df = self._calculate_indicators_vectorized(df)
        
        # 3. 计算Prophet（如果需要）
        df = self._calculate_prophet_vectorized(df)
        
        # 4. 存储预计算结果
        self.precomputed_indicators = df
        self.write_log("预计算完成：{} 根bar".format(len(df)))
    
    def on_5min_bar(self, bar: BarData):
        if self.backtest_mode:
            # 回测模式：直接查询预计算结果
            indicators = self.precomputed_indicators.loc[bar.datetime]
            self.price_macd = indicators['Price_MACD']
            self.price_cross = indicators['Price_Cross']
            self.prophet_yhat = indicators['PH_yhat']
            # ...
        else:
            # 实盘模式：逐bar计算
            self.am.update_bar(bar)
            if not self.am.inited:
                return
            self.calculate_all_indicators()
        
        # 交易逻辑（统一）
        self.execute_trading_logic()
```

#### B2. Prophet集成
```python
def _calculate_prophet_vectorized(self, df):
    """批量计算Prophet预测（仅回测）"""
    prophet_df = df[['close']].reset_index()
    prophet_df.columns = ['ds', 'y']
    
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05
    )
    model.fit(prophet_df)
    
    future = model.make_future_dataframe(periods=20, freq='5T')
    forecast = model.predict(future)
    
    df['PH_yhat'] = forecast['yhat'].values[:len(df)]
    df['PH_yhat_lower'] = forecast['yhat_lower'].values[:len(df)]
    df['PH_yhat_upper'] = forecast['yhat_upper'].values[:len(df)]
    
    # 计算Prophet MACD
    prophet_signals = calculate_macd_signals(df['PH_yhat'], ...)
    df['PH_Cross'] = prophet_signals['Cross_1']
    # ...
    
    return df
```

#### B3. 实盘模式降级
```python
def on_start(self):
    """策略启动"""
    if not self.backtest_mode:
        # 实盘模式：禁用Prophet
        self.use_prophet = False
        self.write_log("实盘模式：Prophet已禁用")
```

#### 优点
- ✅ 回测速度快（向量化）
- ✅ 可以使用Prophet
- ✅ 实盘时自动降级
- ✅ 灵活性高

#### 缺点
- ⚠️ 代码复杂度增加
- ⚠️ 需要维护两套计算逻辑
- ⚠️ 实盘和回测可能有差异

---

### 方案C: **完全独立回测引擎（用于研究）**

**适用场景**: 纯研究、策略开发、快速迭代

**核心思路**: 保留standalone的向量化回测，VNPy只用于实盘

#### C1. 研发流程
```
开发阶段：
  hlm5-standalone (向量化回测) 
    ↓ 快速迭代、参数优化
  找到最优参数
    ↓
  移植到VNPy (保留核心逻辑)
    ↓ 纸上交易验证
  实盘交易
```

#### C2. 代码组织
```
quant/hlm5-standalone/  # 研究环境
  ├── hlm5_all_parallel.py  # 向量化回测（保留）
  ├── trading_signals.db    # SQLite数据库
  └── run_*.py              # 各种测试脚本

quant/hlm5/  # 生产环境
  ├── strategies/hlm5_strategy.py  # 事件驱动策略（移植）
  ├── backtesting/run_backtest.py  # VNPy回测（验证用）
  └── trading/paper_trading.py     # 纸上/实盘交易
```

#### 优点
- ✅ 研发效率最高
- ✅ 两边代码独立，互不干扰
- ✅ 向量化回测极快

#### 缺点
- ⚠️ 需要维护两套代码
- ⚠️ 移植时需要注意差异
- ⚠️ 回测和实盘可能有偏差

---

## 📊 VNPy数据架构详解

### 回测 vs 优化 vs 实盘

| 场景 | 数据来源 | 数据加载方式 | 数据传递 |
|------|---------|-------------|---------|
| **回测** | 本地数据库/RQData | `load_data()` 一次性加载 | `run_backtesting()` 逐bar回放 |
| **优化** | 本地数据库/RQData | `load_data()` 一次性加载 | 多进程并行，每个进程独立回放 |
| **实盘** | 交易接口实时行情 | `load_bar()` 加载初始历史 | 实时tick/bar触发 `on_bar()` |

### 数据流详解

#### 1. 回测时的数据流
```python
# run_backtest.py
engine = BacktestingEngine()
engine.set_parameters(...)
engine.add_strategy(HLM5Strategy, {...})

# 步骤1: load_data() - 一次性加载
engine.load_data()
# → 从数据库查询start到end的所有bar
# → 存储在 engine.history_data: dict[(datetime, symbol)] = BarData

# 步骤2: run_backtesting() - 逐bar回放
engine.run_backtesting()
# → for each datetime in sorted(dts):
#      strategy.on_bar(bar)  # 模拟逐bar到达
#      strategy.on_5min_bar(bar)  # 触发策略逻辑

# 步骤3: calculate_result() - 统计结果
stats = engine.calculate_result()
```

#### 2. 优化时的数据流
```python
# optimizer.py
setting = OptimizationSetting()
setting.set_target("sharpe_ratio")
setting.add_parameter("price_macd_long", 15, 25, 1)

engine.run_optimization(setting)
# → 生成多个参数组合
# → 每个组合启动一个独立的BacktestingEngine
# → 多进程并行执行回测
# → 汇总结果，找到最优参数
```

#### 3. 实盘时的数据流
```python
# paper_trading.py
cta_engine.init_engine()
cta_engine.add_strategy(HLM5Strategy, {...})

# 步骤1: on_init() - 初始化
strategy.on_init()
# → strategy.load_bar(10)  # 加载最近10天历史
# → 逐bar回放这10天数据，初始化ArrayManager

# 步骤2: on_start() - 启动策略
strategy.on_start()

# 步骤3: 实时行情到达
# → 交易接口推送tick: on_tick(tick)
# → BarGenerator聚合为bar: on_bar(bar)
# → 策略接收5min bar: on_5min_bar(bar)
# → 执行交易逻辑
```

---

## 🎯 推荐方案总结

### 短期方案（立即实施）：**方案A**

1. **增加ArrayManager大小**
   ```python
   self.am = ArrayManager(size=500)  # 从100增加到500
   ```

2. **暂时禁用Prophet**
   ```python
   # 已实现，保持现状
   self.prophet_yhat = 0.0
   ```

3. **优化指标缓存**
   ```python
   # 已实现 prev_cross 缓存机制
   self.prev_price_cross = price_signals['Cross_1'].iloc[-2]
   ```

4. **增加load_bar天数**
   ```python
   def on_init(self):
       self.load_bar(20)  # 从10天增加到20天
   ```

**预期效果**:
- ✅ 回测结果更准确
- ✅ 指标计算更可靠
- ✅ 代码复杂度低
- ⚠️ 但无法使用Prophet

---

### 中期方案（下一阶段）：**方案B混合架构**

1. **实现回测预计算模式**
   - 检测是否在回测环境
   - 回测时预计算所有指标（向量化）
   - 实盘时逐bar计算

2. **集成Prophet（仅回测）**
   - 回测时一次性训练Prophet
   - 实盘时禁用Prophet或使用缓存

3. **性能优化**
   - 向量化计算提速
   - 多进程优化支持

**预期效果**:
- ✅ 回测速度提升10-100倍
- ✅ 可以使用Prophet
- ✅ 支持大规模参数优化
- ✅ 实盘时自动降级

---

### 长期方案（未来规划）：**方案C独立引擎**

1. **保持standalone引擎用于研发**
2. **VNPy专注于实盘交易**
3. **建立标准化移植流程**

---

## 📝 具体实施建议

### 立即可做（本周）

1. **测试ArrayManager大小影响**
   ```bash
   # 测试不同size对回测结果的影响
   python run_backtest.py --am-size 100
   python run_backtest.py --am-size 200
   python run_backtest.py --am-size 500
   ```

2. **对比standalone和VNPy的指标值**
   ```python
   # 导出两边的中间数据CSV
   # 对比同一时间点的MACD、HLBW值是否一致
   ```

3. **文档化差异点**
   - 记录所有发现的差异
   - 建立测试用例

### 下周开始（如需要）

1. **实现方案B的预计算框架**
2. **集成Prophet（回测模式）**
3. **性能测试和优化**

---

## ❓ 待讨论的问题

1. **是否需要Prophet？**
   - 如果Prophet信号确实提升了策略表现，需要实现方案B
   - 如果影响不大，可以永久禁用，简化架构

2. **回测速度要求？**
   - 如果需要大量参数优化（数千次回测），建议方案B或C
   - 如果只是验证策略，方案A足够

3. **实盘部署时间？**
   - 如果近期就要实盘，建议方案A（稳定优先）
   - 如果还有充裕时间，可以尝试方案B

4. **历史数据依赖？**
   - 除了Prophet，其他指标需要多少历史数据？
   - ArrayManager size=500是否足够？

---

## 📌 结论

当前架构差异是**设计哲学的不同**，不是bug：
- **Standalone**: 研究导向，向量化，全局视野
- **VNPy**: 实盘导向，事件驱动，流式处理

**两者各有优势，可以共存**：
- 用Standalone做策略研发和快速回测
- 用VNPy做实盘验证和真实交易

目前的修复已经解决了**代码层面的bug**（Cross信号取值错误），但**架构层面的差异**需要通过上述方案来处理。

**建议优先级**:
1. 🔥 立即：增加ArrayManager大小，验证指标一致性
2. ⭐ 短期：实现方案A的全部优化
3. 💡 中期：如需Prophet，实现方案B
4. 🚀 长期：完善方案C的研发流程

---

**文档作者**: AI Assistant  
**审阅人**: 待定  
**下一步**: 用户决策选择方案

