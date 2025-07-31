"""
币安WebSocket客户端 - 整洁优雅版
专注于稳定连接币安WebSocket API，代码规范整洁
"""

import asyncio
import websockets
import json
import time
from typing import Optional, Callable, Any, Dict
from logger import get_logger


class BinanceWebSocketClient:
    """币安WebSocket客户端 - 整洁优雅，专注稳定性"""
    
    # 连接配置常量 - 经过精心调优的默认值
    BASE_URL = "wss://fstream.binance.com"
    PING_INTERVAL = 20
    PING_TIMEOUT = 10
    CLOSE_TIMEOUT = 10
    MAX_CONNECTION_HOURS = 23.9
    
    # 备用服务器
    BACKUP_HOSTS = [
        "fstream.binance.com",
        "fstream1.binance.com", 
        "fstream2.binance.com"
    ]
    
    # 重连间隔（指数退避）
    RECONNECT_INTERVALS = [1, 2, 5, 10, 20, 30, 60]
    
    def __init__(self, 
                 stream_path: str = "/ws/!markPrice@arr@1s", 
                 data_handler: Optional[Callable] = None):
        """
        初始化币安WebSocket客户端
        
        Args:
            stream_path: WebSocket流路径，默认为全市场标记价格流
            data_handler: 数据处理回调函数
        """
        self.logger = get_logger(__name__)
        
        # 核心配置
        self.stream_path = stream_path
        self.data_handler = data_handler
        
        # 连接状态
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.is_running = False
        self.connection_task: Optional[asyncio.Task] = None
        
        # 并发安全锁 - 保护启停操作
        self._control_lock = asyncio.Lock()
        
        # 统计信息
        self.connection_start_time = 0
        self.message_count = 0
        self.reconnect_count = 0
        self.current_host_index = 0
        
        self.logger.info("币安WebSocket客户端初始化完成")
    
    async def start(self) -> None:
        """启动WebSocket客户端 - 并发安全版本"""
        async with self._control_lock:
            if self.is_running:
                self.logger.warning("客户端已在运行中")
                return
            
            self.is_running = True
            self.connection_task = asyncio.create_task(self._connection_loop())
            self.logger.info("WebSocket客户端已启动")
    
    async def stop(self) -> None:
        """停止WebSocket客户端 - 优雅关闭版本"""
        async with self._control_lock:
            if not self.is_running:
                self.logger.info("客户端已经停止")
                return
            
            self.logger.info("正在停止WebSocket客户端...")
            
            # 第一步：通知后台任务停止
            self.is_running = False
            
            # 第二步：优雅关闭WebSocket连接
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception as e:
                    self.logger.warning(f"关闭WebSocket连接时出现异常: {e}")
                finally:
                    self.websocket = None
            
            # 第三步：优雅等待后台任务结束
            if self.connection_task:
                try:
                    # 给任务3秒时间自行退出
                    await asyncio.wait_for(self.connection_task, timeout=3.0)
                    self.logger.info("后台任务已优雅退出")
                except asyncio.TimeoutError:
                    # 超时则强制取消
                    self.logger.warning("后台任务未能及时退出，执行强制取消")
                    self.connection_task.cancel()
                    try:
                        await self.connection_task
                    except asyncio.CancelledError:
                        pass
                except Exception as e:
                    self.logger.error(f"等待后台任务退出时出现异常: {e}")
                finally:
                    self.connection_task = None
            
            self.is_connected = False
            self.logger.info("WebSocket客户端已完全停止")
    
    async def _connection_loop(self) -> None:
        """主连接循环 - 外循环负责建立连接"""
        reconnect_attempt = 0
        
        while self.is_running:
            try:
                current_url = self._get_current_url()
                self.logger.info(f"尝试连接: {current_url}")
                
                async with websockets.connect(
                    current_url,
                    ping_interval=self.PING_INTERVAL,
                    ping_timeout=self.PING_TIMEOUT,
                    close_timeout=self.CLOSE_TIMEOUT,
                    max_size=2**20,
                    compression=None
                ) as websocket:
                    self.websocket = websocket
                    self.is_connected = True
                    self.connection_start_time = time.time()
                    self.reconnect_count += 1
                    reconnect_attempt = 0
                    
                    self.logger.info(f"✓ 连接成功 (第{self.reconnect_count}次)")
                    
                    # 内循环：消息接收和24小时主动重连
                    await self._message_loop()
                        
            except Exception as e:
                self._handle_connection_error(e, reconnect_attempt)
                self._switch_to_next_host()
                reconnect_attempt += 1
                
                wait_time = self._get_reconnect_interval(reconnect_attempt)
                await asyncio.sleep(wait_time)
        
        self.logger.info("连接循环已退出")
    
    async def _message_loop(self) -> None:
        """消息接收循环 - 内循环负责接收消息和生命周期管理"""
        while self.is_connected and self.is_running:
            try:
                # 检查24小时连接限制
                if self._should_reconnect():
                    self.logger.info("主动重连：接近24小时限制，建立新连接")
                    break
                
                # 非阻塞接收消息
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    continue
                    
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("连接已关闭")
                break
            except Exception as e:
                self.logger.error(f"消息循环异常: {e}")
                break
        
        self.is_connected = False
        self.websocket = None
    
    async def _process_message(self, message: str) -> None:
        """处理接收到的消息"""
        try:
            self.message_count += 1
            data = json.loads(message)
            
            if self.data_handler:
                await self._call_handler_safely(data)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
        except Exception as e:
            self.logger.error(f"消息处理失败: {e}")
    
    async def _call_handler_safely(self, data: Any) -> None:
        """安全调用外部数据处理器 - 无阻塞版本"""
        try:
            if asyncio.iscoroutinefunction(self.data_handler):
                # 异步处理器：直接调用
                await self.data_handler(data)
            else:
                # 同步处理器：使用线程池执行，避免阻塞事件循环
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.data_handler, data)
        except Exception as e:
            self.logger.error(f"数据处理器异常: {e}", exc_info=True)
    
    def _should_reconnect(self) -> bool:
        """检查是否应该主动重连"""
        connection_duration = time.time() - self.connection_start_time
        max_seconds = self.MAX_CONNECTION_HOURS * 3600
        return connection_duration > max_seconds
    
    def _get_current_url(self) -> str:
        """获取当前WebSocket URL"""
        host = self.BACKUP_HOSTS[self.current_host_index]
        return f"wss://{host}{self.stream_path}"
    
    def _switch_to_next_host(self) -> None:
        """切换到下一个备用服务器"""
        self.current_host_index = (self.current_host_index + 1) % len(self.BACKUP_HOSTS)
        next_host = self.BACKUP_HOSTS[self.current_host_index]
        self.logger.info(f"切换到备用服务器: {next_host}")
    
    def _handle_connection_error(self, error: Exception, attempt: int) -> None:
        """处理连接错误"""
        self.is_connected = False
        self.websocket = None
        
        if not self.is_running:
            return
        
        error_type = self._classify_error(str(error))
        wait_time = self._get_reconnect_interval(attempt)
        
        self.logger.warning(
            f"连接失败: {error_type} - "
            f"将在 {wait_time} 秒后重试 (第{attempt + 1}次)"
        )
    
    def _classify_error(self, error_str: str) -> str:
        """分类错误类型"""
        error_lower = error_str.lower()
        
        if 'timeout' in error_lower:
            return "连接超时"
        elif 'refused' in error_lower:
            return "连接被拒绝"
        elif 'dns' in error_lower or 'name resolution' in error_lower:
            return "DNS解析失败"
        elif 'unreachable' in error_lower:
            return "网络不可达"
        else:
            return f"未知错误: {error_str[:50]}"
    
    def _get_reconnect_interval(self, attempt: int) -> int:
        """获取重连间隔（指数退避）"""
        if attempt < len(self.RECONNECT_INTERVALS):
            return self.RECONNECT_INTERVALS[attempt]
        return self.RECONNECT_INTERVALS[-1]
    
    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        connection_duration = 0
        if self.connection_start_time > 0:
            connection_duration = time.time() - self.connection_start_time
        
        return {
            'is_connected': self.is_connected,
            'is_running': self.is_running,
            'current_host': self.BACKUP_HOSTS[self.current_host_index],
            'connection_count': self.reconnect_count,
            'message_count': self.message_count,
            'connection_duration_hours': connection_duration / 3600,
            'current_url': self._get_current_url()
        }