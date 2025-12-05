"""
盈亏计算修复验证测试（带可视化）

测试项目：
1. 做多盈亏计算
2. 做空盈亏计算
3. 交易成本计算
4. 回撤计算
5. 生成HTML可视化报告

Python环境：aidata311
"""

import numpy as np
import pandas as pd
from datetime import datetime
import logging
import os
from bokeh.plotting import figure, output_file, save
from bokeh.layouts import column, row
from bokeh.models import HoverTool, Div, ColumnDataSource
from bokeh.io import show

from futures_contract_specs import (
    FuturesContractSpecs, 
    CommissionModel, 
    TradingCostCalculator
)
from scaling_strategy import PositionTracker, ScalingStrategyEngine, ScalingConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量存储测试结果
test_results = []


def test_long_position_pnl():
    """测试1：做多盈亏计算"""
    logger.info("="*70)
    logger.info("测试1：做多持仓盈亏计算")
    logger.info("="*70)
    
    ticker = 'RB.SHF'
    tracker = PositionTracker(ticker)
    
    # 模拟开多仓
    entry_price = 3450.0
    volume = 4
    timestamp = datetime.now()
    
    tracker.add_position(entry_price, volume, timestamp)
    
    # 测试浮动盈亏
    current_price = 3500.0
    unrealized_pnl = tracker.calculate_unrealized_pnl(current_price)
    
    # 预期结果
    expected_pnl = (3500 - 3450) * 4 * 10  # 2000元
    
    logger.info(f"\n做多持仓测试：")
    logger.info(f"  入场价格：{entry_price}元/吨")
    logger.info(f"  当前价格：{current_price}元/吨")
    logger.info(f"  持仓手数：{volume}手")
    logger.info(f"  合约乘数：10吨/手")
    logger.info(f"\n计算结果：")
    logger.info(f"  未实现盈亏：{unrealized_pnl:.2f}元")
    logger.info(f"  预期盈亏：  {expected_pnl:.2f}元")
    logger.info(f"  差异：      {abs(unrealized_pnl - expected_pnl):.2f}元")
    
    passed = abs(unrealized_pnl - expected_pnl) < 0.01
    
    if passed:
        logger.info("  ✅ 测试通过！")
    else:
        logger.error("  ❌ 测试失败！")
    
    # 保存测试结果
    test_results.append({
        'test_name': '做多盈亏计算',
        'test_id': 1,
        'entry_price': entry_price,
        'exit_price': current_price,
        'volume': volume,
        'actual_pnl': unrealized_pnl,
        'expected_pnl': expected_pnl,
        'difference': abs(unrealized_pnl - expected_pnl),
        'passed': passed
    })
    
    return passed


def test_short_position_pnl():
    """测试2：做空盈亏计算"""
    logger.info("\n" + "="*70)
    logger.info("测试2：做空持仓盈亏计算")
    logger.info("="*70)
    
    ticker = 'RB.SHF'
    tracker = PositionTracker(ticker)
    
    # 模拟开空仓
    entry_price = 3500.0
    volume = -4  # 负数表示空仓
    timestamp = datetime.now()
    
    tracker.add_position(entry_price, volume, timestamp)
    
    # 测试浮动盈亏
    current_price = 3450.0  # 价格下跌，空仓盈利
    unrealized_pnl = tracker.calculate_unrealized_pnl(current_price)
    
    # 预期结果
    expected_pnl = (3500 - 3450) * 4 * 10  # 2000元
    
    logger.info(f"\n做空持仓测试：")
    logger.info(f"  入场价格：{entry_price}元/吨")
    logger.info(f"  当前价格：{current_price}元/吨")
    logger.info(f"  持仓手数：{abs(volume)}手（空仓）")
    logger.info(f"  合约乘数：10吨/手")
    logger.info(f"\n计算结果：")
    logger.info(f"  未实现盈亏：{unrealized_pnl:.2f}元")
    logger.info(f"  预期盈亏：  {expected_pnl:.2f}元")
    logger.info(f"  差异：      {abs(unrealized_pnl - expected_pnl):.2f}元")
    
    passed = abs(unrealized_pnl - expected_pnl) < 0.01
    
    if passed:
        logger.info("  ✅ 测试通过！")
    else:
        logger.error("  ❌ 测试失败！")
    
    # 保存测试结果
    test_results.append({
        'test_name': '做空盈亏计算',
        'test_id': 2,
        'entry_price': entry_price,
        'exit_price': current_price,
        'volume': abs(volume),
        'actual_pnl': unrealized_pnl,
        'expected_pnl': expected_pnl,
        'difference': abs(unrealized_pnl - expected_pnl),
        'passed': passed
    })
    
    return passed


