# CTP Gateway 模块安装说明

## 当前状态

⚠ **vnpy_ctp 模块未安装**

VeighNa Trader UI 已启动，但无法使用 CTP Gateway 功能。

## 问题原因

`vnpy_ctp` 模块需要从源代码编译，需要 C++ 编译器。在 Windows 上需要：

1. **Visual Studio Build Tools** 或 **Visual Studio**（包含 C++ 编译工具）
2. 或者使用预编译的 wheel 包（如果有）

## 解决方案

### 方案1：安装 Visual Studio Build Tools（推荐）

1. 下载并安装 [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
2. 在安装时选择 "C++ 生成工具" 工作负载
3. 安装完成后，重新运行：
   ```powershell
   conda activate vnpyenv
   pip install vnpy_ctp
   ```

### 方案2：使用预编译 wheel 包（推荐，Python 3.10）

**当前环境：Python 3.10.19**

对于 Python 3.10，有预编译的 wheel 包可用，**无需 C++ 编译器**：

```powershell
# 安装最新稳定版本（推荐）
pip install vnpy_ctp==6.6.9.1

# 或者指定 wheel 文件
pip install https://files.pythonhosted.org/packages/py3/v/vnpy_ctp/vnpy_ctp-6.6.9.1-cp310-cp310-win_amd64.whl
```

**可用版本（Python 3.10）：**
- `vnpy_ctp-6.6.9.1-cp310-cp310-win_amd64.whl` ✅ 推荐
- `vnpy_ctp-6.6.9.0-cp310-cp310-win_amd64.whl`

**注意：**
- 6.7.x 系列只有 Python 3.13 的 wheel 文件
- 如果使用 Python 3.11/3.12，需要从源码编译（需要 C++ 编译器）

### 方案3：使用 VeighNa Studio（最简单）

VeighNa 官方提供了集成环境 [VeighNa Studio](https://download.vnpy.com/veighna_studio-4.2.0.exe)，已包含所有必要的模块和依赖。

### 方案4：暂时不使用 CTP（仅测试 UI）

当前脚本已修改，即使没有 CTP 模块也能启动 UI 界面。您可以：
- 查看 VeighNa Trader 的界面
- 测试其他功能模块
- 等安装好 CTP 模块后再使用交易功能

## 当前运行状态

✅ VeighNa Trader UI 已启动
⚠ CTP Gateway 模块未安装（无法连接交易接口）

## 验证安装

安装完成后，运行以下命令验证：

```powershell
conda activate vnpyenv
python check_ctp.py
```

如果显示 "✓ vnpy_ctp 模块已安装"，说明安装成功。

## 重新运行

安装 CTP 模块后，重新运行：

```powershell
conda activate vnpyenv
python run_ctp.py
```

脚本会自动：
- 检测并加载 CTP Gateway
- 加载账号配置
- 自动连接账号

## 临时解决方案

如果您只是想测试 UI 界面，当前脚本已经可以运行。虽然无法使用 CTP 功能，但可以：
1. 查看 VeighNa Trader 的完整界面
2. 了解各个功能模块的位置
3. 测试其他不需要 CTP 的功能

## 下一步

1. **如果只需要测试 UI**：当前状态已满足，可以查看界面
2. **如果需要使用 CTP 交易**：
   - 安装 Visual Studio Build Tools
   - 或使用 VeighNa Studio
   - 然后重新安装 vnpy_ctp 模块


