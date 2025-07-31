#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目配置管理模块
统一管理所有配置参数，便于维护和修改
"""

import os
from typing import Dict, Any

class Config:
    """项目配置类 - 统一管理所有配置参数"""
    
    # ==================== 币安API配置 ====================
    # 币安WebSocket公开数据流端点
    # 新的 ws-fapi 端点需要身份验证，我们继续使用公开端点
    BINANCE_WS_URL = "wss://fstream.binance.com/ws/!markPrice@arr@1s"
    
    # ==================== WebSocket配置 ====================
    WS_PING_INTERVAL = 20  # WebSocket ping间隔（秒）
    WS_PING_TIMEOUT = 10   # WebSocket ping超时（秒）
    WS_CLOSE_TIMEOUT = 10  # WebSocket关闭超时（秒）
    WS_RECONNECT_INTERVAL = 5  # 重连间隔（秒）
    WS_MAX_RECONNECT_ATTEMPTS = 10  # 最大重连次数
    
    # ==================== 币安WebSocket专用配置 ====================
    BINANCE_PING_INTERVAL = 180  # 币安ping间隔（3分钟）
    BINANCE_PONG_TIMEOUT = 600   # 币安pong超时（10分钟）
    BINANCE_CONNECTION_LIFETIME = 84600  # 连接生命周期（23.5小时）
    MESSAGE_TIMEOUT = 30         # 消息超时阈值（秒）
    MAX_ERROR_COUNT = 100        # 最大错误计数
    
    # ==================== 数据处理配置 ====================
    # ==================== 数据处理配置 ====================
    MAX_HISTORY_LENGTH = 50  # 每个交易对保留的历史数据点数量（扩展5倍）
    TOP_RANKING_COUNT = 5    # TOP排行榜显示数量
    DATA_FRESHNESS_THRESHOLD = 10  # 数据新鲜度阈值（秒）
    STATS_PRINT_INTERVAL = 100     # 统计信息打印间隔（次）
    
    # ==================== 缓存和性能配置 ====================
    RATE_CACHE_SIZE = 1000          # 费率数据缓存大小
    VOLATILITY_CACHE_SIZE = 500     # 波动率计算缓存大小
    TREND_ANALYSIS_DEPTH = 100      # 趋势分析历史深度
    DATA_VALIDATION_BUFFER = 200    # 数据验证缓冲区大小
    ANOMALY_DETECTION_WINDOW = 1024  # 异常检测窗口大小（约17分钟历史数据）
    
    # ==================== 连接稳定性配置 ====================
    WS_CONNECTION_POOL_SIZE = 3     # WebSocket连接池大小
    WS_BACKUP_CONNECTIONS = 2       # 备用连接数量
    WS_HEARTBEAT_INTERVAL = 10      # 心跳检测间隔（秒）
    WS_DATA_INTEGRITY_CHECK = True  # 数据完整性检查开关
    
    # ==================== UI界面配置 ====================
    UI_HOST = "localhost"
    UI_PORT = 8080
    UI_TITLE = "币安资金费率波动TOP5监控"
    UI_UPDATE_INTERVAL = 1.0  # UI更新间隔（秒）
    UI_DARK_MODE = True       # 是否启用深色模式
    UI_AUTO_OPEN_BROWSER = True  # 是否自动打开浏览器
    
    # ==================== 交易对过滤配置 ====================
    SYMBOL_SUFFIX_FILTER = "USDT"  # 只处理以此结尾的交易对
    SYMBOL_EXCLUDE_KEYWORDS = ["UP", "DOWN"]  # 排除包含这些关键词的交易对
    
    # ==================== 波动率计算配置 ====================
    VOLATILITY_ABSOLUTE_WEIGHT = 1000  # 绝对波动率权重
    VOLATILITY_RELATIVE_WEIGHT = 100   # 相对波动率权重
    
    # ==================== Deviation from Moving Average 算法配置 ====================
    MOVING_AVERAGE_WINDOW = 512        # 滑动平均窗口大小（数据点数量）- 约512秒历史数据
    # DEVIATION_AMPLIFICATION_FACTOR = 0.1  # 已移除：偏离度非线性放大因子（改为使用真实偏离度）
    DEVIATION_SENSITIVITY_THRESHOLD = 0.01  # 偏离度敏感度阈值（百分比）
    
    # ==================== 日志配置 ====================
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_TO_FILE = False  # 是否启用文件日志（默认False保持项目目录整洁）
    LOG_FILE_PATH = "logs/app.log"  # 日志文件路径
    LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 单个日志文件最大大小（10MB）
    LOG_FILE_BACKUP_COUNT = 5  # 保留的日志文件备份数量
    
    # ==================== 开发调试配置 ====================
    DEBUG_MODE = os.getenv("DEBUG", "False").lower() == "true"
    MOCK_DATA_MODE = os.getenv("MOCK_DATA", "False").lower() == "true"
    
    @classmethod
    def get_all_config(cls) -> Dict[str, Any]:
        """
        获取所有配置参数
        
        Returns:
            包含所有配置的字典
        """
        config_dict = {}
        for attr_name in dir(cls):
            if not attr_name.startswith('_') and not callable(getattr(cls, attr_name)):
                config_dict[attr_name] = getattr(cls, attr_name)
        return config_dict
    
    @classmethod
    def print_config(cls):
        """打印当前配置信息（用于调试）"""
        print("=" * 60)
        print("当前项目配置:")
        print("=" * 60)
        
        config_dict = cls.get_all_config()
        for key, value in sorted(config_dict.items()):
            print(f"{key:<30} = {value}")
        
        print("=" * 60)

# 创建全局配置实例
config = Config()

# 如果直接运行此文件，则打印配置信息
if __name__ == "__main__":
    config.print_config()