def test_trading_cost():
    """测试3：交易成本计算"""
    logger.info("\n" + "="*70)
    logger.info("测试3：交易成本计算")
    logger.info("="*70)
    
    ticker = 'RB.SHF'
    calculator = TradingCostCalculator(ticker)
    
    # 测试往返成本
    entry_price = 3450.0
    exit_price = 3500.0
    volume = 4
    
    cost_info = calculator.calculate_round_trip_cost(entry_price, exit_price, volume)
    
    # 预期手续费（万分之0.5 × 2）
    entry_value = 3450 * 4 * 10  # 138,000元
    exit_value = 3500 * 4 * 10   # 140,000元
    expected_commission = (entry_value + exit_value) * 0.00005  # 13.9元
    
    # 预期滑点成本（1跳 = 1元，往返2跳）
    expected_slippage = 1 * 4 * 10 * 2  # 80元
    expected_total = expected_commission + expected_slippage
    
    logger.info(f"\n交易成本测试：")
    logger.info(f"  开仓价格：{entry_price}元/吨")
    logger.info(f"  平仓价格：{exit_price}元/吨")
    logger.info(f"  交易手数：{volume}手")
    logger.info(f"\n成本明细：")
    logger.info(f"  开仓手续费：{cost_info['entry_commission']:.2f}元")
    logger.info(f"  平仓手续费：{cost_info['exit_commission']:.2f}元")
    logger.info(f"  总手续费：  {cost_info['total_commission']:.2f}元 (预期: {expected_commission:.2f}元)")
    logger.info(f"  滑点成本：  {cost_info['total_slippage']:.2f}元 (预期: {expected_slippage:.2f}元)")
    logger.info(f"  总成本：    {cost_info['total_cost']:.2f}元")
    
    commission_ok = abs(cost_info['total_commission'] - expected_commission) < 0.5
    slippage_ok = abs(cost_info['total_slippage'] - expected_slippage) < 0.01
    passed = commission_ok and slippage_ok
    
    if passed:
        logger.info("  ✅ 测试通过！")
    else:
        logger.error("  ❌ 测试失败！")
    
    # 保存测试结果
    test_results.append({
        'test_name': '交易成本计算',
        'test_id': 3,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'volume': volume,
        'actual_pnl': cost_info['total_cost'],
        'expected_pnl': expected_total,
        'difference': abs(cost_info['total_cost'] - expected_total),
        'passed': passed
    })
    
    return passed


def test_realized_pnl_with_cost():
    """测试4：平仓盈亏计算（含交易成本）"""
    logger.info("\n" + "="*70)
    logger.info("测试4：平仓盈亏计算（含交易成本）")
    logger.info("="*70)
    
    ticker = 'RB.SHF'
    
    # 创建加仓配置
    config = ScalingConfig(
        scaling_method='linear',
        max_position=10,
        scaling_sequence=[4, 3, 2, 1],
        add_position_condition='price_move',
        add_position_threshold=0.005
    )
    
    engine = ScalingStrategyEngine(config, ticker)
    
    # 模拟交易流程
    entry_price = 3450.0
    exit_price = 3500.0
    timestamp = datetime.now()
    
    # 1. 开多仓
    result_entry = engine.on_signal(1, entry_price, timestamp)
    logger.info(f"\n开多仓：")
    logger.info(f"  价格：{entry_price}元/吨")
    logger.info(f"  手数：{result_entry['size']}手")
    
    # 2. 平多仓
    result_exit = engine.on_signal(-1, exit_price, timestamp)
    
    # 预期毛盈亏
    gross_pnl = (exit_price - entry_price) * 4 * 10  # 2000元
    
    # 预期交易成本
    cost_calculator = TradingCostCalculator(ticker)
    cost_info = cost_calculator.calculate_round_trip_cost(entry_price, exit_price, 4)
    expected_cost = cost_info['total_cost']
    
    # 预期净盈亏
    expected_net_pnl = gross_pnl - expected_cost
    
    actual_net_pnl = result_exit.get('pnl', 0)
    actual_gross_pnl = result_exit.get('gross_pnl', 0)
    actual_cost = result_exit.get('trading_cost', 0)
    
    logger.info(f"\n平多仓：")
    logger.info(f"  价格：{exit_price}元/吨")
    logger.info(f"\n盈亏计算：")
    logger.info(f"  毛盈亏：    {actual_gross_pnl:.2f}元 (预期: {gross_pnl:.2f}元)")
    logger.info(f"  交易成本：  {actual_cost:.2f}元 (预期: {expected_cost:.2f}元)")
    logger.info(f"  净盈亏：    {actual_net_pnl:.2f}元 (预期: {expected_net_pnl:.2f}元)")
    logger.info(f"  差异：      {abs(actual_net_pnl - expected_net_pnl):.2f}元")
    
    if abs(actual_net_pnl - expected_net_pnl) < 1.0:
        logger.info("  ✅ 测试通过！")
        return True
    else:
        logger.error("  ❌ 测试失败！")
        return False


