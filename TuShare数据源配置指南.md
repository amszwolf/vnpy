# TuShare 数据源配置完整指南

## 为什么选择 TuShare？

- ✅ **性价比高**：相比RQData，TuShare价格更实惠
- ✅ **数据全面**：支持股票、期货、指数、基金等多种数据
- ✅ **易于使用**：配置简单，Token方式授权
- ✅ **已安装**：`vnpy_tushare` 模块已安装完成

## 第一步：获取 TuShare Token

### 1. 注册账号

1. 访问 [Tushare Pro](https://tushare.pro/)
2. 点击右上角【注册】
3. 填写手机号、验证码等信息完成注册

### 2. 获取 Token

1. 登录 Tushare Pro
2. 点击右上角头像，进入【个人中心】
3. 在【接口Token】页面可以看到你的Token
4. 复制Token（格式类似：`a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`）

### 3. 积分说明

- **免费版**：注册后自动获得120积分，每日有调用限制
- **付费版**：根据套餐不同，积分和调用频率更高
- **积分用途**：每次数据查询会消耗积分，不同数据消耗不同

## 第二步：配置 TuShare 数据源

### 方法1：通过GUI界面配置（推荐）

1. 启动 VeighNa Trader
2. 点击菜单栏的【配置】按钮
3. 在弹出的全局配置对话框中，找到数据服务相关配置：
   - **datafeed.name**: `tushare`
   - **datafeed.username**: `token`（固定值，必须填写"token"）
   - **datafeed.password**: 你的TuShare Token（从Tushare Pro获取）
4. 填写完成后，点击【确定】保存

### 方法2：通过代码配置

在启动脚本中（如 `run_with_accounts.py`）的 `main()` 函数开头添加：

```python
from vnpy.trader.setting import SETTINGS

# 配置TuShare数据服务
SETTINGS["datafeed.name"] = "tushare"
SETTINGS["datafeed.username"] = "token"  # 固定值，必须为"token"
SETTINGS["datafeed.password"] = "你的TuShare Token"  # 替换为你的实际Token
```

### 方法3：直接编辑配置文件

1. 找到配置文件：`.vntrader/vt_setting.json`
2. 编辑文件，添加或修改以下字段：
```json
{
    "datafeed.name": "tushare",
    "datafeed.username": "token",
    "datafeed.password": "你的TuShare Token"
}
```

## 第三步：验证配置

### 检查配置是否生效

运行以下命令检查配置：

```python
from vnpy.trader.setting import SETTINGS

print("数据源名称:", SETTINGS.get("datafeed.name", "未配置"))
print("用户名:", SETTINGS.get("datafeed.username", "未配置"))
print("Token:", "已配置" if SETTINGS.get("datafeed.password") else "未配置")
```

### 测试数据下载

1. 启动 VeighNa Trader
2. 打开【功能】->【数据管理】
3. 点击【下载数据】
4. 填写测试信息：
   - **代码**: `000001`（平安银行股票）或 `IF888`（股指期货）
   - **交易所**: `SSE`（上交所）或 `CFFEX`（中金所）
   - **周期**: `DAILY`（日线）
   - **开始日期**: `2024/01/01`
5. 点击【下载】按钮
6. 如果配置正确，应该能够成功下载数据

## TuShare 支持的数据类型

### 股票数据
- 代码格式：`000001`、`600000` 等
- 交易所：`SSE`（上交所）、`SZSE`（深交所）
- 周期：日线、分钟线（根据Token等级）

### 期货数据
- 代码格式：`IF888`、`rb888` 等
- 交易所：`CFFEX`、`SHFE`、`DCE`、`CZCE` 等
- 周期：日线、分钟线（根据Token等级）

### 指数数据
- 代码格式：`000001`（上证指数）、`399001`（深证成指）等
- 交易所：`SSE`、`SZSE`

## 常见问题

### 1. Token无效或过期

- **问题**：下载数据时提示Token错误
- **解决**：
  - 检查Token是否正确复制（不要有多余空格）
  - 登录Tushare Pro确认Token是否有效
  - 如果Token过期，重新生成新Token

### 2. 积分不足

- **问题**：下载数据时提示积分不足
- **解决**：
  - 登录Tushare Pro查看剩余积分
  - 免费版每日有调用限制，建议升级付费版
  - 或者等待第二天积分重置

### 3. 数据查询失败

- **问题**：某些合约无法下载数据
- **解决**：
  - 检查合约代码格式是否正确
  - 确认该合约在TuShare中有数据
  - 检查Token等级是否支持该数据类型

### 4. 配置不生效

- **问题**：修改配置后仍然无法下载
- **解决**：
  - 确认配置文件路径正确（`.vntrader/vt_setting.json`）
  - 重启VeighNa Trader使配置生效
  - 检查配置字段名称是否正确（注意大小写）

## 从 RQData 切换到 TuShare

如果你之前使用的是RQData，切换到TuShare的步骤：

1. **安装模块**（已完成）：
   ```bash
   pip install vnpy_tushare
   ```

2. **获取Token**：
   - 访问 https://tushare.pro/ 注册并获取Token

3. **修改配置**：
   - 通过GUI：点击【配置】，将 `datafeed.name` 改为 `tushare`
   - 或直接编辑 `vt_setting.json` 文件

4. **重启程序**：
   - 关闭VeighNa Trader
   - 重新运行 `run_with_accounts.py`

## 价格对比

| 数据服务 | 免费版 | 付费版价格 | 数据范围 |
|---------|--------|-----------|---------|
| TuShare | 120积分/日 | 约200-2000元/年 | 股票、期货、指数等 |
| RQData | 无 | 约3000-10000元/年 | 股票、期货、期权等 |

**建议**：对于个人用户，TuShare性价比更高。

## 更多资源

- **TuShare官方文档**: https://tushare.pro/document/1
- **TuShare GitHub**: https://github.com/waditu/tushare
- **vnpy_tushare项目**: https://github.com/vnpy/vnpy_tushare
- **VeighNa数据源文档**: 查看 `数据源配置指南.md`

