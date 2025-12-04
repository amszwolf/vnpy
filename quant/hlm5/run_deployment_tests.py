# -*- coding: utf-8 -*-
"""
HLM5 策略部署测试脚本

按照 DEPLOYMENT_PLAN.md 逐步执行验证
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 设置工作目录
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))


class DeploymentTester:
    """部署测试器"""
    
    def __init__(self):
        self.results = {}
        self.current_stage = 0
    
    def print_header(self, stage, title):
        """打印阶段标题"""
        print("\n" + "=" * 70)
        print(f"阶段 {stage}: {title}")
        print("=" * 70)
    
    def print_step(self, step_num, description):
        """打印步骤"""
        print(f"\n[步骤 {step_num}] {description}")
        print("-" * 70)
    
    def run_stage_0(self):
        """阶段0: 环境验证"""
        self.print_header(0, "环境验证")
        
        checks = {}
        
        # 1. Python版本
        self.print_step(1, "检查 Python 版本")
        try:
            import sys
            version = sys.version_info
            version_str = f"{version.major}.{version.minor}.{version.micro}"
            print(f"Python 版本: {version_str}")
            checks['python'] = version.major >= 3 and version.minor >= 8
            print(f"  {'✓' if checks['python'] else '✗'} Python 3.8+")
        except Exception as e:
            checks['python'] = False
            print(f"  ✗ 错误: {e}")
        
        # 2. VNPy
        self.print_step(2, "检查 VNPy 框架")
        try:
            import vnpy
            print(f"VNPy 版本: {vnpy.__version__}")
            checks['vnpy'] = True
            print("  ✓ VNPy")
        except Exception as e:
            checks['vnpy'] = False
            print(f"  ✗ VNPy 未安装: {e}")
        
        # 3. CTA策略模块
        self.print_step(3, "检查 CTA 策略模块")
        try:
            import vnpy_ctastrategy
            print("  ✓ vnpy_ctastrategy")
            checks['cta'] = True
        except Exception as e:
            checks['cta'] = False
            print(f"  ✗ vnpy_ctastrategy 未安装: {e}")
        
        # 4. TA-Lib
        self.print_step(4, "检查 TA-Lib")
        try:
            import talib
            print("  ✓ TA-Lib")
            checks['talib'] = True
        except Exception as e:
            checks['talib'] = False
            print(f"  ✗ TA-Lib 未安装: {e}")
        
        # 5. RQData
        self.print_step(5, "检查数据源配置")
        try:
            from vnpy.trader.setting import SETTINGS
            datafeed = SETTINGS.get("datafeed.name", "")
            username = SETTINGS.get("datafeed.username", "")
            
            if datafeed:
                print(f"  数据源: {datafeed}")
                print(f"  用户名: {username[:10]}..." if len(username) > 10 else f"  用户名: {username}")
                checks['datafeed'] = bool(username)
                print(f"  {'✓' if checks['datafeed'] else '⚠️'} 数据源配置")
            else:
                print("  ⚠️ 数据源未配置")
                checks['datafeed'] = False
        except Exception as e:
            checks['datafeed'] = False
            print(f"  ✗ 错误: {e}")
        
        # 6. 自定义模块
        self.print_step(6, "检查 HLM5 模块")
        module_checks = {}
        
        modules = [
            ('strategies.hlm5_strategy', 'HLM5Strategy', '策略模块'),
            ('utils.indicators', 'calculate_macd_signals', '指标模块'),
            ('utils.scaling_strategy', 'SCALING_CONFIGS', '加仓模块'),
            ('utils.trading_session', 'TradingSessionManager', '时段管理'),
            ('utils.cost_model', 'TradingCostCalculator', '成本模块'),
        ]
        
        for module_name, item_name, display_name in modules:
            try:
                module = __import__(module_name, fromlist=[item_name])
                getattr(module, item_name)
                print(f"  ✓ {display_name}")
                module_checks[display_name] = True
            except Exception as e:
                print(f"  ✗ {display_name}: {e}")
                module_checks[display_name] = False
        
        checks['modules'] = all(module_checks.values())
        
        # 总结
        print("\n" + "=" * 70)
        print("阶段0 验证结果:")
        print("=" * 70)
        
        all_passed = all(checks.values())
        
        for check_name, passed in checks.items():
            status = "✓ 通过" if passed else "✗ 失败"
            print(f"  {status}: {check_name}")
        
        if all_passed:
            print("\n✅ 阶段0：环境验证通过！")
            print("\n下一步：运行阶段1（数据准备验证）")
            print("命令：python run_deployment_tests.py --stage 1")
            self.results[0] = 'PASS'
            return True
        else:
            print("\n❌ 阶段0：环境验证失败！")
            print("\n请根据上述提示安装缺失的依赖")
            print("参考：QUICKSTART.md 的环境准备部分")
            self.results[0] = 'FAIL'
            return False
    
    def run_stage_1(self):
        """阶段1: 数据准备验证"""
        self.print_header(1, "数据准备验证")
        
        # 1. 检查现有数据
        self.print_step(1, "检查数据库中的现有数据")
        
        try:
            from vnpy.trader.database import get_database
            from vnpy.trader.constant import Exchange, Interval
            from datetime import datetime
            
            db = get_database()
            bars = db.load_bar_data(
                'OI888', 
                Exchange.CZCE, 
                Interval.MINUTE,  # 查询1分钟数据
                datetime(2025, 1, 1), 
                datetime(2025, 12, 31)
            )
            
            if bars:
                print(f"  ✓ 找到 {len(bars)} 条数据（1分钟K线）")
                print(f"  起始: {bars[0].datetime}")
                print(f"  结束: {bars[-1].datetime}")
                
                if len(bars) >= 10000:  # 1分钟数据量更大，调整阈值
                    print("\n✅ 数据充足，可以进行回测")
                    self.results[1] = 'PASS'
                    print("\n下一步：运行阶段2（指标计算验证）")
                    print("命令：python run_deployment_tests.py --stage 2")
                    return True
                else:
                    print("\n⚠️ 数据较少，建议下载更多数据")
            else:
                print("  ⚠️ 数据库无数据")
        except Exception as e:
            print(f"  ✗ 查询失败: {e}")
        
        # 2. 提示下载数据
        print("\n" + "-" * 70)
        print("请手动下载数据：")
        print("  python data/download_futures_data.py --symbol OI888 --exchange CZCE --start 2025-01-01 --interval 1m")
        print("\n下载完成后，重新运行：")
        print("  python run_deployment_tests.py --stage 1")
        
        self.results[1] = 'PENDING'
        return False
    
    def run_stage_2(self):
        """阶段2: 指标计算验证"""
        self.print_header(2, "指标计算验证")
        
        import pandas as pd
        import numpy as np
        
        checks = {}
        
        # 1. Price MACD
        self.print_step(1, "测试 Price MACD 计算")
        try:
            from utils.indicators import calculate_macd_signals
            from hlm5_config import EQUITY_CONFIG
            
            np.random.seed(42)
            prices = 100 + np.cumsum(np.random.randn(200) * 2)
            series = pd.Series(prices)
            
            config = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']
            result = calculate_macd_signals(series, config=config)
            
            print(f"  输出列: {list(result.columns)}")
            print(f"  数据行数: {len(result)}")
            print(f"  XLPL阶段分布:")
            for phase in [1, 2, 3, 4]:
                count = (result['XLPL_Phase'] == phase).sum()
                print(f"    阶段{phase}: {count}次")
            
            checks['price_macd'] = len(result) == len(series)
            print(f"  {'✓' if checks['price_macd'] else '✗'} Price MACD")
            
        except Exception as e:
            checks['price_macd'] = False
            print(f"  ✗ Price MACD 失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 2. HLBW
        self.print_step(2, "测试 HLBW 计算")
        try:
            from utils.indicators import calculate_hlbw
            
            base = 100 + np.cumsum(np.random.randn(200) * 2)
            high = base + np.random.rand(200) * 5
            low = base - np.random.rand(200) * 5
            
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(base)
            
            config = EQUITY_CONFIG['INDICATORS']['HLBW']
            result = calculate_hlbw(high_series, low_series, close_series, config=config)
            
            print(f"  输出列: {list(result.columns)}")
            print(f"  趋势线范围: {result['HLBW_Trend_Line'].min():.2f} ~ {result['HLBW_Trend_Line'].max():.2f}")
            
            checks['hlbw'] = len(result) == len(close_series)
            print(f"  {'✓' if checks['hlbw'] else '✗'} HLBW")
            
        except Exception as e:
            checks['hlbw'] = False
            print(f"  ✗ HLBW 失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. 加仓策略
        self.print_step(3, "测试加仓策略")
        try:
            from utils.scaling_strategy import SCALING_CONFIGS
            
            print(f"  预定义策略数量: {len(SCALING_CONFIGS)}")
            for name in SCALING_CONFIGS.keys():
                print(f"    - {name}")
            
            checks['scaling'] = len(SCALING_CONFIGS) == 5
            print(f"  {'✓' if checks['scaling'] else '✗'} 加仓策略")
            
        except Exception as e:
            checks['scaling'] = False
            print(f"  ✗ 加仓策略失败: {e}")
        
        # 总结
        print("\n" + "=" * 70)
        print("阶段2 验证结果:")
        print("=" * 70)
        
        all_passed = all(checks.values())
        
        for check_name, passed in checks.items():
            status = "✓ 通过" if passed else "✗ 失败"
            print(f"  {status}: {check_name}")
        
        if all_passed:
            print("\n✅ 阶段2：指标计算验证通过！")
            print("\n下一步：运行阶段3（策略逻辑验证）")
            print("命令：python run_deployment_tests.py --stage 3")
            self.results[2] = 'PASS'
            return True
        else:
            print("\n❌ 阶段2：指标计算验证失败！")
            print("\n请检查指标模块的实现")
            self.results[2] = 'FAIL'
            return False
    
    def run_stage_3(self):
        """阶段3: 策略逻辑验证"""
        self.print_header(3, "策略逻辑验证")
        
        self.print_step(1, "测试信号生成逻辑")
        
        try:
            from strategies.hlm5_strategy import HLM5Strategy
            
            # 模拟策略实例
            class MockStrategy(HLM5Strategy):
                def __init__(self):
                    # 设置测试值
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
            
            strategy = MockStrategy()
            
            # 测试做多信号
            long_signal = strategy.check_entry_conditions_long()
            print(f"\n测试1: 做多信号")
            print(f"  所有指标拉升 → 信号值: {long_signal}")
            print(f"  预期: 1 (最强做多信号)")
            print(f"  {'✓' if long_signal == 1 else '✗'} 做多信号")
            
            # 测试做空信号
            strategy.price_cross = -1
            strategy.price_xlpl_phase = 4  # 下跌
            strategy.hlbw_cross = -1
            strategy.prophet_phase = 4
            
            short_signal = strategy.check_entry_conditions_short()
            print(f"\n测试2: 做空信号")
            print(f"  所有指标下跌 → 信号值: {short_signal}")
            print(f"  预期: -1 (最强做空信号)")
            print(f"  {'✓' if short_signal == -1 else '✗'} 做空信号")
            
            # 测试出场信号
            strategy.price_cross = -1  # 反向信号
            exit_signal = strategy.check_exit_conditions_long()
            print(f"\n测试3: 做多出场信号")
            print(f"  反向Cross信号 → 出场: {exit_signal}")
            print(f"  预期: True")
            print(f"  {'✓' if exit_signal else '✗'} 出场信号")
            
            # 验证
            tests_passed = (long_signal == 1) and (short_signal == -1) and exit_signal
            
            print("\n" + "=" * 70)
            if tests_passed:
                print("✅ 阶段3：策略逻辑验证通过！")
                print("\n下一步：运行阶段4（历史回测-固定仓位）")
                print("命令：python run_deployment_tests.py --stage 4")
                self.results[3] = 'PASS'
                return True
            else:
                print("❌ 阶段3：策略逻辑验证失败！")
                print("\n请检查策略的信号生成逻辑")
                self.results[3] = 'FAIL'
                return False
                
        except Exception as e:
            print(f"\n✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.results[3] = 'FAIL'
            return False
    
    def run_stage_4(self):
        """阶段4: 历史回测（固定仓位）"""
        self.print_header(4, "历史回测（固定仓位）")
        
        print("\n⚠️ 此阶段需要手动操作")
        print("\n操作步骤：")
        print("-" * 70)
        print("1. 确认 backtesting/run_backtest.py 中的配置:")
        print("   - enable_scaling = False")
        print("   - fixed_size = 1")
        print("")
        print("2. 运行回测:")
        print("   python backtesting/run_backtest.py --start 2025-01-01 --end 2025-01-31")
        print("")
        print("3. 检查结果是否满足:")
        print("   ✓ 总收益率 > 10%")
        print("   ✓ 夏普比率 > 0.3")
        print("   ✓ 最大回撤 < 30%")
        print("   ✓ 总交易次数 > 10")
        print("   ✓ 胜率 > 40%")
        print("")
        print("4. 查看回测图表，检查:")
        print("   - 权益曲线是否合理")
        print("   - 交易点位是否合理")
        print("   - 是否有异常交易")
        
        print("\n" + "=" * 70)
        print("完成阶段4后，继续下一步")
        print("=" * 70)
        print("\n下一步选择：")
        print("  [A] 如果回测满意 → 阶段5（测试加仓策略）")
        print("      命令：python run_deployment_tests.py --stage 5")
        print("")
        print("  [B] 如果需要优化 → 阶段6（参数优化）")
        print("      命令：python run_deployment_tests.py --stage 6")
        print("")
        print("  [C] 如果回测不理想 → 检查数据和策略逻辑")
        print("      返回：python run_deployment_tests.py --stage 1")
        
        return None
    
    def run_stage_5(self):
        """阶段5: 历史回测（加仓策略）"""
        self.print_header(5, "历史回测（加仓策略）")
        
        print("\n⚠️ 此阶段用于对比固定仓位和加仓策略")
        print("\n操作步骤：")
        print("-" * 70)
        print("1. 运行对比测试:")
        print("   python examples/test_scaling_strategy.py")
        print("")
        print("2. 或者手动测试:")
        print("   修改 run_backtest.py:")
        print("   strategy_setting = {")
        print("       'enable_scaling': True,")
        print("       'scaling_method': 'aggressive_pyramid',")
        print("       'max_position': 10,")
        print("       'scaling_threshold': 0.01,")
        print("   }")
        print("")
        print("   python backtesting/run_backtest.py")
        print("")
        print("3. 对比结果（加仓 vs 固定仓位）:")
        print("   - 总收益提升了多少？")
        print("   - 夏普比率是否提升？")
        print("   - 回撤增加了多少？")
        print("   - 是否值得使用加仓？")
        
        print("\n" + "=" * 70)
        print("决策指南")
        print("=" * 70)
        print("\n[A] 加仓效果好（收益提升>20%，回撤增加<5%）")
        print("    → 采用加仓策略")
        print("    → 进入阶段7（模拟交易）")
        print("      命令：python run_deployment_tests.py --stage 7")
        print("")
        print("[B] 加仓效果一般")
        print("    → 进入阶段6优化参数")
        print("      命令：python run_deployment_tests.py --stage 6")
        print("")
        print("[C] 加仓效果差")
        print("    → 暂不使用加仓，直接进入阶段7测试固定仓位")
        
        return None
    
    def run_stage_6(self):
        """阶段6: 参数优化"""
        self.print_header(6, "参数优化")
        
        print("\n⚠️ 参数优化可能需要较长时间")
        print("\n操作步骤：")
        print("-" * 70)
        print("1. 运行参数优化（预计30分钟-2小时）:")
        print("   python backtesting/optimizer.py --start 2025-01-01 --end 2025-01-31")
        print("")
        print("2. 查看优化结果:")
        print("   结果保存在: output/optimization_*.txt")
        print("")
        print("3. 选择最优参数组合:")
        print("   - 优先考虑夏普比率最高的")
        print("   - 兼顾总收益和回撤")
        print("   - 避免过度拟合")
        print("")
        print("4. 更新配置文件:")
        print("   编辑 hlm5_config.py，更新最优参数")
        print("")
        print("5. 验证新参数（重要！）:")
        print("   python backtesting/run_backtest.py --start 2025-02-01 --end 2025-02-28")
        print("   在新的时间段验证参数是否依然有效")
        
        print("\n" + "=" * 70)
        print("优化完成后")
        print("=" * 70)
        print("\n下一步：进入阶段7（SimNow模拟交易）")
        print("命令：python run_deployment_tests.py --stage 7")
        
        return None
    
    def run_stage_7(self):
        """阶段7: SimNow模拟交易"""
        self.print_header(7, "SimNow模拟交易")
        
        print("\n⚠️ 这是实盘前的最后验证")
        print("\n操作步骤：")
        print("-" * 70)
        print("1. 确认策略配置（建议保守）:")
        print("   strategy_setting = {")
        print("       'enable_scaling': False,  # 先测试固定仓位")
        print("       'fixed_size': 1,")
        print("       'enable_bidirectional': False,  # 仅做多")
        print("       'stop_loss_pct': 0.03,  # 3%止损（严格）")
        print("       'take_profit_pct': 0.10,  # 10%止盈（保守）")
        print("   }")
        print("")
        print("2. 启动模拟交易:")
        print("   python trading/paper_trading.py")
        print("")
        print("3. 观察运行状态（至少运行2-3个交易日）:")
        print("   - 行情数据是否正常接收")
        print("   - 信号生成是否合理")
        print("   - 订单执行是否成功")
        print("   - 持仓管理是否正确")
        print("   - 收盘前是否自动平仓")
        print("")
        print("4. 每日记录:")
        print("   - 开仓次数")
        print("   - 平仓次数")
        print("   - 当日盈亏")
        print("   - 是否有异常")
        
        print("\n" + "=" * 70)
        print("模拟交易检查清单（运行3天后）")
        print("=" * 70)
        print("\n必须满足:")
        print("  [ ] 连接稳定，无频繁断线")
        print("  [ ] 至少完成5笔完整交易")
        print("  [ ] 信号生成符合预期")
        print("  [ ] 止损止盈正常工作")
        print("  [ ] 收盘前自动平仓")
        print("  [ ] 无程序崩溃")
        print("")
        print("建议满足:")
        print("  [ ] 总体盈利或盈亏平衡")
        print("  [ ] 胜率 > 50%")
        print("  [ ] 无重大异常交易")
        
        print("\n" + "=" * 70)
        print("决策指南")
        print("=" * 70)
        print("\n[继续] 如果上述检查都通过")
        print("  → 准备进入实盘（阶段8）")
        print("  → 命令：python run_deployment_tests.py --stage 8")
        print("")
        print("[优化] 如果有小问题")
        print("  → 调整参数后继续模拟")
        print("  → 返回阶段6优化")
        print("")
        print("[停止] 如果有重大问题")
        print("  → 检查策略逻辑")
        print("  → 返回阶段3-4重新测试")
        
        return None
    
    def run_stage_8(self):
        """阶段8: 小资金实盘测试"""
        self.print_header(8, "小资金实盘测试")
        
        print("\n🚨 警告：这是真实资金！")
        print("\n" + "=" * 70)
        print("实盘前最后确认")
        print("=" * 70)
        
        questions = [
            "回测收益率 > 20%？",
            "夏普比率 > 0.5？",
            "模拟交易至少3天无重大问题？",
            "完全理解策略逻辑？",
            "准备好承受可能的亏损？",
            "设置了明确的止损规则？",
            "账户资金充足（建议1-2万元）？"
        ]
        
        print("\n请确认以下条件（建议全部满足）：")
        for i, q in enumerate(questions, 1):
            print(f"  {i}. {q}")
        
        print("\n" + "=" * 70)
        print("建议配置（小资金实盘）")
        print("=" * 70)
        print("""
