# -*- coding: utf-8 -*-
"""
HLM5 QMT统一接口模块
提供QMT交易和行情数据的统一接口

主要功能:
1. 多账户配置管理
2. QMT连接和初始化
3. 交易接口封装
4. 行情数据接口封装
5. 单元测试功能
"""

import os
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd

# QMT相关导入
try:
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
    from xtquant.xttype import StockAccount
    from xtquant import xtconstant
    from xtquant import xtdata
    HAS_XTQUANT = True
except ImportError:
    HAS_XTQUANT = False
    print("警告: 未找到xtquant模块，QMT功能将受限")


class QMTAccountConfig:
    """QMT账户配置类"""
    
    ACCOUNTS = {
        'hfzq_real': {
            'account_id': '291200008553',
            'base_path': 'D:\\Install\\qmt_fhzq',
            'name': '华福证券实盘账号'
        },
        'hfzq_sim': {
            'account_id': '29050000002701',
            'base_path': 'D:\\Install\\QMT_HF_Sim',
            'name': '华福证券模拟账号(默认)'
        },
        'hfzq_sim_old': {
            'account_id': '02300801159901',
            'base_path': 'D:\\Install\\QMT_HF_Sim',
            'name': '华福证券模拟账号(旧)'
        }
    }
    
    @classmethod
    def get_account_config(cls, account_name: str = 'hfzq_sim') -> Dict:
        """获取账户配置"""
        if account_name not in cls.ACCOUNTS:
            raise ValueError(f"未知账户: {account_name}")
        return cls.ACCOUNTS[account_name].copy()


class QMTCallback(XtQuantTraderCallback):
    """QMT回调处理器"""
    
    def __init__(self, qmt_client=None):
        self.qmt_client = qmt_client
        self.logger = logging.getLogger(__name__)
    
    def on_disconnected(self):
        self.logger.warning("QMT连接断开")

    def on_stock_order(self, order):
        self.logger.info(f"委托回报: {order.stock_code} {order.order_status}")

    def on_stock_asset(self, asset):
        self.logger.info(f"资金变动: {asset.cash}")

    def on_stock_trade(self, trade):
        self.logger.info(f"成交变动: {trade.stock_code}")

    def on_stock_position(self, position):
        self.logger.info(f"持仓变动: {position.stock_code}")