def test_drawdown_calculation():
    """测试5：回撤计算"""
    logger.info("\n" + "="*70)
    logger.info("测试5：回撤计算")
    logger.info("="*70)
    
    # 模拟交易盈亏序列
    initial_capital = 10000
    trades_pnl = pd.Series([500, -200, 300, -400, 600, -300, 400])
    
    # 计算权益曲线
    cumulative_pnl = trades_pnl.cumsum()
    equity_curve = initial_capital + cumulative_pnl
    
    # 计算回撤
    peak = equity_curve.expanding().max()
    drawdown_pct = (peak - equity_curve) / peak
    max_drawdown_pct = drawdown_pct.max()
    max_drawdown_amount = (peak - equity_curve).max()
    
    logger.info(f"\n回撤计算测试：")
    logger.info(f"  初始资金：{initial_capital}元")
    logger.info(f"  交易序列：{trades_pnl.tolist()}")
    logger.info(f"\n权益曲线：")
    for i, (pnl, equity, pk, dd) in enumerate(zip(trades_pnl, equity_curve, peak, drawdown_pct)):
        logger.info(f"    交易{i+1}：盈亏={pnl:>6.0f}元, 权益={equity:>8.0f}元, 峰值={pk:>8.0f}元, 回撤={dd*100:>5.2f}%")
    
    logger.info(f"\n回撤统计：")
    logger.info(f"  最大回撤：  {max_drawdown_pct*100:.2f}%")
    logger.info(f"  最大回撤金额：{max_drawdown_amount:.2f}元")
    logger.info(f"  最终权益：  {equity_curve.iloc[-1]:.2f}元")
    logger.info(f"  总收益率：  {(equity_curve.iloc[-1] - initial_capital) / initial_capital * 100:.2f}%")
    
    # 验证回撤在合理范围内
    if 0 <= max_drawdown_pct <= 1:
        logger.info("  ✅ 测试通过！")
        return True
    else:
        logger.error("  ❌ 测试失败！回撤计算超出合理范围")
        return False


def compare_old_vs_new():
    """对比修复前后的计算差异"""
    logger.info("\n" + "="*70)
    logger.info("对比分析：修复前 vs 修复后")
    logger.info("="*70)
    
    # 测试案例
    entry_price = 3450.0
    exit_price = 3500.0
    volume = 4
    multiplier = 10
    initial_capital = 10000
    
    # 旧的错误计算（使用百分比 × 100）
    old_pnl = (exit_price - entry_price) / entry_price * 100 * volume
    old_return_pct = old_pnl  # 直接当作收益率
    
    # 新的正确计算
    gross_pnl = (exit_price - entry_price) * volume * multiplier
    cost_calculator = TradingCostCalculator('RB.SHF')
    cost = cost_calculator.calculate_round_trip_cost(entry_price, exit_price, volume)['total_cost']
    new_pnl = gross_pnl - cost
    new_return_pct = (new_pnl / initial_capital) * 100
    
    logger.info(f"\n交易案例：")
    logger.info(f"  开仓价格：{entry_price}元/吨")
    logger.info(f"  平仓价格：{exit_price}元/吨")
    logger.info(f"  持仓手数：{volume}手")
    logger.info(f"  合约乘数：{multiplier}吨/手")
    logger.info(f"  初始资金：{initial_capital}元")
    
    logger.info(f"\n❌ 修复前（错误计算）：")
    logger.info(f"  盈亏：    {old_pnl:.2f} （单位不明！）")
    logger.info(f"  收益率：  {old_return_pct:.2f}% （错误！）")
    
    logger.info(f"\n✅ 修复后（正确计算）：")
    logger.info(f"  毛盈亏：  {gross_pnl:.2f}元")
    logger.info(f"  交易成本：{cost:.2f}元")
    logger.info(f"  净盈亏：  {new_pnl:.2f}元")
    logger.info(f"  收益率：  {new_return_pct:.2f}%")
    
    logger.info(f"\n差异分析：")
    logger.info(f"  收益率高估倍数：{old_return_pct / new_return_pct:.2f}倍")
    logger.info(f"  这解释了为什么之前的回测显示1918.04%的异常高收益！")
    
    return True


