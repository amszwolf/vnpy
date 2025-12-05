import numpy as np
import pandas as pd
import sqlite3
import cvxpy as cp
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
from typing import Dict, List, Tuple, Optional
import logging
import argparse
import json
import os
import sys
import webbrowser
import plotly.graph_objects as go
import plotly.subplots as sp
from plotly.offline import plot
import tempfile

# 导入投资组合数据库管理器
try:
    from portfolio_database_manager import PortfolioDatabaseManager
except ImportError:
    PortfolioDatabaseManager = None
    print("Warning: portfolio_database_manager not found, database functionality will be disabled")

# 导入统一配置
try:
    from hlm5_config import PORTFOLIO_CONFIG, EQUITY_CONFIG, OVERALL_CONFIG, LOG_CONFIG
    print("[OK] 成功导入hlm5_config配置")
except ImportError:
    print("[WARNING] 无法导入hlm5_config，使用默认配置")
    PORTFOLIO_CONFIG = {
        'DATABASE_PATH': 'portfolio.db',
        'OPTIMIZATION_METHODS': {
            'profit_weighted': {'name': '利润加权', 'enabled': True, 'default': True},
            'sharpe_weighted': {'name': '夏普比率加权', 'enabled': True, 'default': False},
            'equal_weighted': {'name': '等权重', 'enabled': True, 'default': False},
            'risk_parity_weighted': {'name': '风险平价', 'enabled': True, 'default': False}
        },
        'OPTIMIZATION_CONSTRAINTS': {
            'MIN_WEIGHT': 0.02,
            'MAX_WEIGHT': 0.20,
            'MAX_STOCKS': 20,
            'MIN_STOCKS': 5
        }
    }
    EQUITY_CONFIG = {'DATABASE_PATH': 'trading_signals.db'}
    OVERALL_CONFIG = {'TRADING_SIGNALS_DB': 'trading_signals.db', 'PORTFOLIO_DB': 'portfolio.db'}

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

warnings.filterwarnings('ignore')

class ConfigFileLoader:
    """
    配置文件加载器，支持从hlm5_stock_final_optimized_config.json文件中提取股票列表和优化参数
    """
    
    def __init__(self, config_file_path: str):
        """
        初始化配置文件加载器
        
        Parameters:
        -----------
        config_file_path : str
            配置文件路径
        """
        self.config_file_path = config_file_path
        self.config_data = None
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_file_path}")
        
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            logger.info(f"[OK] 成功加载配置文件: {self.config_file_path}")
            logger.info(f"   实验名称: {self.config_data.get('experiment_name', 'N/A')}")
            logger.info(f"   优化日期: {self.config_data.get('optimization_date', 'N/A')}")
            logger.info(f"   最佳得分: {self.config_data.get('best_score', 'N/A')}")
            logger.info(f"   选择股票数量: {len(self.config_data.get('selected_stocks', []))}")
            
        except Exception as e:
            raise ValueError(f"配置文件格式错误: {e}")
    
    def get_selected_stocks(self) -> List[str]:
        """获取选择的股票列表"""
        return self.config_data.get('selected_stocks', [])
    
    def get_stock_rankings(self) -> pd.DataFrame:
        """获取股票排名信息"""
        rankings = self.config_data.get('stock_rankings', [])
        if rankings:
            df = pd.DataFrame(rankings)
            return df
        else:
            # 如果没有rankings，从selected_stocks创建基础DataFrame
            stocks = self.get_selected_stocks()
            return pd.DataFrame({'ticker': stocks})
    
    def get_technical_indicators(self) -> Dict:
        """获取技术指标参数"""
        return self.config_data.get('technical_indicators', {})
    
    def get_trading_parameters(self) -> Dict:
        """获取交易参数"""
        return self.config_data.get('trading_parameters', {})
    
    def get_portfolio_performance(self) -> Dict:
        """获取组合表现信息"""
        return self.config_data.get('portfolio_performance', {})
    
    def get_experiment_info(self) -> Dict:
        """获取实验基本信息"""
        return {
            'experiment_name': self.config_data.get('experiment_name', 'N/A'),
            'optimization_date': self.config_data.get('optimization_date', 'N/A'),
            'best_score': self.config_data.get('best_score', 'N/A'),
            'optimization_summary': self.config_data.get('optimization_summary', {})
        }