class QMTClient:
    """QMT统一接口客户端"""
    
    def __init__(self, account_name: str = 'hfzq_sim', session_id: int = 123456, simulation_mode: bool = False):
        self.account_name = account_name
        self.session_id = session_id
        # 强制禁用模拟模式
        self.simulation_mode = False
        
        self.account_config = QMTAccountConfig.get_account_config(account_name)
        self.xt_trader = None
        self.account = None
        self.is_connected = False
        self.logger = logging.getLogger(__name__)
        
        print(f"QMT客户端初始化: {self.account_config['name']} (真实模式)")
        
        # 检查xtquant模块
        if not HAS_XTQUANT:
            raise ImportError("未找到xtquant模块，无法使用QMT功能。请确保已正确安装QMT并配置Python环境。")
    
    def connect(self) -> bool:
        """连接QMT - 失败时直接抛出异常"""
        print("开始连接QMT...")
        
        # 检查QMT安装路径
        exe_path = f"{self.account_config['base_path']}\\bin.x64\\XtMiniQmt.exe"
        userdata_path = f"{self.account_config['base_path']}\\userdata_mini"
        
        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"QMT执行文件不存在: {exe_path}\n请检查QMT安装路径是否正确")
        
        if not os.path.exists(userdata_path):
            raise FileNotFoundError(f"QMT用户数据目录不存在: {userdata_path}\n请检查QMT安装路径是否正确")
        
        print(f"启动QMT客户端: {exe_path}")
        # 启动QMT客户端
        subprocess.Popen(exe_path)
        print("等待QMT客户端启动...")
        time.sleep(10)
        
        print("创建交易接口...")
        # 创建交易接口
        self.xt_trader = XtQuantTrader(userdata_path, self.session_id)
        
        callback = QMTCallback(self)
        self.xt_trader.register_callback(callback)
        self.xt_trader.start()
        
        self.account = StockAccount(self.account_config['account_id'])
        
        print("连接交易服务器...")
        connect_result = self.xt_trader.connect()
        if connect_result != 0:
            error_messages = {
                -1: "连接失败，可能的原因：QMT客户端未登录或网络连接问题",
                -2: "账户信息错误",
                -3: "服务器拒绝连接",
                -4: "超时"
            }
            error_msg = error_messages.get(connect_result, f"未知错误码: {connect_result}")
            raise ConnectionError(f"QMT连接失败 (错误码: {connect_result}): {error_msg}\n"
                                f"请确保:\n"
                                f"1. QMT客户端已经启动并登录\n"
                                f"2. 账户ID正确: {self.account_config['account_id']}\n"
                                f"3. 网络连接正常")
        
        print("订阅账户...")
        subscribe_result = self.xt_trader.subscribe(self.account)
        if subscribe_result != 0:
            raise ConnectionError(f"账号订阅失败 (错误码: {subscribe_result})\n"
                                f"账户ID: {self.account_config['account_id']}\n"
                                f"请检查账户是否有效")
        
        self.is_connected = True
        print(f"✅ QMT连接成功! 账户: {self.account_config['account_id']}")
        return True
    
    def place_order(self, stock_code: str, action: str, volume: int, price: float = None) -> Optional[str]:
        """下单 - 真实模式，错误直接抛出"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法进行交易")
        
        if not self.is_connected:
            raise ConnectionError("QMT未连接，请先调用connect()方法")
        
        print(f"提交订单: {action} {stock_code} {volume}股 @{price}")
        
        order_type = xtconstant.STOCK_BUY if action.upper() == 'BUY' else xtconstant.STOCK_SELL
        order_id = self.xt_trader.order_stock(
            self.account, stock_code, order_type, volume,
            xtconstant.FIX_PRICE, price or 10.0, 'HLM5', ''
        )
        
        if order_id:
            print(f"✅ 订单提交成功: {order_id}")
            return str(order_id)
        else:
            raise RuntimeError(f"订单提交失败: {action} {stock_code} {volume}股")
    
    def get_account_info(self) -> Dict:
        """获取账户信息 - 真实模式"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法获取账户信息")
        
        if not self.is_connected:
            raise ConnectionError("QMT未连接，请先调用connect()方法")
        
        print("获取账户信息...")
        asset = self.xt_trader.query_stock_asset(self.account)
        
        return {
            'account_id': self.account_config['account_id'],
            'total_asset': asset.total_asset if asset else 0,
            'cash': asset.cash if asset else 0,
            'positions': {}
        }
    
    def get_market_data(self, stock_list: List[str], period: str = '1d', count: int = 1, 
                       field_list: List[str] = None, start_time: str = '', end_time: str = '') -> Dict:
        """获取行情数据 - 使用标准QMT API"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法获取行情数据")
        
        if not self.is_connected:
            raise ConnectionError("QMT未连接，请先调用connect()方法")
        
        # 如果field_list为空，获取所有字段
        if field_list is None:
            field_list = []
        
        print(f"获取行情数据: {stock_list}, 周期: {period}, 数量: {count}")
        
        return xtdata.get_market_data(
            field_list=field_list,
            stock_list=stock_list,
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=count,
            dividend_type='none',
            fill_data=True
        )
    
    def download_sector_data(self) -> bool:
        """下载板块数据"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法下载板块数据")
        
        print("下载板块数据...")
        xtdata.download_sector_data()
        print("✅ 板块数据下载完成")
        return True
    
    def get_stock_list_in_sector(self, sector_name: str) -> List[str]:
        """获取板块成分股"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法获取板块成分股")
        
        print(f"获取板块成分股: {sector_name}")
        stocks = xtdata.get_stock_list_in_sector(sector_name)
        print(f"✅ 获取到 {len(stocks)} 只成分股")
        return stocks
    
    def get_index_data(self, index_codes: List[str] = None) -> Dict:
        """获取指数数据 - 包含沪深300等主要指数"""
        if index_codes is None:
            index_codes = [
                '000001.SH',  # 上证指数
                '399001.SZ',  # 深成指数
                '000300.SH',  # 沪深300
                '000852.SH'   # 中证1000
            ]
        
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法获取指数数据")
        
        if not self.is_connected:
            raise ConnectionError("QMT未连接，请先调用connect()方法")
        
        result = {}
        failed_codes = []
        
        print(f"获取指数数据: {index_codes}")
        
        # 逐个获取指数数据
        for code in index_codes:
            print(f"  正在获取 {code} 数据...")
            
            try:
                market_data = xtdata.get_market_data(
                    field_list=['close'],
                    stock_list=[code],
                    period='1d',
                    count=2,  # 获取2天数据用于计算涨跌幅
                    dividend_type='none',
                    fill_data=True
                )
                
                if market_data and 'close' in market_data:
                    close_df = market_data['close']
                    if code in close_df.columns:
                        if len(close_df) >= 2:
                            current_price = close_df.iloc[-1][code]
                            prev_price = close_df.iloc[-2][code]
                            
                            if current_price and prev_price and not pd.isna(current_price) and not pd.isna(prev_price):
                                change_pct = ((current_price - prev_price) / prev_price) * 100
                                result[code] = {
                                    'close': float(current_price),
                                    'change_pct': float(change_pct)
                                }
                                print(f"    ✓ {code}: {current_price:.2f} ({change_pct:+.2f}%)")
                            else:
                                print(f"    ✗ {code}: 价格数据无效")
                                failed_codes.append(code)
                        elif len(close_df) >= 1:
                            # 如果只有一天数据，涨跌幅设为0
                            current_price = close_df.iloc[-1][code]
                            if current_price and not pd.isna(current_price):
                                result[code] = {
                                    'close': float(current_price),
                                    'change_pct': 0.0
                                }
                                print(f"    ✓ {code}: {current_price:.2f} (无前一日数据)")
                            else:
                                print(f"    ✗ {code}: 当前价格数据无效")
                                failed_codes.append(code)
                        else:
                            print(f"    ✗ {code}: 无价格数据")
                            failed_codes.append(code)
                    else:
                        print(f"    ✗ {code}: 指数代码不在返回数据中")
                        failed_codes.append(code)
                else:
                    print(f"    ✗ {code}: 获取行情数据失败")
                    failed_codes.append(code)
            except Exception as e:
                print(f"    ✗ {code}: 获取异常 - {e}")
                failed_codes.append(code)
        
        # 如果有成功获取的数据，返回成功的部分
        if result:
            if failed_codes:
                print(f"警告: {len(failed_codes)} 个指数获取失败: {failed_codes}")
            return result
        else:
            # 所有指数都失败，但不抛出异常，返回空字典
            print(f"警告: 所有指数数据获取失败: {index_codes}")
            return {}
    
    def get_detailed_account_info(self) -> Dict:
        """获取详细账户信息（包括持仓详情） - 真实模式"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法获取账户信息")
        
        if not self.is_connected:
            raise ConnectionError("QMT未连接，请先调用connect()方法")
        
        print("获取详细账户信息...")
        
        # 获取资金信息
        asset = self.xt_trader.query_stock_asset(self.account)
        
        # 获取持仓信息
        positions = self.xt_trader.query_stock_positions(self.account)
        
        result = {
            'account_id': self.account_config['account_id'],
            'total_asset': asset.total_asset if asset else 0,
            'cash': asset.cash if asset else 0,
            'market_value': asset.market_value if asset else 0,
            'frozen_cash': asset.frozen_cash if asset else 0,
            'positions': {}
        }
        
        # 处理持仓数据
        if positions:
            for pos in positions:
                result['positions'][pos.stock_code] = {
                    'volume': pos.volume,
                    'can_use_volume': pos.can_use_volume,
                    'open_price': pos.open_price,
                    'market_value': pos.market_value
                }
        
        return result
    
    def get_financial_data(self, stock_list: List[str], table_list: List[str]) -> Dict:
        """获取财务数据"""
        if not HAS_XTQUANT:
            raise RuntimeError("xtquant模块未安装，无法获取财务数据")
        
        print(f"获取财务数据: {stock_list}, 表: {table_list}")
        return xtdata.get_financial_data(
            stock_list=stock_list,
            table_list=table_list,
            start_time='',
            end_time='',
            report_type='report_time'
        )