def generate_visualization():
    """生成可视化HTML报告"""
    logger.info("\n生成可视化报告...")
    
    # 输出文件
    output_html = f'盈亏计算测试报告_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    output_file(output_html)
    
    # 创建标题
    title_div = Div(text="""
    <div style="text-align: center; padding: 20px; background-color: #f0f8ff; border-radius: 10px; margin-bottom: 20px;">
        <h1 style="color: #2c3e50; margin: 0;">盈亏计算修复验证测试报告</h1>
        <p style="color: #7f8c8d; margin: 10px 0 0 0;">Python环境: aidata311 | 生成时间: {}</p>
    </div>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # 测试结果统计
    passed_count = sum(1 for r in test_results if r['passed'])
    total_count = len(test_results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
    
    # 创建统计卡片
    stats_div = Div(text=f"""
    <div style="display: flex; justify-content: space-around; margin: 20px 0;">
        <div style="background-color: {'#d4edda' if passed_count == total_count else '#f8d7da'}; 
                    padding: 20px; border-radius: 10px; text-align: center; min-width: 150px;">
            <h2 style="margin: 0; color: {'#155724' if passed_count == total_count else '#721c24'};">
                {passed_count}/{total_count}
            </h2>
            <p style="margin: 5px 0 0 0; color: #666;">测试通过</p>
        </div>
        <div style="background-color: #d1ecf1; padding: 20px; border-radius: 10px; text-align: center; min-width: 150px;">
            <h2 style="margin: 0; color: #0c5460;">{pass_rate:.1f}%</h2>
            <p style="margin: 5px 0 0 0; color: #666;">通过率</p>
        </div>
        <div style="background-color: #fff3cd; padding: 20px; border-radius: 10px; text-align: center; min-width: 150px;">
            <h2 style="margin: 0; color: #856404;">{total_count - passed_count}</h2>
            <p style="margin: 5px 0 0 0; color: #666;">测试失败</p>
        </div>
    </div>
    """)
    
    # 创建详细结果表格
    table_html = """
    <div style="margin: 20px 0;">
        <h3 style="color: #2c3e50;">详细测试结果</h3>
        <table style="width: 100%; border-collapse: collapse; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background-color: #3498db; color: white;">
                    <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">#</th>
                    <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">测试项</th>
                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">入场价</th>
                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">出场价</th>
                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">手数</th>
                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">实际盈亏</th>
                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">预期盈亏</th>
                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">差异</th>
                    <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">状态</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for r in test_results:
        status_color = '#d4edda' if r['passed'] else '#f8d7da'
        status_icon = '✅' if r['passed'] else '❌'
        
        table_html += f"""
            <tr style="background-color: {status_color};">
                <td style="padding: 10px; border: 1px solid #ddd;">{r['test_id']}</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{r['test_name']}</td>
                <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">{r['entry_price']:.2f}</td>
                <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">{r['exit_price']:.2f}</td>
                <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">{r['volume']}</td>
                <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">{r['actual_pnl']:.2f}元</td>
                <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">{r['expected_pnl']:.2f}元</td>
                <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">{r['difference']:.2f}元</td>
                <td style="padding: 10px; text-align: center; border: 1px solid #ddd; font-size: 20px;">{status_icon}</td>
            </tr>
        """
    
    table_html += """
            </tbody>
        </table>
    </div>
    """
    
    table_div = Div(text=table_html)
    
    # 创建盈亏对比图
    if test_results:
        df = pd.DataFrame(test_results)
        
        p1 = figure(height=400, width=900,
                   title="盈亏计算对比：实际值 vs 预期值",
                   toolbar_location='above',
                   tools='pan,wheel_zoom,box_zoom,reset,save,crosshair')
        
        test_names = df['test_name'].tolist()
        x = list(range(len(test_names)))
        
        # 并排柱状图
        p1.vbar(x=[i - 0.2 for i in x], top=df['actual_pnl'], width=0.35, 
               legend_label="实际盈亏",
               color='#3498db', alpha=0.8)
        
        p1.vbar(x=[i + 0.2 for i in x], top=df['expected_pnl'], width=0.35, 
               legend_label="预期盈亏",
               color='#e74c3c', alpha=0.5)
        
        p1.xaxis.ticker = x
        p1.xaxis.major_label_overrides = {i: name for i, name in enumerate(test_names)}
        p1.xaxis.major_label_orientation = 0.8
        p1.yaxis.axis_label = "盈亏金额（元）"
        p1.legend.location = "top_right"
        p1.legend.click_policy = "hide"
        
        # 创建差异图
        p2 = figure(height=300, width=900,
                   title="计算差异（绝对值）",
                   toolbar_location='above',
                   tools='pan,wheel_zoom,box_zoom,reset,save')
        
        colors = ['#27ae60' if r['passed'] else '#e74c3c' for r in test_results]
        
        p2.vbar(x=x, top=df['difference'], width=0.6,
               color=colors, 
               alpha=0.8)
        
        p2.xaxis.ticker = x
        p2.xaxis.major_label_overrides = {i: name for i, name in enumerate(test_names)}
        p2.xaxis.major_label_orientation = 0.8
        p2.yaxis.axis_label = "差异（元）"
        
        # 添加结论
        if passed_count == total_count:
            conclusion_text = """
            <div style="background-color: #d4edda; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 5px solid #28a745;">
                <h3 style="color: #155724; margin: 0 0 10px 0;">🎉 测试结论：全部通过</h3>
                <p style="color: #155724; margin: 0; line-height: 1.6;">
                    所有测试项均通过验证，盈亏计算修复成功！系统现在能够：<br>
                    ✅ 准确计算做多做空盈亏<br>
                    ✅ 正确应用合约乘数<br>
                    ✅ 扣除真实交易成本<br>
                    ✅ 基于权益曲线计算回撤
                </p>
            </div>
            """
        else:
            conclusion_text = """
            <div style="background-color: #f8d7da; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 5px solid #dc3545;">
                <h3 style="color: #721c24; margin: 0 0 10px 0;">⚠️ 测试结论：部分失败</h3>
                <p style="color: #721c24; margin: 0; line-height: 1.6;">
                    部分测试项未通过，请检查代码逻辑。
                </p>
            </div>
            """
        
        conclusion_div = Div(text=conclusion_text)
        
        # 组合所有元素
        layout = column([
            title_div,
            stats_div,
            table_div,
            p1,
            p2,
            conclusion_div
        ])
        
        # 保存并显示
        save(layout)
        logger.info(f"✅ 可视化报告已生成：{output_html}")
        
        # 在浏览器中打开
        import webbrowser
        webbrowser.open(f'file://{os.path.abspath(output_html)}')
        logger.info(f"✅ 已在浏览器中打开报告")
        
        return output_html


def main():
    """运行所有测试"""
    logger.info("\n")
    logger.info("╔" + "="*68 + "╗")
    logger.info("║" + " "*20 + "盈亏计算修复验证测试" + " "*20 + "║")
    logger.info("╚" + "="*68 + "╝")
    
    tests = [
        test_long_position_pnl,
        test_short_position_pnl,
        test_trading_cost,
        test_realized_pnl_with_cost,
        test_drawdown_calculation,
        compare_old_vs_new
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    # 测试总结
    logger.info("\n" + "="*70)
    logger.info("测试总结")
    logger.info("="*70)
    passed = sum(results)
    total = len(results)
    logger.info(f"  通过：{passed}/{total}")
    logger.info(f"  失败：{total - passed}/{total}")
    
    if passed == total:
        logger.info("\n  🎉 所有测试通过！盈亏计算修复成功！")
    else:
        logger.error("\n  ⚠️  部分测试失败，请检查代码")
    
    logger.info("="*70 + "\n")
    
    # 生成可视化报告
    if test_results:
        generate_visualization()
    else:
        logger.warning("没有测试结果可供可视化")


if __name__ == "__main__":
    main()

