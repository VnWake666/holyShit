#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务核心模块 - 资金费率分析和波动率计算
使用 Pandas 和 NumPy 优化的高性能版本
负责处理币安WebSocket数据，计算波动率，生成TOP5排行
"""

import time
import threading
import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from config import config
from logger import get_logger

class BusinessCore:
    """业务核心 - 基于 Pandas/NumPy 的高性能核心业务逻辑处理器"""
    
    def __init__(self):
        """初始化业务核心"""
        self.logger = get_logger(__name__)
        
        # 核心数据存储 - 使用 Pandas Series 替代原始列表
        self.current_rates: Dict[str, float] = {}
        self.rate_history: Dict[str, pd.Series] = {}  # 每个交易对的历史费率时间序列
        self.volatility_data: Dict[str, Dict] = {}
        
        # TOP5排行数据 - 冠军保持机制
        self.top5_symbols: List[str] = []
        self.champion_records: Dict[str, Dict] = {}  # 保存历史最高波动率记录
        
        # 统计信息
        self.total_symbols: int = 0
        self.data_update_count: int = 0
        self.last_update_time: Optional[float] = None
        
        # 线程安全
        self.data_lock = threading.RLock()
        
        # 内存管理
        self.symbol_last_seen: Dict[str, float] = {}
        
        # 独立的排名更新线程
        self.ranking_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.ranking_update_interval = 0.2
        
        # 配置参数
        self.window_size = getattr(config, 'MOVING_AVERAGE_WINDOW', 20)
        self.champion_ttl = 15 * 60  # 15分钟冠军TTL
        
        self.logger.info("业务核心初始化完成 (Pandas/NumPy 优化版本)")

    def start(self):
        """启动后台排名更新线程"""
        if self.ranking_thread is None:
            self.stop_event.clear()
            self.ranking_thread = threading.Thread(target=self._ranking_loop, daemon=True)
            self.ranking_thread.start()
            self.logger.info(f"独立的排名更新线程已启动，刷新间隔: {self.ranking_update_interval}秒")

    def stop(self):
        """停止后台排名更新线程"""
        self.logger.info("正在停止排名更新线程...")
        self.stop_event.set()
        if self.ranking_thread and self.ranking_thread.is_alive():
            self.ranking_thread.join()
        self.logger.info("排名更新线程已停止")

    def _ranking_loop(self):
        """排名更新的循环，由后台线程执行"""
        while not self.stop_event.is_set():
            try:
                with self.data_lock:
                    self._update_top5_ranking()
            except Exception as e:
                self.logger.error(f"排名更新循环中发生错误: {e}", exc_info=True)
            self.stop_event.wait(self.ranking_update_interval)
    
    def update_data(self, data: Any) -> None:
        """处理资金费率数据的主要入口方法"""
        try:
            with self.data_lock:
                items_to_process = []
                if isinstance(data, list):
                    items_to_process = data
                elif isinstance(data, dict):
                    items_to_process = [data]

                processed_count = 0
                for item in items_to_process:
                    if self._process_single_item(item):
                        processed_count += 1
                
                if processed_count > 0:
                    self._update_statistics(processed_count)
                    if self.data_update_count % 100 == 0:
                        self._cleanup_caches()
                
        except Exception as e:
            self.logger.error(f"处理资金费率数据时发生错误: {e}", exc_info=True)

    def _process_single_item(self, item: Dict) -> bool:
        """处理单个数据项"""
        try:
            if not self._validate_item(item):
                return False
            
            symbol, new_rate = self._extract_rate(item)
            if symbol is None or new_rate is None:
                return False

            if not self._should_process_symbol(symbol):
                return False
            
            old_rate = self.current_rates.get(symbol, new_rate)
            
            # 更新当前费率
            self.current_rates[symbol] = new_rate
            
            # 更新历史记录 - 使用 Pandas Series
            current_time = pd.Timestamp.now()
            if symbol not in self.rate_history:
                # 创建新的 Series，包含第一个数据点
                self.rate_history[symbol] = pd.Series([new_rate], index=[current_time], name=symbol)
            else:
                # 添加新的费率数据点到现有 Series
                new_data = pd.Series([new_rate], index=[current_time])
                self.rate_history[symbol] = pd.concat([self.rate_history[symbol], new_data])
            
            # 维护窗口大小 - 使用 Pandas 的高效切片
            if len(self.rate_history[symbol]) > self.window_size:
                self.rate_history[symbol] = self.rate_history[symbol].iloc[-self.window_size:]
            
            self.symbol_last_seen[symbol] = time.time()

            # 仅在费率实际变化时才计算波动率
            rate_diff = abs(new_rate - old_rate)
            if rate_diff > 1e-9:
                self._calculate_volatility(symbol, old_rate, new_rate)
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理单个数据项 {item.get('s', item.get('symbol', ''))} 时出错: {e}")
            return False

    def _extract_rate(self, item: Dict) -> tuple[Optional[str], Optional[float]]:
        """从数据项中提取交易对和费率"""
        try:
            if 's' in item and 'r' in item:
                return item['s'], float(item['r']) * 100
            if 'symbol' in item and 'fundingRate' in item:
                return item['symbol'], float(item['fundingRate']) * 100
            if 'symbol' in item and 'funding_rate' in item:
                return item['symbol'], float(item['funding_rate'])
        except (ValueError, TypeError) as e:
            self.logger.warning(f"费率提取失败: {e}")
        return None, None

    def _validate_item(self, item: Dict) -> bool:
        """验证数据项格式和值的合理性"""
        try:
            if not isinstance(item, dict): 
                return False
            
            symbol, rate = self._extract_rate(item)
            if symbol is None or rate is None: 
                return False
                
            if not isinstance(symbol, str) or not (-1000 < rate < 1000):
                self.logger.warning(f"无效的费率数据: {symbol}, {rate}")
                return False
                
            return True
        except Exception:
            return False

    def _should_process_symbol(self, symbol: str) -> bool:
        """判断是否应该处理该交易对"""
        if not symbol.endswith(config.SYMBOL_SUFFIX_FILTER):
            return False
        if any(keyword in symbol for keyword in config.SYMBOL_EXCLUDE_KEYWORDS):
            return False
        return True

    def _calculate_volatility(self, symbol: str, old_rate: float, new_rate: float) -> None:
        """
        计算并存储波动率 - 使用 Pandas/NumPy 优化的 Z-score 算法
        + 15分钟TTL冠军机制
        """
        try:
            history_series = self.rate_history.get(symbol)
            if history_series is None or len(history_series) < 3:
                return  # 历史数据不足
            
            # 使用 Pandas 的高效统计方法 - 排除最新的数据点进行统计计算
            historical_data = history_series.iloc[:-1]  # 排除最新添加的数据点
            
            if len(historical_data) < 2:
                return
            
            # 使用 Pandas 内置的高效统计函数
            moving_average = historical_data.mean()
            std_dev = historical_data.std()
            
            # 检查标准差是否有效
            if pd.isna(std_dev) or std_dev < 1e-10:
                return
            
            # 计算 Z-score
            z_score = (new_rate - moving_average) / std_dev
            current_volatility = abs(z_score)
            
            current_time = time.time()
            
            # 检查并清理过期的冠军记录
            if symbol in self.champion_records:
                champion_age = current_time - self.champion_records[symbol]['champion_timestamp']
                if champion_age > self.champion_ttl:
                    del self.champion_records[symbol]
                    self.logger.debug(f"⏰ {symbol} 冠军记录已过期，清除")
            
            # 检查是否创造新纪录
            is_new_champion = (
                symbol not in self.champion_records or 
                current_volatility > self.champion_records[symbol]['max_volatility']
            )
            
            if is_new_champion:
                self.champion_records[symbol] = {
                    'max_volatility': current_volatility,
                    'z_score': z_score,
                    'moving_average': float(moving_average),  # 转换为 Python float
                    'std_dev': float(std_dev),
                    'champion_old_rate': old_rate,
                    'champion_new_rate': new_rate,
                    'champion_timestamp': current_time,
                    'champion_age_hours': 0.0
                }
                self.logger.info(f"🏆 {symbol} 创造新的Z-score纪录: {z_score:.4f}")
            
            # 更新波动率数据
            if symbol in self.champion_records:
                champion_info = self.champion_records[symbol]
                champion_age_hours = (current_time - champion_info['champion_timestamp']) / 3600
                champion_info['champion_age_hours'] = champion_age_hours
                
                self.volatility_data[symbol] = {
                    'combined': champion_info['max_volatility'],
                    'z_score': champion_info['z_score'],
                    'moving_average': champion_info['moving_average'],
                    'std_dev': champion_info['std_dev'],
                    'rate_change': champion_info['champion_new_rate'] - champion_info['champion_old_rate'],
                    'champion_info': champion_info,
                    'timestamp': current_time
                }
            
        except Exception as e:
            self.logger.error(f"计算 {symbol} 波动率时出错: {e}", exc_info=True)

    def _update_statistics(self, processed_count: int) -> None:
        """更新统计信息"""
        self.total_symbols = len(self.current_rates)
        self.data_update_count += 1
        self.last_update_time = time.time()
        
        if self.data_update_count % config.STATS_PRINT_INTERVAL == 0:
            self.logger.info(f"已处理 {self.data_update_count} 次更新, 当前监控 {self.total_symbols} 个交易对")

    def _update_top5_ranking(self) -> None:
        """更新TOP5排行 - 智能动态排名系统（冠军TTL + 实时Z-score）"""
        try:
            current_time = time.time()
            
            ranking_data = []
            for symbol in self.current_rates.keys():
                score = 0.0
                champion_info = self.champion_records.get(symbol)
                
                if champion_info and current_time - champion_info.get('champion_timestamp', 0) <= self.champion_ttl:
                    # 冠军记录仍有效
                    score = champion_info.get('max_volatility', 0)
                else:
                    # 实时计算当前 Z-score
                    score = self._calculate_current_zscore(symbol)
                
                if score > 0:
                    ranking_data.append({'symbol': symbol, 'score': score})
            
            # 使用 NumPy 进行高效排序
            if ranking_data:
                scores = np.array([item['score'] for item in ranking_data])
                symbols = np.array([item['symbol'] for item in ranking_data])
                
                # 获取排序索引（降序）
                sorted_indices = np.argsort(scores)[::-1]
                
                # 获取 TOP5
                top_count = min(config.TOP_RANKING_COUNT, len(sorted_indices))
                new_top5 = symbols[sorted_indices[:top_count]].tolist()
                
                if new_top5 != self.top5_symbols:
                    self.top5_symbols = new_top5
                    self.logger.info(f"🏆 TOP5 排名更新: {self.top5_symbols}")

        except Exception as e:
            self.logger.error(f"更新TOP5排行时出错: {e}", exc_info=True)
    
    def _calculate_current_zscore(self, symbol: str) -> float:
        """使用 Pandas 为指定交易对实时计算当前的Z-score"""
        try:
            history_series = self.rate_history.get(symbol)
            if history_series is None or len(history_series) < 3:
                return 0.0
            
            # 使用 Pandas 的高效统计方法
            historical_data = history_series.iloc[:-1]  # 排除最新数据点
            current_rate = history_series.iloc[-1]  # 最新数据点
            
            if len(historical_data) < 2:
                return 0.0
            
            moving_average = historical_data.mean()
            std_dev = historical_data.std()
            
            if pd.isna(std_dev) or std_dev < 1e-10:
                return 0.0
            
            z_score = (current_rate - moving_average) / std_dev
            return abs(z_score)
                
        except Exception as e:
            self.logger.error(f"计算 {symbol} 实时Z-score时出错: {e}")
            return 0.0
    
    def _cleanup_caches(self) -> None:
        """定期清理不活跃的交易对以防止内存泄漏"""
        try:
            current_time = time.time()
            inactive_threshold = 72 * 3600  # 72小时
            
            inactive_symbols = [
                symbol for symbol, last_seen in self.symbol_last_seen.items() 
                if current_time - last_seen > inactive_threshold
            ]
            
            if inactive_symbols:
                self.logger.info(f"清理 {len(inactive_symbols)} 个不活跃交易对...")
                for symbol in inactive_symbols:
                    # 清理所有相关数据
                    self.current_rates.pop(symbol, None)
                    self.volatility_data.pop(symbol, None)
                    self.rate_history.pop(symbol, None)
                    self.champion_records.pop(symbol, None)
                    self.symbol_last_seen.pop(symbol, None)
                
                self.logger.info(f"成功清理 {len(inactive_symbols)} 个不活跃交易对")
            
        except Exception as e:
            self.logger.error(f"清理缓存时出错: {e}")
    
    def get_top5_data(self) -> List[Dict]:
        """获取TOP5数据用于前端展示"""
        try:
            with self.data_lock:
                top5_data = []
                
                for symbol in self.top5_symbols:
                    volatility_info = self.volatility_data.get(symbol)
                    if not volatility_info:
                        continue

                    champion_info = volatility_info.get('champion_info', {})
                    rate_change = volatility_info.get('rate_change', 0.0)
                    
                    # 确定颜色类别
                    if rate_change > 0: 
                        color_class = 'text-red-400'
                    elif rate_change < 0: 
                        color_class = 'text-green-400'
                    else: 
                        color_class = 'text-gray-400'
                    
                    # 判断是否为近期冠军（15分钟内）
                    is_recent = champion_info.get('champion_age_hours', 1) < 0.25
                    
                    top5_data.append({
                        'symbol': symbol,
                        'current_rate': champion_info.get('champion_new_rate', 0.0),
                        'rate_change': rate_change,
                        'volatility': volatility_info['combined'],
                        'z_score': champion_info.get('z_score', 0.0),
                        'moving_average': champion_info.get('moving_average', 0.0),
                        'std_dev': champion_info.get('std_dev', 0.0),
                        'champion_badge': '',
                        'champion_time_display': self._format_champion_time(
                            champion_info.get('champion_timestamp', 0)
                        ),
                        'trend': 'unknown',  # 可以后续扩展趋势分析
                        'color_class': color_class,
                        'timestamp': volatility_info['timestamp'],
                    })
                
                return top5_data
                
        except Exception as e:
            self.logger.error(f"获取TOP5数据时出错: {e}", exc_info=True)
            return []
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        with self.data_lock:
            try:
                # 计算历史数据点总数 - 使用 Pandas 的高效方法
                total_history_points = sum(len(series) for series in self.rate_history.values())
                
                return {
                    'total_symbols': len(self.current_rates),
                    'data_updates': self.data_update_count,
                    'last_update': self.last_update_time,
                    'top5_count': len(self.top5_symbols),
                    'has_data': len(self.current_rates) > 0,
                    'volatility_data_count': len(self.volatility_data),
                    'history_total_points': total_history_points,
                    'champion_records_count': len(self.champion_records),
                    'cache_statistics': {
                        'pandas_series_count': len(self.rate_history),
                        'avg_series_length': total_history_points / max(len(self.rate_history), 1)
                    },
                    'quality_statistics': {
                        'active_symbols': len(self.symbol_last_seen),
                        'champion_coverage': len(self.champion_records) / max(len(self.current_rates), 1)
                    },
                }
            except Exception as e:
                self.logger.error(f"获取统计信息时出错: {e}")
                return {'has_data': False, 'total_symbols': 0}

    def get_last_update_age(self) -> Optional[float]:
        """获取最后更新时间距离现在的秒数"""
        if self.last_update_time is None:
            return None
        return time.time() - self.last_update_time

    def get_champion_summary(self) -> Dict:
        """获取冠军记录摘要"""
        try:
            with self.data_lock:
                if not self.champion_records:
                    return {'total_champions': 0, 'recent_champions': 0}
                
                current_time = time.time()
                
                # 使用 NumPy 进行高效的数组操作
                volatilities = np.array([
                    info.get('max_volatility', 0) 
                    for info in self.champion_records.values()
                ])
                
                timestamps = np.array([
                    info.get('champion_timestamp', 0) 
                    for info in self.champion_records.values()
                ])
                
                symbols = np.array(list(self.champion_records.keys()))
                
                # 找到最高波动率的冠军
                max_idx = np.argmax(volatilities)
                
                # 计算近期冠军数量（15分钟内）
                recent_mask = (current_time - timestamps) < 900  # 15分钟
                recent_champions = np.sum(recent_mask)
                
                return {
                    'total_champions': len(self.champion_records),
                    'recent_champions': int(recent_champions),
                    'max_volatility_champion': {
                        'symbol': symbols[max_idx],
                        'volatility': float(volatilities[max_idx]),
                        'age_hours': (current_time - timestamps[max_idx]) / 3600
                    }
                }
                
        except Exception as e:
            self.logger.error(f"获取冠军摘要时出错: {e}", exc_info=True)
            return {'total_champions': 0, 'recent_champions': 0}
    
    def _format_champion_time(self, timestamp: float) -> str:
        """格式化时间显示"""
        if timestamp == 0: 
            return "未知"
        
        try:
            time_diff = time.time() - timestamp
            china_tz = timezone(timedelta(hours=8))
            absolute_time = datetime.fromtimestamp(timestamp, tz=china_tz).strftime("%H:%M:%S")
            
            if time_diff < 1: 
                return f"刚刚 ({absolute_time})"
            elif time_diff < 60: 
                return f"{int(time_diff)}秒前 ({absolute_time})"
            elif time_diff < 3600: 
                return f"{int(time_diff / 60)}分钟前 ({absolute_time})"
            else:
                return f"{int(time_diff / 3600)}小时前 ({absolute_time})"
                
        except Exception as e:
            self.logger.error(f"格式化时间时出错: {e}")
            return "时间错误"

    def get_symbol_analysis(self, symbol: str) -> Optional[Dict]:
        """获取指定交易对的详细分析数据（新增功能）"""
        try:
            with self.data_lock:
                if symbol not in self.rate_history:
                    return None
                
                history_series = self.rate_history[symbol]
                if len(history_series) < 2:
                    return None
                
                # 使用 Pandas 的强大统计功能
                analysis = {
                    'symbol': symbol,
                    'current_rate': self.current_rates.get(symbol, 0.0),
                    'data_points': len(history_series),
                    'statistics': {
                        'mean': float(history_series.mean()),
                        'std': float(history_series.std()),
                        'min': float(history_series.min()),
                        'max': float(history_series.max()),
                        'median': float(history_series.median()),
                    },
                    'recent_trend': {
                        'last_5_mean': float(history_series.tail(5).mean()) if len(history_series) >= 5 else None,
                        'last_10_mean': float(history_series.tail(10).mean()) if len(history_series) >= 10 else None,
                    },
                    'champion_info': self.champion_records.get(symbol, {}),
                    'last_update': self.symbol_last_seen.get(symbol, 0)
                }
                
                return analysis
                
        except Exception as e:
            self.logger.error(f"获取 {symbol} 分析数据时出错: {e}")
            return None