def test_qmt_module():
    """测试QMT模块 - 已废弃，请使用run_qmt_test"""
    print("此函数已废弃，请使用 run_qmt_test() 函数")
    return False


# 单元测试功能 - 真实模式
def run_qmt_test(account_name: str = 'hfzq_sim'):
    """QMT模块单元测试 - 真实模式，连接失败将直接抛出异常"""
    print("="*60)
    print("QMT模块单元测试开始 (真实模式)")
    print("="*60)
    
    # 1. 测试账户配置
    print("\n1. 测试账户配置:")
    config = QMTAccountConfig.get_account_config(account_name)
    print(f"✓ 账户配置成功: {config['name']}")
    print(f"  账户ID: {config['account_id']}")
    print(f"  QMT路径: {config['base_path']}")
    
    # 2. 测试QMT客户端初始化
    print("\n2. 测试QMT客户端初始化:")
    client = QMTClient(account_name=account_name)
    print(f"✓ QMT客户端创建成功 (真实模式)")
    
    # 3. 测试连接 - 失败将直接抛出异常
    print("\n3. 测试连接:")
    client.connect()
    print("✅ QMT连接成功")
    
    # 4. 测试市场数据获取
    print("\n4. 测试市场数据获取:")
    test_stocks = ['000001.SZ', '600000.SH']
    market_data = client.get_market_data(test_stocks, period='1d', count=5)
    print(f"✓ 市场数据获取成功")
    print(f"  返回数据类型: {type(market_data)}")
    if isinstance(market_data, dict):
        print(f"  数据字段: {list(market_data.keys())}")
    
    # 5. 测试常见股票行情获取
    print("\n5. 测试常见股票行情获取:")
    try:
        common_stocks = ['000001.SZ', '600519.SH', '000002.SZ']  # 平安银行、茅台、万科
        stock_data = client.get_market_data(common_stocks, period='1d', count=1, field_list=['close'])
        if stock_data and 'close' in stock_data:
            print(f"✓ 股票行情获取成功")
            close_df = stock_data['close']
            for stock in common_stocks:
                if stock in close_df.columns:
                    price = close_df.iloc[-1][stock]
                    if not pd.isna(price):
                        print(f"  {stock}: ¥{price:.2f}")
                    else:
                        print(f"  {stock}: 价格数据无效")
                else:
                    print(f"  {stock}: 未找到数据")
        else:
            print("⚠️  股票行情获取失败")
    except Exception as e:
        print(f"⚠️  股票行情获取异常: {e}")
    
    # 5.5. 测试交易功能 (小量测试)
    print("\n5.5. 测试交易功能:")
    print("⚠️  注意: 这将提交真实订单!")
    response = input("确认要进行交易测试吗? (y/N): ")
    if response.lower() == 'y':
        try:
            order_id = client.place_order('000001.SZ', 'BUY', 100, 10.0)
            print(f"✓ 下单测试成功，订单ID: {order_id}")
        except Exception as e:
            print(f"✗ 下单测试失败: {e}")
    else:
        print("⏭️  跳过交易测试")
    
    # 6. 测试指数数据获取
    print("\n6. 测试指数数据获取:")
    try:
        index_data = client.get_index_data()
        if index_data:
            print(f"✓ 指数数据获取成功 ({len(index_data)}个指数)")
            index_names = {
                '000001.SH': '上证指数',
                '399001.SZ': '深成指数',
                '000300.SH': '沪深300',
                '000852.SH': '中证1000'
            }
            
            for code, data in index_data.items():
                name = index_names.get(code, code)
                close_price = data.get('close', 0)
                change_pct = data.get('change_pct', 0)
                change_symbol = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
                print(f"  {name}: {close_price:.2f} ({change_pct:+.2f}%) {change_symbol}")
        else:
            print("⚠️  指数数据获取失败，但程序继续运行")
            print("  可能原因：指数代码格式不正确或权限不足")
    except Exception as e:
        print(f"⚠️  指数数据获取异常: {e}")
        print("  测试继续进行...")
    
    # 7. 测试详细账户信息获取
    print("\n7. 测试账户信息获取:")
    account_info = client.get_detailed_account_info()
    print(f"✓ 账户信息获取成功")
    print(f"  账户ID: {account_info.get('account_id', 'N/A')}")
    print(f"  总资产: ¥{account_info.get('total_asset', 0):,.2f}")
    print(f"  可用资金: ¥{account_info.get('cash', 0):,.2f}")
    print(f"  股票市值: ¥{account_info.get('market_value', 0):,.2f}")
    print(f"  冻结资金: ¥{account_info.get('frozen_cash', 0):,.2f}")
    
    positions = account_info.get('positions', {})
    if positions:
        print(f"  持仓详情 ({len(positions)}只股票):")
        total_market_value = 0
        for stock_code, pos in positions.items():
            volume = pos.get('volume', 0)
            open_price = pos.get('open_price', 0)
            market_value = pos.get('market_value', 0)
            total_market_value += market_value
            
            print(f"    {stock_code}: {volume}股, 成本价¥{open_price:.2f}, 市值¥{market_value:,.2f}")
        
        print(f"  持仓总市值: ¥{total_market_value:,.2f}")
        
        # 计算资产配置比例
        total_asset = account_info.get('total_asset', 0)
        if total_asset > 0:
            cash_ratio = (account_info.get('cash', 0) / total_asset) * 100
            stock_ratio = (total_market_value / total_asset) * 100
            print(f"  资产配置: 现金{cash_ratio:.1f}% | 股票{stock_ratio:.1f}%")
    else:
        print("  当前无持仓")
    
    print("\n" + "="*60)
    print("QMT模块单元测试完成")
    print("="*60)
    return True


