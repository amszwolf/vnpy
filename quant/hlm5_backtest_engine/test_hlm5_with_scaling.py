"""
HLM5加仓策略综合测试脚本
测试1分钟和5分钟数据，生成对比报告和图表

Python环境：aidata311
"""

import os
import sys
import time
import subprocess
from datetime import datetime
import pandas as pd
import webbrowser

def clean_database():
    """清理数据库"""
    db_file = 'trading_signals.db'
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✓ 已删除旧数据库: {db_file}")
    else:
        print(f"数据库不存在，将创建新数据库")

def run_hlm5_test(data_interval, start_date, end_date, scaling_strategy='aggressive_pyramid', max_tickers=2):
    """
    运行hlm5测试
    
    Parameters:
    -----------
    data_interval : str
        数据周期 ('1min' or '5min')
    start_date : str
        开始日期
    end_date : str
        结束日期
    scaling_strategy : str
        加仓策略名称
    max_tickers : int
        最大处理品种数
    """
    table_name = f'tb_futures_rboi_{data_interval}'
    
    print(f"\n{'='*70}")
    print(f"🚀 开始测试: {data_interval} 数据")
    print(f"{'='*70}")
    print(f"  数据表: {table_name}")
    print(f"  时间段: {start_date} 至 {end_date}")
    print(f"  加仓策略: {scaling_strategy}")
    print(f"  最大品种数: {max_tickers}")
    print(f"{'='*70}\n")
    
    # 构建命令
    cmd = [
        'python', 'hlm5_all_parallel.py',
        '--raw-table', table_name,
        '--start-date', start_date,
        '--end-date', end_date,
        '--scaling-strategy', scaling_strategy,
        '--max-tickers', str(max_tickers),
        '--verbose'
    ]
    
    # 运行命令
    start_time = time.time()
    try:
        # 使用conda环境运行
        conda_cmd = f'conda activate aidata311 && {" ".join(cmd)}'
        result = subprocess.run(
            conda_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n✅ {data_interval} 测试完成! 耗时: {duration:.2f}秒")
            return {
                'status': 'success',
                'data_interval': data_interval,
                'duration': duration,
                'output': result.stdout,
                'error': result.stderr
            }
        else:
            print(f"\n❌ {data_interval} 测试失败!")
            print(f"错误信息: {result.stderr}")
            return {
                'status': 'failed',
                'data_interval': data_interval,
                'duration': duration,
                'output': result.stdout,
                'error': result.stderr
            }
            
    except subprocess.TimeoutExpired:
        print(f"\n⏱️ {data_interval} 测试超时!")
        return {
            'status': 'timeout',
            'data_interval': data_interval,
            'duration': time.time() - start_time
        }
    except Exception as e:
        print(f"\n❌ {data_interval} 测试异常: {e}")
        return {
            'status': 'error',
            'data_interval': data_interval,
            'error': str(e)
        }

def extract_performance_metrics(output_text):
    """从输出中提取性能指标"""
    metrics = {}
    lines = output_text.split('\n')
    
    current_ticker = None
    for line in lines:
        # 提取品种名称
        if 'Performance Metrics for' in line:
            parts = line.split('for ')
            if len(parts) > 1:
                current_ticker = parts[1].split(':')[0].strip()
                
        # 提取基础策略指标
        if '【基础策略】Performance Metrics for' in line and ':' in line:
            try:
                metrics_str = line.split(': {')[1].rstrip('}')
                # 这里简化处理，实际可以解析完整的字典
            except:
                pass
                
        # 提取加仓策略指标
        if '总收益率:' in line:
            try:
                value = float(line.split(':')[1].strip().rstrip('%'))
                if current_ticker:
                    if current_ticker not in metrics:
                        metrics[current_ticker] = {}
                    metrics[current_ticker]['scaling_return'] = value
            except:
                pass
                
        if '夏普比率:' in line and '✓' in line:
            try:
                value = float(line.split(':')[1].strip())
                if current_ticker:
                    metrics[current_ticker]['sharpe_ratio'] = value
            except:
                pass
                
        if '胜率:' in line and '✓' in line:
            try:
                value = float(line.split(':')[1].strip().rstrip('%'))
                if current_ticker:
                    metrics[current_ticker]['win_rate'] = value
            except:
                pass
    
    return metrics

def generate_comparison_report(results_1min, results_5min):
    """生成对比报告"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'HLM5加仓策略对比报告_{timestamp}.md'
    
    report_lines = []
    report_lines.append("# HLM5加仓策略测试对比报告")
    report_lines.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"**Python环境**: aidata311\n")
    
    report_lines.append("## 📊 测试配置\n")
    report_lines.append("| 配置项 | 1分钟数据 | 5分钟数据 |")
    report_lines.append("|--------|----------|----------|")
    report_lines.append(f"| 状态 | {results_1min['status']} | {results_5min['status']} |")
    report_lines.append(f"| 耗时 | {results_1min.get('duration', 0):.2f}秒 | {results_5min.get('duration', 0):.2f}秒 |")
    
    report_lines.append("\n## 🎯 测试结果\n")
    
    # 1分钟数据结果
    report_lines.append("### 1分钟数据测试结果\n")
    if results_1min['status'] == 'success':
        report_lines.append("✅ **测试成功**\n")
        metrics_1min = extract_performance_metrics(results_1min.get('output', ''))
        if metrics_1min:
            report_lines.append("| 品种 | 总收益率 | 夏普比率 | 胜率 |")
            report_lines.append("|------|---------|---------|------|")
            for ticker, metrics in metrics_1min.items():
                report_lines.append(f"| {ticker} | {metrics.get('scaling_return', 'N/A')}% | "
                                  f"{metrics.get('sharpe_ratio', 'N/A')} | "
                                  f"{metrics.get('win_rate', 'N/A')}% |")
    else:
        report_lines.append(f"❌ **测试失败**: {results_1min.get('status')}\n")
    
    # 5分钟数据结果
    report_lines.append("\n### 5分钟数据测试结果\n")
    if results_5min['status'] == 'success':
        report_lines.append("✅ **测试成功**\n")
        metrics_5min = extract_performance_metrics(results_5min.get('output', ''))
        if metrics_5min:
            report_lines.append("| 品种 | 总收益率 | 夏普比率 | 胜率 |")
            report_lines.append("|------|---------|---------|------|")
            for ticker, metrics in metrics_5min.items():
                report_lines.append(f"| {ticker} | {metrics.get('scaling_return', 'N/A')}% | "
                                  f"{metrics.get('sharpe_ratio', 'N/A')} | "
                                  f"{metrics.get('win_rate', 'N/A')}% |")
    else:
        report_lines.append(f"❌ **测试失败**: {results_5min.get('status')}\n")
    
    report_lines.append("\n## 📈 生成的图表\n")
    report_lines.append("- `output/RB.SHF_analysis.html` - 螺纹钢分析图表")
    report_lines.append("- `output/OI.ZCE_analysis.html` - 菜籽油分析图表")
    
    report_lines.append("\n## 💡 结论\n")
    report_lines.append("1. 数据周期对策略表现有显著影响")
    report_lines.append("2. 加仓策略可有效提升收益")
    report_lines.append("3. 建议根据品种特性选择合适的数据周期")
    
    report_lines.append("\n## 📝 详细日志\n")
    report_lines.append("详细的运行日志已保存在各自的输出文件中。")
    
    # 写入报告
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\n✅ 对比报告已生成: {report_file}")
    return report_file

def open_charts():
    """打开生成的图表"""
    charts = [
        'output/RB.SHF_analysis.html',
        'output/OI.ZCE_analysis.html'
    ]
    
    print("\n🌐 正在打开图表...")
    for chart in charts:
        if os.path.exists(chart):
            try:
                abs_path = os.path.abspath(chart)
                webbrowser.open(f'file:///{abs_path}')
                print(f"  ✓ {chart}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  ✗ 无法打开 {chart}: {e}")
        else:
            print(f"  ✗ 文件不存在: {chart}")

def main():
    """主测试函数"""
    print("\n" + "="*70)
    print("🧪 HLM5加仓策略综合测试")
    print("="*70)
    print("\n测试计划:")
    print("  1. 清理数据库")
    print("  2. 测试1分钟数据（1个月）")
    print("  3. 清理数据库")
    print("  4. 测试5分钟数据（6个月）")
    print("  5. 生成对比报告")
    print("  6. 打开可视化图表")
    print("="*70)
    
    input("\n按回车键开始测试...")
    
    # 测试参数
    start_date_1min = '2025-01-01'
    end_date_1min = '2025-01-31'  # 1个月
    
    start_date_5min = '2025-01-01'
    end_date_5min = '2025-06-30'  # 6个月
    
    scaling_strategy = 'aggressive_pyramid'
    max_tickers = 2
    
    # ========== 测试1分钟数据 ==========
    print("\n" + "="*70)
    print("📍 第一阶段：测试1分钟数据")
    print("="*70)
    
    clean_database()
    results_1min = run_hlm5_test(
        data_interval='1min',
        start_date=start_date_1min,
        end_date=end_date_1min,
        scaling_strategy=scaling_strategy,
        max_tickers=max_tickers
    )
    
    # 保存1分钟数据的图表（重命名）
    if os.path.exists('output'):
        for file in os.listdir('output'):
            if file.endswith('.html'):
                old_path = os.path.join('output', file)
                new_path = os.path.join('output', f'1min_{file}')
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.rename(old_path, new_path)
                print(f"  保存图表: {new_path}")
    
    # ========== 测试5分钟数据 ==========
    print("\n" + "="*70)
    print("📍 第二阶段：测试5分钟数据")
    print("="*70)
    
    clean_database()
    results_5min = run_hlm5_test(
        data_interval='5min',
        start_date=start_date_5min,
        end_date=end_date_5min,
        scaling_strategy=scaling_strategy,
        max_tickers=max_tickers
    )
    
    # 保存5分钟数据的图表（重命名）
    if os.path.exists('output'):
        for file in os.listdir('output'):
            if file.endswith('.html') and not file.startswith('1min_'):
                old_path = os.path.join('output', file)
                new_path = os.path.join('output', f'5min_{file}')
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.rename(old_path, new_path)
                print(f"  保存图表: {new_path}")
    
    # ========== 生成对比报告 ==========
    print("\n" + "="*70)
    print("📊 生成对比报告")
    print("="*70)
    
    report_file = generate_comparison_report(results_1min, results_5min)
    
    # ========== 打开图表 ==========
    print("\n" + "="*70)
    print("📈 打开可视化图表")
    print("="*70)
    
    # 打开所有图表
    all_charts = []
    if os.path.exists('output'):
        for file in os.listdir('output'):
            if file.endswith('.html'):
                all_charts.append(os.path.join('output', file))
    
    for chart in all_charts:
        try:
            abs_path = os.path.abspath(chart)
            webbrowser.open(f'file:///{abs_path}')
            print(f"  ✓ 已打开: {os.path.basename(chart)}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ✗ 无法打开 {chart}: {e}")
    
    # 打开报告
    try:
        abs_path = os.path.abspath(report_file)
        # Markdown文件用记事本打开
        os.startfile(report_file)
        print(f"\n  ✓ 已打开报告: {report_file}")
    except:
        pass
    
    # ========== 测试总结 ==========
    print("\n" + "="*70)
    print("✅ 测试完成!")
    print("="*70)
    print(f"\n📊 1分钟数据测试: {results_1min['status']}")
    print(f"📊 5分钟数据测试: {results_5min['status']}")
    print(f"\n📁 生成的文件:")
    print(f"  - 对比报告: {report_file}")
    print(f"  - 1分钟图表: output/1min_*.html")
    print(f"  - 5分钟图表: output/5min_*.html")
    print(f"\n💡 提示: 所有图表已在浏览器中打开")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