class TradingDataManager:
    """
    交易数据管理器，负责从trading_signals.db中提取和处理数据
    """
    
    def __init__(self, db_path: str = None):
        """
        初始化数据管理器
        
        Parameters:
        -----------
        db_path : str, optional
            数据库文件路径，如果为None则从配置文件获取
        """
        if db_path is None:
            db_path = EQUITY_CONFIG['DATABASE_PATH']
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
        print(f"[OK] 交易数据管理器初始化完成")
        print(f"   数据库路径: {self.db_path}")
        
    def get_available_tickers(self) -> List[str]:
        """获取所有可用的股票代码"""
        query = "SELECT DISTINCT ticker FROM trading_data ORDER BY ticker"
        df = pd.read_sql_query(query, self.conn)
        return df['ticker'].tolist()
    
    def get_price_data(self, tickers: List[str] = None, 
                      start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取价格数据
        
        Parameters:
        -----------
        tickers : List[str], optional
            股票代码列表，如果为None则获取所有股票
        start_date : str, optional
            开始日期，格式 'YYYY-MM-DD'
        end_date : str, optional
            结束日期，格式 'YYYY-MM-DD'
            
        Returns:
        --------
        pd.DataFrame
            价格数据，索引为日期，列为股票代码
        """
        # 构建查询条件
        where_conditions = []
        
        if tickers is not None:
            ticker_list = "', '".join(tickers)
            where_conditions.append(f"ticker IN ('{ticker_list}')")
            
        if start_date is not None:
            where_conditions.append(f"datetime >= '{start_date}'")
            
        if end_date is not None:
            where_conditions.append(f"datetime <= '{end_date}'")
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        query = f"""
        SELECT ticker, datetime, close 
        FROM trading_data 
        {where_clause}
        ORDER BY datetime, ticker
        """
        
        df = pd.read_sql_query(query, self.conn)
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # 转换为宽格式
        price_data = df.pivot(index='datetime', columns='ticker', values='close')
        
        # 使用前向填充处理缺失值，然后只删除所有值都为空的行
        price_data = price_data.ffill()
        price_data = price_data.dropna(how='all')
        
        return price_data
    
    def get_trading_signals(self, tickers: List[str] = None,
                           start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取交易信号数据
        
        Parameters:
        -----------
        tickers : List[str], optional
            股票代码列表
        start_date : str, optional
            开始日期
        end_date : str, optional
            结束日期
            
        Returns:
        --------
        pd.DataFrame
            包含所有交易信号的数据
        """
        where_conditions = []
        
        if tickers is not None:
            ticker_list = "', '".join(tickers)
            where_conditions.append(f"ticker IN ('{ticker_list}')")
            
        if start_date is not None:
            where_conditions.append(f"datetime >= '{start_date}'")
            
        if end_date is not None:
            where_conditions.append(f"datetime <= '{end_date}'")
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
        query = f"""
        SELECT ticker, datetime, close, Entry_Signal, Exit_Signal, Position, Entry_Price, Exit_Price, Profit_Loss 
        FROM trading_data {where_clause}
        ORDER BY datetime, ticker
        """
        
        df = pd.read_sql_query(query, self.conn)
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        return df
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()


class StockSelector:
    """
    股票选择器，基于多种指标筛选优质股票
    """
    
    def __init__(self, data_manager: TradingDataManager):
        """
        初始化股票选择器
        
        Parameters:
        -----------
        data_manager : TradingDataManager
            数据管理器实例
        """
        self.data_manager = data_manager
        
    def calculate_stock_scores(self, lookback_days: int = 252) -> pd.DataFrame:
        """
        计算股票评分，基于历史交易信号的表现
        
        Parameters:
        -----------
        lookback_days : int
            回望天数
            
        Returns:
        --------
        pd.DataFrame
            包含各种评分的DataFrame
        """
        # 获取所有股票数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days + 50)).strftime('%Y-%m-%d')
        
        # 获取交易信号数据
        signal_data = self.data_manager.get_trading_signals(start_date=start_date, end_date=end_date)
        
        scores = []
        
        for ticker in signal_data['ticker'].unique():
            ticker_signals = signal_data[signal_data['ticker'] == ticker].copy()
            
            # 放宽数据要求，至少需要30天的数据
            min_days = min(30, lookback_days // 4)
            if len(ticker_signals) < min_days:
                continue
                
            # 使用可用的数据长度，但不超过lookback_days
            actual_lookback = min(len(ticker_signals), lookback_days)
            recent_signals = ticker_signals.tail(actual_lookback)
            
            # 1. 交易信号统计
            total_trades = len(recent_signals[recent_signals['Exit_Signal'] == 1])
            winning_trades = len(recent_signals[(recent_signals['Exit_Signal'] == 1) & (recent_signals['Profit_Loss'] > 0)])
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            # 2. 盈利能力评分
            profit_loss_data = recent_signals[recent_signals['Profit_Loss'] != 0]['Profit_Loss']
            avg_profit_loss = profit_loss_data.mean() if len(profit_loss_data) > 0 else 0
            total_profit_loss = profit_loss_data.sum() if len(profit_loss_data) > 0 else 0
            
            # 3. 计算最大回撤
            max_drawdown, avg_drawdown = self._calculate_drawdown(recent_signals)
            
            # 4. 交易频率评分（适中为好）
            entry_signals = recent_signals['Entry_Signal'].sum()
            exit_signals = recent_signals['Exit_Signal'].sum()
            signal_frequency = (entry_signals + exit_signals) / len(recent_signals)
            
            # 5. 最近价格表现
            recent_prices = recent_signals['close'].dropna()
            if len(recent_prices) > 1:
                price_return = (recent_prices.iloc[-1] / recent_prices.iloc[0] - 1) * 100
                price_volatility = recent_prices.pct_change().std() * np.sqrt(252) * 100
            else:
                price_return = 0
                price_volatility = 0
            
            # 6. 综合评分
            # 考虑盈利能力、胜率、交易频率等因素
            composite_score = (
                avg_profit_loss * 0.3 +  # 平均盈利
                win_rate * 50 * 0.25 +   # 胜率（转换为0-50分）
                total_profit_loss * 0.2 + # 总盈利
                min(signal_frequency * 100, 10) * 0.15 +  # 信号频率（适中为好）
                min(price_return / 10, 5) * 0.1   # 价格表现（限制影响）
            )
            
            # 7. 高收益+低回撤综合评分 (新增)
            return_drawdown_score = self._calculate_return_drawdown_score(
                total_profit_loss, max_drawdown, avg_profit_loss
            )
            
            # 8. 胜率权重评分 (新增)
            win_rate_score = win_rate * total_trades * 0.5 + win_rate * 50  # 胜率*交易次数权重
            
            scores.append({
                'ticker': ticker,
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_profit_loss': avg_profit_loss,
                'total_profit_loss': total_profit_loss,
                'max_drawdown': max_drawdown,
                'avg_drawdown': avg_drawdown,
                'signal_frequency': signal_frequency,
                'price_return': price_return,
                'price_volatility': price_volatility,
                'composite_score': composite_score,
                'return_drawdown_score': return_drawdown_score,
                'win_rate_score': win_rate_score
            })
        
        return pd.DataFrame(scores)
    
    def _calculate_drawdown(self, ticker_signals: pd.DataFrame) -> Tuple[float, float]:
        """
        计算最大回撤和平均回撤
        
        Parameters:
        -----------
        ticker_signals : pd.DataFrame
            单个股票的信号数据
            
        Returns:
        --------
        Tuple[float, float]
            (最大回撤, 平均回撤)
        """
        profit_loss_data = ticker_signals[ticker_signals['Profit_Loss'] != 0]['Profit_Loss']
        
        if len(profit_loss_data) < 2:
            return 0.0, 0.0
        
        # 计算累积收益
        cumulative_profit = profit_loss_data.cumsum()
        
        # 计算回撤
        running_max = cumulative_profit.expanding().max()
        drawdown = cumulative_profit - running_max
        
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
        avg_drawdown = abs(drawdown.mean()) if len(drawdown) > 0 else 0
        
        return max_drawdown, avg_drawdown
    
    def _calculate_return_drawdown_score(self, total_profit: float, max_drawdown: float, avg_profit: float) -> float:
        """
        计算高收益+低回撤综合评分
        
        Parameters:
        -----------
        total_profit : float
            总收益
        max_drawdown : float
            最大回撤
        avg_profit : float
            平均收益
            
        Returns:
        --------
        float
            综合评分
        """
        if max_drawdown == 0:
            max_drawdown = 0.01  # 避免除零
        
        # 收益回撤比
        profit_drawdown_ratio = total_profit / max_drawdown if max_drawdown > 0 else total_profit
        
        # 综合评分：70%收益权重 + 30%回撤控制权重
        score = (
            total_profit * 0.4 +  # 总收益权重
            avg_profit * 30 * 0.3 +  # 平均收益权重
            profit_drawdown_ratio * 0.3  # 收益回撤比权重
        )
        
        return score
    
    def select_stocks(self, n_stocks: int = 10, method: str = 'composite') -> List[str]:
        """
        选择股票
        
        Parameters:
        -----------
        n_stocks : int
            选择的股票数量
        method : str
            选择方法: 'composite', 'total_profit', 'return_drawdown', 'win_rate', 'win_rate_score', 'frequency'
            
        Returns:
        --------
        List[str]
            选中的股票代码列表
        """
        scores_df = self.calculate_stock_scores()
        
        # 筛选有足够交易记录的股票
        scores_df = scores_df[scores_df['total_trades'] >= 3]  # 至少3次交易
        
        # 根据方法排序
        if method == 'composite':
            sorted_stocks = scores_df.nlargest(n_stocks, 'composite_score')
            score_col = 'composite_score'
        elif method == 'total_profit':
            sorted_stocks = scores_df.nlargest(n_stocks, 'total_profit_loss')
            score_col = 'total_profit_loss'
        elif method == 'return_drawdown':
            sorted_stocks = scores_df.nlargest(n_stocks, 'return_drawdown_score')
            score_col = 'return_drawdown_score'
        elif method == 'win_rate':
            sorted_stocks = scores_df.nlargest(n_stocks, 'win_rate')
            score_col = 'win_rate'
        elif method == 'win_rate_score':
            sorted_stocks = scores_df.nlargest(n_stocks, 'win_rate_score')
            score_col = 'win_rate_score'
        elif method == 'frequency':
            sorted_stocks = scores_df.nlargest(n_stocks, 'signal_frequency')
            score_col = 'signal_frequency'
        else:
            raise ValueError(f"Unknown selection method: {method}")
        
        selected_tickers = sorted_stocks['ticker'].tolist()
        
        logger.info(f"Selected {len(selected_tickers)} stocks using {method} method:")
        for i, (_, row) in enumerate(sorted_stocks.iterrows(), 1):
            logger.info(f"{i}. {row['ticker']}: Score={row[score_col]:.3f}, Trades={row['total_trades']}, WinRate={row['win_rate']:.2%}, MaxDrawdown={row['max_drawdown']:.2f}")
        
        return selected_tickers
    
    def select_top_performers(self, n_stocks: int = 15, 
                             custom_weights: Dict[str, float] = None,
                             min_trades: int = 5,
                             max_drawdown_threshold: float = 0.20) -> List[str]:
        """
        🚀 增强版股票选择器 - 可配置的综合表现评分
        
        Parameters:
        -----------
        n_stocks : int
            选择的股票数量 (默认15)
        custom_weights : Dict[str, float], optional
            自定义评分权重，可包含：
            - 'return': 收益权重 (默认0.35)
            - 'drawdown': 回撤权重 (默认0.25) 
            - 'win_rate': 胜率权重 (默认0.20)
            - 'profit_stability': 盈利稳定性权重 (默认0.15)
            - 'trade_frequency': 交易频率权重 (默认0.05)
        min_trades : int
            最小交易次数要求 (默认5)
        max_drawdown_threshold : float
            最大回撤阈值，超过此值的股票将被排除 (默认0.20)
            
        Returns:
        --------
        List[str]
            按综合表现排序的top N股票代码列表
        """
        # 默认权重配置
        default_weights = {
            'return': 0.35,           # 收益权重35%
            'drawdown': 0.25,         # 回撤控制25%
            'win_rate': 0.20,         # 胜率20%
            'profit_stability': 0.15, # 盈利稳定性15%
            'trade_frequency': 0.05   # 交易频率5%
        }
        
        # 使用自定义权重或默认权重
        weights = custom_weights if custom_weights else default_weights
        
        logger.info(f"🔍 使用可配置评分选择前 {n_stocks} 只股票")
        logger.info(f"   评分权重: {weights}")
        logger.info(f"   最小交易次数: {min_trades}")
        logger.info(f"   最大回撤阈值: {max_drawdown_threshold:.1%}")
        
        # 计算基础评分
        scores_df = self.calculate_stock_scores()
        
        # 应用筛选条件
        filtered_df = scores_df[
            (scores_df['total_trades'] >= min_trades) &           # 最小交易次数
            (scores_df['max_drawdown'] <= max_drawdown_threshold) # 回撤控制
        ].copy()
        
        if len(filtered_df) == 0:
            logger.warning("⚠️ 没有股票满足筛选条件，放宽条件重新筛选")
            filtered_df = scores_df[scores_df['total_trades'] >= max(1, min_trades//2)].copy()
        
        logger.info(f"   筛选后候选股票: {len(filtered_df)}")
        
        # 标准化各项指标到[0,1]区间
        def normalize_column(series, reverse=False):
            if series.std() == 0:
                return pd.Series(0.5, index=series.index)
            normalized = (series - series.min()) / (series.max() - series.min())
            return (1 - normalized) if reverse else normalized
        
        # 计算各项标准化评分
        filtered_df['return_score'] = normalize_column(filtered_df['total_profit_loss'])
        filtered_df['drawdown_score'] = normalize_column(filtered_df['max_drawdown'], reverse=True)  # 回撤越小越好
        filtered_df['win_rate_score_norm'] = normalize_column(filtered_df['win_rate'])
        filtered_df['stability_score'] = normalize_column(
            filtered_df['avg_profit_loss'] / (filtered_df['price_volatility'] + 0.01)  # 收益稳定性
        )
        filtered_df['frequency_score'] = normalize_column(filtered_df['signal_frequency'])
        
        # 计算加权综合评分
        filtered_df['weighted_composite_score'] = (
            filtered_df['return_score'] * weights.get('return', 0.35) +
            filtered_df['drawdown_score'] * weights.get('drawdown', 0.25) +
            filtered_df['win_rate_score_norm'] * weights.get('win_rate', 0.20) +
            filtered_df['stability_score'] * weights.get('profit_stability', 0.15) +
            filtered_df['frequency_score'] * weights.get('trade_frequency', 0.05)
        )
        
        # 选择top N股票
        top_stocks = filtered_df.nlargest(n_stocks, 'weighted_composite_score')
        selected_tickers = top_stocks['ticker'].tolist()
        
        # 详细日志输出
        logger.info(f"\n🏆 Top {len(selected_tickers)} 股票评分结果:")
        logger.info("=" * 100)
        logger.info(f"{'排名':<4} {'股票代码':<12} {'综合评分':<8} {'总收益':<8} {'最大回撤':<8} {'胜率':<8} {'交易次数':<8} {'平均收益':<10}")
        logger.info("=" * 100)
        
        for i, (_, row) in enumerate(top_stocks.iterrows(), 1):
            logger.info(f"{i:<4} {row['ticker']:<12} {row['weighted_composite_score']:<8.3f} "
                       f"{row['total_profit_loss']:<8.2f} {row['max_drawdown']:<8.2%} "
                       f"{row['win_rate']:<8.2%} {row['total_trades']:<8} {row['avg_profit_loss']:<10.3f}")
        
        return selected_tickers


class SignalDrivenPortfolioBacktester:
    """
    基于交易信号的组合回测器
    """
    
    def __init__(self, data_manager: TradingDataManager, initial_capital: float = 1000000):
        """
        初始化回测器
        
        Parameters:
        -----------
        data_manager : TradingDataManager
            数据管理器实例
        initial_capital : float
            初始资金
        """
        self.data_manager = data_manager
        self.initial_capital = initial_capital
        
    def backtest_portfolio(self, selected_tickers: List[str], weights: pd.Series,
                          start_date: str, end_date: str,
                          transaction_cost: float = 0.001) -> Dict:
        """
        基于交易信号回测组合表现
        
        Parameters:
        -----------
        selected_tickers : List[str]
            选中的股票列表
        weights : pd.Series
            各股票权重
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        transaction_cost : float
            交易成本（双边）
            
        Returns:
        --------
        Dict
            回测结果
        """
        logger.info("Starting signal-driven portfolio backtest")
        
        # 获取交易信号数据
        signals_data = self.data_manager.get_trading_signals(
            tickers=selected_tickers,
            start_date=start_date,
            end_date=end_date
        )
        
        # 确保权重对齐
        weights = weights.reindex(selected_tickers, fill_value=0)
        weights = weights / weights.sum()  # 重新标准化
        
        # 初始化组合状态
        portfolio_state = {
            'cash': self.initial_capital,
            'positions': {ticker: 0 for ticker in selected_tickers},  # 持仓数量
            'position_values': {ticker: 0 for ticker in selected_tickers},  # 持仓价值
            'total_value': self.initial_capital
        }
        
        # 记录每日组合价值
        daily_values = []
        daily_positions = []
        trade_log = []
        
        # 按日期处理信号
        for date in pd.date_range(start_date, end_date):
            date_str = date.strftime('%Y-%m-%d')
            daily_signals = signals_data[signals_data['datetime'].dt.date == date.date()]
            
            if len(daily_signals) == 0:
                # 没有数据的日子，更新持仓价值但不交易
                self._update_portfolio_value(portfolio_state, daily_signals, selected_tickers)
                daily_values.append({
                    'date': date,
                    'total_value': portfolio_state['total_value'],
                    'cash': portfolio_state['cash'],
                    'positions_value': sum(portfolio_state['position_values'].values())
                })
                daily_positions.append({
                    'date': date,
                    **portfolio_state['positions'].copy()
                })
                continue
            
            # 处理当日信号
            for _, signal in daily_signals.iterrows():
                ticker = signal['ticker']
                current_price = signal['close']
                
                # 更新持仓价值
                if portfolio_state['positions'][ticker] > 0:
                    portfolio_state['position_values'][ticker] = portfolio_state['positions'][ticker] * current_price
                
                # 处理入场信号 (Entry_Signal > 0 表示入场，信号强度越高越优先)
                if signal['Entry_Signal'] > 0 and portfolio_state['positions'][ticker] == 0:
                    # 计算应投入的资金（考虑交易成本）
                    available_cash = portfolio_state['cash']
                    target_weight = weights[ticker]
                    
                    # 计算实际可投入金额（扣除交易成本）
                    max_investment = available_cash / (1 + transaction_cost)
                    target_value = min(portfolio_state['total_value'] * target_weight, max_investment)
                    
                    if target_value > 0:
                        # 买入
                        shares_to_buy = target_value / current_price
                        cost = shares_to_buy * current_price * (1 + transaction_cost)
                        
                        if portfolio_state['cash'] >= cost:
                            portfolio_state['positions'][ticker] = shares_to_buy
                            portfolio_state['position_values'][ticker] = shares_to_buy * current_price
                            portfolio_state['cash'] -= cost
                            
                            trade_log.append({
                                'date': signal['datetime'],
                                'ticker': ticker,
                                'action': 'BUY',
                                'shares': shares_to_buy,
                                'price': current_price,
                                'value': shares_to_buy * current_price,
                                'cost': cost
                            })
                
                # 处理出场信号
                elif signal['Exit_Signal'] == 1 and portfolio_state['positions'][ticker] > 0:
                    # 卖出
                    shares_to_sell = portfolio_state['positions'][ticker]
                    proceeds = shares_to_sell * current_price * (1 - transaction_cost)
                    
                    portfolio_state['cash'] += proceeds
                    portfolio_state['positions'][ticker] = 0
                    portfolio_state['position_values'][ticker] = 0
                    
                    trade_log.append({
                        'date': signal['datetime'],
                        'ticker': ticker,
                        'action': 'SELL',
                        'shares': shares_to_sell,
                        'price': current_price,
                        'value': shares_to_sell * current_price,
                        'proceeds': proceeds
                    })
            
            # 更新总价值
            portfolio_state['total_value'] = portfolio_state['cash'] + sum(portfolio_state['position_values'].values())
            
            # 记录当日状态
            daily_values.append({
                'date': date,
                'total_value': portfolio_state['total_value'],
                'cash': portfolio_state['cash'],
                'positions_value': sum(portfolio_state['position_values'].values())
            })
            
            daily_positions.append({
                'date': date,
                **portfolio_state['positions'].copy()
            })
        
        # 转换为DataFrame
        daily_values_df = pd.DataFrame(daily_values).set_index('date')
        daily_positions_df = pd.DataFrame(daily_positions).set_index('date')
        trade_log_df = pd.DataFrame(trade_log)
        
        # 计算收益率
        portfolio_returns = daily_values_df['total_value'].pct_change().dropna()
        
        # 计算表现指标
        total_return = (daily_values_df['total_value'].iloc[-1] / self.initial_capital) - 1
        volatility = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = portfolio_returns.mean() * 252 / (portfolio_returns.std() * np.sqrt(252)) if volatility > 0 else 0
        
        # 计算最大回撤
        cumulative_returns = daily_values_df['total_value'] / self.initial_capital
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 计算年化收益率
        days = len(daily_values_df)
        cagr = (daily_values_df['total_value'].iloc[-1] / self.initial_capital) ** (365.25 / days) - 1
        
        # 计算胜率（基于交易）
        if len(trade_log_df) > 0:
            # 配对买卖交易
            buy_trades = trade_log_df[trade_log_df['action'] == 'BUY']
            sell_trades = trade_log_df[trade_log_df['action'] == 'SELL']
            
            # 简单统计：卖出价格高于买入价格的比例
            profitable_days = (portfolio_returns > 0).sum()
            total_trading_days = len(portfolio_returns[portfolio_returns != 0])
            win_rate = profitable_days / total_trading_days if total_trading_days > 0 else 0
        else:
            win_rate = 0
        
        backtest_results = {
            'daily_values': daily_values_df,
            'daily_positions': daily_positions_df,
            'trade_log': trade_log_df,
            'portfolio_returns': portfolio_returns,
            'total_return': total_return,
            'cagr': cagr,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(trade_log_df),
            'final_value': daily_values_df['total_value'].iloc[-1],
            'start_date': start_date,
            'end_date': end_date
        }
        
        logger.info(f"Signal-driven backtest completed:")
        logger.info(f"  Total Return: {total_return:.2%}")
        logger.info(f"  CAGR: {cagr:.2%}")
        logger.info(f"  Volatility: {volatility:.2%}")
        logger.info(f"  Sharpe Ratio: {sharpe_ratio:.3f}")
        logger.info(f"  Max Drawdown: {max_drawdown:.2%}")
        logger.info(f"  Win Rate: {win_rate:.2%}")
        logger.info(f"  Total Trades: {len(trade_log_df)}")
        
        return backtest_results
    
    def _update_portfolio_value(self, portfolio_state: Dict, daily_signals: pd.DataFrame, tickers: List[str]):
        """更新组合价值（当没有交易信号时）"""
        # 如果没有当日数据，保持之前的价值
        for ticker in tickers:
            if portfolio_state['positions'][ticker] > 0:
                # 尝试从daily_signals中获取价格，如果没有则保持不变
                ticker_data = daily_signals[daily_signals['ticker'] == ticker]
                if len(ticker_data) > 0:
                    current_price = ticker_data['close'].iloc[0]
                    portfolio_state['position_values'][ticker] = portfolio_state['positions'][ticker] * current_price
        
        portfolio_state['total_value'] = portfolio_state['cash'] + sum(portfolio_state['position_values'].values())


class WeightMethod:
    """权重分配方法枚举"""
    EQUAL_WEIGHT = 'equal_weight'
    SCORE_WEIGHTED = 'score_weighted'
    PROFIT_WEIGHTED = 'profit_weighted'
    MULTI_OBJECTIVE_OPTIMIZED = 'multi_objective_optimized'
    ENHANCED_TOP_PERFORMERS = 'enhanced_top_performers'

class PortfolioConstructor:
    """
    投资组合构建器 - 优化版本
    支持多种权重分配方法和动态仓位管理
    """
    
    def __init__(self, optimization_results: Dict, 
                 weight_method: str = WeightMethod.ENHANCED_TOP_PERFORMERS,
                 experiment_name: str = None):
        """
        初始化投资组合构建器
        
        Parameters:
        -----------
        optimization_results : Dict
            优化结果，包含股票表现和评分
        weight_method : str
            权重分配方法，默认使用增强版顶级表现者
        experiment_name : str
            实验名称，用于结果保存
        """
        self.optimization_results = optimization_results
        self.weight_method = weight_method
        self.experiment_name = experiment_name or f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        # 初始化日志
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🏗️ 初始化投资组合构建器")
        self.logger.info(f"   实验名称: {self.experiment_name}")
        self.logger.info(f"   权重方法: {self.weight_method}")
    
    def construct_portfolio(self) -> Dict:
        """
        构建投资组合，使用优化后的权重分配策略
        
        Returns:
        --------
        Dict
            包含权重、表现指标等的完整结果
        """
        self.logger.info("🚀 开始构建投资组合")
        
        try:
            # 1. 获取股票表现数据
            stock_performances = self.optimization_results.get('stock_performances', {})
            if not stock_performances:
                raise ValueError("优化结果中缺少股票表现数据")
            
            # 2. 根据方法分配权重
            weights = self._allocate_weights(stock_performances)
            
            # 3. 计算组合指标
            portfolio_metrics = self._calculate_portfolio_metrics(weights, stock_performances)
            
            # 4. 生成完整结果
            result = {
                'weights': weights,
                'metrics': portfolio_metrics,
                'experiment_name': self.experiment_name,
                'weight_method': self.weight_method,
                'construction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stock_performances': stock_performances
            }
            
            self.logger.info("✅ 投资组合构建完成")
            self._log_portfolio_summary(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 投资组合构建失败: {str(e)}")
            raise
    
    def _allocate_weights(self, stock_performances: Dict) -> Dict[str, float]:
        """分配投资组合权重"""
        if self.weight_method == WeightMethod.EQUAL_WEIGHT:
            return self._equal_weight_allocation(stock_performances)
        elif self.weight_method == WeightMethod.SCORE_WEIGHTED:
            return self._score_weighted_allocation(stock_performances)
        elif self.weight_method == WeightMethod.PROFIT_WEIGHTED:
            return self._profit_weighted_allocation(stock_performances)
        elif self.weight_method == WeightMethod.MULTI_OBJECTIVE_OPTIMIZED:
            return self._multi_objective_allocation(stock_performances)
        elif self.weight_method == WeightMethod.ENHANCED_TOP_PERFORMERS:
            return self._enhanced_top_performers_allocation(stock_performances)
        else:
            raise ValueError(f"未知的权重分配方法: {self.weight_method}")
    
    def _equal_weight_allocation(self, stock_performances: Dict) -> Dict[str, float]:
        """等权重分配"""
        n_stocks = len(stock_performances)
        weight = 1.0 / n_stocks
        return {ticker: weight for ticker in stock_performances.keys()}
    
    def _score_weighted_allocation(self, stock_performances: Dict) -> Dict[str, float]:
        """基于综合评分的权重分配"""
        scores = {ticker: perf['composite_score'] for ticker, perf in stock_performances.items()}
        total_score = sum(scores.values())
        return {ticker: score/total_score for ticker, score in scores.items()}
    
    def _profit_weighted_allocation(self, stock_performances: Dict) -> Dict[str, float]:
        """基于历史盈利的权重分配"""
        profits = {ticker: max(0, perf['total_profit_loss']) 
                  for ticker, perf in stock_performances.items()}
        total_profit = sum(profits.values())
        if total_profit == 0:
            return self._equal_weight_allocation(stock_performances)
        return {ticker: profit/total_profit for ticker, profit in profits.items()}
    
    def _multi_objective_allocation(self, stock_performances: Dict) -> Dict[str, float]:
        """多目标优化权重分配"""
        # 1. 计算多个目标的标准化得分
        scores = {}
        for ticker, perf in stock_performances.items():
            # 收益得分
            return_score = perf['annual_return'] * 0.4
            
            # 风险控制得分
            risk_score = (1 - abs(perf['max_drawdown'])) * 0.3
            
            # 稳定性得分
            stability_score = perf['sharpe_ratio'] * 0.2
            
            # 交易频率得分
            trade_score = min(perf['total_trades'] / 100, 1) * 0.1
            
            # 综合得分
            scores[ticker] = return_score + risk_score + stability_score + trade_score
        
        # 2. 基于综合得分分配权重
        total_score = sum(scores.values())
        return {ticker: score/total_score for ticker, score in scores.items()}
    
    def _enhanced_top_performers_allocation(self, stock_performances: Dict) -> Dict[str, float]:
        """增强版顶级表现者权重分配"""
        # 1. 计算增强版评分
        enhanced_scores = {}
        for ticker, perf in stock_performances.items():
            # 基础收益评分
            return_score = perf['annual_return'] * 0.35
            
            # 风险调整后收益
            risk_adj_return = perf['annual_return'] / (abs(perf['max_drawdown']) + 0.01)
            risk_score = min(risk_adj_return, 5) * 0.25  # 限制极端值
            
            # 交易质量评分
            quality_score = (perf['win_rate'] * 0.7 + perf['sharpe_ratio'] * 0.3) * 0.25
            
            # 交易活跃度评分
            activity_score = min(perf['total_trades'] / 100, 1) * 0.15
            
            # 综合评分
            enhanced_scores[ticker] = return_score + risk_score + quality_score + activity_score
        
        # 2. 动态权重分配
        total_score = sum(enhanced_scores.values())
        base_weights = {ticker: score/total_score 
                       for ticker, score in enhanced_scores.items()}
        
        # 3. 权重优化
        min_weight = 0.02  # 最小权重2%
        max_weight = 0.15  # 最大权重15%
        
        # 应用权重限制
        adjusted_weights = {}
        remaining_weight = 1.0
        
        # 先处理超过最大权重的股票
        for ticker, weight in base_weights.items():
            if weight > max_weight:
                adjusted_weights[ticker] = max_weight
                remaining_weight -= max_weight
            elif weight < min_weight:
                adjusted_weights[ticker] = min_weight
                remaining_weight -= min_weight
        
        # 分配剩余权重
        remaining_tickers = [t for t in base_weights if t not in adjusted_weights]
        if remaining_tickers:
            remaining_base_total = sum(base_weights[t] for t in remaining_tickers)
            for ticker in remaining_tickers:
                if remaining_base_total > 0:
                    adjusted_weights[ticker] = (base_weights[ticker] / remaining_base_total) * remaining_weight
                else:
                    adjusted_weights[ticker] = remaining_weight / len(remaining_tickers)
        
        # 确保权重和为1
        total_weight = sum(adjusted_weights.values())
        return {ticker: weight/total_weight for ticker, weight in adjusted_weights.items()}
    
    def _calculate_portfolio_metrics(self, weights: Dict[str, float], 
                                  stock_performances: Dict) -> Dict:
        """计算组合整体指标"""
        # 1. 加权收益率
        portfolio_return = sum(perf['annual_return'] * weights[ticker]
                             for ticker, perf in stock_performances.items())
        
        # 2. 加权夏普比率
        portfolio_sharpe = sum(perf['sharpe_ratio'] * weights[ticker]
                             for ticker, perf in stock_performances.items())
        
        # 3. 组合最大回撤（保守估计）
        portfolio_max_drawdown = max(abs(perf['max_drawdown']) * weights[ticker]
                                   for ticker, perf in stock_performances.items())
        
        # 4. 平均交易次数
        avg_trades = sum(perf['total_trades'] * weights[ticker]
                        for ticker, perf in stock_performances.items())
        
        # 5. 加权胜率
        portfolio_win_rate = sum(perf['win_rate'] * weights[ticker]
                               for ticker, perf in stock_performances.items())
        
        return {
            'portfolio_return': portfolio_return,
            'portfolio_sharpe': portfolio_sharpe,
            'portfolio_max_drawdown': portfolio_max_drawdown,
            'avg_trades': avg_trades,
            'portfolio_win_rate': portfolio_win_rate,
            'n_stocks': len(weights),
            'max_weight': max(weights.values()),
            'min_weight': min(weights.values())
        }
    
    def _log_portfolio_summary(self, result: Dict):
        """记录投资组合摘要"""
        metrics = result['metrics']
        self.logger.info(f"\n=== 📊 投资组合摘要 ===")
        self.logger.info(f"实验名称: {self.experiment_name}")
        self.logger.info(f"权重方法: {self.weight_method}")
        self.logger.info(f"股票数量: {metrics['n_stocks']}")
        self.logger.info(f"权重范围: {metrics['min_weight']:.1%} ~ {metrics['max_weight']:.1%}")
        self.logger.info(f"\n性能指标:")
        self.logger.info(f"  📈 组合收益率: {metrics['portfolio_return']:.2%}")
        self.logger.info(f"  📊 组合夏普比: {metrics['portfolio_sharpe']:.3f}")
        self.logger.info(f"  📉 最大回撤: {metrics['portfolio_max_drawdown']:.2%}")
        self.logger.info(f"  🎯 平均胜率: {metrics['portfolio_win_rate']:.2%}")
        self.logger.info(f"  🔄 平均交易: {metrics['avg_trades']:.1f}次")
        
        # 显示前10大持仓
        weights = result['weights']
        top_10_weights = dict(sorted(weights.items(), key=lambda x: x[1], reverse=True)[:10])
        self.logger.info(f"\n📊 前10大持仓:")
        for ticker, weight in top_10_weights.items():
            perf = result['stock_performances'][ticker]
            self.logger.info(f"  {ticker}: {weight:.1%} (收益:{perf['annual_return']:.1%}, "
                           f"回撤:{perf['max_drawdown']:.1%}, 胜率:{perf['win_rate']:.1%})")

class PortfolioBuilder:
    """
    基于信号驱动的组合构建器
    """
    
    def __init__(self, data_manager: TradingDataManager, portfolio_db_path: str = None):
        """
        初始化组合构建器
        
        Parameters:
        -----------
        data_manager : TradingDataManager
            数据管理器实例
        portfolio_db_path : str, optional
            投资组合数据库路径，如果为None则从配置文件获取
        """
        if portfolio_db_path is None:
            portfolio_db_path = PORTFOLIO_CONFIG['DATABASE_PATH']
        
        self.data_manager = data_manager
        self.selector = StockSelector(data_manager)
        self.backtester = SignalDrivenPortfolioBacktester(data_manager)
        
        # 初始化投资组合数据库管理器
        if PortfolioDatabaseManager:
            self.portfolio_db = PortfolioDatabaseManager(portfolio_db_path)
            print(f"[OK] 投资组合构建器初始化完成")
            print(f"   组合数据库路径: {portfolio_db_path}")
        else:
            self.portfolio_db = None
            logger.warning("Portfolio database manager not available")
        
    def build_portfolio(self, n_stocks: int = None, 
                       weight_method: str = 'score_weighted',
                       lookback_days: int = 365,
                       min_weight: float = None,
                       max_weight: float = None) -> Dict:
        """
        构建信号驱动的组合 - 现已支持多目标优化
        
        Parameters:
        -----------
        n_stocks : int
            选择的股票数量
        weight_method : str
            权重分配方法: 'score_weighted'(默认), 'multi_objective_optimized', 'equal_weight', 'profit_weighted'
        lookback_days : int
            用于评分的回望天数
        min_weight : float
            最小权重限制
        max_weight : float
            最大权重限制
            
        Returns:
        --------
        Dict
            包含权重、选中股票等信息的字典
        """
        # 从配置文件获取默认参数
        if n_stocks is None:
            n_stocks = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MAX_STOCKS']
        if min_weight is None:
            min_weight = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MIN_WEIGHT']
        if max_weight is None:
            max_weight = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MAX_WEIGHT']
        
        logger.info(f"Building signal-driven portfolio with {n_stocks} stocks")
        logger.info(f"Weight constraints: {min_weight:.1%} ~ {max_weight:.1%}")
        logger.info(f"Method: {weight_method}")
        
        # 1. 股票选择 - 支持增强版选择器
        if weight_method == 'enhanced_top_performers':
            # 使用增强版选择器，支持自定义权重
            custom_weights = {
                'return': 0.40,           # 收益权重40%
                'drawdown': 0.30,         # 回撤控制30%
                'win_rate': 0.20,         # 胜率20%
                'profit_stability': 0.10, # 盈利稳定性10%
            }
            selected_tickers = self.selector.select_top_performers(
                n_stocks=n_stocks,
                custom_weights=custom_weights,
                min_trades=5,
                max_drawdown_threshold=0.15  # 15%最大回撤限制
            )
        else:
            selected_tickers = self.selector.select_stocks(n_stocks)
        
        # 2. 获取股票评分（用于权重分配）
        scores_df = self.selector.calculate_stock_scores(lookback_days)
        scores_df = scores_df[scores_df['ticker'].isin(selected_tickers)]
        
        # 3. 计算权重 - 新增多目标优化
        if weight_method == 'multi_objective_optimized':
            # 多目标优化：利润最大化 + 回撤最小化 + 夏普比率最大化 + 胜率最大化
            weights = self._multi_objective_optimization(scores_df, selected_tickers, min_weight, max_weight)
        elif weight_method == 'config_weighted':
            # 在标准模式下，config_weighted 等同于 score_weighted
            logger.warning("在标准模式下，config_weighted方法自动转换为score_weighted")
            scores = scores_df.set_index('ticker')['composite_score']
            scores = scores.reindex(selected_tickers, fill_value=0)
            scores = scores.clip(lower=0)  # 确保非负
            weights = scores / scores.sum() if scores.sum() > 0 else pd.Series(1/len(selected_tickers), index=selected_tickers)
        elif weight_method == 'equal_weight':
            weights = pd.Series(1/len(selected_tickers), index=selected_tickers)
        elif weight_method == 'score_weighted':
            # 基于综合评分加权
            scores = scores_df.set_index('ticker')['composite_score']
            scores = scores.reindex(selected_tickers, fill_value=0)
            scores = scores.clip(lower=0)  # 确保非负
            weights = scores / scores.sum() if scores.sum() > 0 else pd.Series(1/len(selected_tickers), index=selected_tickers)
        elif weight_method == 'profit_weighted':
            # 基于历史盈利加权
            profits = scores_df.set_index('ticker')['total_profit_loss']
            profits = profits.reindex(selected_tickers, fill_value=0)
            profits = profits.clip(lower=0)  # 只考虑盈利的股票
            weights = profits / profits.sum() if profits.sum() > 0 else pd.Series(1/len(selected_tickers), index=selected_tickers)
        elif weight_method == 'enhanced_top_performers':
            # 增强版选择器已经选择了股票，这里使用综合评分进行权重分配
            logger.info("使用增强版顶级表现者选择结果进行权重分配")
            scores = scores_df.set_index('ticker')['composite_score']
            scores = scores.reindex(selected_tickers, fill_value=0)
            scores = scores.clip(lower=0)  # 确保非负
            weights = scores / scores.sum() if scores.sum() > 0 else pd.Series(1/len(selected_tickers), index=selected_tickers)
        else:
            raise ValueError(f"Unknown weight method: {weight_method}")
        
        result = {
            'weights': weights,
            'selected_tickers': selected_tickers,
            'scores': scores_df,
            'weight_method': weight_method,
            'lookback_days': lookback_days,
            'optimization_constraints': {'min_weight': min_weight, 'max_weight': max_weight}
        }
        
        logger.info(f"Portfolio built successfully:")
        logger.info(f"  Selected stocks: {len(selected_tickers)}")
        logger.info(f"  Weight method: {weight_method}")
        if weight_method == 'multi_objective_optimized':
            logger.info("  优化目标: 1)利润最大化 2)回撤最小化 3)夏普比率最大化 4)胜率最大化")
        for ticker, weight in weights.items():
            ticker_info = scores_df[scores_df['ticker'] == ticker]
            if len(ticker_info) > 0:
                info = ticker_info.iloc[0]
                logger.info(f"    {ticker}: {weight:.1%} (利润:{info['total_profit_loss']:.1f}, 胜率:{info['win_rate']:.1%})")
            else:
                logger.info(f"    {ticker}: {weight:.2%}")
        
        return result
    
    def build_portfolio_from_config(self, config_loader: ConfigFileLoader,
                                  weight_method: str = 'config_weighted',
                                  lookback_days: int = 365,
                                  min_weight: float = None,
                                  max_weight: float = None) -> Dict:
        """
        基于配置文件构建投资组合
        
        Parameters:
        -----------
        config_loader : ConfigFileLoader
            配置文件加载器
        weight_method : str
            权重分配方法: 'config_weighted', 'equal_weight', 'profit_weighted', 'multi_objective_optimized'
        lookback_days : int
            用于评分的回望天数
        min_weight : float
            最小权重限制
        max_weight : float
            最大权重限制
            
        Returns:
        --------
        Dict
            包含权重、选中股票等信息的字典
        """
        # 从配置文件获取默认参数
        if min_weight is None:
            min_weight = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MIN_WEIGHT']
        if max_weight is None:
            max_weight = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MAX_WEIGHT']
        
        # 获取配置文件信息
        experiment_info = config_loader.get_experiment_info()
        selected_tickers = config_loader.get_selected_stocks()
        stock_rankings = config_loader.get_stock_rankings()
        
        logger.info(f"Building portfolio from config file:")
        logger.info(f"  实验名称: {experiment_info['experiment_name']}")
        logger.info(f"  优化日期: {experiment_info['optimization_date']}")
        logger.info(f"  最佳得分: {experiment_info['best_score']}")
        logger.info(f"  Selected stocks: {len(selected_tickers)}")
        logger.info(f"  Weight method: {weight_method}")
        logger.info(f"  Weight constraints: {min_weight:.1%} ~ {max_weight:.1%}")
        
        # 验证股票在数据库中是否存在
        available_tickers = self.data_manager.get_available_tickers()
        valid_tickers = [ticker for ticker in selected_tickers if ticker in available_tickers]
        invalid_tickers = [ticker for ticker in selected_tickers if ticker not in available_tickers]
        
        if invalid_tickers:
            logger.warning(f"以下股票在数据库中不存在，将被排除: {invalid_tickers}")
        
        if not valid_tickers:
            raise ValueError("配置文件中的股票在数据库中都不存在！")
        
        logger.info(f"有效股票数量: {len(valid_tickers)}/{len(selected_tickers)}")
        
        # 获取这些股票的评分（用于权重分配）
        scores_df = self.selector.calculate_stock_scores(lookback_days)
        scores_df = scores_df[scores_df['ticker'].isin(valid_tickers)]
        
        # 计算权重
        if weight_method == 'config_weighted':
            # 基于配置文件中的股票排名加权
            if 'annual_return' in stock_rankings.columns:
                # 使用年化收益率加权
                ranking_scores = stock_rankings.set_index('ticker')['annual_return']
                ranking_scores = ranking_scores.reindex(valid_tickers, fill_value=0)
                ranking_scores = ranking_scores.clip(lower=0)
                weights = ranking_scores / ranking_scores.sum() if ranking_scores.sum() > 0 else pd.Series(1/len(valid_tickers), index=valid_tickers)
                logger.info("使用配置文件中的年化收益率进行加权")
            else:
                # 等权重
                weights = pd.Series(1/len(valid_tickers), index=valid_tickers)
                logger.info("配置文件无排名信息，使用等权重")
        elif weight_method == 'equal_weight':
            weights = pd.Series(1/len(valid_tickers), index=valid_tickers)
        elif weight_method == 'score_weighted':
            # 基于综合评分加权
            composite_scores = scores_df.set_index('ticker')['composite_score']
            composite_scores = composite_scores.reindex(valid_tickers, fill_value=0)
            composite_scores = composite_scores.clip(lower=0)
            weights = composite_scores / composite_scores.sum() if composite_scores.sum() > 0 else pd.Series(1/len(valid_tickers), index=valid_tickers)
            logger.info("使用综合评分进行加权")
        elif weight_method == 'enhanced_top_performers':
            # 基于增强表现评分加权
            enhanced_scores = scores_df.set_index('ticker')['return_drawdown_score']
            enhanced_scores = enhanced_scores.reindex(valid_tickers, fill_value=0)
            enhanced_scores = enhanced_scores.clip(lower=0)
            weights = enhanced_scores / enhanced_scores.sum() if enhanced_scores.sum() > 0 else pd.Series(1/len(valid_tickers), index=valid_tickers)
            logger.info("使用增强表现评分进行加权")
        elif weight_method == 'multi_objective_optimized':
            weights = self._multi_objective_optimization(scores_df, valid_tickers, min_weight, max_weight)
        elif weight_method == 'profit_weighted':
            # 基于历史盈利加权
            profits = scores_df.set_index('ticker')['total_profit_loss']
            profits = profits.reindex(valid_tickers, fill_value=0)
            profits = profits.clip(lower=0)
            weights = profits / profits.sum() if profits.sum() > 0 else pd.Series(1/len(valid_tickers), index=valid_tickers)
            logger.info("使用历史盈利进行加权")
        else:
            raise ValueError(f"Unknown weight method: {weight_method}")
        
        # 应用权重约束
        weights = weights.clip(lower=min_weight, upper=max_weight)
        weights = weights / weights.sum()  # 重新标准化
        
        result = {
            'weights': weights,
            'selected_tickers': valid_tickers,
            'scores': scores_df,
            'weight_method': weight_method,
            'lookback_days': lookback_days,
            'optimization_constraints': {'min_weight': min_weight, 'max_weight': max_weight},
            'config_info': experiment_info,
            'config_stock_rankings': stock_rankings,
            'config_technical_indicators': config_loader.get_technical_indicators(),
            'config_trading_parameters': config_loader.get_trading_parameters(),
            'config_portfolio_performance': config_loader.get_portfolio_performance()
        }
        
        logger.info(f"Config-based portfolio built successfully:")
        for ticker, weight in weights.items():
            config_stock_info = stock_rankings[stock_rankings['ticker'] == ticker]
            if len(config_stock_info) > 0:
                info = config_stock_info.iloc[0]
                annual_return = info.get('annual_return', 0)
                win_rate = info.get('win_rate', 0)
                logger.info(f"    {ticker}: {weight:.1%} (配置年收益:{annual_return:.1%}, 胜率:{win_rate:.1%})")
            else:
                logger.info(f"    {ticker}: {weight:.2%}")
        
        return result
    
    def optimize_portfolio_from_config(self, config_loader: ConfigFileLoader,
                                     start_date: str, end_date: str,
                                     initial_capital: float = 1000000,
                                     lookback_days: int = 365,
                                     min_weight: float = None,
                                     max_weight: float = None,
                                     save_to_db: bool = True) -> Dict:
        """
        基于配置文件测试所有优化方法，找到最优组合
        
        Parameters:
        -----------
        config_loader : ConfigFileLoader
            配置文件加载器
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        initial_capital : float
            初始资金
        lookback_days : int
            用于评分的回望天数
        min_weight : float
            最小权重限制
        max_weight : float
            最大权重限制
        save_to_db : bool
            是否保存到数据库
            
        Returns:
        --------
        Dict
            包含所有方法测试结果和最优组合的字典
        """
        # 从配置文件获取默认参数
        if min_weight is None:
            min_weight = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MIN_WEIGHT']
        if max_weight is None:
            max_weight = PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MAX_WEIGHT']
        
        experiment_info = config_loader.get_experiment_info()
        
        logger.info(f"开始基于配置文件的全方法投资组合优化")
        logger.info(f"  配置实验: {experiment_info['experiment_name']}")
        logger.info(f"  股票数量: {len(config_loader.get_selected_stocks())}")
        logger.info(f"  回测期间: {start_date} ~ {end_date}")
        logger.info(f"  初始资金: ¥{initial_capital:,.0f}")
        
        # 测试所有权重方法
        weight_methods = [
            ('config_weighted', '配置文件年化收益加权'),
            ('equal_weight', '等权重'),
            ('score_weighted', '综合评分加权'),
            ('profit_weighted', '历史盈利加权'),
            ('enhanced_top_performers', '增强表现加权'),
            ('multi_objective_optimized', '多目标优化')
        ]
        
        results = {}
        
        for method, method_name in weight_methods:
            logger.info(f"\n正在测试方法: {method_name}")
            
            try:
                # 构建组合
                portfolio_result = self.build_portfolio_from_config(
                    config_loader=config_loader,
                    weight_method=method,
                    lookback_days=lookback_days,
                    min_weight=min_weight,
                    max_weight=max_weight
                )
                
                # 回测组合
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                portfolio_name = f"Config_Optimize_{method}_{timestamp}"
                
                full_result = self.backtest_and_analyze(
                    portfolio_result=portfolio_result,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    save_to_db=save_to_db,
                    portfolio_name=portfolio_name
                )
                
                # 存储结果
                results[method] = {
                    'method_name': method_name,
                    'portfolio_result': full_result,
                    'performance_metrics': {
                        'total_return': full_result['total_return'],
                        'cagr': full_result['cagr'],
                        'volatility': full_result['volatility'],
                        'sharpe_ratio': full_result['sharpe_ratio'],
                        'max_drawdown': full_result['max_drawdown'],
                        'win_rate': full_result['win_rate'],
                        'total_trades': full_result['total_trades'],
                        'final_value': full_result['final_value']
                    },
                    'portfolio_id': full_result.get('portfolio_id', None)
                }
                
                logger.info(f"[OK] {method_name} 测试完成")
                logger.info(f"   总收益率: {full_result['total_return']:.2%}")
                logger.info(f"   年化收益率: {full_result['cagr']:.2%}")
                logger.info(f"   夏普比率: {full_result['sharpe_ratio']:.3f}")
                logger.info(f"   最大回撤: {full_result['max_drawdown']:.2%}")
                
            except Exception as e:
                logger.error(f"方法 {method_name} 测试失败: {str(e)}")
                results[method] = {
                    'method_name': method_name,
                    'error': str(e),
                    'performance_metrics': None
                }
        
        # 找出最优组合
        valid_results = {k: v for k, v in results.items() if 'error' not in v}
        
        if not valid_results:
            raise ValueError("所有优化方法都失败了！")
        
        # 根据不同标准找出最佳方法
        best_by_sharpe = max(valid_results.items(), key=lambda x: x[1]['performance_metrics']['sharpe_ratio'])
        best_by_return = max(valid_results.items(), key=lambda x: x[1]['performance_metrics']['total_return'])
        best_by_cagr = max(valid_results.items(), key=lambda x: x[1]['performance_metrics']['cagr'])
        min_drawdown = min(valid_results.items(), key=lambda x: abs(x[1]['performance_metrics']['max_drawdown']))
        
        # 计算综合评分
        def calculate_composite_score(metrics):
            return (
                metrics['cagr'] * 0.3 +
                metrics['sharpe_ratio'] * 0.1 * 0.3 +
                (1 - abs(metrics['max_drawdown'])) * 0.25 +
                metrics['win_rate'] * 0.15
            )
        
        best_composite = max(valid_results.items(), 
                           key=lambda x: calculate_composite_score(x[1]['performance_metrics']))
        
        optimization_summary = {
            'config_info': experiment_info,
            'test_results': results,
            'best_methods': {
                'sharpe_ratio': best_by_sharpe,
                'total_return': best_by_return,
                'cagr': best_by_cagr,
                'min_drawdown': min_drawdown,
                'composite_score': best_composite
            },
            'recommended_method': best_composite[0],
            'recommended_portfolio': best_composite[1]['portfolio_result'],
            'test_parameters': {
                'start_date': start_date,
                'end_date': end_date,
                'initial_capital': initial_capital,
                'lookback_days': lookback_days,
                'min_weight': min_weight,
                'max_weight': max_weight
            }
        }
        
        logger.info(f"\n=== 🏆 最优化结果总结 ===")
        logger.info(f"推荐方法: {best_composite[1]['method_name']} (综合评分最高)")
        logger.info(f"最高夏普比率: {best_by_sharpe[1]['method_name']} ({best_by_sharpe[1]['performance_metrics']['sharpe_ratio']:.3f})")
        logger.info(f"最高总收益率: {best_by_return[1]['method_name']} ({best_by_return[1]['performance_metrics']['total_return']:.2%})")
        logger.info(f"最高年化收益: {best_by_cagr[1]['method_name']} ({best_by_cagr[1]['performance_metrics']['cagr']:.2%})")
        logger.info(f"最小回撤: {min_drawdown[1]['method_name']} ({min_drawdown[1]['performance_metrics']['max_drawdown']:.2%})")
        
        return optimization_summary
    
    def _multi_objective_optimization(self, scores_df: pd.DataFrame, 
                                    selected_tickers: List[str],
                                    min_weight: float, max_weight: float) -> pd.Series:
        """
        多目标优化函数
        优化目标：
        1. 利润最大化 (Profit maximization)
        2. 回撤最小化 (Drawdown minimization) 
        3. 夏普比率最大化 (Sharpe ratio maximization)
        4. 胜率最大化 (Win rate maximization)
        """
        n_stocks = len(selected_tickers)
        
        if len(scores_df) == 0:
            logger.warning("没有足够的评分数据，使用等权重")
            return pd.Series(1/n_stocks, index=selected_tickers)
        
        # 标准化指标到[0,1]区间
        def normalize_metric(series, higher_better=True):
            if series.std() == 0 or len(series) == 0:
                return pd.Series(0.5, index=series.index)
            if higher_better:
                normalized = (series - series.min()) / (series.max() - series.min())
            else:
                normalized = 1 - (series - series.min()) / (series.max() - series.min())
            return normalized.fillna(0.5)
        
        # 为每只股票计算标准化指标
        metrics_by_ticker = {}
        for ticker in selected_tickers:
            ticker_data = scores_df[scores_df['ticker'] == ticker]
            if len(ticker_data) > 0:
                row = ticker_data.iloc[0]
                metrics_by_ticker[ticker] = {
                    'total_profit_loss': row.get('total_profit_loss', 0),
                    'win_rate': row.get('win_rate', 0),
                    'average_profit_loss': row.get('average_profit_loss', 0),
                    'composite_score': row.get('composite_score', 0),
                    'price_volatility': row.get('price_volatility', 0)
                }
            else:
                metrics_by_ticker[ticker] = {
                    'total_profit_loss': 0, 'win_rate': 0, 'average_profit_loss': 0, 
                    'composite_score': 0, 'price_volatility': 0
                }
        
        # 转换为DataFrame便于处理
        metrics_df = pd.DataFrame(metrics_by_ticker).T
        
        # 计算标准化评分
        profit_score = normalize_metric(metrics_df['total_profit_loss'], True)
        win_rate_score = normalize_metric(metrics_df['win_rate'], True)
        avg_profit_score = normalize_metric(metrics_df['average_profit_loss'], True)
        
        # 回撤评分：假设volatile程度越高，风险越大
        volatility_score = normalize_metric(metrics_df['price_volatility'], False)  # 波动率越小越好
        
        # 模拟夏普比率评分：平均利润除以波动率
        sharpe_proxy = metrics_df['average_profit_loss'] / (metrics_df['price_volatility'] + 0.01)  # 避免除零
        sharpe_score = normalize_metric(sharpe_proxy, True)
        
        # 综合多目标评分 - 根据您的要求调整权重
        logger.info("多目标优化权重分配:")
        logger.info("  - 利润最大化: 30%")
        logger.info("  - 回撤最小化: 25%") 
        logger.info("  - 夏普比率最大化: 20%")
        logger.info("  - 胜率最大化: 25%")
        
        composite_score = (
            profit_score * 0.30 +      # 利润最大化 30%
            volatility_score * 0.25 +  # 回撤最小化（用波动率代理） 25%
            sharpe_score * 0.20 +      # 夏普比率最大化 20%
            win_rate_score * 0.25      # 胜率最大化 25%
        )
        
        # 使用CVXPY进行约束优化
        try:
            weights = cp.Variable(n_stocks)
            
            # 目标函数：最大化综合评分
            objective = cp.Maximize(weights @ composite_score.values)
            
            # 约束条件
            constraints = [
                cp.sum(weights) == 1,      # 权重和为1
                weights >= min_weight,     # 最小权重
                weights <= max_weight      # 最大权重
            ]
            
            # 求解优化问题
            problem = cp.Problem(objective, constraints)
            problem.solve()
            
            if weights.value is not None and not np.isnan(weights.value).any():
                optimized_weights = pd.Series(weights.value, index=selected_tickers)
                # 确保权重和为1
                optimized_weights = optimized_weights / optimized_weights.sum()
                
                logger.info("多目标优化成功完成!")
                return optimized_weights
            else:
                logger.warning("CVXPY优化失败，使用基于评分的权重分配")
                return self._score_based_weights(composite_score, selected_tickers, min_weight, max_weight)
                
        except Exception as e:
            logger.warning(f"优化过程出错: {e}，使用基于评分的权重分配")
            return self._score_based_weights(composite_score, selected_tickers, min_weight, max_weight)
    
    def _score_based_weights(self, scores: pd.Series, tickers: List[str], 
                           min_weight: float, max_weight: float) -> pd.Series:
        """基于评分的权重分配（备用方法）"""
        scores_positive = scores.clip(lower=0)
        if scores_positive.sum() > 0:
            weights = scores_positive / scores_positive.sum()
        else:
            weights = pd.Series(1/len(tickers), index=tickers)
        
        # 应用权重约束
        weights = weights.clip(lower=min_weight, upper=max_weight)
        weights = weights / weights.sum()  # 重新标准化
        
        return weights
    
    def backtest_and_analyze(self, portfolio_result: Dict, 
                           start_date: str, end_date: str,
                           initial_capital: float = 1000000,
                           save_to_db: bool = True,
                           portfolio_name: str = None) -> Dict:
        """
        回测并分析组合表现
        
        Parameters:
        -----------
        portfolio_result : Dict
            组合构建结果
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        initial_capital : float
            初始资金
        save_to_db : bool
            是否保存到数据库
        portfolio_name : str
            投资组合名称（用于数据库保存）
            
        Returns:
        --------
        Dict
            完整的分析结果
        """
        # 设置初始资金
        self.backtester.initial_capital = initial_capital
        
        # 回测
        backtest_result = self.backtester.backtest_portfolio(
            selected_tickers=portfolio_result['selected_tickers'],
            weights=portfolio_result['weights'],
            start_date=start_date,
            end_date=end_date
        )
        
        # 合并结果
        full_result = {
            **portfolio_result,
            **backtest_result
        }
        
        # 保存到数据库（如果启用）
        if save_to_db and self.portfolio_db:
            try:
                if portfolio_name is None:
                    method = portfolio_result.get('weight_method', 'unknown')
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    portfolio_name = f"Portfolio_{method}_{timestamp}"
                
                # 保存到数据库
                portfolio_id = self.portfolio_db.save_portfolio(
                    portfolio_result=full_result,
                    name=portfolio_name,
                    description=f"Backtest: {start_date} to {end_date}, Method: {portfolio_result.get('weight_method', 'unknown')}",
                    set_active=True
                )
                
                full_result['portfolio_id'] = portfolio_id
                full_result['saved_to_db'] = True
                
                logger.info(f"Portfolio saved to database with ID: {portfolio_id}")
                
            except Exception as e:
                logger.error(f"Failed to save portfolio to database: {e}")
                full_result['saved_to_db'] = False
        else:
            full_result['saved_to_db'] = False
        
        return full_result
    
    def plot_portfolio_analysis(self, full_result: Dict):
        """
        绘制组合分析图表
        
        Parameters:
        -----------
        full_result : Dict
            完整的分析结果
        """
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 构建详细的标题信息
        method = full_result.get('weight_method', 'Unknown')
        n_stocks = len(full_result.get('selected_tickers', []))
        start_date = full_result.get('start_date', 'N/A')
        end_date = full_result.get('end_date', 'N/A')
        total_return = full_result.get('total_return', 0)
        sharpe_ratio = full_result.get('sharpe_ratio', 0)
        max_drawdown = full_result.get('max_drawdown', 0)
        cagr = full_result.get('cagr', 0)
        total_trades = full_result.get('total_trades', 0)
        
        # 设置详细的 figure 标题
        title = (f"信号驱动组合分析 | 方法: {method} | 股票数: {n_stocks} | "
                f"期间: {start_date} ~ {end_date}\n"
                f"总收益: {total_return:.2%} | CAGR: {cagr:.2%} | "
                f"夏普比率: {sharpe_ratio:.3f} | 最大回撤: {max_drawdown:.2%} | "
                f"交易次数: {total_trades}")
        
        fig.suptitle(title, fontsize=14, y=0.98)
        
        # 1. 权重分布饼图
        weights = full_result['weights']
        axes[0, 0].pie(weights.values, labels=weights.index, autopct='%1.1f%%')
        axes[0, 0].set_title('Portfolio Weights Distribution')
        
        # 2. 权重条形图
        weights.plot(kind='bar', ax=axes[0, 1])
        axes[0, 1].set_title('Portfolio Weights')
        axes[0, 1].set_ylabel('Weight')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 3. 累积收益曲线
        daily_values = full_result['daily_values']
        cumulative_returns = daily_values['total_value'] / daily_values['total_value'].iloc[0]
        axes[0, 2].plot(cumulative_returns.index, cumulative_returns.values)
        axes[0, 2].set_title('Cumulative Portfolio Value')
        axes[0, 2].set_ylabel('Value Multiple')
        axes[0, 2].grid(True)
        
        # 4. 现金vs持仓价值
        axes[1, 0].plot(daily_values.index, daily_values['cash'], label='Cash', alpha=0.7)
        axes[1, 0].plot(daily_values.index, daily_values['positions_value'], label='Positions', alpha=0.7)
        axes[1, 0].set_title('Cash vs Positions Value')
        axes[1, 0].set_ylabel('Value')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
        
        # 5. 回撤图
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        axes[1, 1].fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
        axes[1, 1].set_title(f"Drawdown (Max: {drawdown.min():.2%})")
        axes[1, 1].set_ylabel('Drawdown')
        axes[1, 1].grid(True)
        
        # 6. 交易记录统计
        if len(full_result['trade_log']) > 0:
            trade_log = full_result['trade_log']
            monthly_trades = trade_log.groupby(trade_log['date'].dt.to_period('M')).size()
            monthly_trades.plot(kind='bar', ax=axes[1, 2])
            axes[1, 2].set_title('Monthly Trading Activity')
            axes[1, 2].set_ylabel('Number of Trades')
            axes[1, 2].tick_params(axis='x', rotation=45)
        else:
            axes[1, 2].text(0.5, 0.5, 'No trades executed', 
                           ha='center', va='center', transform=axes[1, 2].transAxes)
            axes[1, 2].set_title('Trading Activity')
        
        plt.tight_layout(rect=[0, 0, 1, 0.94])  # 为顶部标题留出空间
        plt.show(block=False)  # 不阻塞后续代码执行
        plt.pause(0.1)  # 短暂暂停确保图形显示
        
        # 保持图形窗口打开
        plt.ioff()  # 关闭交互模式，防止图形自动关闭
        plt.ion()   # 重新开启交互模式，但保持窗口
    
    def generate_browser_report(self, optimization_summary: Dict, 
                              save_path: str = None, auto_open: bool = True) -> str:
        """
        生成浏览器端的投资组合优化报告
        
        Parameters:
        -----------
        optimization_summary : Dict
            优化结果总结
        save_path : str
            保存路径，如果为None则使用临时文件
        auto_open : bool
            是否自动在浏览器中打开
            
        Returns:
        --------
        str
            HTML文件路径
        """
        # 创建子图
        fig = sp.make_subplots(
            rows=3, cols=3,
            subplot_titles=(
                '各方法收益率对比', '各方法夏普比率对比', '各方法最大回撤对比',
                '推荐组合权重分布', '推荐组合累积收益', '推荐组合回撤分析',
                '各方法详细指标', '月度交易活动', '风险收益散点图'
            ),
            specs=[
                [{"type": "bar"}, {"type": "bar"}, {"type": "bar"}],
                [{"type": "pie"}, {"type": "scatter"}, {"type": "scatter"}],
                [{"type": "table"}, {"type": "bar"}, {"type": "scatter"}]
            ]
        )
        
        # 获取数据
        config_info = optimization_summary['config_info']
        test_results = optimization_summary['test_results']
        best_methods = optimization_summary['best_methods']
        recommended_portfolio = optimization_summary['recommended_portfolio']
        
        # 准备对比数据
        methods = []
        returns = []
        sharpes = []
        drawdowns = []
        cagrs = []
        volatilities = []
        
        for method, result in test_results.items():
            if 'error' not in result:
                methods.append(result['method_name'])
                metrics = result['performance_metrics']
                returns.append(metrics['total_return'] * 100)
                sharpes.append(metrics['sharpe_ratio'])
                drawdowns.append(abs(metrics['max_drawdown']) * 100)
                cagrs.append(metrics['cagr'] * 100)
                volatilities.append(metrics['volatility'] * 100)
        
        # 1. 收益率对比
        fig.add_trace(
            go.Bar(x=methods, y=returns, name='总收益率 (%)', 
                   marker_color='lightblue'),
            row=1, col=1
        )
        
        # 2. 夏普比率对比
        fig.add_trace(
            go.Bar(x=methods, y=sharpes, name='夏普比率',
                   marker_color='lightgreen'),
            row=1, col=2
        )
        
        # 3. 最大回撤对比
        fig.add_trace(
            go.Bar(x=methods, y=drawdowns, name='最大回撤 (%)',
                   marker_color='lightcoral'),
            row=1, col=3
        )
        
        # 4. 推荐组合权重分布
        weights = recommended_portfolio['weights']
        # 只显示前10大权重
        top_weights = weights.nlargest(10)
        fig.add_trace(
            go.Pie(labels=top_weights.index, values=top_weights.values,
                   name="权重分布"),
            row=2, col=1
        )
        
        # 5. 推荐组合累积收益
        daily_values = recommended_portfolio['daily_values']
        cumulative_returns = daily_values['total_value'] / daily_values['total_value'].iloc[0]
        fig.add_trace(
            go.Scatter(x=cumulative_returns.index, y=cumulative_returns.values,
                      mode='lines', name='累积收益', line=dict(color='blue')),
            row=2, col=2
        )
        
        # 6. 推荐组合回撤分析
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        fig.add_trace(
            go.Scatter(x=drawdown.index, y=drawdown.values,
                      fill='tonexty', mode='lines', name='回撤',
                      line=dict(color='red'), fillcolor='rgba(255,0,0,0.3)'),
            row=2, col=3
        )
        
        # 7. 详细指标表格
        table_data = []
        for i, method in enumerate(methods):
            table_data.append([
                method,
                f"{returns[i]:.2f}%",
                f"{cagrs[i]:.2f}%",
                f"{sharpes[i]:.3f}",
                f"{drawdowns[i]:.2f}%",
                f"{volatilities[i]:.2f}%"
            ])
        
        fig.add_trace(
            go.Table(
                header=dict(values=['方法', '总收益率', '年化收益率', '夏普比率', '最大回撤', '波动率'],
                          fill_color='lightblue'),
                cells=dict(values=list(zip(*table_data)),
                          fill_color='white')
            ),
            row=3, col=1
        )
        
        # 8. 月度交易活动
        if len(recommended_portfolio['trade_log']) > 0:
            trade_log = recommended_portfolio['trade_log']
            monthly_trades = trade_log.groupby(trade_log['date'].dt.to_period('M')).size()
            fig.add_trace(
                go.Bar(x=[str(period) for period in monthly_trades.index], 
                      y=monthly_trades.values, name='月度交易次数',
                      marker_color='orange'),
                row=3, col=2
            )
        
        # 9. 风险收益散点图
        fig.add_trace(
            go.Scatter(x=volatilities, y=cagrs,
                      mode='markers+text', text=methods,
                      textposition="top center",
                      marker=dict(size=10, color=sharpes, 
                                colorscale='Viridis', showscale=True,
                                colorbar=dict(title="夏普比率")),
                      name='风险收益'),
            row=3, col=3
        )
        
        # 更新布局
        title_text = f"""
        <b>投资组合优化结果分析报告</b><br>
        <sup>配置实验: {config_info['experiment_name']} | 
        优化日期: {config_info['optimization_date']} | 
        推荐方法: {optimization_summary['recommended_method']}</sup>
        """
        
        fig.update_layout(
            title_text=title_text,
            height=1200,
            showlegend=False,
            template="plotly_white"
        )
        
        # 更新子图标题
        fig.update_xaxes(title_text="方法", row=1, col=1)
        fig.update_yaxes(title_text="总收益率 (%)", row=1, col=1)
        
        fig.update_xaxes(title_text="方法", row=1, col=2)
        fig.update_yaxes(title_text="夏普比率", row=1, col=2)
        
        fig.update_xaxes(title_text="方法", row=1, col=3)
        fig.update_yaxes(title_text="最大回撤 (%)", row=1, col=3)
        
        fig.update_xaxes(title_text="日期", row=2, col=2)
        fig.update_yaxes(title_text="累积收益倍数", row=2, col=2)
        
        fig.update_xaxes(title_text="日期", row=2, col=3)
        fig.update_yaxes(title_text="回撤", row=2, col=3)
        
        fig.update_xaxes(title_text="月份", row=3, col=2)
        fig.update_yaxes(title_text="交易次数", row=3, col=2)
        
        fig.update_xaxes(title_text="波动率 (%)", row=3, col=3)
        fig.update_yaxes(title_text="年化收益率 (%)", row=3, col=3)
        
        # 生成HTML
        if save_path is None:
            # 使用临时文件
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = os.path.join(temp_dir, f'portfolio_optimization_report_{timestamp}.html')
        
        # 保存HTML文件
        plot(fig, filename=save_path, auto_open=auto_open, include_plotlyjs=True)
        
        logger.info(f"浏览器报告已生成: {save_path}")
        if auto_open:
            logger.info("报告将在默认浏览器中自动打开")
        
        return save_path


def parse_arguments():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(
        description="信号驱动投资组合优化系统 - 基于交易信号的投资组合构建和回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python hlm5_portfolio_signal_driven.py                                    # 使用默认参数运行
  python hlm5_portfolio_signal_driven.py --compare                         # 运行对比测试
  python hlm5_portfolio_signal_driven.py --config-file my_config.json      # 使用指定配置文件
  python hlm5_portfolio_signal_driven.py --help-examples                   # 查看详细示例
        """
    )
    
    # 配置文件参数
    parser.add_argument(
        '--config-file', '-c',
        type=str,
        default='hlm5_stock_final_optimized_config.json',
        help='股票优化配置文件路径 (默认: hlm5_stock_final_optimized_config.json)'
    )
    
    # 投资组合参数
    parser.add_argument(
        '--weight-method', '-w',
        type=str,
        choices=['config_weighted', 'equal_weight', 'profit_weighted', 'multi_objective_optimized', 'score_weighted', 'enhanced_top_performers'],
        default='score_weighted',
        help='权重分配方法 (默认: score_weighted，标准模式推荐)'
    )
    
    parser.add_argument(
        '--initial-capital', '-capital',
        type=float,
        default=1000000,
        help='初始资金 (默认: 1000000)'
    )
    
    parser.add_argument(
        '--start-date', '-start',
        type=str,
        default='2023-01-01',
        help='回测开始日期 (格式: YYYY-MM-DD, 默认: 2023-01-01)'
    )
    
    parser.add_argument(
        '--end-date', '-end',
        type=str,
        default='2024-12-31',
        help='回测结束日期 (格式: YYYY-MM-DD, 默认: 2024-12-31)'
    )
    
    parser.add_argument(
        '--lookback-days', '-lookback',
        type=int,
        default=252,
        help='评分计算的回望天数 (默认: 252)'
    )
    
    parser.add_argument(
        '--n-stocks', '-n',
        type=int,
        default=15,
        help='选择的股票数量 (默认: 15)'
    )
    
    # 权重约束
    parser.add_argument(
        '--min-weight',
        type=float,
        default=0.02,
        help='单个股票最小权重 (默认: 0.02)'
    )
    
    parser.add_argument(
        '--max-weight',
        type=float,
        default=0.20,
        help='单个股票最大权重 (默认: 0.20)'
    )
    
    # 输出控制
    parser.add_argument(
        '--save-to-db',
        action='store_true',
        default=True,
        help='是否保存结果到数据库 (默认: True)'
    )
    
    parser.add_argument(
        '--portfolio-name',
        type=str,
        help='投资组合名称 (用于数据库保存)'
    )
    
    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='不显示图表'
    )
    
    # 模式选择
    parser.add_argument(
        '--compare',
        action='store_true',
        help='运行多种方法对比测试'
    )
    
    parser.add_argument(
        '--use-config',
        action='store_true',
        help='使用配置文件模式（基于--config-file参数）'
    )
    
    parser.add_argument(
        '--optimize-all',
        action='store_true',
        help='测试配置文件中所有优化方法，找到最优组合'
    )
    
    # 帮助相关
    parser.add_argument(
        '--help-examples',
        action='store_true',
        help='显示详细使用示例'
    )
    
    return parser.parse_args()


def show_help_examples():
    """
    显示详细的使用示例
    """
    examples = """
=== 信号驱动投资组合优化系统 - 详细使用示例 ===

1. 基础用法 - 使用默认参数运行标准流程 (默认选择15只股票):
   python hlm5_portfolio_signal_driven.py

2. 🆕 指定股票数量 - 选择top20股票进行投资组合优化:
   python hlm5_portfolio_signal_driven.py --n-stocks 20

3. 使用配置文件 - 基于股票优化结果文件构建投资组合:
   python hlm5_portfolio_signal_driven.py --use-config --config-file hlm5_stock_final_optimized_config.json
   
4. 指定不同的配置文件:
   python hlm5_portfolio_signal_driven.py --use-config --config-file hlm5_stock_final_optimized_config-50.json

5. 🆕 标准模式 - 自定义股票数量和权重方法:
   # 选择20只股票，使用利润加权方法
   python hlm5_portfolio_signal_driven.py --n-stocks 20 --weight-method profit_weighted
   
   # 选择10只股票，使用多目标优化
   python hlm5_portfolio_signal_driven.py --n-stocks 10 --weight-method multi_objective_optimized
   
   # 选择25只股票，使用增强版顶级表现者选择
   python hlm5_portfolio_signal_driven.py --n-stocks 25 --weight-method enhanced_top_performers

6. 使用不同的权重方法:
   # 配置文件年化收益率加权
   python hlm5_portfolio_signal_driven.py --use-config --weight-method config_weighted
   
   # 等权重
   python hlm5_portfolio_signal_driven.py --use-config --weight-method equal_weight
   
   # 利润加权
   python hlm5_portfolio_signal_driven.py --use-config --weight-method profit_weighted
   
   # 多目标优化
   python hlm5_portfolio_signal_driven.py --use-config --weight-method multi_objective_optimized

7. 自定义回测参数:
   python hlm5_portfolio_signal_driven.py --use-config \\
       --start-date 2022-01-01 --end-date 2024-12-31 \\
       --initial-capital 5000000 \\
       --lookback-days 365

8. 权重约束控制:
   python hlm5_portfolio_signal_driven.py --use-config \\
       --min-weight 0.01 --max-weight 0.15 \\
       --weight-method multi_objective_optimized

9. 指定投资组合名称并保存到数据库:
   python hlm5_portfolio_signal_driven.py --use-config \\
       --portfolio-name "My_Config_Portfolio_2024" \\
       --config-file hlm5_stock_final_optimized_config-50.json

10. 运行多种方法对比测试:
    python hlm5_portfolio_signal_driven.py --compare

11. 🆕 测试配置文件中所有优化方法并找到最优组合（推荐！）:
    python hlm5_portfolio_signal_driven.py --optimize-all --config-file hlm5_stock_final_optimized_config-50.json

12. 不显示图表的批量运行:
    python hlm5_portfolio_signal_driven.py --use-config --no-plot

13. 🆕 全方法优化 + 自定义参数 + 浏览器报告:
    python hlm5_portfolio_signal_driven.py --optimize-all \\
        --config-file hlm5_stock_final_optimized_config-50.json \\
        --start-date 2023-01-01 --end-date 2024-12-31 \\
        --initial-capital 2000000 \\
        --min-weight 0.01 --max-weight 0.15

14. 🆕 增强版top20股票选择（推荐用于从数据库直接选股）:
    python hlm5_portfolio_signal_driven.py \\
        --n-stocks 20 --weight-method enhanced_top_performers \\
        --start-date 2023-01-01 --end-date 2024-12-31 \\
        --initial-capital 2000000 \\
        --min-weight 0.02 --max-weight 0.15 \\
        --portfolio-name "Enhanced_Top20_Portfolio_2024"

15. 完整高级示例 - 使用52股票配置文件进行多目标优化:
    python hlm5_portfolio_signal_driven.py --use-config \\
        --config-file hlm5_stock_final_optimized_config-50.json \\
        --weight-method multi_objective_optimized \\
        --start-date 2022-06-01 --end-date 2024-12-31 \\
        --initial-capital 2000000 \\
        --min-weight 0.015 --max-weight 0.12 \\
        --portfolio-name "Multi_Objective_52_Stocks_2024" \\
        --lookback-days 300

=== 🔥 最新验证的单一方法命令（基于最新测试结果）===

16. 🥇 历史盈利加权方法（最高收益 269.04%）:
    python hlm5_portfolio_signal_driven.py --n-stocks 10 --weight-method profit_weighted --start-date 2023-01-01 --end-date 2024-12-31

17. 🥇 综合评分加权方法（最高夏普比率 2.790）:
    python hlm5_portfolio_signal_driven.py --n-stocks 10 --weight-method score_weighted --start-date 2023-01-01 --end-date 2024-12-31

18. 等权重方法（稳健收益 174.42%）:
    python hlm5_portfolio_signal_driven.py --n-stocks 10 --weight-method equal_weight --start-date 2023-01-01 --end-date 2024-12-31

19. 多目标优化方法（平衡风险 156.53%）:
    python hlm5_portfolio_signal_driven.py --n-stocks 10 --weight-method multi_objective_optimized --start-date 2023-01-01 --end-date 2024-12-31

=== 🚀 一次性运行所有方法对比测试（强烈推荐）===

20. 🔥 一次性运行所有投资组合优化方法对比（自动选择20只股票）:
    python hlm5_portfolio_signal_driven.py --compare --start-date 2023-01-01 --end-date 2024-12-31 --no-plot

21. 🔥 显示图表版本的对比测试:
    python hlm5_portfolio_signal_driven.py --compare --start-date 2023-01-01 --end-date 2024-12-31

22. 🔥 自定义时间范围的对比测试（使用约3年数据）:
    python hlm5_portfolio_signal_driven.py --compare --start-date 2022-01-01 --end-date 2024-12-31

=== 📊 实际测试结果参考（可复现） ===

基于最新测试（10只股票，2023-2024年）:
• 历史盈利加权: 269.04%总收益, 92.02%年化, 2.742夏普, -7.89%回撤
• 综合评分加权: 232.78%总收益, 82.35%年化, 2.790夏普, -7.73%回撤  
• 等权重方法: 174.42%总收益, 65.60%年化, 2.598夏普, -9.14%回撤
• 多目标优化: 156.53%总收益, 60.12%年化, 2.226夏普, -11.45%回撤

基于对比测试（20只股票，2022-2024年）:
• 利润加权: 263.08%总收益, 55.55%年化, 2.573夏普, -7.28%回撤
• 评分加权: 227.66%总收益, 50.18%年化, 2.596夏普, -8.06%回撤
• 等权重: 175.97%总收益, 41.60%年化, 2.416夏普, -8.95%回撤
• 多目标优化: 164.15%总收益, 39.49%年化, 2.186夏普, -8.81%回撤

=== 权重方法说明 ===
- config_weighted: 基于配置文件中的年化收益率加权（推荐用于配置文件模式）
- equal_weight: 等权重分配
- profit_weighted: 基于历史交易盈利加权
- multi_objective_optimized: 多目标优化（利润最大化+回撤最小化+夏普比率最大化+胜率最大化）
- score_weighted: 基于综合评分加权（推荐用于标准模式）
- enhanced_top_performers: 🆕 增强版顶级表现者选择（可配置权重的综合表现评分）

=== 配置文件说明 ===
程序支持读取 hlm5_stock_optimize.py 生成的优化结果文件，包含：
- selected_stocks: 优化选择的股票列表
- stock_rankings: 股票评分和表现指标
- technical_indicators: 技术指标参数
- trading_parameters: 交易参数
- portfolio_performance: 组合表现预期

=== 输出说明 ===
- 投资组合权重分配
- 回测表现指标（总收益率、年化收益率、夏普比率、最大回撤等）
- 交易记录分析
- 可视化图表（如不使用 --no-plot）
- 数据库保存结果（portfolio.db）

=== 文件要求 ===
- 配置文件: JSON格式，包含股票列表和优化参数
- 数据库: trading_signals.db（交易信号数据）
- 数据库: portfolio.db（投资组合结果保存）
    """
    print(examples)


def run_config_based_portfolio(args):
    """
    运行基于配置文件的投资组合优化
    
    Parameters:
    -----------
    args : argparse.Namespace
        命令行参数
    """
    print(f"=== 基于配置文件的投资组合优化 ===")
    print(f"配置文件: {args.config_file}")
    print(f"权重方法: {args.weight_method}")
    print(f"回测期间: {args.start_date} ~ {args.end_date}")
    print(f"初始资金: ¥{args.initial_capital:,.0f}")
    print()
    
    # 检查配置文件是否存在
    if not os.path.exists(args.config_file):
        logger.error(f"配置文件不存在: {args.config_file}")
        return False
    
    # 初始化数据管理器
    data_manager = TradingDataManager()
    
    try:
        # 加载配置文件
        config_loader = ConfigFileLoader(args.config_file)
        
        # 创建组合构建器
        portfolio_builder = PortfolioBuilder(data_manager)
        
        # 基于配置文件构建组合
        portfolio_result = portfolio_builder.build_portfolio_from_config(
            config_loader=config_loader,
            weight_method=args.weight_method,
            lookback_days=args.lookback_days,
            min_weight=args.min_weight,
            max_weight=args.max_weight
        )
        
        # 回测组合
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        portfolio_name = args.portfolio_name or f"Config_Portfolio_{args.weight_method}_{timestamp}"
        
        full_result = portfolio_builder.backtest_and_analyze(
            portfolio_result=portfolio_result,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            save_to_db=args.save_to_db,
            portfolio_name=portfolio_name
        )
        
        # 显示结果摘要
        print(f"\n=== 投资组合表现摘要 ===")
        print(f"实验名称: {full_result['config_info']['experiment_name']}")
        print(f"配置优化日期: {full_result['config_info']['optimization_date']}")
        print(f"配置最佳得分: {full_result['config_info']['best_score']}")
        print(f"选择股票数量: {len(full_result['selected_tickers'])}")
        print(f"权重方法: {args.weight_method}")
        print()
        print(f"回测表现:")
        print(f"  总收益率: {full_result['total_return']:.2%}")
        print(f"  年化收益率: {full_result['cagr']:.2%}")
        print(f"  波动率: {full_result['volatility']:.2%}")
        print(f"  夏普比率: {full_result['sharpe_ratio']:.3f}")
        print(f"  最大回撤: {full_result['max_drawdown']:.2%}")
        print(f"  交易次数: {full_result['total_trades']}")
        print(f"  最终价值: ¥{full_result['final_value']:,.0f}")
        
        if full_result.get('saved_to_db'):
            print(f"  💾 已保存到数据库，ID: {full_result.get('portfolio_id')}")
        
        # 显示权重分配
        print(f"\n=== 权重分配 ===")
        for ticker, weight in full_result['weights'].items():
            print(f"  {ticker}: {weight:.2%}")
        
        # 绘制分析图表（如果需要）
        if not args.no_plot:
            portfolio_builder.plot_portfolio_analysis(full_result)
            print("\n📊 投资组合分析图表已生成")
            
            # 等待用户查看图表
            import matplotlib.pyplot as plt
            print("请查看图表，完成后按 Enter 键继续...")
            input()
            plt.close('all')
        
        return True
        
    except Exception as e:
        logger.error(f"配置文件模式运行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        data_manager.close()


def run_all_optimization_methods(args):
    """
    运行基于配置文件的所有优化方法测试
    
    Parameters:
    -----------
    args : argparse.Namespace
        命令行参数
    """
    print(f"=== 基于配置文件的全方法投资组合优化 ===")
    print(f"配置文件: {args.config_file}")
    print(f"回测期间: {args.start_date} ~ {args.end_date}")
    print(f"初始资金: ¥{args.initial_capital:,.0f}")
    print(f"权重约束: {args.min_weight:.2%} ~ {args.max_weight:.2%}")
    print()
    
    # 检查配置文件是否存在
    if not os.path.exists(args.config_file):
        logger.error(f"配置文件不存在: {args.config_file}")
        return False
    
    # 初始化数据管理器
    data_manager = TradingDataManager()
    
    try:
        # 加载配置文件
        config_loader = ConfigFileLoader(args.config_file)
        
        # 创建组合构建器
        portfolio_builder = PortfolioBuilder(data_manager)
        
        # 运行所有优化方法
        optimization_summary = portfolio_builder.optimize_portfolio_from_config(
            config_loader=config_loader,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            lookback_days=args.lookback_days,
            min_weight=args.min_weight,
            max_weight=args.max_weight,
            save_to_db=args.save_to_db
        )
        
        # 显示详细结果
        print(f"\n=== 📊 全方法优化结果总结 ===")
        config_info = optimization_summary['config_info']
        test_results = optimization_summary['test_results']
        best_methods = optimization_summary['best_methods']
        
        print(f"配置实验: {config_info['experiment_name']}")
        print(f"优化日期: {config_info['optimization_date']}")
        print(f"配置得分: {config_info['best_score']}")
        print(f"测试期间: {args.start_date} ~ {args.end_date}")
        print()
        
        # 对比表格
        print("=" * 120)
        print(f"{'方法':<20} {'总收益率':<12} {'年化收益':<12} {'波动率':<10} {'夏普比率':<10} {'最大回撤':<10} {'胜率':<8} {'交易次数':<8} {'最终价值':<12}")
        print("=" * 120)
        
        for method, result in test_results.items():
            if 'error' not in result:
                metrics = result['performance_metrics']
                print(f"{result['method_name']:<20} {metrics['total_return']:<12.2%} {metrics['cagr']:<12.2%} {metrics['volatility']:<10.2%} {metrics['sharpe_ratio']:<10.2f} {metrics['max_drawdown']:<10.2%} {metrics['win_rate']:<8.2%} {metrics['total_trades']:<8} ¥{metrics['final_value']:<11,.0f}")
            else:
                print(f"{result['method_name']:<20} {'ERROR':<12} {'N/A':<12} {'N/A':<10} {'N/A':<10} {'N/A':<10} {'N/A':<8} {'N/A':<8} {'N/A':<12}")
        
        print("=" * 120)
        
        # 最佳方法总结
        print(f"\n=== 🏆 各指标最佳方法 ===")
        print(f"🥇 最高夏普比率: {best_methods['sharpe_ratio'][1]['method_name']} ({best_methods['sharpe_ratio'][1]['performance_metrics']['sharpe_ratio']:.3f})")
        print(f"🥇 最高总收益率: {best_methods['total_return'][1]['method_name']} ({best_methods['total_return'][1]['performance_metrics']['total_return']:.2%})")
        print(f"🥇 最高年化收益: {best_methods['cagr'][1]['method_name']} ({best_methods['cagr'][1]['performance_metrics']['cagr']:.2%})")
        print(f"🥇 最小回撤: {best_methods['min_drawdown'][1]['method_name']} ({best_methods['min_drawdown'][1]['performance_metrics']['max_drawdown']:.2%})")
        print(f"🏆 综合推荐: {best_methods['composite_score'][1]['method_name']} (综合评分最高)")
        
        # 推荐组合详情
        recommended_portfolio = optimization_summary['recommended_portfolio']
        print(f"\n=== 💡 推荐投资组合详情 ===")
        print(f"推荐方法: {optimization_summary['recommended_method']}")
        print(f"选择股票数量: {len(recommended_portfolio['selected_tickers'])}")
        print(f"总收益率: {recommended_portfolio['total_return']:.2%}")
        print(f"年化收益率: {recommended_portfolio['cagr']:.2%}")
        print(f"夏普比率: {recommended_portfolio['sharpe_ratio']:.3f}")
        print(f"最大回撤: {recommended_portfolio['max_drawdown']:.2%}")
        print(f"交易次数: {recommended_portfolio['total_trades']}")
        print(f"最终价值: ¥{recommended_portfolio['final_value']:,.0f}")
        
        if recommended_portfolio.get('portfolio_id'):
            print(f"💾 已保存到数据库，ID: {recommended_portfolio['portfolio_id']}")
        
        # 显示前10大权重
        print(f"\n=== 📈 推荐组合权重分配 (前10大持仓) ===")
        top_weights = recommended_portfolio['weights'].nlargest(10)
        for ticker, weight in top_weights.items():
            print(f"  {ticker}: {weight:.2%}")
        
        # 生成浏览器报告
        if not args.no_plot:
            print(f"\n📊 正在生成浏览器端优化报告...")
            try:
                report_path = portfolio_builder.generate_browser_report(
                    optimization_summary, auto_open=True
                )
                print(f"✅ 浏览器报告已生成并自动打开: {report_path}")
            except Exception as e:
                logger.error(f"生成浏览器报告失败: {e}")
                print("⚠️ 浏览器报告生成失败，但优化结果仍然有效")
        else:
            print(f"\n🚫 跳过图表生成（--no-plot 参数）")
        
        # 数据库保存统计
        print(f"\n📊 数据库保存统计:")
        saved_count = sum(1 for result in test_results.values() 
                         if 'error' not in result and result.get('portfolio_id'))
        print(f"   💾 成功保存投资组合: {saved_count}/{len(test_results)} 个")
        print(f"   🗃️ 数据库文件: portfolio.db")
        if saved_count > 0:
            print(f"   [OK] 所有优化结果已保存，可供后续分析和交易使用")
        
        return optimization_summary
        
    except Exception as e:
        logger.error(f"所有优化方法测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        data_manager.close()


def compare_optimization_methods(args=None):
    """
    对比不同的组合优化方法 - 增强版本，追求更高收益
    统一保存到portfolio.db数据库，不生成CSV文件
    """
    print("=== 增强版组合优化方法对比测试 ===")
    if args:
        print(f"回测期间: {args.start_date} ~ {args.end_date}")
        print(f"初始资金: ¥{args.initial_capital:,.0f}")
        print("使用命令行参数，确保与其他模式一致性")
    else:
        print("参数优化：更多股票、更长回测期间、更大资金规模")
    print("所有结果统一保存到portfolio.db数据库\n")
    
    # 初始化数据管理器
    data_manager = TradingDataManager()
    
    try:
        # 创建组合构建器 - 使用统一的portfolio.db数据库
        portfolio_builder = PortfolioBuilder(data_manager)
        
        # 测试不同的方法 - 使用更优化的参数
        methods = [
            ('equal_weight', '等权重'),
            ('score_weighted', '评分加权'),
            ('profit_weighted', '利润加权'),
            ('multi_objective_optimized', '多目标优化')
        ]
        
        results = {}
        
        for method, method_name in methods:
            print(f"正在测试 {method_name} 方法...")
            
            # 构建组合 - 优化参数（用于对比测试时使用更多股票）
            if method == 'multi_objective_optimized':
                portfolio_result = portfolio_builder.build_portfolio(
                    n_stocks=20,  # 增加到20只股票用于对比测试
                    weight_method=method,
                    lookback_days=365,  # 增加到365天lookback
                    min_weight=0.02,  # 降低最小权重
                    max_weight=0.20   # 降低最大权重，分散风险
                )
            else:
                portfolio_result = portfolio_builder.build_portfolio(
                    n_stocks=20,  # 增加到20只股票用于对比测试
                    weight_method=method,
                    lookback_days=365  # 增加到365天lookback
                )
            
            # 回测 - 使用更长期间和更大资金，并保存到数据库
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 使用命令行参数或默认值
            start_date = args.start_date if args else '2022-01-01'
            end_date = args.end_date if args else '2024-12-01'
            initial_capital = args.initial_capital if args else 1000000
            
            full_result = portfolio_builder.backtest_and_analyze(
                portfolio_result=portfolio_result,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                save_to_db=True,  # 启用数据库保存
                portfolio_name=f"Comparison_{method}_{timestamp}"
            )
            
            # 生成图表（不阻塞）
            portfolio_builder.plot_portfolio_analysis(full_result)
            
            results[method_name] = {
                'total_return': full_result['total_return'],
                'cagr': full_result['cagr'],
                'volatility': full_result['volatility'],
                'sharpe_ratio': full_result['sharpe_ratio'],
                'max_drawdown': full_result['max_drawdown'],
                'total_trades': full_result['total_trades'],
                'final_value': full_result['final_value'],
                'weights': full_result['weights'],
                'saved_to_db': full_result.get('saved_to_db', False),
                'portfolio_id': full_result.get('portfolio_id', None)
            }
            
            print(f"[OK] {method_name} 测试完成")
            print(f"   总收益率: {full_result['total_return']:.2%}")
            print(f"   年化收益率: {full_result['cagr']:.2%}")
            print(f"   夏普比率: {full_result['sharpe_ratio']:.3f}")
            if full_result.get('saved_to_db'):
                print(f"   💾 已保存到数据库，ID: {full_result.get('portfolio_id')}")
            print()
        
        # 生成对比表格
        print("=== 增强版投资组合表现对比 ===")
        if args:
            print(f"回测期间: {args.start_date} 到 {args.end_date}")
            print(f"初始资金: ¥{args.initial_capital:,.0f}")
        else:
            print(f"回测期间: 2022-01-01 到 2024-12-01 (约3年)")
            print(f"初始资金: ¥1,000,000")
        print(f"股票数量: 20只")
        print("-" * 100)
        print(f"{'方法':<15} {'总收益率':<12} {'年化收益':<12} {'波动率':<10} {'夏普比率':<10} {'最大回撤':<10} {'交易次数':<8} {'最终价值':<12}")
        print("-" * 100)
        
        for method_name, result in results.items():
            print(f"{method_name:<15} {result['total_return']:<12.2%} {result['cagr']:<12.2%} {result['volatility']:<10.2%} {result['sharpe_ratio']:<10.2f} {result['max_drawdown']:<10.2%} {result['total_trades']:<8} ¥{result['final_value']:<11,.0f}")
        
        # 找出最佳方法
        best_sharpe = max(results.items(), key=lambda x: x[1]['sharpe_ratio'])
        best_return = max(results.items(), key=lambda x: x[1]['total_return'])
        min_drawdown = min(results.items(), key=lambda x: abs(x[1]['max_drawdown']))
        
        print(f"\n=== 🏆 最佳表现 ===")
        print(f"🥇 最高夏普比率: {best_sharpe[0]} ({best_sharpe[1]['sharpe_ratio']:.3f})")
        print(f"🥇 最高总收益率: {best_return[0]} ({best_return[1]['total_return']:.2%})")
        print(f"🥇 最小回撤: {min_drawdown[0]} ({min_drawdown[1]['max_drawdown']:.2%})")
        
        # 收益率分析
        print(f"\n=== 💰 收益分析 ===")
        for method_name, result in results.items():
            initial_value = args.initial_capital if args else 1000000
            profit = result['final_value'] - initial_value
            print(f"{method_name}: 绝对收益 ¥{profit:,.0f}, 年化收益率 {result['cagr']:.2%}")
        
        # 权重分配对比（只显示前5大权重）
        print(f"\n=== 📊 主要权重分配 (前5大持仓) ===")
        for method_name, result in results.items():
            print(f"\n{method_name}:")
            sorted_weights = sorted(result['weights'].items(), key=lambda x: x[1], reverse=True)
            for ticker, weight in sorted_weights[:5]:
                print(f"  {ticker}: {weight:.1%}")
        
        # 数据库保存统计
        print(f"\n📊 数据库保存情况:")
        print(f"   🗃️ 数据库文件: {PORTFOLIO_CONFIG['DATABASE_PATH']}")
        saved_count = sum(1 for result in results.values() if result.get('saved_to_db', False))
        print(f"   💾 成功保存投资组合: {saved_count}/{len(results)} 个")
        if saved_count > 0:
            print(f"   [OK] 所有对比结果已保存到统一数据库，可供后续分析和交易使用")
        
        return results
        
    except Exception as e:
        logger.error(f"对比测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        data_manager.close()


def run_standard_portfolio(args):
    """
    运行标准投资组合模式
    
    Parameters:
    -----------
    args : argparse.Namespace
        命令行参数
    """
    print(f"=== 标准投资组合优化 ===")
    print(f"股票数量: {args.n_stocks}")
    print(f"权重方法: {args.weight_method}")
    print(f"回测期间: {args.start_date} ~ {args.end_date}")
    print(f"初始资金: ¥{args.initial_capital:,.0f}")
    print()
    
    # 初始化数据管理器
    data_manager = TradingDataManager()
    
    try:
        # 创建组合构建器
        portfolio_builder = PortfolioBuilder(data_manager)
        
        # 构建组合
        portfolio_result = portfolio_builder.build_portfolio(
            n_stocks=args.n_stocks,
            weight_method=args.weight_method,
            lookback_days=args.lookback_days,
            min_weight=args.min_weight,
            max_weight=args.max_weight
        )
        
        # 回测组合
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        portfolio_name = args.portfolio_name or f"Standard_Portfolio_{args.weight_method}_{timestamp}"
        
        full_result = portfolio_builder.backtest_and_analyze(
            portfolio_result=portfolio_result,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            save_to_db=args.save_to_db,
            portfolio_name=portfolio_name
        )
        
        # 显示结果摘要
        print(f"\n=== 投资组合表现摘要 ===")
        print(f"选择股票数量: {len(full_result['selected_tickers'])}")
        print(f"权重方法: {args.weight_method}")
        print()
        print(f"回测表现:")
        print(f"  总收益率: {full_result['total_return']:.2%}")
        print(f"  年化收益率: {full_result['cagr']:.2%}")
        print(f"  波动率: {full_result['volatility']:.2%}")
        print(f"  夏普比率: {full_result['sharpe_ratio']:.3f}")
        print(f"  最大回撤: {full_result['max_drawdown']:.2%}")
        print(f"  交易次数: {full_result['total_trades']}")
        print(f"  最终价值: ¥{full_result['final_value']:,.0f}")
        
        if full_result.get('saved_to_db'):
            print(f"  💾 已保存到数据库，ID: {full_result.get('portfolio_id')}")
        
        # 显示权重分配
        print(f"\n=== 权重分配 ===")
        for ticker, weight in full_result['weights'].items():
            print(f"  {ticker}: {weight:.2%}")
        
        # 绘制分析图表（如果需要）
        if not args.no_plot:
            portfolio_builder.plot_portfolio_analysis(full_result)
            print("\n📊 投资组合分析图表已生成")
            
            # 等待用户查看图表
            import matplotlib.pyplot as plt
            print("请查看图表，完成后按 Enter 键继续...")
            input()
            plt.close('all')
        
        return True
        
    except Exception as e:
        logger.error(f"标准模式运行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        data_manager.close()


def main():
    """
    主函数，演示信号驱动的组合构建和回测流程
    """
    print("[START] 启动信号驱动投资组合优化系统")
    print(f"配置信息:")
    print(f"  交易信号数据库: {EQUITY_CONFIG['DATABASE_PATH']}")
    print(f"  投资组合数据库: {PORTFOLIO_CONFIG['DATABASE_PATH']}")
    print(f"  最大股票数量: {PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MAX_STOCKS']}")
    print(f"  权重约束: {PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MIN_WEIGHT']:.1%} ~ {PORTFOLIO_CONFIG['OPTIMIZATION_CONSTRAINTS']['MAX_WEIGHT']:.1%}")
    
    # 初始化数据管理器 - 使用配置文件中的路径
    data_manager = TradingDataManager()
    
    try:
        # 创建组合构建器 - 使用配置文件中的portfolio.db路径
        portfolio_builder = PortfolioBuilder(data_manager)
        
        # 构建组合 - 不同的权重方法
        weight_methods = ['equal_weight', 
                          'score_weighted', 
                          'profit_weighted', 
                          'multi_objective_optimized'
                        ]
        
        for method in weight_methods:
            logger.info(f"\n{'='*50}")
            logger.info(f"Building portfolio using {method} weighting")
            logger.info(f"{'='*50}")
            
            # 构建组合
            if method == 'multi_objective_optimized':
                portfolio_result = portfolio_builder.build_portfolio(
                    n_stocks=20,
                    weight_method=method,
                    lookback_days=252,
                    min_weight=0.01,
                    max_weight=0.30
                )
            else:
                portfolio_result = portfolio_builder.build_portfolio(
                    n_stocks=20,  # 减少股票数量，便于管理
                    weight_method=method,
                    lookback_days=252
                )
            
            # 回测组合
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            full_result = portfolio_builder.backtest_and_analyze(
                portfolio_result=portfolio_result,
                start_date='2023-01-01',
                end_date='2024-12-31',
                initial_capital=1000000,
                save_to_db=True,
                portfolio_name=f"Signal_Driven_Portfolio_{method}_{timestamp}"
            )
            
            # 绘制分析图表
            portfolio_builder.plot_portfolio_analysis(full_result)
            
            logger.info(f"Portfolio {method} saved to database with ID: {full_result.get('portfolio_id', 'N/A')}")
    
    finally:
        # 关闭数据库连接
        data_manager.close()


if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()
    
    # 显示详细帮助示例
    if args.help_examples:
        show_help_examples()
        sys.exit(0)
    
    # 根据参数选择运行模式
    if args.compare:
        # 运行对比测试
        print("启动投资组合优化方法对比测试...")
        results = compare_optimization_methods(args)
        if results:
            print("\n[OK] 增强版优化方法对比测试完成!")
            print("所有结果已保存到portfolio.db数据库")
            
            # 等待用户查看图表
            import matplotlib.pyplot as plt
            print("\n📊 所有图表已生成并保持显示状态")
            print("请仔细观察对比各方法的图表，完成后按 Enter 键关闭所有图表...")
            input()
            plt.close('all')
            print("所有图表已关闭。")
        else:
            print("\n[ERROR] 对比测试失败!")
    elif args.use_config:
        # 运行配置文件模式
        print("启动基于配置文件的投资组合优化...")
        success = run_config_based_portfolio(args)
        if success:
            print("\n[OK] 配置文件模式运行完成!")
        else:
            print("\n[ERROR] 配置文件模式运行失败!")
    elif args.optimize_all:
        # 运行所有优化方法
        print("启动所有优化方法测试...")
        results = run_all_optimization_methods(args)
        if results:
            print("\n[OK] 所有优化方法测试完成!")
            print("结果已保存到portfolio.db数据库并在浏览器中显示")
        else:
            print("\n[ERROR] 所有优化方法测试失败!")
    else:
        # 运行标准流程，使用命令行参数
        print("启动标准投资组合构建...")
        success = run_standard_portfolio(args)
        if success:
            print("\n[OK] 标准投资组合构建完成!")
        else:
            print("\n[ERROR] 标准投资组合构建失败!") 