strategy_setting = {
    'enable_scaling': False,        # 禁用加仓
    'fixed_size': 1,                # 仅1手
    'enable_bidirectional': False,  # 仅做多（更保守）
    'hold_overnight': False,        # 不持仓过夜
    'stop_loss_pct': 0.03,         # 3%止损（严格）
    'take_profit_pct': 0.10,       # 10%止盈（保守）
}
        """)
        
        print("\n操作步骤：")
        print("-" * 70)
        print("1. 准备实盘账户（建议1-2万元）")
        print("")
        print("2. 修改 trading/live_trading.py 或 paper_trading.py")
        print("   - 连接实盘账户")
        print("   - 使用上述保守配置")
        print("")
        print("3. 启动实盘交易:")
        print("   python trading/live_trading.py")
        print("")
        print("4. 每日监控（必须！）:")
        print("   - 开盘前检查程序状态")
        print("   - 盘中每小时检查持仓")
        print("   - 收盘后记录交易日志")
        print("")
        print("5. 创建交易日志 Excel:")
        print("   日期 | 信号 | 开仓价 | 平仓价 | 盈亏 | 备注")
        
        print("\n" + "=" * 70)
        print("2周后评估标准")
        print("=" * 70)
        print("\n继续使用:")
        print("  [ ] 总收益 >= 0")
        print("  [ ] 胜率 > 50%")
        print("  [ ] 最大单笔亏损 < 500元")
        print("  [ ] 严格按策略执行")
        print("")
        print("停止使用:")
        print("  [ ] 累计亏损 > 10% (1000元)")
        print("  [ ] 连续亏损 > 5笔")
        print("  [ ] 单笔亏损 > 1000元")
        
        print("\n" + "=" * 70)
        print("测试期建议: 2-4周")
        print("=" * 70)
        print("\n如果测试成功，进入阶段9（正式实盘部署）")
        print("命令：python run_deployment_tests.py --stage 9")
        
        return None
    
    def run_stage_9(self):
        """阶段9: 正式实盘部署"""
        self.print_header(9, "正式实盘部署")
        
        print("\n📊 资金管理建议")
        print("=" * 70)
        
        stages = [
            ("第1-2月", "2万元", "1手", "禁用", "稳定盈利 > 5%/月"),
            ("第3-4月", "5万元", "1-2手", "pyramid", "月收益 > 8%"),
            ("第5-6月", "10万元", "最大5手", "aggressive_pyramid", "月收益 > 10%"),
        ]
        
        print("\n阶段 | 资金 | 仓位 | 加仓策略 | 目标")
        print("-" * 70)
        for stage, capital, position, scaling, target in stages:
            print(f"{stage:<10} {capital:<8} {position:<8} {scaling:<20} {target}")
        
        print("\n" + "=" * 70)
        print("风险控制规则")
        print("=" * 70)
        print("""
