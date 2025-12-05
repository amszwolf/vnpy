import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Union
import threading
from contextlib import contextmanager
import numpy as np
from sqlalchemy import text

class FinScreenerDBManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            # 使用文件数据库
            self.conn_str = 'finscreener.db'  # 改用文件数据库
            self.initialized = True
            self._create_tables()

    @contextmanager
    def get_connection(self):
        """Thread-safe connection manager"""
        connection = sqlite3.connect(
            self.conn_str,
            timeout=30.0,  # 增加超时时间
            isolation_level='IMMEDIATE'  # 提高并发性能
        )
        try:
            # 启用 WAL 模式以提高并发性能
            connection.execute('PRAGMA journal_mode=WAL')
            # 启用外键约束
            connection.execute('PRAGMA foreign_keys=ON')
            yield connection
        finally:
            connection.close()

    def _create_tables(self):
        """Create the finscreener table if it doesn't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS finscreener (
            ticker TEXT PRIMARY KEY,  -- 设置ticker为主键，确保唯一性
            datetime TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            
            -- Surprise Factor fields
            adjusted_net_profit_rate REAL,
            sue_score REAL,
            surprise_factor REAL,
            
            -- Growth Factor fields
            inc_revenue_rate REAL,
            inc_net_profit_rate REAL,
            inc_total_revenue_annual REAL,
            inc_net_profit_to_shareholders_annual REAL,
            growth_factor REAL,
            
            -- Valuation Factor fields
            eps_basic REAL,
            eps_diluted REAL,
            bps REAL,
            current_price REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            valuation_factor REAL,
            
            -- Profit Factor fields
            du_return_on_equity REAL,
            sales_gross_profit REAL,
            gross_profit REAL,
            net_profit REAL,
            profit_factor REAL,
            
            -- Final Score
            total_score REAL,
            
            -- Metadata
            update_datetime TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_datetime ON finscreener(datetime);
        CREATE INDEX IF NOT EXISTS idx_update_datetime ON finscreener(update_datetime);
        CREATE INDEX IF NOT EXISTS idx_total_score ON finscreener(total_score);
        """
        
        with self.get_connection() as conn:
            conn.executescript(create_table_sql)
            conn.commit()

    def cleanup_duplicate_data(self):
        """清理重复的ticker数据，只保留最新的记录"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM finscreener")
            total_before = cursor.fetchone()[0]
            
            # 由于ticker现在是主键，理论上不应该有重复
            # 但如果有临时表或数据不一致，我们可以重建表来确保一致性
            print(f"[数据清理] 当前有 {total_before} 条记录")
            
            # 检查是否有无效数据（ticker为空或NULL）
            cursor = conn.execute("SELECT COUNT(*) FROM finscreener WHERE ticker IS NULL OR ticker = ''")
            invalid_count = cursor.fetchone()[0]
            
            if invalid_count > 0:
                print(f"[数据清理] 发现 {invalid_count} 条无效记录（ticker为空），正在删除...")
                conn.execute("DELETE FROM finscreener WHERE ticker IS NULL OR ticker = ''")
                conn.commit()
                
            cursor = conn.execute("SELECT COUNT(*) FROM finscreener")
            total_after = cursor.fetchone()[0]
            
            removed_count = total_before - total_after
            if removed_count > 0:
                print(f"[数据清理] 移除了 {removed_count} 条无效记录，保留 {total_after} 条记录")
            else:
                print(f"[数据清理] 数据库干净，共有 {total_after} 条记录")

    def upsert_stock_data(self, data: Dict[str, Any]):
        """Insert or update stock data - 确保每个ticker只有一条记录"""
        # 定义所有可能的字段及其默认值
        default_data = {
            'ticker': None,
            'datetime': None,
            'open': None,
            'high': None,
            'low': None,
            'close': None,
            'volume': None,
            'adjusted_net_profit_rate': None,
            'sue_score': None,
            'surprise_factor': None,
            'inc_revenue_rate': None,
            'inc_net_profit_rate': None,
            'inc_total_revenue_annual': None,
            'inc_net_profit_to_shareholders_annual': None,
            'growth_factor': None,
            'eps_basic': None,
            'eps_diluted': None,
            'bps': None,
            'current_price': None,
            'pe_ratio': None,
            'pb_ratio': None,
            'valuation_factor': None,
            'du_return_on_equity': None,
            'sales_gross_profit': None,
            'gross_profit': None,
            'net_profit': None,
            'profit_factor': None,
            'total_score': None
        }
        
        # 更新默认值
        default_data.update(data)
        
        # 清理数据，处理 NaN 值
        cleaned_data = {}
        for key, value in default_data.items():
            if pd.isna(value) or value is None:
                cleaned_data[key] = None
            else:
                cleaned_data[key] = value
        
        # 确保所有浮点数都是有效的数字
        for key, value in cleaned_data.items():
            if isinstance(value, float) and (pd.isna(value) or np.isinf(value)):
                cleaned_data[key] = None
        
        # 设置当前时间为更新时间
        cleaned_data['update_datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 使用INSERT OR REPLACE确保ticker唯一性
        sql = """
        INSERT OR REPLACE INTO finscreener (
            ticker, datetime,
            open, high, low, close, volume,
            adjusted_net_profit_rate, sue_score, surprise_factor,
            inc_revenue_rate, inc_net_profit_rate, inc_total_revenue_annual,
            inc_net_profit_to_shareholders_annual, growth_factor,
            eps_basic, eps_diluted, bps, current_price, pe_ratio, pb_ratio,
            valuation_factor, du_return_on_equity, sales_gross_profit,
            gross_profit, net_profit, profit_factor, total_score,
            update_datetime
        ) VALUES (
            :ticker, :datetime,
            :open, :high, :low, :close, :volume,
            :adjusted_net_profit_rate, :sue_score, :surprise_factor,
            :inc_revenue_rate, :inc_net_profit_rate, :inc_total_revenue_annual,
            :inc_net_profit_to_shareholders_annual, :growth_factor,
            :eps_basic, :eps_diluted, :bps, :current_price, :pe_ratio,
            :pb_ratio, :valuation_factor, :du_return_on_equity,
            :sales_gross_profit, :gross_profit, :net_profit,
            :profit_factor, :total_score, :update_datetime
        )
        """
        
        with self.get_connection() as conn:
            conn.execute(sql, cleaned_data)
            conn.commit()

    def get_stock_data(self, ticker: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Retrieve stock data from database"""
        sql = "SELECT * FROM finscreener WHERE ticker = ?"
        params = [ticker]
        
        if start_date:
            sql += " AND datetime >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND datetime <= ?"
            params.append(end_date)
            
        sql += " ORDER BY datetime DESC"
        
        with self.get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def get_latest_scores(self, top_n: int = None) -> pd.DataFrame:
        """Get latest scores for all stocks"""
        sql = """
        SELECT ticker, total_score, update_datetime
        FROM finscreener
        WHERE update_datetime = (
            SELECT MAX(update_datetime)
            FROM finscreener
        )
        ORDER BY total_score DESC
        """
        
        if top_n:
            sql += f" LIMIT {top_n}"
            
        with self.get_connection() as conn:
            return pd.read_sql_query(sql, conn)

    def get_top_n_stocks(self, n: int = 50) -> List[Dict[str, Union[str, float]]]:
        """
        获取最新的total_score排名前n的股票列表及其分数
        
        Args:
            n (int): 需要返回的股票数量，默认50
            
        Returns:
            List[Dict[str, Union[str, float]]]: 包含股票代码和分数的列表
            例如: [{'ticker': '000001.SZ', 'total_score': 0.85}, ...]
        """
        with self.get_connection() as conn:
            query = """
                SELECT ticker, total_score
                FROM finscreener
                WHERE total_score > 0
                ORDER BY total_score DESC
                LIMIT ?
            """
            
            result = conn.execute(query, (n,))
            stocks = [{'ticker': row[0], 'total_score': float(row[1])} 
                     for row in result]
            
            return stocks

    def get_recent_stock_data(self, days: int = 1) -> pd.DataFrame:
        """
        获取最近几天的股票数据
        
        Args:
            days (int): 获取最近几天的数据，默认1天
            
        Returns:
            pd.DataFrame: 包含最近数据的DataFrame
        """
        with self.get_connection() as conn:
            query = """
                SELECT *
                FROM finscreener
                WHERE datetime(update_datetime) >= datetime('now', '-{} days')
                ORDER BY update_datetime DESC, total_score DESC
            """.format(days)
            
            return pd.read_sql_query(query, conn) 