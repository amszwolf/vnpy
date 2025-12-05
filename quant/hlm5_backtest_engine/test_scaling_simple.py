"""简化的加仓策略测试"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from trading_signal_database_manager import TradingSignalDatabaseManager
from scaling_strategy import generate_scaling_signals, calculate_scaling_performance, SCALING_CONFIGS
from datetime import datetime

print("="*70)
print("开始测试加仓策略（5分钟数据，2025-01-01至2025-06-30）")
print("="*70)

db = TradingSignalDatabaseManager('trading_signals.db')

tickers = ['RB.SHF', 'OI.ZCE']
start_date = '2025-01-01'
end_date = '2025-06-30'

results_html = []
results_html.append("<html><head><meta charset='utf-8'><title>加仓策略测试结果</title></head><body>")
results_html.append("<h1>加仓策略测试结果（5分钟数据）</h1>")
results_html.append(f"<p>测试期间: {start_date} 至 {end_date}</p>")

for ticker in tickers:
    print(f"\n{'='*50}")
    print(f"测试 {ticker}")
    print(f"{'='*50}")
    
    results_html.append(f"<h2>{ticker}</h2>")
    results_html.append("<table border='1' cellpadding='5'>")
    results_html.append("<tr><th>策略</th><th>总收益率</th><th>年化收益</th><th>夏普比率</th><th>胜率</th><th>交易次数</th><th>平均加仓层级</th></tr>")
    
    for strategy_name, config in SCALING_CONFIGS.items():
        print(f"\n  测试策略: {strategy_name}")
        
        try:
            # 生成加仓信号
            signals_df = generate_scaling_signals(db, ticker, start_date, end_date, config)
            
            if signals_df.empty:
                print(f"    ❌ 无信号数据")
                results_html.append(f"<tr><td>{strategy_name}</td><td colspan='6'>无信号数据</td></tr>")
                continue
            
            # 计算性能
            metrics = calculate_scaling_performance(signals_df)
            
            print(f"    ✓ 总收益: {metrics['total_return_pct']:.2f}%")
            print(f"    ✓ 胜率: {metrics['win_rate']:.2%}")
            print(f"    ✓ 交易次数: {metrics['total_trades']}")
            print(f"    ✓ 平均加仓层级: {metrics['avg_scaling_levels']:.2f}")
            
            results_html.append(
                f"<tr>"
                f"<td>{strategy_name}</td>"
                f"<td>{metrics['total_return_pct']:.2f}%</td>"
                f"<td>{metrics['annual_return_pct']:.2f}%</td>"
                f"<td>{metrics['sharpe_ratio']:.4f}</td>"
                f"<td>{metrics['win_rate']:.2%}</td>"
                f"<td>{metrics['total_trades']}</td>"
                f"<td>{metrics['avg_scaling_levels']:.2f}</td>"
                f"</tr>"
            )
            
        except Exception as e:
            print(f"    ❌ 错误: {str(e)}")
            results_html.append(f"<tr><td>{strategy_name}</td><td colspan='6'>错误: {str(e)}</td></tr>")
    
    results_html.append("</table>")

results_html.append("<p>测试完成时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "</p>")
results_html.append("</body></html>")

# 保存HTML结果
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
html_file = f'scaling_test_results_{timestamp}.html'
with open(html_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(results_html))

print(f"\n{'='*70}")
print(f"测试完成！结果已保存到: {html_file}")
print(f"{'='*70}")

db.close()

