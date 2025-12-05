#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
监控测试进度并自动打开图表
"""
import os
import time
import webbrowser
from datetime import datetime

print("="*80)
print("监控 hlm5_all_parallel.py 运行进度")
print("="*80)
print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 检查output目录
output_dir = 'output'
expected_files = ['RB.SHF_analysis.html', 'OI.ZCE_analysis.html']

print("等待图表生成...")
print(f"监控目录: {os.path.abspath(output_dir)}\n")

max_wait = 300  # 最多等待5分钟
check_interval = 5  # 每5秒检查一次
waited = 0

existing_files = set()

while waited < max_wait:
    # 检查文件是否存在
    current_files = set()
    
    if os.path.exists(output_dir):
        for filename in os.listdir(output_dir):
            if filename.endswith('.html'):
                current_files.add(filename)
    
    # 检查是否有新文件生成
    new_files = current_files - existing_files
    if new_files:
        for filename in new_files:
            print(f"✓ 发现新文件: {filename}")
        existing_files = current_files
    
    # 检查是否所有文件都生成了
    all_generated = all(f in current_files for f in expected_files)
    
    if all_generated:
        print(f"\n✓ 所有图表已生成！")
        break
    
    # 显示进度
    if waited % 30 == 0 and waited > 0:
        print(f"  已等待 {waited} 秒... ({len(current_files)}/{len(expected_files)} 个文件)")
    
    time.sleep(check_interval)
    waited += check_interval

print(f"\n{'='*80}")
print("打开图表...")
print(f"{'='*80}\n")

# 打开图表
charts_opened = 0

if os.path.exists(output_dir):
    html_files = [f for f in os.listdir(output_dir) if f.endswith('.html') and 'analysis' in f]
    
    print(f"找到 {len(html_files)} 个图表文件:\n")
    
    for filename in html_files:
        filepath = os.path.join(output_dir, filename)
        abs_path = os.path.abspath(filepath)
        
        try:
            print(f"  打开: {filename}")
            webbrowser.open(f'file:///{abs_path}')
            charts_opened += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"    错误: {e}")

# 打开output目录
print(f"\n打开output目录...")
try:
    os.startfile(output_dir)
    print("✓ 目录已打开")
except Exception as e:
    print(f"  错误: {e}")

print(f"\n{'='*80}")
print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*80}")

if charts_opened > 0:
    print(f"\n✓ 成功打开 {charts_opened} 个图表")
else:
    print(f"\n⚠️ 未找到图表文件")
    print(f"请检查 {os.path.abspath(output_dir)} 目录")

print(f"\n所有图表保存在: {os.path.abspath(output_dir)}\n")


