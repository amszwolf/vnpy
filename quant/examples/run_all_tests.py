"""
按照常规流程逐个运行和调试量化交易框架
"""

import sys
import subprocess
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))


def run_step(step_num: int, step_name: str, script_path: str, description: str):
    """
    运行单个步骤
    
    参数:
        step_num: 步骤编号
        step_name: 步骤名称
        script_path: 脚本路径
        description: 步骤描述
    """
    print("\n" + "=" * 60)
    print(f"步骤 {step_num}: {step_name}")
    print("=" * 60)
    print(f"描述: {description}")
    print(f"脚本: {script_path}")
    print("-" * 60)
    
    # 检查脚本是否存在
    script_file = Path(__file__).parent / script_path
    if not script_file.exists():
        print(f"⚠ 脚本不存在: {script_file}")
        return False
    
    # 运行脚本
    print(f"\n正在运行: {script_path}")
    result = subprocess.run(
        [sys.executable, str(script_file)],
        cwd=str(Path(__file__).parent),
        capture_output=False
    )
    
    if result.returncode == 0:
        print(f"\n✓ 步骤 {step_num} 完成")
        return True
    else:
        print(f"\n✗ 步骤 {step_num} 失败 (退出码: {result.returncode})")
        return False


def main():
    """
    主函数：按照流程逐个运行
    """
    print("=" * 60)
    print("VeighNa 量化交易框架 - 完整测试流程")
    print("=" * 60)
    print("\n本脚本将按照常规流程逐个运行和调试各个模块")
    print("按Enter继续，按Ctrl+C中断\n")
    
    input("按Enter开始...")
    
    # 步骤列表
    steps = [
        {
            "num": 1,
            "name": "数据准备",
            "script": "data/download_main_contract_data.py",
            "description": "使用RQData下载主力合约5分钟数据（基于OI持仓量）"
        },
        {
            "num": 2,
            "name": "策略回测",
            "script": "backtesting/run_backtest.py",
            "description": "运行策略回测，验证策略表现"
        },
        {
            "num": 3,
            "name": "参数优化",
            "script": "backtesting/optimizer.py",
            "description": "运行参数优化，寻找最优参数组合"
        },
        {
            "num": 4,
            "name": "完整工作流",
            "script": "complete_example.py",
            "description": "运行完整工作流（回测+分析+复盘）"
        }
    ]
    
    # 逐个运行
    results = []
    for step in steps:
        success = run_step(
            step["num"],
            step["name"],
            step["script"],
            step["description"]
        )
        results.append((step["num"], step["name"], success))
        
        if not success:
            print(f"\n⚠ 步骤 {step['num']} 失败，是否继续？(y/n): ", end="")
            choice = input().strip().lower()
            if choice != 'y':
                print("已中断")
                break
        
        # 等待用户确认继续
        if step["num"] < len(steps):
            print("\n按Enter继续下一步...")
            input()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试流程总结")
    print("=" * 60)
    for num, name, success in results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"步骤 {num}: {name} - {status}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

