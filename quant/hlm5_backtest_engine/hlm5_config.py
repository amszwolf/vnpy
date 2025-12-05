# -*- coding: utf-8 -*-
"""
HLM5 智能股票数据处理系统配置文件

这个文件包含了所有系统的配置参数，包括：
- 数据库配置
- 更新策略配置  
- 技术指标参数
- 并行处理配置
- 实时数据配置

更新历史:
- 2024-12-15: 添加智能更新策略配置
- 2024-12-15: 添加实时数据处理配置
"""

import os
from datetime import datetime

# ====================================================================
# 全局配置
# ====================================================================

OVERALL_CONFIG = {
    'TRADING_SIGNALS_DB': 'trading_signals.db',
    'LOG_LEVEL': 'INFO',
    'LOG_FORMAT': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'TIMEZONE': 'Asia/Shanghai',
    'CACHE_SIZE': 100000,  # 缓存大小
}

# ====================================================================
# 股票数据处理配置
# ====================================================================

EQUITY_CONFIG = {
    # 数据库配置
    'DATABASE_PATH': 'trading_signals.db',
    'DATABASE_BACKUP_PATH': 'backup/trading_signals_backup.db',
    'DATABASE_VACUUM_INTERVAL': 7,  # 天数，数据库清理间隔
    
    # 并行处理配置
    'PARALLEL_PROCESSING': True,
    'MAX_WORKERS': 4,  # 最大并行工作进程数
    'BATCH_SIZE': 100,  # 批量处理大小
    'CHUNK_SIZE': 1000,  # 数据块大小
    
    # 智能更新策略配置
    'UPDATE_STRATEGY': {
        # 基本策略
        'enable_incremental': True,      # 启用增量更新
        'enable_realtime': False,        # 启用实时更新
        'force_full_update': False,      # 强制全量更新
        'skip_existing': False,          # 跳过已存在数据的股票
        'auto_cleanup_realtime': True,   # 自动清理过期实时数据
        
        # 数据完整性控制
        'max_missing_days': 5,           # 最大允许缺失天数，超过则全量更新
        'min_data_points': 200,          # 最小数据点数量
        'data_quality_threshold': 0.95,  # 数据质量阈值
        
        # 实时数据配置
        'realtime_update_interval': 300,  # 实时更新间隔（秒）
        'realtime_data_retention_days': 3,  # 实时数据保留天数
        'trading_hours': {
            'start': '09:00',
            'end': '15:00',
            'lunch_start': '11:30',
            'lunch_end': '13:00',
        },
        
        # 性能优化
        'use_bulk_insert': True,         # 使用批量插入
        'optimize_queries': True,        # 优化查询
        'enable_indexes': True,          # 启用数据库索引
        'compression_level': 1,          # 数据压缩级别 (0-9)
        
        # 错误处理
        'max_retries': 3,                # 最大重试次数
        'retry_delay': 5,                # 重试延迟（秒）
        'error_tolerance': 0.1,          # 错误容忍度（失败率）
        'log_detailed_errors': True,     # 记录详细错误信息
    },
    
    # 数据源配置
    'DATA_SOURCES': {
        'primary': {
            'type': 'mysql',
            'host': 'rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
            'port': 3306,
            'user': 'root',
            'password': 'Wxtfz13245',
            'database': 'tushare',
            'table': 'tb_szsh_day_2024',
            'timeout': 30,
            'pool_size': 5,
        },
        'backup': {
            'type': 'csv',
            'path': 'data/backup/',
            'enabled': False,
        }
    },
    
    # 技术指标配置
    'INDICATORS': {
        'PRICE_MACD': {
            'macd_long': 20,      # 优化: 26 → 20，缩短长期EMA周期，更敏感
            'macd_mid': 8,        # 优化: 12 → 8，缩短中期EMA周期，更快响应
            'macd_short': 5,      # 优化: 9 → 5，缩短短期EMA周期，更快信号
            'diff_ema_period': 2, # 优化: 3 → 2，减少滞后
            'enable': True,
            'cache_results': True,
        },
        'VOLUME_MACD': {
            'macd_long': 20,      # 优化: 26 → 20
            'macd_mid': 8,        # 优化: 12 → 8
            'macd_short': 5,      # 优化: 9 → 5
            'diff_ema_period': 3, # 优化: 5 → 3，减少滞后
            'enable': True,
            'cache_results': True,
        },
        'HLBW': {
            'lookback_period': 40,  # 优化: 55 → 40，缩短回望周期，更快适应
            'inner_ema': 3,         # 优化: 5 → 3，更敏感
            'outer_ema': 2,         # 优化: 3 → 2，更快响应
            'trend_ema': 2,         # 优化: 3 → 2，更快趋势识别
            'enable': True,
            'cache_results': True,
            # HLBW水平线配置
            'levels': {
                'top_line': 89,
                'mid_high_line': 75,
                'mid_line': 50,
                'mid_low_line': 25,
                'bottom_line': 11,
            }
        },
        'PROPHET': {
            'periods': 20,                    # 优化: 30 → 20，缩短预测周期
            'daily_seasonality': False,       # 日季节性
            'weekly_seasonality': True,       # 周季节性
            'yearly_seasonality': False,      # 优化: True → False，关闭年季节性
            'changepoint_prior_scale': 0.08,  # 优化: 0.05 → 0.08，提高变点敏感性
            'seasonality_prior_scale': 10.0,  # 季节性先验尺度
            'holidays_prior_scale': 10.0,     # 节假日先验尺度
            'mcmc_samples': 0,                # MCMC样本数
            'interval_width': 0.80,           # 置信区间宽度
            'uncertainty_samples': 1000,      # 不确定性样本数
            'enable': True,
            'cache_results': True,
            'model_cache_days': 7,            # 模型缓存天数
        },
    },
    
    # 交易信号配置
    'TRADING_SIGNALS': {
        'entry_conditions': {
            'min_cross_signals': 1,          # 优化: 2 → 1，降低信号门槛
            'require_prophet_trend': False,  # 优化: True → False，降低限制
            'prophet_min_duration': 2,       # 优化: 3 → 2，缩短最小趋势持续时间
            'prophet_min_change': 0.01,      # 优化: 0.02 → 0.01，降低最小趋势变化幅度
            # 新增: 多层次信号强度系统
            'signal_strength_levels': {
                'min_tradeable_strength': 3,  # 最小可交易信号强度
                'position_scaling': {
                    10: 1.0,  # 最强信号 → 100%仓位
                    9: 0.9,   # 强信号 → 90%仓位
                    8: 0.8,
                    7: 0.7,
                    6: 0.6,
                    5: 0.5,
                    4: 0.4,
                    3: 0.3,   # 最小可交易信号 → 30%仓位
                }
            }
        },
        'exit_conditions': {
            'enable_stop_loss': True,        # 启用止损
            'stop_loss_pct': 0.04,          # 优化: 0.05 → 0.04，更紧密止损
            'enable_take_profit': True,      # 启用止盈
            'take_profit_pct': 0.12,        # 优化: 0.15 → 0.12，更快获利
            'trailing_stop': True,          # 启用跟踪止损
            'trailing_stop_pct': 0.02,      # 新增: 2%跟踪止损
        },
        'risk_management': {
            'max_position_size': 0.10,      # 最大单仓位大小
            'max_daily_trades': 8,          # 优化: 5 → 8，最大日交易次数
            'max_drawdown': 0.05,           # 优化: 0.20 → 0.05，严格控制回撤
            'max_total_positions': 30,      # 新增: 最大总持仓数
        }
    },
    
    # 性能监控配置
    'PERFORMANCE': {
        'enable_profiling': False,        # 启用性能分析
        'log_slow_queries': True,         # 记录慢查询
        'slow_query_threshold': 5.0,      # 慢查询阈值（秒）
        'memory_limit_mb': 2048,          # 内存限制（MB）
        'disk_space_warning_gb': 5,       # 磁盘空间警告阈值（GB）
    },
    
    # 通知配置
    'NOTIFICATIONS': {
        'enable_email': False,
        'enable_webhook': False,
        'email_settings': {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'to_addresses': [],
        },
        'webhook_settings': {
            'url': '',
            'headers': {},
        }
    }
}

