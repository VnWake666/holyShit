#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户界面管理模块
负责创建和管理NiceGUI界面，处理数据展示和用户交互

主要功能:
1. 创建响应式Web界面
2. 实时更新TOP5数据显示
3. 管理界面状态和样式
4. 处理用户交互事件
"""

import time
from typing import Dict, List, Optional, Any
from nicegui import ui, app
from config import config
from logger import get_logger
import asyncio

class UIManager:
    """
    用户界面管理器 - 负责界面创建和数据展示
    
    职责:
    - 创建和管理Web界面组件
    - 实时更新数据显示
    - 处理界面样式和布局
    - 管理界面状态和交互
    """
    
    def __init__(self, data_analyzer, ws_client=None):
        """
        初始化UI管理器
        
        Args:
            data_analyzer: 数据分析器实例，用于获取显示数据
            ws_client: WebSocket客户端实例（可选）
        """
        # 获取模块专用logger
        self.logger = get_logger(__name__)
        
        # ==================== 核心组件 ====================
        self.data_analyzer = data_analyzer  # 数据分析器引用
        self.ws_client = ws_client  # WebSocket客户端引用
        
        # ==================== UI组件引用 ====================
        self.status_elements: Dict[str, Any] = {}  # 状态显示元素
        self.top5_rows: List[Dict[str, Any]] = []  # TOP5数据行元素
        self.update_timer: Optional[Any] = None  # 更新定时器
        
        # ==================== 界面状态 ====================
        self.is_initialized: bool = False  # 界面是否已初始化
        self.last_update_time: Optional[float] = None  # 最后更新时间
        self.update_count: int = 0  # 更新次数
        self.start_time: float = time.time()  # 启动时间
        
        self.logger.info("UI管理器初始化完成")
    
    def create_interface(self) -> None:
        """
        创建完整的用户界面
        
        界面结构:
        1. 页面标题和配置
        2. 系统状态信息栏
        3. TOP5数据展示区域
        4. 页面底部说明信息
        """
        try:
            # 设置页面基础配置
            self._setup_page_config()
            
            # 创建主界面布局 - 充分利用屏幕宽度
            with ui.column().classes('w-full mx-auto px-4 sm:px-6 lg:px-8 xl:px-12 2xl:px-16'):
                # 创建各个界面区域 - 状态栏已移至底部
                self._create_header()
                self._create_top5_section()
                self._create_footer()
                self._create_status_section()
            
            # 启动数据更新定时器
            self._start_update_timer()
            
            self.is_initialized = True
            self.logger.info("用户界面创建完成")
            
        except Exception as e:
            self.logger.error(f"创建用户界面时发生错误: {e}", exc_info=True)
            raise
    
    def _setup_page_config(self) -> None:
        """
        设置页面基础配置
        """
        # 启用深色模式
        ui.dark_mode().enable()
        
        # 设置页面标题
        ui.page_title(config.UI_TITLE)
        
        # 添加最小化必要CSS - 仅包含动画效果
        ui.add_head_html(self._get_minimal_css())
    
    def _get_minimal_css(self) -> str:
        """
        获取最小化的必要CSS - 基于Context7最佳实践
        包含动画效果和全局字体加粗优化，适合金融数据阅读
        """
        return """
        <style>
        /* 全局提升基础字体粗细度，使其更适合金融数据阅读 */
        body, html, .nicegui-content, .q-item__label, .q-field__label, .q-btn__content {
            font-weight: 600 !important; /* 600是'semibold'半粗体 */
        }

        /* 对于已经标记为'font-bold'的元素，让它们更粗，拉开对比 */
        .font-bold, b, strong {
            font-weight: 800 !important; /* 800是'extrabold'特粗体 */
        }

        /* 状态指示器脉冲动画 - NiceGUI暂无直接替代 */
        @keyframes status-pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.02); }
        }
        .status-pulse { animation: status-pulse 2s cubic-bezier(0.4, 0.0, 0.6, 1) infinite; }
        
        /* 呼吸动画效果 - 用于费率显示 */
        @keyframes breathing {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(1.03); }
        }
        .breathing { animation: breathing 2.5s ease-in-out infinite; }
        </style>
        """
    
    def _create_header(self) -> None:
        """
        创建页面标题区域 - 简洁设计（无标题）
        """
        # 移除所有标题，让界面更简洁专业
        pass
    
    def _create_status_section(self) -> None:
        """
        创建系统状态信息区域 - 使用Tailwind CSS毛玻璃效果
        """
        with ui.card().classes('w-full mb-8 p-6 backdrop-blur-xl bg-white/5 border border-white/10 shadow-lg rounded-3xl'):
            ui.label('📊 系统状态').classes('text-2xl font-semibold mb-4 text-green-400')
            
            with ui.row().classes('w-full justify-between items-center flex-wrap gap-6'):
                # 连接状态
                self.status_elements['connection'] = ui.label('🔗 连接状态: 初始化中...').classes(
                    'text-lg font-medium status-pulse'
                )
                
                # 数据统计
                self.status_elements['data_count'] = ui.label('📈 监控交易对: 0').classes(
                    'text-lg font-medium font-mono'
                )
                
                # 更新时间
                self.status_elements['last_update'] = ui.label('⏰ 最后更新: --').classes(
                    'text-lg font-medium'
                )
                
                # 系统运行时间
                self.status_elements['uptime'] = ui.label('⏱️ 运行时间: 0秒').classes(
                    'text-lg font-medium font-mono'
                )
    
    def _create_top5_section(self) -> None:
        """
        创建TOP5数据展示区域 - 双列布局苹果风格
        """
        # 使用响应式双列布局 - 充分拉伸利用空间
        with ui.row().classes('w-full gap-4 sm:gap-6 lg:gap-8 xl:gap-12 mb-8'):
            # 左侧：资金费率波动TOP5排行榜 - 自适应宽度
            with ui.card().classes('flex-1 p-4 sm:p-6 lg:p-8 xl:p-10 backdrop-blur-xl bg-white/5 border border-white/10 shadow-lg rounded-3xl'):
                # 区域标题
                ui.label('资金费率波动TOP5排行榜').classes(
                    'text-2xl md:text-3xl font-bold text-yellow-400 mb-6'
                )
                
                # 创建表格头部
                self._create_funding_rate_header()
                
                # 创建数据行
                self._create_funding_rate_rows()
            
            # 右侧：成交额涨幅排行榜 - 自适应宽度
            with ui.card().classes('flex-1 p-4 sm:p-6 lg:p-8 xl:p-10 backdrop-blur-xl bg-white/5 border border-white/10 shadow-lg rounded-3xl'):
                # 区域标题
                ui.label('📈 成交额涨幅排行榜').classes(
                    'text-2xl md:text-3xl font-bold text-green-400 mb-6'
                )
                
                # 创建成交额涨幅表格
                self._create_volume_change_section()
    
    def _create_funding_rate_header(self) -> None:
        """
        创建资金费率表格头部 - V8版: 合并交易对和费率列
        """
        with ui.row().classes('w-full mb-4 pb-3 border-b border-gray-600'):
            ui.label('排名').classes('w-16 text-center font-semibold text-gray-300 text-base')
            ui.label('交易对 / 费率').classes('w-48 text-center font-semibold text-gray-300 text-base') # 增加宽度
            ui.label('波动率').classes('w-28 text-center font-semibold text-gray-300 text-base')
            ui.label('波动时间').classes('flex-1 text-center font-semibold text-gray-300 text-base')
    
    def _create_funding_rate_rows(self) -> None:
        """
        创建资金费率TOP5数据行 - V8版: 合并交易对和费率列
        """
        for i in range(config.TOP_RANKING_COUNT):
            with ui.row().classes('w-full py-4 border-b border-gray-700 hover:bg-blue-500/8 hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 items-center'): # 垂直居中
                # 排名列
                rank_label = ui.label(f'#{i+1}').classes(
                    'w-16 text-center text-2xl font-bold text-blue-400'
                )
                
                # 交易对/费率组合列
                with ui.column().classes('w-48 items-center gap-0'): # 增加宽度，移除间距，水平居中
                    symbol_label = ui.label('等待数据...').classes('text-white leading-tight') # leading-tight 减少行高
                    rate_label = ui.label('').classes(
                        'text-base text-gray-400 font-mono breathing'
                    )

                # 波动率列
                volatility_label = ui.label('').classes(
                    'w-28 text-center'
                )
                
                # 波动时间列
                time_label = ui.label('').classes(
                    'flex-1 text-center text-base text-cyan-400 font-medium'
                )
                
                # 保存行元素引用
                self.top5_rows.append({
                    'rank': rank_label,
                    'symbol': symbol_label,
                    'rate': rate_label,
                    'volatility': volatility_label,
                    'time': time_label
                })
    
    def _create_volume_change_section(self) -> None:
        """
        创建成交额涨幅排行榜区域 - 苹果风格
        """
        # 创建成交额涨幅表格头部
        with ui.row().classes('w-full mb-4 pb-3 border-b border-gray-600'):
            ui.label('排名').classes('w-16 text-center font-semibold text-gray-300 text-base')
            ui.label('交易对').classes('w-28 font-semibold text-gray-300 text-base')
            ui.label('24h成交额').classes('w-32 font-semibold text-gray-300 text-base')
            ui.label('涨幅').classes('w-28 font-semibold text-gray-300 text-base')
            ui.label('更新时间').classes('flex-1 font-semibold text-gray-300 text-base')
        
        # 创建成交额涨幅数据行（空状态）
        for i in range(config.TOP_RANKING_COUNT):
            with ui.row().classes('w-full py-4 border-b border-gray-700 hover:bg-blue-500/8 hover:-translate-y-0.5 hover:shadow-md transition-all duration-200'):
                # 排名列
                ui.label(f'#{i+1}').classes(
                    'w-16 text-center text-2xl font-bold text-purple-400'
                )
                
                # 交易对列
                ui.label('待开发...').classes(
                    'w-28 text-lg font-semibold text-gray-500'
                )
                
                # 24h成交额列
                ui.label('').classes(
                    'w-32 text-lg text-gray-500 font-mono'
                )
                
                # 涨幅列
                ui.label('').classes(
                    'w-28 text-lg text-gray-500 font-mono'
                )
                
                # 更新时间列
                ui.label('').classes(
                    'flex-1 text-base text-gray-500'
                )
        
        # 功能开发提示（移到底部，保持高度一致）
        with ui.row().classes('w-full mt-6 justify-center'):
            with ui.row().classes('items-center gap-3 px-4 py-2 backdrop-blur-sm bg-white/10 border border-white/20 hover:bg-white/15 rounded-full transition-all duration-200'):
                ui.icon('construction', size='sm').classes('text-amber-400')
                ui.label('功能开发中').classes('text-base text-amber-400 font-medium')
    
    def _create_footer(self) -> None:
        """
        创建自选池功能区域 - 苹果风格
        """
        with ui.card().classes('w-full mt-10 p-4 sm:p-6 lg:p-8 xl:p-10 backdrop-blur-xl bg-white/5 border border-white/10 shadow-lg rounded-3xl'):
            ui.label('⭐ 自选池').classes('text-2xl font-bold mb-6 text-blue-400')
            
            # 自选池功能提示
            with ui.row().classes('w-full mb-6'):
                ui.icon('info').classes('text-cyan-400 mr-3')
                ui.label('自选池功能正在开发中，敬请期待...').classes('text-lg text-gray-300 font-medium')
            
            # 预留的功能区域布局
            with ui.column().classes('w-full gap-6'):
                # 添加交易对区域
                with ui.row().classes('w-full items-center gap-4'):
                    ui.label('添加交易对:').classes('text-lg text-gray-300 w-24 font-medium')
                    ui.input(placeholder='输入交易对名称，如: BTCUSDT').classes('flex-1 text-lg').props('outlined dense')
                    ui.button('添加', icon='add').classes('backdrop-blur-sm bg-white/10 border border-white/20 hover:bg-white/15 text-lg px-6 py-2 rounded-lg transition-all duration-200').props('dense')
                
                # 自选列表区域
                with ui.column().classes('w-full'):
                    ui.label('我的自选:').classes('text-lg text-gray-300 mb-4 font-medium')
                    
                    # 空状态提示
                    with ui.row().classes('w-full justify-center py-12'):
                        with ui.column().classes('items-center gap-4'):
                            ui.icon('star_border', size='4em').classes('text-gray-500')
                            ui.label('暂无自选交易对').classes('text-xl text-gray-500 font-medium')
                            ui.label('添加您关注的交易对到自选池').classes('text-base text-gray-600')
                
                # 快捷操作区域
                with ui.row().classes('w-full gap-4 mt-6'):
                    ui.label('快捷添加:').classes('text-lg text-gray-300 font-medium')
                    ui.button('热门币种', icon='trending_up').classes('backdrop-blur-sm bg-white/10 border border-white/20 hover:bg-white/15 text-base px-4 py-2 rounded-lg transition-all duration-200').props('dense')
                    ui.button('主流币', icon='currency_bitcoin').classes('backdrop-blur-sm bg-white/10 border border-white/20 hover:bg-white/15 text-base px-4 py-2 rounded-lg transition-all duration-200').props('dense')
                    ui.button('DeFi', icon='account_balance').classes('backdrop-blur-sm bg-white/10 border border-white/20 hover:bg-white/15 text-base px-4 py-2 rounded-lg transition-all duration-200').props('dense')
    
    def _start_update_timer(self) -> None:
        """
        启动数据更新定时器 - 优化更新频率
        """
        try:
            # 优化：降低更新频率到2秒，减少性能消耗
            update_interval = max(config.UI_UPDATE_INTERVAL, 2.0)
            self.update_timer = ui.timer(
                interval=update_interval,
                callback=self.update_display
            )
            self.logger.info(f"数据更新定时器已启动 - 间隔: {update_interval}秒")
            
            # 注册WebSocket启动钩子 - 基于Context7最佳实践
            if self.ws_client:
                app.on_startup(self._startup_websocket_client)
                self.logger.info("WebSocket启动钩子已注册")
            
        except Exception as e:
            self.logger.error(f"启动更新定时器失败: {e}", exc_info=True)
    
    async def _startup_websocket_client(self) -> None:
        """
        在NiceGUI启动时异步启动WebSocket客户端
        基于Context7最佳实践的app.on_startup钩子实现
        """
        try:
            if self.ws_client:
                self.logger.info("🚀 在NiceGUI事件循环中启动WebSocket客户端...")
                
                # 异步启动WebSocket客户端
                await self.ws_client.start()
                self.logger.info("✅ WebSocket客户端启动完成")
                
                # 启动渐进式状态验证
                ui.timer(2.0, self._verify_websocket_connection, once=True)
                
            else:
                self.logger.warning("⚠️ WebSocket客户端实例未设置")
        except Exception as e:
            self.logger.error(f"❌ 启动WebSocket客户端时发生错误: {e}", exc_info=True)
    
    def _verify_websocket_connection(self) -> None:
        """
        验证WebSocket连接状态（渐进式检查）
        基于Context7 websockets最佳实践实现
        """
        try:
            if not self.ws_client:
                return
            
            # 获取详细连接状态
            connection_status = self._get_websocket_connection_status()
            
            if connection_status == "已连接":
                self.logger.info("✓ WebSocket连接验证成功")
            elif connection_status == "连接中":
                self.logger.info("WebSocket正在连接中，继续等待...")
                # 继续等待，再次检查
                ui.timer(2.0, self._verify_websocket_connection, once=True)
            elif connection_status == "已断开":
                self.logger.warning("WebSocket连接已断开，但可能正在重连...")
            else:
                self.logger.info(f"WebSocket状态: {connection_status}")
                
        except Exception as e:
            self.logger.error(f"验证WebSocket连接时发生错误: {e}", exc_info=True)
    
    def _get_websocket_connection_status(self) -> str:
        """
        获取详细的WebSocket连接状态
        基于Context7 websockets.connection.Connection API实现
        
        Returns:
            str: 连接状态描述
        """
        try:
            if not self.ws_client:
                return "未初始化"
            
            # 检查WebSocket连接对象
            if hasattr(self.ws_client, 'websocket') and self.ws_client.websocket:
                # 检查连接是否关闭
                if hasattr(self.ws_client.websocket, 'closed'):
                    if self.ws_client.websocket.closed:
                        return "已断开"
                    else:
                        return "已连接"
                else:
                    # 检查连接状态属性
                    if hasattr(self.ws_client.websocket, 'state'):
                        state = str(self.ws_client.websocket.state)
                        if 'OPEN' in state:
                            return "已连接"
                        elif 'CONNECTING' in state:
                            return "连接中"
                        elif 'CLOSING' in state:
                            return "断开中"
                        elif 'CLOSED' in state:
                            return "已断开"
                        else:
                            return f"状态: {state}"
                    else:
                        return "已连接"  # 假设连接正常
            
            # 检查连接任务状态
            elif hasattr(self.ws_client, '_connecting') and self.ws_client._connecting:
                return "连接中"
            elif hasattr(self.ws_client, '_connection_task'):
                if self.ws_client._connection_task and not self.ws_client._connection_task.done():
                    return "连接中"
                elif self.ws_client._connection_task and self.ws_client._connection_task.done():
                    if self.ws_client._connection_task.exception():
                        return "连接失败"
                    else:
                        return "已连接"
            
            return "未启动"
            
        except Exception as e:
            self.logger.error(f"获取WebSocket状态时出错: {e}", exc_info=True)
            return "状态未知"
    
    def update_display(self) -> None:
        """
        更新界面显示数据
        
        更新内容:
        1. 系统状态信息
        2. TOP5排行数据
        3. 运行时间统计
        """
        try:
            self.update_count += 1
            self.last_update_time = time.time()
            
            # 更新系统状态
            self._update_status_display()
            
            # 更新TOP5数据
            self._update_top5_display()
            
            # 定期输出更新统计
            if self.update_count % config.STATS_PRINT_INTERVAL == 0:
                self.logger.debug(f"界面更新统计 - 更新次数: {self.update_count}")
                
        except Exception as e:
            self.logger.error(f"更新界面显示时发生错误: {e}", exc_info=True)
    
    def _update_status_display(self) -> None:
        """
        更新系统状态显示
        """
        try:
            # 获取分析器统计信息
            stats = self.data_analyzer.get_statistics()
            
            # 更新连接状态
            if stats['has_data']:
                self.status_elements['connection'].text = "🔗 连接状态: ✅ 数据连接正常"
                self.status_elements['connection'].classes(
                    replace='text-lg font-medium text-green-400'
                )
            else:
                self.status_elements['connection'].text = "🔗 连接状态: ⚠️ 等待数据连接"
                self.status_elements['connection'].classes(
                    replace='text-lg font-medium text-yellow-400 status-pulse'
                )
            
            # 更新数据统计
            self.status_elements['data_count'].text = f"📈 监控交易对: {stats['total_symbols']}"
            
            # 更新最后更新时间
            if stats['last_update']:
                update_time = time.strftime('%H:%M:%S', time.localtime(stats['last_update']))
                self.status_elements['last_update'].text = f"⏰ 最后更新: {update_time}"
            else:
                self.status_elements['last_update'].text = "⏰ 最后更新: --"
            
            # 更新运行时间
            uptime = int(time.time() - self.start_time)
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                uptime_text = f"⏱️ 运行时间: {hours}小时{minutes}分{seconds}秒"
            elif minutes > 0:
                uptime_text = f"⏱️ 运行时间: {minutes}分{seconds}秒"
            else:
                uptime_text = f"⏱️ 运行时间: {seconds}秒"
            
            self.status_elements['uptime'].text = uptime_text
            
        except Exception as e:
            self.logger.error(f"更新状态显示时出错: {e}", exc_info=True)
    
    def _update_top5_display(self) -> None:
        """
        更新TOP5数据显示 - V9版: 增强错误处理和数据验证
        """
        try:
            # 获取TOP5数据
            top5_data = self.data_analyzer.get_top5_data()
            
            # 验证数据有效性
            if not isinstance(top5_data, list):
                self.logger.warning(f"TOP5数据格式异常: {type(top5_data)}")
                top5_data = []
            
            # 更新每一行数据
            for i in range(len(self.top5_rows)):
                row_elements = self.top5_rows[i]
                
                if i < len(top5_data):
                    # 有数据的行
                    data = top5_data[i]
                    # 验证单行数据完整性
                    if self._validate_row_data(data):
                        self._update_data_row(row_elements, data, i + 1)
                    else:
                        self.logger.warning(f"第{i+1}行数据不完整: {data}")
                        self._clear_data_row(row_elements, i + 1)
                else:
                    # 无数据的行
                    self._clear_data_row(row_elements, i + 1)
                    
        except Exception as e:
            self.logger.error(f"更新TOP5显示时出错: {e}", exc_info=True)
            # 发生错误时清空所有行显示
            for i, row_elements in enumerate(self.top5_rows):
                self._clear_data_row(row_elements, i + 1)
    
    def _format_time_display(self, time_text: str) -> str:
        """
        格式化时间显示，去掉秒数部分
        
        Args:
            time_text: 原始时间文本，格式如 "15分钟前 (14:32:05)"
            
        Returns:
            str: 格式化后的时间文本，格式如 "15分钟前 (14:32)"
        """
        try:
            # 使用正则表达式去掉时间中的秒数部分
            import re
            # 匹配格式：(HH:MM:SS) 并替换为 (HH:MM)
            pattern = r'\((\d{2}):(\d{2}):\d{2}\)'
            replacement = r'(\1:\2)'
            formatted_text = re.sub(pattern, replacement, time_text)
            return formatted_text
        except Exception as e:
            self.logger.debug(f"格式化时间显示时出错: {e}")
            # 如果格式化失败，返回原始文本
            return time_text
    
    def _validate_row_data(self, data: Dict[str, Any]) -> bool:
        """
        验证单行数据的完整性
        
        Args:
            data: 数据字典
            
        Returns:
            bool: 数据是否有效
        """
        required_fields = ['symbol', 'current_rate', 'z_score']
        
        if not isinstance(data, dict):
            return False
            
        for field in required_fields:
            if field not in data:
                self.logger.debug(f"缺少必需字段: {field}")
                return False
                
        return True
    
    def _update_data_row(self, row_elements: Dict[str, Any], data: Dict[str, Any], rank: int) -> None:
        """
        更新单行数据显示 - V9版: 适配新的business_core.py数据结构
        
        Args:
            row_elements: 行UI元素字典
            data: 数据字典
            rank: 排名
        """
        try:
            # 更新排名
            row_elements['rank'].text = f"#{rank}"
            
            # 更新交易对名称并应用Tailwind样式
            symbol_display = data['symbol'].replace('USDT', '') if data['symbol'].endswith('USDT') else data['symbol']
            row_elements['symbol'].text = symbol_display
            
            # 根据排名应用不同的Tailwind CSS类
            if rank == 1:
                row_elements['symbol'].classes(
                    replace='text-4xl font-extrabold text-white leading-tight'
                )
            elif rank == 2:
                row_elements['symbol'].classes(
                    replace='text-3xl font-extrabold text-white leading-tight'
                )
            elif rank == 3:
                row_elements['symbol'].classes(
                    replace='text-2xl font-extrabold text-white leading-tight'
                )
            else:
                row_elements['symbol'].classes(
                    replace='text-xl font-bold text-white leading-tight'
                )

            # 更新当前费率
            rate_text = f"{data['current_rate']:.6f}%"
            row_elements['rate'].text = rate_text
            
            # 动态生成方向符号 - 适配新的数据结构
            z_score = data.get('z_score', 0.0)
            rate_change = data.get('rate_change', 0.0)
            
            # 根据rate_change确定+/-符号
            if rate_change > 0:
                sign = '+'
            elif rate_change < 0:
                sign = '-'
            else:
                sign = '' # 无变化时不显示符号
            
            # 更新波动率文本 - 使用Z-score的绝对值作为波动率，并防止换行
            volatility_value = abs(z_score)
            volatility_text = f"{sign}{volatility_value:.2f}"
            row_elements['volatility'].text = volatility_text
            
            # 应用波动率Tailwind样式 - 根据颜色类别应用相应的Tailwind颜色类，保持宽度和居中对齐
            color_class = data.get('color_class', 'text-yellow-400')
            if color_class == 'text-red-400':
                row_elements['volatility'].classes(
                    replace='w-28 text-center text-xl font-bold text-red-400'
                )
            elif color_class == 'text-green-400':
                row_elements['volatility'].classes(
                    replace='w-28 text-center text-xl font-bold text-green-400'
                )
            else:
                row_elements['volatility'].classes(
                    replace='w-28 text-center text-xl font-bold text-yellow-400'
                )

            # 更新波动时间，保持宽度和居中对齐
            time_text = data.get('champion_time_display', '时间未知')
            # 优化时间显示：去掉秒数，只保留时:分
            time_text = self._format_time_display(time_text)
            row_elements['time'].text = time_text
            row_elements['time'].classes(
                replace='flex-1 text-center text-base text-cyan-400 font-medium'
            )
            
        except Exception as e:
            self.logger.error(f"更新数据行时出错: {e}", exc_info=True)
            # 发生错误时显示调试信息
            self.logger.debug(f"数据内容: {data}")
    
    def _clear_data_row(self, row_elements: Dict[str, Any], rank: int) -> None:
        """
        清空数据行显示 - V8版: 适应合并后的UI结构
        
        Args:
            row_elements: 行UI元素字典
            rank: 排名
        """
        try:
            row_elements['rank'].text = f"#{rank}"
            row_elements['symbol'].text = "等待数据..."
            
            # 应用默认的Tailwind样式
            row_elements['symbol'].classes(
                replace='text-xl font-bold text-white leading-tight'
            )
            
            row_elements['rate'].text = ""
            row_elements['volatility'].text = ""
            
            # 应用默认的波动率样式，保持宽度和居中对齐
            row_elements['volatility'].classes(
                replace='w-28 text-center text-xl font-bold text-yellow-400'
            )
            
            row_elements['time'].text = ""
            # 应用默认的时间样式，保持宽度和居中对齐
            row_elements['time'].classes(
                replace='flex-1 text-center text-base text-cyan-400 font-medium'
            )
            
        except Exception as e:
            self.logger.error(f"清空数据行时出错: {e}", exc_info=True)
    
    def stop_updates(self) -> None:
        """
        停止界面更新
        """
        try:
            if self.update_timer:
                self.update_timer.cancel()
                self.update_timer = None
                self.logger.info("界面更新定时器已停止")
                
        except Exception as e:
            self.logger.error(f"停止界面更新时出错: {e}", exc_info=True)
    
    def run(self, host: str = 'localhost', port: int = 8080, show: bool = True) -> None:
        """
        启动UI界面
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
            show: 是否自动打开浏览器
        """
        try:
            self.logger.info(f"启动UI界面 - {host}:{port}")
            
            # 创建界面
            self.create_interface()
            
            # 启动NiceGUI服务器
            ui.run(
                host=host,
                port=port,
                title=config.UI_TITLE,
                dark=True,
                show=show,
                reload=False
            )
            
        except Exception as e:
            self.logger.error(f"启动UI界面失败: {e}", exc_info=True)
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取UI管理器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'is_initialized': self.is_initialized,
            'update_count': self.update_count,
            'last_update_time': self.last_update_time,
            'uptime': time.time() - self.start_time,
            'timer_active': self.update_timer is not None,
            'top5_rows_count': len(self.top5_rows),
            'status_elements_count': len(self.status_elements)
        }

# 独立运行测试代码
if __name__ == "__main__":
    # 创建模拟数据分析器
    class MockAnalyzer:
        def __init__(self):
            self.start_time = time.time()
            
        def get_statistics(self):
            return {
                'total_symbols': 498,
                'data_updates': 100,
                'last_update': time.time(),
                'has_data': True
            }
        
        def get_top5_data(self):
            return [
                {
                    'symbol': 'BTCUSDT',
                    'current_rate': 0.001234,
                    'volatility': 1.23,
                    'direction': '上涨',
                    'direction_symbol': '+',
                    'color_class': 'text-red-400'    # 红涨
                },
                {
                    'symbol': 'ETHUSDT', 
                    'current_rate': -0.000567,
                    'volatility': 0.89,
                    'direction': '下跌',
                    'direction_symbol': '-',
                    'color_class': 'text-green-400'  # 绿跌
                }
            ]
    
    # 创建UI管理器并测试
    analyzer = MockAnalyzer()
    ui_manager = UIManager(analyzer)
    
    try:
        # 创建界面
        ui_manager.create_interface()
        
        print("UI管理器测试启动，访问 http://localhost:8080")
        print("按 Ctrl+C 停止测试")
        
        # 启动NiceGUI
        ui.run(
            host='localhost',
            port=8080,
            title='UI管理器测试',
            dark=True,
            show=True
        )
        
    except KeyboardInterrupt:
        print("用户中断测试")
    finally:
        ui_manager.stop_updates()
        print("UI管理器测试完成")