单日止损:
  - 日亏损 > 3% → 停止交易当日
  - 日亏损 > 5% → 停止交易3天
  - 周亏损 > 10% → 停止交易1周

回撤控制:
  - 总回撤 > 15% → 减少仓位50%
  - 总回撤 > 25% → 停止交易，全面检讨

盈利保护:
  - 月盈利 > 15% → 提取盈利的50%
  - 季度盈利 > 50% → 提取盈利的70%
        """)
        
        print("\n下一步：进入阶段10（持续监控和优化）")
        print("命令：python run_deployment_tests.py --stage 10")
        
        return None
    
    def run_stage_10(self):
        """阶段10: 监控和优化"""
        self.print_header(10, "监控和优化")
        
        print("\n📊 日常监控任务")
        print("=" * 70)
        
        print("\n每日任务:")
        print("  1. 开盘前（9:00前）")
        print("     - 检查程序运行状态")
        print("     - 检查网络连接")
        print("     - 查看账户余额")
        print("")
        print("  2. 盘中（交易时段）")
        print("     - 每小时检查持仓")
        print("     - 观察信号是否合理")
        print("     - 监控盈亏变化")
        print("")
        print("  3. 收盘后（15:30后）")
        print("     - 记录当日交易")
        print("     - 计算当日盈亏")
        print("     - 更新交易日志")
        
        print("\n" + "-" * 70)
        print("每周任务:")
        print("  1. 周日晚上复盘")
        print("     - 本周交易回顾")
        print("     - 盈亏分析")
        print("     - 策略表现评估")
        print("  2. 制定下周计划")
        print("     - 是否调整参数")
        print("     - 是否调整仓位")
        
        print("\n" + "-" * 70)
        print("每月任务:")
        print("  1. 重新运行回测（最近3个月）")
        print("     python backtesting/run_backtest.py --start 最近3个月")
        print("")
        print("  2. 参数优化测试")
        print("     python backtesting/optimizer.py --start 最近3个月")
        print("")
        print("  3. 对比分析")
        print("     - 实盘表现 vs 回测表现")
        print("     - 如果差异 > 20% → 需要优化")
        
        print("\n" + "=" * 70)
        print("持续改进建议")
        print("=" * 70)
        print("""