def show_help():
    """显示帮助信息"""
    help_text = """
HLM5 QMT统一接口模块
====================

主要功能:
- 多账户配置管理  
- QMT连接和初始化
- 交易接口封装
- 行情数据接口封装
- 单元测试功能

使用方法:
---------

基本用法:
  python hlm5_qmt.py                    # 使用默认模拟账户测试
  python hlm5_qmt.py --account hfzq_sim # 使用指定账户测试
  python hlm5_qmt.py --account hfzq_real # 使用实盘账户测试

参数说明:
  --account ACCOUNT    选择QMT账户类型
                       可选值: hfzq_sim (默认), hfzq_real, hfzq_sim_old
  --test-only         仅测试连接，跳过交易功能测试
  --verbose           显示详细日志信息
  --help              显示此帮助信息
  --help-examples     显示使用示例

支持的账户类型:
  hfzq_sim       华福证券模拟账号(默认) - 安全测试环境
  hfzq_real      华福证券实盘账号 - 真实交易环境
  hfzq_sim_old   华福证券模拟账号(旧) - 备用测试环境

注意事项:
  ⚠️  使用实盘账户(hfzq_real)将连接真实交易环境
  ⚠️  交易测试功能会提交真实订单，请谨慎使用
  ⚠️  确保QMT客户端已启动并登录相应账户
"""
    print(help_text)


