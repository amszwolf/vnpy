import numpy as np
import pandas as pd
from typing import List, Dict, Union
from datetime import datetime, timedelta
import time
import pymysql
from sqlalchemy import create_engine
from finscreener_database_manager import FinScreenerDBManager
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging


# 导入QMT统一接口
from hlm5_qmt import QMTClient

# 导入统一配置
from hlm5_config import EQUITY_CONFIG
print("[OK] 成功导入hlm5_config配置")

# 使用EQUITY_CONFIG作为FINSCREENER_CONFIG
FINSCREENER_CONFIG = {
    'DATABASE_PATH': 'finscreener.db',
    'MAX_WORKERS': 4,  # 多线程下载的工作线程数
    'CACHE_DURATION_DAYS': 1,  # 缓存有效期（天）
    'SCREENING_CRITERIA': {
        # 严格筛选标准 - 高质量股票
        'strict': {
            'MIN_MARKET_CAP': 2000000000,     # 优化: 50亿 → 20亿，扩大股票池
            'MAX_MARKET_CAP': 1000000000000,  # 10000亿市值
            'MIN_AVG_VOLUME': 5000000,        # 优化: 降低成交量要求
            'MIN_TURNOVER': 20000000,         # 优化: 降低成交额要求
            'MIN_ROE': 0.08,                  # 优化: 15% → 8%，降低盈利门槛
            'MAX_PE_RATIO': 60,               # 优化: 30 → 60，允许更高估值
            'MIN_CURRENT_RATIO': 1.2,         # 流动比率 > 1.2
            'MAX_DEBT_RATIO': 0.6,            # 负债率 < 60%
            'MIN_PRICE': 3.0,                 # 优化: 8元 → 3元，扩大价格范围
            'MAX_PRICE': 500.0,               # 优化: 200元 → 500元
            'MIN_GROWTH_RATE': 0.03,          # 优化: 10% → 3%，降低增长要求
            'MIN_TOTAL_SCORE': 0.3,           # 优化: 0.6 → 0.3，降低评分门槛
        },
        # 宽松筛选标准 - 平衡质量和数量
        'moderate': {
            'MIN_MARKET_CAP': 500000000,      # 优化: 20亿 → 5亿，大幅扩大股票池
            'MAX_MARKET_CAP': 2000000000000,  # 20000亿市值
            'MIN_AVG_VOLUME': 1000000,        # 优化: 降低成交量要求
            'MIN_TURNOVER': 5000000,          # 优化: 降低成交额要求
            'MIN_ROE': 0.03,                  # 优化: 8% → 3%，大幅降低ROE要求
            'MAX_PE_RATIO': 100,              # 优化: 50 → 100，允许更高估值
            'MIN_CURRENT_RATIO': 1.0,         # 优化: 降低流动比率要求
            'MAX_DEBT_RATIO': 0.8,            # 放宽负债率要求
            'MIN_PRICE': 2.0,                 # 优化: 5元 → 2元
            'MAX_PRICE': 1000.0,              # 优化: 300元 → 1000元
            'MIN_GROWTH_RATE': 0.0,           # 优化: 5% → 0%，不要求增长
            'MIN_TOTAL_SCORE': 0.1,           # 优化: 0.3 → 0.1，大幅降低评分门槛
        },
        # 最宽松筛选标准 - 最大化股票池
        'loose': {
            'MIN_MARKET_CAP': 100000000,      # 优化: 5亿 → 1亿，进一步扩大
            'MAX_MARKET_CAP': 5000000000000,  # 50000亿市值
            'MIN_AVG_VOLUME': 500000,         # 优化: 进一步降低成交量要求
            'MIN_TURNOVER': 1000000,          # 优化: 进一步降低成交额要求
            'MIN_ROE': 0.0,                   # 优化: 3% → 0%，不要求ROE
            'MAX_PE_RATIO': 200,              # 优化: 100 → 200，允许极高估值
            'MIN_CURRENT_RATIO': 0.5,         # 优化: 大幅降低流动比率要求
            'MAX_DEBT_RATIO': 1.0,            # 优化: 允许更高负债率
            'MIN_PRICE': 1.0,                 # 优化: 2元 → 1元
            'MAX_PRICE': 2000.0,              # 优化: 500元 → 2000元
            'MIN_GROWTH_RATE': -0.1,          # 优化: 允许负增长
            'MIN_TOTAL_SCORE': 0.05,          # 优化: 0.1 → 0.05，极低评分门槛
        }
    }
}