1. 市场环境适应
   - 震荡市：提高阈值，减少交易
   - 趋势市：启用加仓，适当放宽

2. 定期优化
   - 每月评估参数
   - 每季度深度优化
   
3. 风险监控
   - 设置自动预警
   - 记录异常情况
   - 及时止损
        """)
        
        print("\n✅ 恭喜！您已完成整个部署流程")
        print("\n现在开始持续监控和优化您的量化交易系统！")
        
        return None


def main():
    """主程序"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HLM5 策略部署测试')
    parser.add_argument('--stage', type=int, default=0,
                       help='运行指定阶段 (0-10)')
    parser.add_argument('--all', action='store_true',
                       help='运行所有自动化阶段')
    
    args = parser.parse_args()
    
    tester = DeploymentTester()
    
    # 显示计划概览
    if args.stage == 0 and not args.all:
        print("\n" + "=" * 70)
        print("HLM5 策略部署测试计划")
        print("=" * 70)
        print("""
本脚本将帮助您逐步验证HLM5策略，从开发到实盘部署。

阶段说明：
  阶段 0: 环境验证 ✓ 自动化
  阶段 1: 数据准备验证 ✓ 半自动化
  阶段 2: 指标计算验证 ✓ 自动化
  阶段 3: 策略逻辑验证 ✓ 自动化
  阶段 4: 历史回测（固定仓位） → 需手动操作
  阶段 5: 历史回测（加仓策略） → 需手动操作
  阶段 6: 参数优化 → 需手动操作
  阶段 7: SimNow模拟交易 → 需手动操作
  阶段 8: 小资金实盘测试 → 需手动操作
  阶段 9: 正式实盘部署 → 需手动操作
  阶段 10: 监控和优化 → 持续进行

使用方法：
  python run_deployment_tests.py --stage 0  # 运行阶段0
  python run_deployment_tests.py --stage 1  # 运行阶段1
  ...

建议：按顺序执行，每个阶段通过后再进入下一阶段。
        """)
    
    # 运行指定阶段
    if args.stage == 0:
        tester.run_stage_0()
    elif args.stage == 1:
        tester.run_stage_1()
    elif args.stage == 2:
        tester.run_stage_2()
    elif args.stage == 3:
        tester.run_stage_3()
    elif args.stage == 4:
        tester.run_stage_4()
    elif args.stage == 5:
        tester.run_stage_5()
    elif args.stage == 6:
        tester.run_stage_6()
    elif args.stage == 7:
        tester.run_stage_7()
    elif args.stage == 8:
        tester.run_stage_8()
    elif args.stage == 9:
        tester.run_stage_9()
    elif args.stage == 10:
        tester.run_stage_10()
    
    # 运行所有自动化阶段
    if args.all:
        print("\n运行所有自动化阶段...")
        for stage in [0, 1, 2, 3]:
            if stage == 0:
                success = tester.run_stage_0()
            elif stage == 1:
                success = tester.run_stage_1()
            elif stage == 2:
                success = tester.run_stage_2()
            elif stage == 3:
                success = tester.run_stage_3()
            
            if not success and success is not None:
                print(f"\n阶段{stage}失败，停止后续测试")
                break


if __name__ == "__main__":
    main()