def show_examples():
    """显示使用示例"""
    examples = """
HLM5 QMT模块使用示例
===================

🔥 常用命令:
-----------

# 模拟账户完整测试
python hlm5_qmt.py --account hfzq_sim

# 实盘账户测试(谨慎使用)  
python hlm5_qmt.py --account hfzq_real --test-only

# 详细日志模式
python hlm5_qmt.py --account hfzq_sim --verbose

📋 测试场景示例:
---------------

# 1. 日常连接测试
python hlm5_qmt.py --account hfzq_sim --test-only
# 用途: 验证QMT连接是否正常，不进行交易测试

# 2. 完整功能测试  
python hlm5_qmt.py --account hfzq_sim
# 用途: 测试所有功能，包括行情获取、账户查询等

# 3. 实盘环境检查
python hlm5_qmt.py --account hfzq_real --test-only --verbose
# 用途: 检查实盘环境连接状态，显示详细信息

# 4. 快速验证
python hlm5_qmt.py
# 用途: 使用默认设置快速验证QMT功能

🎯 集成使用示例:
---------------

# 在其他模块中使用QMT客户端
from hlm5_qmt import QMTClient

# 创建客户端实例
client = QMTClient(account_name='hfzq_sim')

# 连接QMT
client.connect()

# 获取市场数据
data = client.get_market_data(['000001.SZ'], period='1d', count=5)

# 获取账户信息
account_info = client.get_detailed_account_info()

# 下单(谨慎使用)
# order_id = client.place_order('000001.SZ', 'BUY', 100, 10.0)

⚠️  重要提醒:
-------------
1. 模拟账户用于开发和测试，无真实资金风险
2. 实盘账户连接真实交易系统，请确认操作无误
3. 交易功能测试会提交真实订单，建议先在模拟环境测试
4. 确保QMT客户端已正确安装并登录相应账户

🔧 故障排除:
-----------
1. 连接失败 → 检查QMT客户端是否启动并登录
2. 账户错误 → 确认账户ID配置正确
3. 权限问题 → 检查账户权限和网络连接
4. 模块缺失 → 确保xtquant模块正确安装
"""
    print(examples)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='HLM5 QMT统一接口模块',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='使用 --help-examples 查看详细使用示例'
    )
    
    # 基础参数
    parser.add_argument('--account', type=str, default='hfzq_sim',
                       choices=['hfzq_sim', 'hfzq_real', 'hfzq_sim_old'],
                       help='选择QMT账户类型 (默认: hfzq_sim)')
    
    # 功能控制参数
    parser.add_argument('--test-only', action='store_true',
                       help='仅测试连接，跳过交易功能测试')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细日志信息')
    
    # 帮助参数
    parser.add_argument('--help-examples', action='store_true',
                       help='显示详细使用示例')
    
    # 兼容旧版本的位置参数
    parser.add_argument('legacy_account', nargs='?', 
                       help=argparse.SUPPRESS)  # 隐藏帮助信息中的位置参数
    
    args = parser.parse_args()
    
    # 显示帮助信息
    if args.help_examples:
        show_examples()
        exit(0)
    
    # 兼容旧版本：如果提供了位置参数，使用位置参数
    if args.legacy_account:
        account_name = args.legacy_account
        print(f"⚠️  使用旧版本参数格式，建议使用: --account {args.legacy_account}")
    else:
        account_name = args.account
    
    # 设置日志级别
    if args.verbose:
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        print("🔍 详细日志模式已启用")
    
    # 显示配置信息
    print(f"使用账户: {account_name}")
    print("连接模式: 真实交易")
    
    # 根据账户类型显示不同的警告信息
    account_configs = QMTAccountConfig.ACCOUNTS
    if account_name in account_configs:
        account_info = account_configs[account_name]
        print(f"账户名称: {account_info['name']}")
        print(f"账户ID: {account_info['account_id']}")
        
        if account_name == 'hfzq_real':
            print("🚨 警告: 即将连接实盘交易账户!")
            print("🚨 警告: 交易测试将提交真实订单!")
            if not args.test_only:
                response = input("确认要连接实盘账户并进行完整测试吗? (y/N): ")
                if response.lower() != 'y':
                    print("已取消测试，建议使用模拟账户或添加 --test-only 参数")
                    exit(0)
        else:
            print("ℹ️  使用模拟账户，安全测试环境")
    else:
        print(f"❌ 错误: 未知账户类型 '{account_name}'")
        print(f"支持的账户类型: {list(account_configs.keys())}")
        exit(1)
    
    # 如果是仅测试模式，修改测试函数行为
    if args.test_only:
        print("🧪 仅测试连接模式，将跳过交易功能测试")
        
        # 临时修改全局变量来控制测试行为
        import types
        original_test = run_qmt_test
        
        def test_only_wrapper(account_name):
            """测试连接模式的包装函数"""
            print("="*60)
            print("QMT模块连接测试 (仅测试模式)")
            print("="*60)
            
            # 1-4步保持不变，第5.5步跳过交易测试
            return original_test.__code__.co_consts  # 这里需要重新实现简化版本
        
        # 直接运行简化测试
        try:
            print("\n1. 测试账户配置:")
            config = QMTAccountConfig.get_account_config(account_name)
            print(f"✓ 账户配置成功: {config['name']}")
            
            print("\n2. 测试QMT客户端初始化:")
            client = QMTClient(account_name=account_name)
            print(f"✓ QMT客户端创建成功")
            
            print("\n3. 测试连接:")
            client.connect()
            print("✅ QMT连接测试成功")
            
            print("\n4. 测试基础功能:")
            account_info = client.get_account_info()
            print(f"✓ 账户信息获取成功")
            print(f"  账户ID: {account_info.get('account_id', 'N/A')}")
            print(f"  总资产: ¥{account_info.get('total_asset', 0):,.2f}")
            
            print("\n⏭️  跳过交易功能测试 (--test-only 模式)")
            print("\n" + "="*60)
            print("QMT连接测试完成")
            print("="*60)
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            exit(1)
    else:
        # 运行完整测试
        try:
            run_qmt_test(account_name)
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            exit(1)  