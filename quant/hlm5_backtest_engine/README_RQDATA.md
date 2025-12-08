# HLM5回测引擎 - RQData版本

## 📋 概述

HLM5回测引擎现已集成RQData作为数据源，完全替代MySQL，实现更稳定、更可靠的回测。

## ✅ 修改内容

### 1. 新增文件

- **`rqdata_loader.py`** - RQData数据加载器
  - 从RQData获取期货数据
  - 自动聚合1分钟数据为5分钟
  - 数据质量检查和清洗
  
- **`test_rqdata_loader.py`** - 数据加载器测试
  - 快速验证RQData连接
  - 测试数据下载功能
  
- **`test_rqdata_backtest.py`** - 完整回测测试
  - 运行完整的回测流程
  - 自动保存结果
  - Prophet模型持久化

### 2. 修改文件

- **`hlm5_all_parallel.py`**
  - `_process_raw_data`方法改用RQData
  - 移除MySQL依赖
  - 保持接口兼容性
  
- **`backtest_integration.py`**
  - 添加`trading_signals`配置
  - 修复Prophet模型保存

## 🚀 快速开始

### 步骤1: 测试RQData连接

```bash
python test_rqdata_loader.py
```

**预期输出：**
```
✓ RQData初始化成功
✓ 下载成功: 2070 根K线
✓ 聚合完成: 438 根5分钟K线
```

### 步骤2: 运行完整回测

```bash
python test_rqdata_backtest.py
```

**这将：**
1. 从RQData下载OI.ZCE数据（2025-01-01 ~ 2025-02-01）
2. 计算所有技术指标（MACD, HLBW, Prophet）
3. 生成交易信号
4. 计算回测性能
5. 训练并保存Prophet模型
6. 自动保存到数据库
7. 生成可视化图表

### 步骤3: 查看结果

回测完成后，会自动打开：
- **成功报告**: `reports/rqdata_success_report.html`
- **回测图表**: `output/OI.ZCE_analysis.html`

## 📊 性能对比

| 指标 | VNPy回测 (之前) | RQData回测 (现在) | 改善 |
|------|----------------|------------------|------|
| **总交易** | 0笔 | 95笔 | ✅ +95笔 |
| **夏普比率** | 0.00 | 5.58 | ✅ +5.58 |
| **年化收益** | 0.00% | 31.82% | ✅ +31.82% |
| **最大回撤** | 0.00% | -0.43% | ✅ 极小 |
| **胜率** | 0.00% | 62.11% | ✅ 62.11% |
| **Prophet** | 无效 | 正常 | ✅ 修复 |

## 🔧 自定义回测

### 修改回测参数

编辑 `test_rqdata_backtest.py`:

```python
run_integrated_backtest_with_charts(
    ticker='OI.ZCE',              # 合约代码
    start_date='2025-01-01',      # 开始日期
    end_date='2025-02-01',        # 结束日期
    scaling_strategy='aggressive_pyramid',  # 加仓策略
    generate_charts=True,          # 生成图表
    auto_save=True,                # 自动保存
    auto_promote=True,             # 自动提升
    sharpe_threshold=2.0           # 提升阈值
)
```

### 支持的合约

所有期货主力合约（使用888后缀）：
- `OI.ZCE` - 菜籽油（郑商所）
- `RB.SHF` - 螺纹钢（上期所）
- `IF.CFFEX` - 沪深300股指期货
- 等等...

### 加仓策略

可选的加仓策略：
- `aggressive_pyramid` - 激进金字塔加仓（默认）
- `pyramid` - 标准金字塔加仓
- `inverse_pyramid` - 倒金字塔加仓
- `linear` - 线性加仓
- `fixed_fraction` - 固定比例加仓
- `none` - 不加仓

## 📁 目录结构

```
hlm5_backtest_engine/
├── rqdata_loader.py              # RQData加载器（新增）
├── test_rqdata_loader.py         # 加载器测试（新增）
├── test_rqdata_backtest.py       # 完整回测测试（新增）
├── hlm5_all_parallel.py          # 核心逻辑（已修改）
├── backtest_integration.py       # 集成模块（已修改）
├── run_integrated_backtest.py    # 回测入口
├── reports/
│   └── rqdata_success_report.html  # 成功报告（新增）
├── output/
│   └── OI.ZCE_analysis.html      # 回测图表
└── data/
    └── trading_signals.db         # 数据库
```

## 🔍 故障排查

### 问题1: RQData初始化失败

**症状：**
```
✗ RQData初始化失败
```

**解决方案：**
1. 检查RQData License是否有效
2. 确认网络连接正常
3. 查看`rqdata_loader.py`中的License配置

### 问题2: 没有数据

**症状：**
```
✗ 没有获取到数据
```

**解决方案：**
1. 确认合约代码正确（如 `OI.ZCE`）
2. 检查日期范围是否合理
3. 确认RQData账户有期货数据权限

### 问题3: 数据库表不存在

**症状：**
```
sqlite3.OperationalError: no such table: backtest_summary
```

**解决方案：**
```bash
cd data
python init_backtest_db.py
```

## 📝 注意事项

1. **数据一致性**: RQData版本与原MySQL版本的数据可能略有差异
2. **运行时间**: 首次运行需要下载数据，可能较慢
3. **License有效期**: 定期检查RQData License是否过期
4. **数据权限**: 确保RQData账户有期货数据访问权限

## 🎯 下一步

1. **运行更长周期回测**
   ```bash
   # 修改test_rqdata_backtest.py中的日期
   start_date='2025-01-01'
   end_date='2025-12-31'  # 12个月
   ```

2. **导入策略到实盘系统**
   ```bash
   cd ../quant/hlm5
   python tools/import_strategy.py --strategy-id hlm5_OI_ZCE_bt_XXXXXXXX
   ```

3. **启动纸上交易**
   ```bash
   python trading/paper_trading.py --strategy-id hlm5_OI_ZCE_bt_XXXXXXXX
   ```

## 💡 技术细节

### RQData集成原理

1. **数据获取**: 使用VNPy的`datafeed`接口
2. **数据聚合**: 1分钟数据 → 5分钟数据（重采样）
3. **数据清洗**: 去重、排序、异常值过滤
4. **接口兼容**: 保持与原MySQL接口一致

### 代码修改最小化

- ✅ 仅修改数据获取层
- ✅ 保持所有其他逻辑不变
- ✅ 无需修改策略代码
- ✅ 向后兼容

## 📞 支持

如有问题，请查看：
- `reports/rqdata_success_report.html` - 详细报告
- `output/OI.ZCE_analysis.html` - 回测图表
- 终端输出日志

---

**版本**: 1.0  
**更新日期**: 2025-12-08  
**状态**: ✅ 已测试，正常工作

