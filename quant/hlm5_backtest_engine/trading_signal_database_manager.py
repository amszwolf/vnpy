import os
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging

class TradingSignalDatabaseManager:
    def __init__(self, db_path: str, enable_realtime: bool = False, daily_update: bool = True):
        """
        初始化数据库管理器
        
        Parameters:
        -----------
        db_path : str
            SQLite数据库文件路径
        enable_realtime : bool
            是否启用实时数据处理模式
        daily_update : bool
            是否启用每日增量更新模式
        """
        self.db_path = db_path
        self.enable_realtime = enable_realtime
        self.daily_update = daily_update
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 确保数据库文件所在目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        # 设置超时和并发访问参数
        self.conn = sqlite3.connect(
            self.db_path,
            timeout=60,  # 增加超时时间到60秒
            isolation_level=None  # 自动提交模式
        )
        
        # 启用WAL模式以提高并发性能
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=NORMAL')
        self.conn.execute('PRAGMA cache_size=20000')  # 增加缓存
        self.conn.execute('PRAGMA temp_store=MEMORY')
        self.conn.execute('PRAGMA mmap_size=268435456')  # 256MB内存映射
        
        # 创建表结构
        self._create_tables()
        self._create_metadata_tables()

    def _create_tables(self):
        """创建统一的数据表结构"""
        cursor = self.conn.cursor()
        
        # 创建统一的交易数据表
        cursor.execute('''CREATE TABLE IF NOT EXISTS trading_data (
            ticker TEXT,
            datetime TIMESTAMP,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            Price_MACD REAL,
            Price_MACD_Signal REAL,
            Price_MACD_Hist REAL,
            Price_XLPL_Phase INTEGER,
            Price_Cross INTEGER,
            Volume_MACD REAL,
            Volume_MACD_Signal REAL,
            Volume_MACD_Hist REAL,
            Volume_XLPL_Phase INTEGER,
            Volume_Cross INTEGER,
            HLBW_Trend_Line REAL,
            HLBW_MACD REAL,
            HLBW_MACD_Signal REAL,
            HLBW_MACD_Hist REAL,
            HLBW_XLPL_Phase INTEGER,
            HLBW_Cross INTEGER,
            PH_yhat REAL,
            PH_yhat_lower REAL,
            PH_yhat_upper REAL,
            PH_MACD REAL,
            PH_MACD_Signal REAL,
            PH_MACD_Hist REAL,
            PH_XLPL_Phase INTEGER,
            PH_Cross INTEGER,
            PH_Trend_Duration INTEGER,
            PH_Trend_Change REAL,
            Entry_Signal BOOLEAN,
            Exit_Signal BOOLEAN,
            Position INTEGER,
            Entry_Price REAL,
            Exit_Price REAL,
            Profit_Loss REAL,
            Scaling_Signal INTEGER DEFAULT 0,  -- 加仓信号类型（0=无，1-10=加仓层级）
            Scaling_Position INTEGER DEFAULT 0,  -- 实际加仓后的持仓数量
            Scaling_Level INTEGER DEFAULT 0,  -- 当前加仓层级
            Scaling_Strategy TEXT,  -- 使用的加仓策略名称
            is_realtime BOOLEAN DEFAULT 0,  -- 标记是否是实时数据
            data_quality INTEGER DEFAULT 1,  -- 数据质量: 1=完整, 0=部分/实时
            PRIMARY KEY (ticker, datetime)
        )''')
        
        # 创建性能优化索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_datetime ON trading_data(ticker, datetime)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_date ON trading_data(ticker, date(datetime))')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datetime ON trading_data(datetime)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_signal ON trading_data(ticker, Entry_Signal) WHERE Entry_Signal = 1')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realtime ON trading_data(ticker, is_realtime) WHERE is_realtime = 1')
        
        self.conn.commit()
        print("Database tables and indexes created successfully")

    def _create_metadata_tables(self):
        """创建元数据表用于跟踪数据更新状态"""
        cursor = self.conn.cursor()
        
        # 股票数据状态表
        cursor.execute('''CREATE TABLE IF NOT EXISTS ticker_metadata (
            ticker TEXT PRIMARY KEY,
            first_date TEXT,
            last_date TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_records INTEGER DEFAULT 0,
            is_complete BOOLEAN DEFAULT 0,
            needs_full_update BOOLEAN DEFAULT 1,
            market TEXT,  -- SH, SZ, HK, US等
            is_active BOOLEAN DEFAULT 1,
            realtime_last_update TIMESTAMP,
            data_source TEXT DEFAULT 'tushare',
            update_frequency TEXT DEFAULT 'daily'  -- daily, realtime, manual
        )''')
        
        # 数据更新日志表
        cursor.execute('''CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            update_type TEXT,  -- full, incremental, realtime
            start_date TEXT,
            end_date TEXT,
            records_updated INTEGER,
            update_duration REAL,
            status TEXT,  -- success, failed, partial
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # 市场交易日历表（用于判断是否为交易日）
        cursor.execute('''CREATE TABLE IF NOT EXISTS trading_calendar (
            date TEXT PRIMARY KEY,
            market TEXT,
            is_trading_day BOOLEAN DEFAULT 1,
            market_open_time TEXT,
            market_close_time TEXT
        )''')
        
        self.conn.commit()
        print("Metadata tables created successfully")

    def check_data_completeness(self, ticker: str, start_date: str = None, end_date: str = None) -> Dict:
        """
        检查股票数据的完整性
        
        Returns:
        --------
        Dict: {
            'has_data': bool,
            'first_date': str,
            'last_date': str,
            'missing_dates': List[str],
            'needs_full_update': bool,
            'needs_incremental_update': bool,
            'expected_end_date': str
        }
        """
        cursor = self.conn.cursor()
        
        # 获取现有数据范围
        cursor.execute("""
            SELECT MIN(date(datetime)) as first_date, 
                   MAX(date(datetime)) as last_date,
                   COUNT(*) as total_records
            FROM trading_data 
            WHERE ticker = ?
        """, (ticker,))
        
        result = cursor.fetchone()
        first_date, last_date, total_records = result
        
        has_data = total_records > 0
        
        # 确定期望的结束日期
        today = datetime.now().date()
        expected_end_date = end_date if end_date else today.strftime('%Y-%m-%d')
        
        # 检查是否需要更新
        needs_full_update = not has_data
        needs_incremental_update = False
        missing_dates = []
        
        if has_data:
            last_date_obj = datetime.strptime(last_date, '%Y-%m-%d').date()
            expected_end_date_obj = datetime.strptime(expected_end_date, '%Y-%m-%d').date()
            
            # 如果最后日期比预期结束日期早，需要增量更新
            if last_date_obj < expected_end_date_obj:
                needs_incremental_update = True
                
                # 计算缺失的日期范围
                missing_start = (last_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
                missing_dates = [missing_start, expected_end_date]
        
        return {
            'has_data': has_data,
            'first_date': first_date,
            'last_date': last_date,
            'total_records': total_records,
            'missing_dates': missing_dates,
            'needs_full_update': needs_full_update,
            'needs_incremental_update': needs_incremental_update,
            'expected_end_date': expected_end_date
        }

    def update_ticker_metadata(self, ticker: str, first_date: str = None, last_date: str = None, 
                              total_records: int = None, is_complete: bool = True):
        """更新股票元数据"""
        cursor = self.conn.cursor()
        
        if first_date and last_date:
            cursor.execute("""
                INSERT INTO ticker_metadata 
                (ticker, first_date, last_date, total_records, is_complete, needs_full_update)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(ticker) DO UPDATE SET
                    first_date = COALESCE(?, first_date),
                    last_date = ?,
                    total_records = COALESCE(?, total_records),
                    is_complete = ?,
                    needs_full_update = 0,
                    last_updated = CURRENT_TIMESTAMP
            """, (ticker, first_date, last_date, total_records, is_complete,
                 first_date, last_date, total_records, is_complete))
        else:
            # 只更新最后更新时间
            cursor.execute("""
                INSERT INTO ticker_metadata (ticker, last_updated)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(ticker) DO UPDATE SET
                    last_updated = CURRENT_TIMESTAMP
            """, (ticker,))

    def log_update(self, ticker: str, update_type: str, start_date: str = None, 
                   end_date: str = None, records_updated: int = 0, 
                   duration: float = 0, status: str = 'success', error_message: str = None):
        """记录更新日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO update_log 
            (ticker, update_type, start_date, end_date, records_updated, 
             update_duration, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, update_type, start_date, end_date, records_updated, 
              duration, status, error_message))

    def update_data_smart(self, ticker: str, datetime_val, data_dict: Dict, is_realtime: bool = False):
        """
        智能数据更新：支持增量更新和实时数据处理
        """
        if pd.isna(datetime_val):
            self.logger.warning(f"Skipping row with NaT datetime for {ticker}")
            return
        
        if isinstance(datetime_val, pd.Timestamp):
            datetime_val = datetime_val.strftime('%Y-%m-%d %H:%M:%S')
        
        # 清理数据字典中的空值
        cleaned_dict = {key: (None if pd.isna(value) else value) for key, value in data_dict.items()}
        
        # 添加实时数据标记和数据质量标记
        cleaned_dict['is_realtime'] = is_realtime
        cleaned_dict['data_quality'] = 0 if is_realtime else 1
        
        columns = ['ticker', 'datetime'] + list(cleaned_dict.keys())
        placeholders = ','.join(['?'] * len(columns))
        values = [ticker, datetime_val] + list(cleaned_dict.values())
        
        update_stmt = ','.join([f"{k}=?" for k in cleaned_dict.keys()])
        
        sql = f"""
        INSERT INTO trading_data ({','.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(ticker, datetime) DO UPDATE SET
        {update_stmt}
        """
        
        cursor = self.conn.cursor()
        
        # 添加重试逻辑
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                cursor.execute(sql, values + list(cleaned_dict.values()))
                break
            except sqlite3.OperationalError as e:
                if attempt == max_retries - 1:
                    raise
                if "database is locked" in str(e):
                    time.sleep(retry_delay)
                    continue
                raise

    def batch_update_data(self, ticker: str, data_df: pd.DataFrame, is_realtime: bool = False):
        """批量更新数据，提高效率"""
        if data_df.empty:
            return 0
        
        # 准备批量插入数据
        records = []
        for idx, row in data_df.iterrows():
            record = [ticker, idx.strftime('%Y-%m-%d %H:%M:%S') if isinstance(idx, pd.Timestamp) else idx]
            
            # 添加所有列的数据
            for col in data_df.columns:
                value = row[col]
                record.append(None if pd.isna(value) else value)
            
            # 添加实时数据标记
            record.extend([is_realtime, 0 if is_realtime else 1])
            records.append(record)
        
        # 构建SQL语句
        columns = ['ticker', 'datetime'] + list(data_df.columns) + ['is_realtime', 'data_quality']
        placeholders = ','.join(['?'] * len(columns))
        update_columns = list(data_df.columns) + ['is_realtime', 'data_quality']
        update_stmt = ','.join([f"{k}=excluded.{k}" for k in update_columns])
        
        sql = f"""
        INSERT INTO trading_data ({','.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(ticker, datetime) DO UPDATE SET
        {update_stmt}
        """
        
        cursor = self.conn.cursor()
        cursor.executemany(sql, records)
        
        return len(records)

    def clean_realtime_data(self, ticker: str, before_date: str = None):
        """清理过期的实时数据"""
        if not before_date:
            # 默认清理3天前的实时数据
            before_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM trading_data 
            WHERE ticker = ? AND is_realtime = 1 AND date(datetime) < ?
        """, (ticker, before_date))
        
        deleted_count = cursor.rowcount
        self.logger.info(f"Cleaned {deleted_count} realtime records for {ticker} before {before_date}")
        
        return deleted_count

    def get_update_strategy(self, ticker: str, start_date: str = None, end_date: str = None) -> Dict:
        """
        确定最优的更新策略
        
        Returns:
        --------
        Dict: {
            'strategy': str,  # 'full', 'incremental', 'realtime', 'skip'
            'start_date': str,
            'end_date': str,
            'reason': str
        }
        """
        # 检查数据完整性
        completeness = self.check_data_completeness(ticker, start_date, end_date)
        
        strategy_info = {
            'strategy': 'skip',
            'start_date': start_date,
            'end_date': end_date,
            'reason': 'Data is up to date'
        }
        
        # 实时数据处理逻辑
        if self.enable_realtime:
            now = datetime.now()
            if now.hour >= 9 and now.hour < 15:  # 交易时间内
                strategy_info.update({
                    'strategy': 'realtime',
                    'start_date': now.strftime('%Y-%m-%d'),
                    'end_date': now.strftime('%Y-%m-%d'),
                    'reason': 'Realtime update during trading hours'
                })
                return strategy_info
        
        # 全量更新逻辑
        if completeness['needs_full_update']:
            strategy_info.update({
                'strategy': 'full',
                'start_date': start_date or '2015-01-01',
                'end_date': end_date or datetime.now().strftime('%Y-%m-%d'),
                'reason': 'No existing data found'
            })
        
        # 增量更新逻辑
        elif completeness['needs_incremental_update']:
            missing_dates = completeness['missing_dates']
            strategy_info.update({
                'strategy': 'incremental',
                'start_date': missing_dates[0],
                'end_date': missing_dates[1],
                'reason': f'Missing data from {missing_dates[0]} to {missing_dates[1]}'
            })
        
        return strategy_info

    # 保持原有方法的兼容性
    def update_data(self, ticker: str, datetime_val, data_dict: Dict):
        """兼容性方法，调用新的智能更新方法"""
        return self.update_data_smart(ticker, datetime_val, data_dict, is_realtime=False)

    def clear_tables(self, ticker: str, keep_realtime: bool = True):
        """
        清除特定股票的记录
        
        Parameters:
        -----------
        ticker : str
            股票代码
        keep_realtime : bool
            是否保留实时数据
        """
        cursor = self.conn.cursor()
        
        if keep_realtime:
            cursor.execute("DELETE FROM trading_data WHERE ticker = ? AND is_realtime = 0", (ticker,))
            print(f"Cleared historical records for {ticker}, kept realtime data")
        else:
            cursor.execute("DELETE FROM trading_data WHERE ticker = ?", (ticker,))
            print(f"Cleared all records for {ticker}")
        
        # 更新元数据
        if not keep_realtime:
            cursor.execute("DELETE FROM ticker_metadata WHERE ticker = ?", (ticker,))

    def get_data(self, ticker: str, start_date: str = None, end_date: str = None, 
                 columns: List[str] = None, include_realtime: bool = True) -> pd.DataFrame:
        """
        获取数据，支持实时数据过滤
        """
        if columns:
            col_str = ', '.join(['datetime'] + columns)
        else:
            col_str = '*'
        
        query = f"SELECT {col_str} FROM trading_data WHERE ticker = ?"
        params = [ticker]
        
        if not include_realtime:
            query += " AND data_quality = 1"
        
        if start_date:
            query += " AND datetime >= date(?)"
            params.append(start_date)
            
        if end_date:
            query += " AND datetime < date(?, '+1 day')"
            params.append(end_date)
            
        query += " ORDER BY datetime"
        
        df = pd.read_sql(query, self.conn, params=params)
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['datetime'])
            return df.set_index('datetime')
        return pd.DataFrame()

    def get_all_tickers(self, active_only: bool = True) -> List[str]:
        """获取所有股票代码"""
        if active_only:
            query = """
                SELECT DISTINCT ticker FROM ticker_metadata 
                WHERE is_active = 1 
                ORDER BY ticker
            """
        else:
            query = "SELECT DISTINCT ticker FROM trading_data ORDER BY ticker"
        
        df = pd.read_sql(query, self.conn)
        return df['ticker'].tolist()

    def get_database_stats(self) -> Dict:
        """获取数据库统计信息"""
        cursor = self.conn.cursor()
        
        # 基本统计
        cursor.execute("SELECT COUNT(DISTINCT ticker) as ticker_count FROM trading_data")
        ticker_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) as total_records FROM trading_data")
        total_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) as realtime_records FROM trading_data WHERE is_realtime = 1")
        realtime_records = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT 
                MIN(datetime) as earliest_date,
                MAX(datetime) as latest_date
            FROM trading_data
        """)
        date_range = cursor.fetchone()
        
        return {
            'ticker_count': ticker_count,
            'total_records': total_records,
            'realtime_records': realtime_records,
            'historical_records': total_records - realtime_records,
            'earliest_date': date_range[0],
            'latest_date': date_range[1],
            'database_size_mb': os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
        }

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn'):
            self.conn.close()

    def get_connection(self):
        """获取数据库连接"""
        return self.conn

    def save_to_disk(self):
        """确保所有更改都已写入磁盘"""
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            self.conn.commit()
            self.conn.execute('PRAGMA wal_checkpoint(FULL)')
            print(f"Successfully saved database to {self.db_path}")
        except Exception as e:
            print(f"Error saving database to disk: {str(e)}")
            raise