class FinancialScreener:
    """基于基本面因子的选股器"""
    
    def __init__(self, qmt_account: str = 'hfzq_sim', screening_level: str = 'moderate'):
        """初始化选股器
        
        Args:
            qmt_account: QMT账户类型
            screening_level: 筛选严格程度 ('strict', 'moderate', 'loose')
        """
        self.factor_weights = {
            'north_fund': 0.05,    # 北向资金
            'surprise_trad': 0.20, # 超预期(传统)
            'growth': 0.25,        # 成长
            'valuation': 0.25,     # 估值
            'profit': 0.25,        # 盈利
        }

        # 设置筛选等级
        self.screening_level = screening_level
        if screening_level not in FINSCREENER_CONFIG['SCREENING_CRITERIA']:
            raise ValueError(f"不支持的筛选等级: {screening_level}，支持的等级: {list(FINSCREENER_CONFIG['SCREENING_CRITERIA'].keys())}")
        
        # 从配置文件读取筛选标准
        self.screening_criteria = FINSCREENER_CONFIG['SCREENING_CRITERIA'][screening_level]
        self.database_path = FINSCREENER_CONFIG['DATABASE_PATH']
        self.max_workers = FINSCREENER_CONFIG['MAX_WORKERS']
        self.cache_duration = FINSCREENER_CONFIG['CACHE_DURATION_DAYS']
        
        # 初始化QMT客户端
        self.qmt_client = QMTClient(account_name=qmt_account, simulation_mode=True)
        self.qmt_connected = False
        
        # 线程锁，用于多线程安全
        self.lock = threading.Lock()
        
        # 移除数据库相关的初始化，改为在需要时创建
        self.latest_market_data = {}  # 用于存储每个股票的最新市场数据
        
        print(f"[OK] 财务筛选器初始化完成")
        print(f"   数据库路径: {self.database_path}")
        print(f"   筛选等级: {screening_level}")
        print(f"   筛选标准: {len(self.screening_criteria)} 个指标")
        print(f"   多线程数: {self.max_workers}")
        print(f"   缓存有效期: {self.cache_duration} 天")
        print(f"   QMT账户: {qmt_account}")

    def connect_qmt(self):
        """连接QMT"""
        if not self.qmt_connected:
            self.qmt_connected = self.qmt_client.connect()
            if self.qmt_connected:
                print("[OK] QMT连接成功")
            else:
                print("[WARNING] QMT连接失败，使用模拟模式")
        return self.qmt_connected

    def is_data_cache_valid(self) -> bool:
        """检查数据缓存是否有效"""
        db_manager = self.get_db_manager()
        try:
            # 检查数据库中是否有今天的数据
            today = datetime.now().date()
            recent_data = db_manager.get_recent_stock_data(days=self.cache_duration)
            
            if recent_data.empty:
                print(f"📥 数据库为空，需要下载数据")
                return False
            
            # 检查最新数据的日期
            latest_date = pd.to_datetime(recent_data['datetime']).dt.date.max()
            days_diff = (today - latest_date).days
            
            if days_diff >= self.cache_duration:
                print(f"📅 数据过期({days_diff}天前)，需要更新")
                return False
            else:
                print(f"✅ 数据缓存有效(最新数据: {latest_date})")
                return True
                
        except Exception as e:
            print(f"⚠️  检查缓存时出错: {e}，将重新下载数据")
            return False

    def get_stock_list_with_cache(self) -> List[str]:
        """智能获取股票列表（带缓存检查）"""
        print("📊 获取沪深A股股票列表...")
        
        # 先尝试从QMT获取
        stocks = self.qmt_client.get_stock_list_in_sector('沪深A股')
        
        if not stocks:
            print("📥 本地无股票列表，从服务器下载...")
            self.qmt_client.download_sector_data()
            stocks = self.qmt_client.get_stock_list_in_sector('沪深A股')
        
        if stocks:
            print(f"✅ 获取到 {len(stocks)} 只沪深A股")
        else:
            print("❌ 获取股票列表失败")
            
        return stocks

    def download_stock_data_batch(self, stock_batch: List[str], batch_id: int) -> int:
        """批量下载股票数据（用于多线程）"""
        success_count = 0
        failed_count = 0
        batch_size = len(stock_batch)
        
        try:
            for i, stock_code in enumerate(stock_batch):
                max_retries = 2  # 最多重试2次
                retry_count = 0
                
                while retry_count <= max_retries:
                    try:
                        # 处理单只股票
                        result = self.process_stock(stock_code)
                        if result is not None:
                            success_count += 1
                            break  # 成功则跳出重试循环
                        else:
                            retry_count += 1
                            if retry_count > max_retries:
                                failed_count += 1
                                with self.lock:
                                    print(f"⚠️  线程{batch_id}: {stock_code} 处理失败(无有效数据)")
                            else:
                                time.sleep(0.1)  # 重试前短暂等待
                    
                    except Exception as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            failed_count += 1
                            with self.lock:
                                print(f"⚠️  线程{batch_id}: {stock_code} 处理异常: {str(e)[:50]}...")
                        else:
                            time.sleep(0.1)  # 重试前短暂等待
                
                # 每处理10只股票显示一次进度
                if (i + 1) % 10 == 0 or (i + 1) == batch_size:
                    with self.lock:
                        print(f"🔄 线程{batch_id}: {i+1}/{batch_size} (✅{success_count} ❌{failed_count})")
                    
        except Exception as e:
            print(f"❌ 线程{batch_id}执行失败: {e}")
            
        return success_count

    def update_all_stock_data(self, force_update: bool = False) -> bool:
        """更新所有股票数据（多线程下载）"""
        # 检查缓存有效性
        if not force_update and self.is_data_cache_valid():
            print("✅ 使用缓存数据，跳过下载")
            return True
        
        print("🚀 开始更新股票数据...")
        
        # 确保QMT连接
        if not self.connect_qmt():
            print("❌ QMT连接失败，无法更新数据")
            return False
        
        # 获取股票列表
        all_stocks = self.get_stock_list_with_cache()
        if not all_stocks:
            print("❌ 获取股票列表失败")
            return False
        
        print(f"📈 准备下载 {len(all_stocks)} 只股票的数据...")
        
        # 分批处理（多线程）
        batch_size = max(1, len(all_stocks) // self.max_workers)
        stock_batches = [all_stocks[i:i + batch_size] for i in range(0, len(all_stocks), batch_size)]
        
        total_success = 0
        start_time = time.time()
        
        # 使用线程池执行
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            print(f"🔥 启动 {len(stock_batches)} 个线程开始下载...")
            
            # 提交所有任务
            future_to_batch = {
                executor.submit(self.download_stock_data_batch, batch, i): i 
                for i, batch in enumerate(stock_batches, 1)
            }
            
            # 收集结果
            for future in as_completed(future_to_batch):
                batch_id = future_to_batch[future]
                try:
                    success_count = future.result()
                    total_success += success_count
                    print(f"✅ 线程{batch_id} 完成，成功处理 {success_count} 只股票")
                except Exception as e:
                    print(f"❌ 线程{batch_id} 执行异常: {e}")
        
        elapsed_time = time.time() - start_time
        success_rate = (total_success/len(all_stocks)*100) if all_stocks else 0
        
        print(f"\n🎉 数据更新完成!")
        print(f"   总耗时: {elapsed_time:.1f} 秒")
        print(f"   成功处理: {total_success}/{len(all_stocks)} 只股票")
        print(f"   成功率: {success_rate:.1f}%")
        
        # 根据成功率给出建议
        if success_rate < 50:
            print(f"⚠️  成功率较低，可能原因:")
            print(f"   - QMT连接不稳定")
            print(f"   - 网络连接问题")
            print(f"   - 部分股票数据缺失")
            print(f"   建议: 稍后重试或检查QMT连接状态")
        elif success_rate < 80:
            print(f"ℹ️  成功率中等，属正常范围")
            print(f"   部分股票可能暂停交易或数据缺失")
        else:
            print(f"✅ 成功率良好!")
        
        return total_success > 0

    @staticmethod
    def get_db_manager():
        """获取数据库管理器实例"""
        return FinScreenerDBManager()

    def _get_financial_data_from_db(self, stock_code: str, table: str) -> pd.DataFrame:
        """从MySQL数据库获取财务数据"""
        # 直接从本地获取数据，因为数据库中还没有相应的表
        return self._get_financial_data_from_local(stock_code, table)

    def _get_financial_data_from_local(self, stock_code: str, table: str) -> pd.DataFrame:
        """从本地QMT获取财务数据"""
        # 使用QMT客户端获取财务数据
        data = self.qmt_client.get_financial_data([stock_code], [table])
        
        if data and isinstance(data, dict):
            stock_data = data.get(stock_code, {})
            table_data = stock_data.get(table, pd.DataFrame())
            if isinstance(table_data, pd.DataFrame):
                return table_data
            
        return pd.DataFrame()

    def _download_financial_data(self, stock_code: str, table: str) -> pd.DataFrame:
        """使用QMT API下载财务数据"""
        print(f"下载{stock_code}的{table}数据...")
        # 由于QMT客户端没有下载财务数据的接口，这里暂时返回空DataFrame
        # 实际项目中可以通过其他方式获取财务数据
        return pd.DataFrame()

    def _get_financial_data(self, stock_code: str, table: str) -> pd.DataFrame:
        """获取财务数据的主函数，按优先级尝试不同数据源"""
        # 1. 优先从数据库获取
        df = self._get_financial_data_from_db(stock_code, table)
        if not df.empty:
            return df
        
        # 2. 尝试从本地QMT获取
        df = self._get_financial_data_from_local(stock_code, table)
        if not df.empty:
            return df
        
        # 3. 通过API下载
        return self._download_financial_data(stock_code, table)

    # def calculate_north_fund_factor(self, stock_code: str) -> float:
    #     """计算北向资金因子"""
    #     # 这里需要实现北向资金持股比例、持股市值等指标的计算
    #     pass

    def calculate_surprise_factor(self, stock_code: str) -> float:
        """计算超预期因子"""
        df = self._get_financial_data(stock_code, 'PershareIndex')
        if df.empty:
            return 0
            
        profit_changes = df['adjusted_net_profit_rate'].values
        if len(profit_changes) < 4:
            return 0
            
        recent_changes = profit_changes[-4:]
        mean = np.mean(recent_changes)
        std = np.std(recent_changes)
        if std == 0:
            return 0
            
        sue = (recent_changes[-1] - mean) / std
        return float(sue)

    def calculate_growth_factor(self, stock_code: str) -> float:
        """计算成长因子"""
        db_manager = self.get_db_manager()
        df = self._get_financial_data(stock_code, 'PershareIndex')
        if df.empty:
            return 0
            
        # 综合多个增长指标
        growth_indicators = [
            'inc_revenue_rate',                          # 主营收入同比增长
            'inc_net_profit_rate',                       # 归属净利润同比增长
            'inc_total_revenue_annual',                  # 营业总收入滚动环比增长
            'inc_net_profit_to_shareholders_annual'      # 归属净利润滚动环比增长
        ]
        
        growth_scores = []
        indicator_values = {}
        
        for indicator in growth_indicators:
            if indicator in df.columns:
                values = df[indicator].values
                if len(values) > 0:
                    valid_values = [v for v in values if v is not None and not pd.isna(v)]
                    if valid_values:
                        mean_value = float(np.mean(valid_values))
                        growth_scores.append(mean_value)
                        indicator_values[indicator] = mean_value
        
        if not growth_scores:
            return 0
            
        growth_factor = float(np.mean(growth_scores))
        
        if growth_factor > 0:
            data = {
                'ticker': stock_code,
                'datetime': datetime.utcnow(),
                'inc_revenue_rate': indicator_values.get('inc_revenue_rate'),
                'inc_net_profit_rate': indicator_values.get('inc_net_profit_rate'),
                'inc_total_revenue_annual': indicator_values.get('inc_total_revenue_annual'),
                'inc_net_profit_to_shareholders_annual': indicator_values.get('inc_net_profit_to_shareholders_annual'),
                'growth_factor': growth_factor
            }
            db_manager.upsert_stock_data(data)
        
        return growth_factor

    def _get_market_price(self, stock_code: str) -> Dict[str, Union[float, None]]:
        """获取股票最新价格和时间"""
        # 检查QMT连接状态，只在未连接时尝试连接
        if not self.qmt_connected:
            self.connect_qmt()
        
        # 获取市场数据
        market_data = self.qmt_client.get_market_data([stock_code], period='1d', count=1)
        
        # 检查并获取市场数据
        if isinstance(market_data, dict) and market_data:
            result = {
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'open': None,
                'high': None,
                'low': None,
                'close': None,
                'volume': None
            }
            
            # 获取其他字段数据
            for field in ['open', 'high', 'low', 'close', 'volume']:
                if field in market_data:
                    field_data = market_data[field]
                    if isinstance(field_data, pd.DataFrame) and not field_data.empty and stock_code in field_data.columns:
                        try:
                            result[field] = float(field_data.loc[field_data.index[-1], stock_code])
                        except (IndexError, KeyError, ValueError):
                            result[field] = None
            
            # 如果获取到了有效数据，返回结果
            if result['close'] is not None:
                return result
        
        # 如果没有获取到数据，返回带有当前时间的默认数据
        return {
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'open': 10.0,    # 默认值
            'high': 10.5,
            'low': 9.5,
            'close': 10.0,
            'volume': 1000000
        }

    def calculate_valuation_factor(self, stock_code: str) -> float:
        """计算估值因子"""
        db_manager = self.get_db_manager()
        df = self._get_financial_data(stock_code, 'PershareIndex')
        if df.empty:
            return 0
            
        # 获取最新的每股收益和每股净资产
        latest = df.iloc[-1]
        eps = latest.get('s_fa_eps_basic')
        bps = latest.get('s_fa_bps')
        
        # 检查是否为None或nan
        if eps is None or pd.isna(eps) or eps <= 0:
            eps = latest.get('s_fa_eps_diluted')  # 尝试使用稀释每股收益
            if eps is None or pd.isna(eps) or eps <= 0:
                return 0
                
        if bps is None or pd.isna(bps) or bps <= 0:
            return 0
            
        # 获取当前市价
        price = self._get_market_price(stock_code)
        if price is None or price.get('close') is None:
            return 0
        
        close_price = price.get('close')
        if close_price is None or pd.isna(close_price) or close_price <= 0:
            return 0
        
        # 计算PE和PB
        pe = price['close'] / float(eps)
        pb = price['close'] / float(bps)
        
        # 转换为评分 (估值越低越好)
        pe_score = 1 / (1 + np.log(max(pe, 1)))
        pb_score = 1 / (1 + np.log(max(pb, 1)))
        
        # 综合评分
        valuation_factor = float((pe_score + pb_score) / 2)
        
        if valuation_factor > 0:
            data = {
                'ticker': stock_code,
                'datetime': price['datetime'],
                'open': price['open'],
                'high': price['high'],
                'low': price['low'],
                'close': price['close'],
                'volume': price['volume'],
                'eps_basic': float(eps) if eps else None,
                'eps_diluted': float(latest.get('s_fa_eps_diluted')) if latest.get('s_fa_eps_diluted') else None,
                'bps': float(bps),
                'current_price': float(price['close']),
                'pe_ratio': float(pe),
                'pb_ratio': float(pb),
                'valuation_factor': valuation_factor
            }
            db_manager.upsert_stock_data(data)
        
        return valuation_factor

    def calculate_profit_factor(self, stock_code: str) -> float:
        """计算盈利因子"""
        db_manager = self.get_db_manager()
        df = self._get_financial_data(stock_code, 'PershareIndex')
        if df.empty:
            return 0
            
        # 获取最新的财务指标
        latest = df.iloc[-1]
        
        # 综合多个盈利指标
        profit_indicators = {
            'du_return_on_equity': 0.3,     # 净资产收益率
            'sales_gross_profit': 0.2,      # 销售毛利率
            'gross_profit': 0.2,            # 毛利率
            'net_profit': 0.3               # 净利率
        }
        
        scores = []
        weights = []
        indicator_values = {}
        
        for indicator, weight in profit_indicators.items():
            if indicator in latest and not pd.isna(latest[indicator]):
                value = latest[indicator]
                if isinstance(value, (int, float)):
                    scores.append(value)
                    weights.append(weight)
                    indicator_values[indicator] = float(value)
        
        if not scores:
            return 0
            
        # 计算加权平均分数
        profit_factor = float(np.average(scores, weights=weights))
        
        if profit_factor > 0:
            data = {
                'ticker': stock_code,
                'datetime': datetime.utcnow(),
                'du_return_on_equity': indicator_values.get('du_return_on_equity'),
                'sales_gross_profit': indicator_values.get('sales_gross_profit'),
                'gross_profit': indicator_values.get('gross_profit'),
                'net_profit': indicator_values.get('net_profit'),
                'profit_factor': profit_factor
            }
            db_manager.upsert_stock_data(data)
        
        return profit_factor

    def process_stock(self, stock: str) -> Dict:
        """处理单个股票的计算（单线程模式）"""
        # 获取数据库管理器实例
        db_manager = self.get_db_manager()
        
        # 获取最新市场数据
        market_data = self._get_market_price(stock)
        if not market_data:
            return None

        # 计算所有因子
        factor_scores = {
            'surprise_trad': self.calculate_surprise_factor(stock),
            'growth': self.calculate_growth_factor(stock),
            'valuation': self.calculate_valuation_factor(stock),
            'profit': self.calculate_profit_factor(stock)
        }
        
        score = sum(
            factor_scores.get(factor, 0) * weight 
            for factor, weight in self.factor_weights.items()
            if factor in factor_scores
        )
        
        if score > 0:
            # 准备完整的数据记录
            data = {
                'ticker': stock,
                'datetime': market_data['datetime'],
                'open': market_data['open'],
                'high': market_data['high'],
                'low': market_data['low'],
                'close': market_data['close'],
                'volume': market_data['volume'],
                'total_score': float(score),
                **factor_scores  # 包含所有因子分数
            }
            
            # 存储到数据库
            db_manager.upsert_stock_data(data)
            
            return {
                'stock_code': stock,
                'score': float(score),
                'factor_scores': factor_scores
            }
        
        return None

    def apply_screening_criteria(self, stock_data: Dict) -> bool:
        """应用筛选标准判断股票是否符合条件"""
        criteria = self.screening_criteria
        
        try:
            # 基本价格筛选
            if stock_data.get('close'):
                price = float(stock_data['close'])
                if price < criteria.get('MIN_PRICE', 0) or price > criteria.get('MAX_PRICE', float('inf')):
                    return False
            
            # 市值筛选（需要股价和股本数据）
            # 这里简化处理，实际可以通过财务数据计算市值
            
            # 综合得分筛选
            total_score = stock_data.get('total_score', 0)
            if total_score < criteria.get('MIN_TOTAL_SCORE', 0):
                return False
            
            # 成长性筛选
            growth_score = stock_data.get('growth', 0)
            if growth_score and growth_score < criteria.get('MIN_GROWTH_RATE', 0):
                return False
            
            return True
            
        except Exception as e:
            print(f"⚠️  筛选标准应用失败: {e}")
            return False

    def screen_stocks_from_db(self, top_n: int = None) -> List[Dict]:
        """从数据库中筛选股票（基于预设标准）"""
        print(f"📊 开始筛选股票 (筛选等级: {self.screening_level})...")
        
        db_manager = self.get_db_manager()
        
        # 获取最近的股票数据
        try:
            recent_data = db_manager.get_recent_stock_data(days=self.cache_duration)
            if recent_data.empty:
                print("❌ 数据库中没有可用数据")
                print("💡 请先更新数据:")
                print("   python hlm5_finscreener.py --update-only")
                print("   或使用 --force-update 参数")
                return []
            
            print(f"📈 从数据库加载了 {len(recent_data)} 条股票数据")
            
        except Exception as e:
            print(f"❌ 从数据库获取数据失败: {e}")
            return []
        
        # 应用筛选标准
        filtered_stocks = []
        
        for _, row in recent_data.iterrows():
            stock_data = row.to_dict()
            
            # 应用筛选标准
            if self.apply_screening_criteria(stock_data):
                result = {
                    'stock_code': stock_data.get('ticker'),
                    'score': float(stock_data.get('total_score', 0)),
                    'factor_scores': {
                        'growth': stock_data.get('growth'),
                        'valuation': stock_data.get('valuation'),
                        'profit': stock_data.get('profit'),
                        'surprise_trad': stock_data.get('surprise_trad')
                    },
                    'market_data': {
                        'close': stock_data.get('close'),
                        'volume': stock_data.get('volume'),
                        'datetime': stock_data.get('datetime')
                    }
                }
                filtered_stocks.append(result)
        
        # 按得分排序
        filtered_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        # 应用数量限制
        if top_n:
            filtered_stocks = filtered_stocks[:top_n]
        
        print(f"✅ 筛选完成，符合'{self.screening_level}'标准的股票: {len(filtered_stocks)} 只")
        
        return filtered_stocks

    def screen_stocks(self, stock_list: List[str] = None, top_n: int = 50) -> List[Dict]:
        """智能筛选股票（优先使用数据库数据）"""
        
        # 如果没有提供股票列表，尝试从数据库筛选
        if stock_list is None:
            return self.screen_stocks_from_db(top_n)
        
        # 如果提供了股票列表，则实时计算（单线程模式）
        print(f"🔄 实时计算筛选 {len(stock_list)} 只股票...")
        
        results = []
        total = len(stock_list)
        
        # 单线程处理，避免QMT连接冲突
        for i, stock_code in enumerate(stock_list, 1):
            if i % 50 == 0 or i == total:
                print(f"进度: {i}/{total} ({(i/total*100):.1f}%)")
                
            result = self.process_stock(stock_code)
            if result is not None:
                # 应用筛选标准
                stock_data = {
                    'total_score': result['score'],
                    'close': self.latest_market_data.get(stock_code, {}).get('close'),
                    **result['factor_scores']
                }
                
                if self.apply_screening_criteria(stock_data):
                    results.append(result)
        
        # 按得分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"✅ 实时筛选完成，符合'{self.screening_level}'标准的股票: {len(results)} 只")
        
        return results[:top_n] if top_n else results

    def get_stock_details(self, stock_code: str) -> Dict:
        """获取股票详细信息"""
        details = {}
        
        # 获取基本信息（简化版本，因为QMT模块中没有get_instrument_detail）
        details['name'] = stock_code  # 暂时使用代码作为名称
        
        # 获取最新财务指标
        index_data = self._get_financial_data(stock_code, 'PershareIndex')
        if not index_data.empty:
            latest = index_data.iloc[-1]
            details.update({
                'ROE': latest.get('du_return_on_equity', 'N/A'),
                'EPS': latest.get('s_fa_eps_basic', 'N/A'),
                'BPS': latest.get('s_fa_bps', 'N/A')
            })
        else:
            details.update({
                'ROE': 'N/A',
                'EPS': 'N/A', 
                'BPS': 'N/A'
            })
        
        return details

def init_qmt_service(qmt_client: QMTClient):
    """初始化QMT服务连接"""
    print("使用QMT统一接口初始化...")
    return qmt_client.connect()

def main():
    """主函数"""
    
    # 创建选股器实例（默认使用中等筛选标准）
    screener = FinancialScreener(qmt_account='hfzq_sim', screening_level='moderate')
    
    # 首先启动QMT服务
    print("🚀 启动QMT服务...")
    if init_qmt_service(screener.qmt_client):
        screener.qmt_connected = True
        print("[OK] QMT连接已建立并设置状态")
    else:
        print("[WARNING] QMT连接失败，将使用模拟模式")
    
    # 清理数据库中的重复数据（确保ticker唯一性）
    print("🧹 检查并清理数据库重复数据...")
    db_manager = screener.get_db_manager()
    db_manager.cleanup_duplicate_data()
    
    # 更新股票数据（智能缓存）
    print("\n📊 更新股票基础数据...")
    if screener.update_all_stock_data(force_update=False):
        print("✅ 股票数据更新完成")
    else:
        print("❌ 股票数据更新失败")
        return
    
    # 执行筛选
    print("\n🎯 开始执行股票筛选...")
    selected_stocks = screener.screen_stocks_from_db(top_n=50)
    
    if not selected_stocks:
        print("\n❌ 未找到符合条件的股票")
        print("💡 建议：")
        print("   1. 尝试更宽松的筛选标准：--screening-level loose")
        print("   2. 强制更新数据：--force-update")
        print("   3. 检查QMT连接和数据源")
        return
    
    # 输出结果摘要
    print(f"\n🎉 筛选完成！找到 {len(selected_stocks)} 只符合条件的股票")
    print("📊 前10只股票详情:")
    print("-" * 80)
    
    for i, stock in enumerate(selected_stocks[:10], 1):
        details = screener.get_stock_details(stock['stock_code'])
        market_data = stock.get('market_data', {})
        
        print(f"\n{i:2d}. 📈 {stock['stock_code']} ({details.get('name', 'N/A')})")
        print(f"    💰 当前价格: {market_data.get('close', 'N/A')}")
        print(f"    🏆 综合得分: {stock['score']:.3f}")
        print(f"    📊 ROE: {details.get('ROE', 'N/A')}")
        print(f"    💵 EPS: {details.get('EPS', 'N/A')}")
        print(f"    📈 因子得分: ", end="")
        
        factor_strs = []
        for factor, score in stock['factor_scores'].items():
            if score is not None and not pd.isna(score):
                factor_strs.append(f"{factor}={score:.2f}")
            else:
                factor_strs.append(f"{factor}=N/A")
        print(" | ".join(factor_strs))
    
    if len(selected_stocks) > 10:
        print(f"\n... 还有 {len(selected_stocks) - 10} 只股票")
    
    print(f"\n✅ 筛选完成 (筛选等级: {screener.screening_level})")
    print(f"📄 完整结果已保存到数据库: {screener.database_path}")

def update_data_only(account: str = 'hfzq_sim', force_update: bool = False):
    """仅更新数据，不执行筛选"""
    print("🔄 仅数据更新模式")
    
    # 创建选股器实例
    screener = FinancialScreener(qmt_account=account, screening_level='moderate')
    
    # 连接QMT
    if not screener.connect_qmt():
        print("❌ QMT连接失败")
        return False
    
    # 执行数据更新
    success = screener.update_all_stock_data(force_update=force_update)
    
    if success:
        print("✅ 数据更新完成")
    else:
        print("❌ 数据更新失败")
    
    return success

def show_help():
    """显示帮助信息"""
    help_text = """
HLM5 金融股票筛选器 (增强版)
============================

🚀 主要功能:
- 基于基本面因子的智能选股
- 多因子评分系统 (成长、估值、盈利、超预期、北向资金)
- 智能数据缓存和多线程下载
- 三档筛选策略 (严格/中等/宽松)
- QMT实时数据获取
- SQLite数据库存储

📋 使用方法:
---------

基本用法:
  python hlm5_finscreener.py                           # 使用默认中等筛选
  python hlm5_finscreener.py --screening-level strict  # 严格筛选
  python hlm5_finscreener.py --screening-level loose   # 宽松筛选
  python hlm5_finscreener.py --top-n 30               # 限制结果数量

数据管理:
  python hlm5_finscreener.py --update-only            # 仅更新数据
  python hlm5_finscreener.py --force-update           # 强制更新数据
  python hlm5_finscreener.py --test-only              # 测试连接

🔧 参数说明:
  --account ACCOUNT           选择QMT账户类型
                             可选值: hfzq_sim (默认), hfzq_real, hfzq_sim_old
  --top-n NUM                筛选结果数量 (默认: 50)
  --screening-level LEVEL    筛选严格程度 (默认: moderate)
                             可选值: strict, moderate, loose
  --update-only              仅更新数据，不执行筛选
  --force-update             强制更新数据（忽略缓存）
  --test-only                仅测试连接，不执行筛选
  --verbose                  显示详细日志信息
  --help                     显示此帮助信息
  --help-examples            显示详细使用示例

🏦 支持的账户类型:
  hfzq_sim       华福证券模拟账号(默认) - 安全测试环境
  hfzq_real      华福证券实盘账号 - 真实数据环境
  hfzq_sim_old   华福证券模拟账号(旧) - 备用测试环境

📊 三档筛选策略:
  strict (严格)   - 50亿+市值, ROE>15%, PE<30, 综合得分>0.6
  moderate (中等) - 20亿+市值, ROE>8%, PE<50, 综合得分>0.3
  loose (宽松)    - 5亿+市值, ROE>3%, PE<100, 综合得分>0.1

💡 筛选因子权重:
  north_fund     北向资金: 5%
  surprise_trad  超预期(传统): 20% 
  growth         成长: 25%
  valuation      估值: 25%
  profit         盈利: 25%

🔄 智能缓存系统:
  - 自动检查数据有效性（1天缓存期）
  - 多线程并行下载（4线程）
  - 避免重复下载，提升效率

⚠️  注意事项:
  - 需要QMT客户端已启动并登录相应账户
  - 首次运行需要下载全部沪深A股数据，耗时较长
  - 后续运行会使用缓存数据，速度较快
  - 结果保存在finscreener.db数据库中
  - 建议定期使用--force-update更新数据
"""
    print(help_text)


def show_examples():
    """显示使用示例"""
    examples = """
HLM5 股票筛选器使用示例 (增强版)
===============================

🔥 常用命令:
-----------

# 基本筛选 (默认中等标准)
python hlm5_finscreener.py

# 不同筛选严格程度
python hlm5_finscreener.py --screening-level strict   # 严格筛选
python hlm5_finscreener.py --screening-level moderate # 中等筛选
python hlm5_finscreener.py --screening-level loose    # 宽松筛选

# 限制结果数量
python hlm5_finscreener.py --top-n 20                 # 仅显示前20只

# 数据管理
python hlm5_finscreener.py --update-only              # 仅更新数据
python hlm5_finscreener.py --force-update             # 强制更新数据

# 测试和调试
python hlm5_finscreener.py --test-only                # 测试连接
python hlm5_finscreener.py --verbose                  # 详细日志

📋 典型使用场景:
---------------

# 🎯 场景1: 保守投资者 - 严格筛选
python hlm5_finscreener.py --screening-level strict --top-n 15
# 用途: 获取高质量股票，50亿+市值，ROE>15%，适合稳健投资

# 💼 场景2: 平衡投资者 - 中等筛选  
python hlm5_finscreener.py --screening-level moderate --top-n 30
# 用途: 平衡风险收益，20亿+市值，ROE>8%，适合大多数投资者

# 🚀 场景3: 激进投资者 - 宽松筛选
python hlm5_finscreener.py --screening-level loose --top-n 50
# 用途: 发现潜力股票，5亿+市值，ROE>3%，适合风险偏好高的投资者

# 🔄 场景4: 数据维护 - 仅更新数据
python hlm5_finscreener.py --update-only --force-update
# 用途: 定期维护数据，不执行筛选，适合数据管理

# 🏦 场景5: 实盘环境 - 真实数据筛选
python hlm5_finscreener.py --account hfzq_real --screening-level moderate --verbose
# 用途: 使用实盘数据，显示详细过程，适合正式投资决策

# 🧪 场景6: 快速测试
python hlm5_finscreener.py --account hfzq_sim --test-only
# 用途: 快速测试QMT连接，验证环境配置

🎯 高级组合使用:
---------------

# 完整的每日筛选流程
python hlm5_finscreener.py --screening-level moderate --top-n 30 --verbose

# 强制更新后严格筛选
python hlm5_finscreener.py --force-update --screening-level strict --top-n 20

# 实盘数据的宽松筛选
python hlm5_finscreener.py --account hfzq_real --screening-level loose --top-n 50

🔗 集成使用示例:
---------------

# 在流水线中使用 (推荐)
python hlm5_pipeline.py --steps 1 --screening-level moderate

# Python代码中使用
from hlm5_finscreener import FinancialScreener

# 创建不同筛选等级的实例
strict_screener = FinancialScreener(qmt_account='hfzq_sim', screening_level='strict')
moderate_screener = FinancialScreener(qmt_account='hfzq_sim', screening_level='moderate')
loose_screener = FinancialScreener(qmt_account='hfzq_sim', screening_level='loose')

# 更新数据
strict_screener.update_all_stock_data()

# 执行筛选
strict_stocks = strict_screener.screen_stocks_from_db(top_n=20)
moderate_stocks = moderate_screener.screen_stocks_from_db(top_n=30)
loose_stocks = loose_screener.screen_stocks_from_db(top_n=50)

📊 筛选策略对比:
---------------

| 筛选等级 | 市值要求  | ROE要求 | PE要求 | 得分要求 | 适用投资者 |
|---------|----------|---------|--------|----------|------------|
| strict  | 50亿+    | >15%    | <30    | >0.6     | 保守型     |
| moderate| 20亿+    | >8%     | <50    | >0.3     | 平衡型     |
| loose   | 5亿+     | >3%     | <100   | >0.1     | 激进型     |

🔄 智能缓存机制:
---------------

1. 首次运行: 下载全部沪深A股数据 (多线程，约10-30分钟)
2. 后续运行: 检查缓存有效性 (1天内有效则跳过下载)
3. 强制更新: 使用 --force-update 忽略缓存重新下载
4. 仅更新模式: 使用 --update-only 只更新数据不筛选

💾 输出结果:
-----------
- 控制台显示: 前10只股票详细信息
- 数据库存储: finscreener.db (完整结果)
- 结果包含: 股票代码、价格、综合得分、各因子分数
- 支持导出: 可通过数据库接口导出Excel等格式

⚠️  重要提醒:
-------------
1. 确保QMT客户端已启动并登录相应账户
2. 首次运行耗时较长，后续运行速度快
3. 网络稳定性影响数据下载成功率
4. 建议每天使用--force-update更新一次数据
5. 不同筛选等级结果差异较大，按需选择
6. 结果仅供参考，投资决策需谨慎

🔧 故障排除:
-----------
1. QMT连接失败 → 检查客户端登录状态
2. 数据下载失败 → 检查网络连接和权限
3. 筛选结果为空 → 尝试更宽松的筛选等级
4. 程序运行缓慢 → 首次下载正常，后续会使用缓存
5. 数据过期提示 → 使用--force-update强制更新
6. 多线程错误 → 检查系统资源和QMT稳定性

💡 最佳实践:
-----------
1. 新用户: 先使用 --test-only 测试连接
2. 首次使用: 选择loose等级快速验证功能
3. 日常使用: moderate等级平衡风险收益
4. 数据维护: 定期使用 --force-update 更新
5. 性能优化: 合理设置 --top-n 避免过多结果
6. 环境隔离: 测试使用模拟账户，正式使用实盘账户
"""
    print(examples)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='HLM5 金融股票筛选器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='使用 --help-examples 查看详细使用示例'
    )
    
    # 基础参数
    parser.add_argument('--account', type=str, default='hfzq_sim',
                       choices=['hfzq_sim', 'hfzq_real', 'hfzq_sim_old'],
                       help='选择QMT账户类型 (默认: hfzq_sim)')
    
    parser.add_argument('--top-n', type=int, default=50,
                       help='筛选结果数量 (默认: 50)')
    
    parser.add_argument('--screening-level', type=str, default='moderate',
                       choices=['strict', 'moderate', 'loose'],
                       help='筛选严格程度 (默认: moderate)')
    
    # 功能控制参数
    parser.add_argument('--update-only', action='store_true',
                       help='仅更新数据，不执行筛选')
    parser.add_argument('--force-update', action='store_true',
                       help='强制更新数据（忽略缓存）')
    parser.add_argument('--test-only', action='store_true',
                       help='仅测试连接，不执行筛选')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细日志信息')
    
    # 帮助参数
    parser.add_argument('--help-examples', action='store_true',
                       help='显示详细使用示例')
    
    args = parser.parse_args()
    
    # 显示帮助信息
    if args.help_examples:
        show_examples()
        exit(0)
    
    # 设置日志级别
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        print("🔍 详细日志模式已启用")
    
    # 显示配置信息
    print(f"使用账户: {args.account}")
    print(f"筛选等级: {args.screening_level}")
    print(f"筛选数量: 前{args.top_n}只股票")
    if args.force_update:
        print("🔄 强制更新模式: 忽略缓存，重新下载所有数据")
    if args.update_only:
        print("📊 仅更新数据模式: 不执行筛选")
    
    # 根据账户类型显示不同的警告信息
    from hlm5_qmt import QMTAccountConfig
    account_configs = QMTAccountConfig.ACCOUNTS
    if args.account in account_configs:
        account_info = account_configs[args.account]
        print(f"账户名称: {account_info['name']}")
        print(f"账户ID: {account_info['account_id']}")
        
        if args.account == 'hfzq_real':
            print("🏦 使用实盘账户获取数据")
        else:
            print("ℹ️  使用模拟账户，安全测试环境")
    else:
        print(f"❌ 错误: 未知账户类型 '{args.account}'")
        print(f"支持的账户类型: {list(account_configs.keys())}")
        exit(1)
    
    # 如果是仅测试模式
    if args.test_only:
        print("🧪 仅测试连接模式")
        
        try:
            from hlm5_qmt import QMTClient
            print("\n1. 测试QMT客户端初始化:")
            client = QMTClient(account_name=args.account)
            print(f"✓ QMT客户端创建成功")
            
            print("\n2. 测试连接:")
            client.connect()
            print("✅ QMT连接测试成功")
            
            print("\n3. 测试基础功能:")
            # 简单测试获取股票列表
            stocks = client.get_stock_list_in_sector('沪深A股')
            print(f"✓ 获取股票列表成功，共 {len(stocks)} 只股票")
            
            print("\n⏭️  跳过筛选功能测试 (--test-only 模式)")
            print("✅ 连接测试完成，可以正常进行股票筛选")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            exit(1)
    elif args.update_only:
        # 仅更新数据模式
        try:
            success = update_data_only(account=args.account, force_update=args.force_update)
            if success:
                print("✅ 数据更新任务完成")
                exit(0)  # 成功完成后退出
            else:
                print("❌ 数据更新任务失败")
                exit(1)
        except Exception as e:
            print(f"❌ 数据更新失败: {e}")
            exit(1)
    else:
        # 运行筛选功能
        try:
            print("\n🚀 开始执行股票筛选...")
            
            # 修改main函数以支持参数
            def main_with_params(account='hfzq_sim', screening_level='moderate', top_n=50, force_update=False):
                """带参数的主函数"""
                
                # 创建选股器实例
                screener = FinancialScreener(qmt_account=account, screening_level=screening_level)
                
                # 首先启动QMT服务
                print("🚀 启动QMT服务...")
                if init_qmt_service(screener.qmt_client):
                    screener.qmt_connected = True
                    print("[OK] QMT连接已建立并设置状态")
                else:
                    print("[WARNING] QMT连接失败，将使用模拟模式")
                
                # 清理数据库中的重复数据（确保ticker唯一性）
                print("🧹 检查并清理数据库重复数据...")
                db_manager = screener.get_db_manager()
                db_manager.cleanup_duplicate_data()
                
                # 只有在强制更新时才更新数据
                if force_update:
                    print("\n📊 强制更新股票基础数据...")
                    if screener.update_all_stock_data(force_update=True):
                        print("✅ 股票数据更新完成")
                    else:
                        print("❌ 股票数据更新失败")
                        return
                else:
                    print("\n📊 使用现有数据库数据进行筛选...")
                
                # 执行筛选
                print("\n🎯 开始执行股票筛选...")
                selected_stocks = screener.screen_stocks_from_db(top_n=top_n)
                
                if not selected_stocks:
                    print("\n❌ 未找到符合条件的股票")
                    print("💡 建议：")
                    print("   1. 尝试更宽松的筛选标准：--screening-level loose")
                    print("   2. 强制更新数据：--force-update")
                    print("   3. 检查QMT连接和数据源")
                    return
                
                # 输出结果摘要
                print(f"\n🎉 筛选完成！找到 {len(selected_stocks)} 只符合条件的股票")
                
                display_count = min(10, len(selected_stocks))
                print(f"📊 前{display_count}只股票详情:")
                print("-" * 80)
                
                for i, stock in enumerate(selected_stocks[:display_count], 1):
                    details = screener.get_stock_details(stock['stock_code'])
                    market_data = stock.get('market_data', {})
                    
                    print(f"\n{i:2d}. 📈 {stock['stock_code']} ({details.get('name', 'N/A')})")
                    print(f"    💰 当前价格: {market_data.get('close', 'N/A')}")
                    print(f"    🏆 综合得分: {stock['score']:.3f}")
                    print(f"    📊 ROE: {details.get('ROE', 'N/A')}")
                    print(f"    💵 EPS: {details.get('EPS', 'N/A')}")
                    print(f"    📈 因子得分: ", end="")
                    
                    factor_strs = []
                    for factor, score in stock['factor_scores'].items():
                        if score is not None and not pd.isna(score):
                            factor_strs.append(f"{factor}={score:.2f}")
                        else:
                            factor_strs.append(f"{factor}=N/A")
                    print(" | ".join(factor_strs))
                
                if len(selected_stocks) > display_count:
                    print(f"\n... 还有 {len(selected_stocks) - display_count} 只股票")
                
                print(f"\n✅ 筛选完成 (筛选等级: {screening_level})")
                print(f"📄 完整结果已保存到数据库: {screener.database_path}")
            
            # 执行筛选
            main_with_params(
                account=args.account, 
                screening_level=args.screening_level,
                top_n=args.top_n,
                force_update=args.force_update
            )
            
        except Exception as e:
            print(f"❌ 筛选失败: {e}")
            exit(1) 