# ====================================================================
# 日志配置
# ====================================================================

LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'logs/hlm5.log',
            'formatter': 'detailed',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': 'logs/hlm5_errors.log',
            'formatter': 'detailed',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        },
        'trading_signals': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}

# ====================================================================
# 市场配置
# ====================================================================

MARKET_CONFIG = {
    'CHINA': {
        'market_code': 'CN',
        'timezone': 'Asia/Shanghai',
        'trading_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'trading_hours': {
            'morning_open': '09:30',
            'morning_close': '11:30',
            'afternoon_open': '13:00',
            'afternoon_close': '15:00',
        },
        'holidays': [
            '2024-01-01',  # 元旦
            '2024-02-10',  # 春节
            # ... 更多节假日
        ],
        'currency': 'CNY',
        'min_tick_size': 0.01,
    },
    'HK': {
        'market_code': 'HK',
        'timezone': 'Asia/Hong_Kong',
        'trading_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'trading_hours': {
            'morning_open': '09:30',
            'morning_close': '12:00',
            'afternoon_open': '13:00',
            'afternoon_close': '16:00',
        },
        'currency': 'HKD',
        'min_tick_size': 0.001,
    },
    'US': {
        'market_code': 'US',
        'timezone': 'America/New_York',
        'trading_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'trading_hours': {
            'regular_open': '09:30',
            'regular_close': '16:00',
            'extended_open': '04:00',
            'extended_close': '20:00',
        },
        'currency': 'USD',
        'min_tick_size': 0.01,
    }
}

# ====================================================================
# 环境配置
# ====================================================================

def get_config_for_environment(env='production'):
    """
    根据环境获取配置
    
    Parameters:
    -----------
    env : str
        环境名称：'development', 'testing', 'production'
    """
    base_config = EQUITY_CONFIG.copy()
    
    if env == 'development':
        base_config.update({
            'DATABASE_PATH': 'dev_trading_signals.db',
            'PARALLEL_PROCESSING': False,
            'MAX_WORKERS': 2,
        })
        base_config['UPDATE_STRATEGY'].update({
            'enable_realtime': True,
            'log_detailed_errors': True,
        })
        base_config['PERFORMANCE'].update({
            'enable_profiling': True,
        })
        
    elif env == 'testing':
        base_config.update({
            'DATABASE_PATH': 'test_trading_signals.db',
            'PARALLEL_PROCESSING': False,
            'MAX_WORKERS': 1,
        })
        base_config['UPDATE_STRATEGY'].update({
            'max_retries': 1,
            'error_tolerance': 0.5,
        })
        
    elif env == 'production':
        base_config.update({
            'DATABASE_PATH': 'production_trading_signals.db',
            'PARALLEL_PROCESSING': True,
            'MAX_WORKERS': 8,
        })
        base_config['UPDATE_STRATEGY'].update({
            'enable_incremental': True,
            'auto_cleanup_realtime': True,
            'optimize_queries': True,
        })
        base_config['PERFORMANCE'].update({
            'enable_profiling': False,
            'memory_limit_mb': 4096,
        })
    
    return base_config

# ====================================================================
# 验证配置
# ====================================================================

def validate_config(config):
    """验证配置的有效性"""
    errors = []
    
    # 验证数据库路径
    if not config.get('DATABASE_PATH'):
        errors.append("DATABASE_PATH is required")
    
    # 验证并行处理配置
    if config.get('PARALLEL_PROCESSING'):
        if not isinstance(config.get('MAX_WORKERS'), int) or config['MAX_WORKERS'] < 1:
            errors.append("MAX_WORKERS must be a positive integer")
    
    # 验证技术指标配置
    indicators = config.get('INDICATORS', {})
    for indicator_name, indicator_config in indicators.items():
        if not isinstance(indicator_config, dict):
            errors.append(f"Invalid configuration for indicator {indicator_name}")
    
    # 验证更新策略配置
    update_strategy = config.get('UPDATE_STRATEGY', {})
    if 'max_missing_days' in update_strategy:
        if not isinstance(update_strategy['max_missing_days'], int) or update_strategy['max_missing_days'] < 0:
            errors.append("max_missing_days must be a non-negative integer")
    
    return errors

# ====================================================================
# 初始化配置
# ====================================================================

def initialize_config():
    """初始化配置，创建必要的目录和文件"""
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    # 创建数据备份目录
    os.makedirs('backup', exist_ok=True)
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 验证配置
    errors = validate_config(EQUITY_CONFIG)
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    print("[OK] 配置初始化完成")
    print(f"   数据库路径: {EQUITY_CONFIG['DATABASE_PATH']}")
    print(f"   并行处理: {EQUITY_CONFIG['PARALLEL_PROCESSING']}")
    print(f"   最大工作进程: {EQUITY_CONFIG['MAX_WORKERS']}")
    print(f"   增量更新: {EQUITY_CONFIG['UPDATE_STRATEGY']['enable_incremental']}")
    print(f"   实时更新: {EQUITY_CONFIG['UPDATE_STRATEGY']['enable_realtime']}")

# 自动初始化
if __name__ == "__main__":
    initialize_config()
else:
    # 导入时自动创建目录
    try:
        initialize_config()
    except Exception as e:
        print(f"[WARNING] 配置初始化失败: {e}") 