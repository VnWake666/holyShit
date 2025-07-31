#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
币安资金费率波动TOP5监控工具 - 主程序入口
整合所有模块，提供统一的程序启动和管理功能

主要功能:
1. 环境检测和依赖管理
2. 模块初始化和协调
3. 程序生命周期管理
4. 异常处理和资源清理
"""

import subprocess
import sys
import importlib
import time
import signal
import atexit
import socket
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple

# 导入NiceGUI
from nicegui import ui

# 设置Windows控制台编码，避免中文乱码
if sys.platform.startswith('win'):
    try:
        # 只设置Python的输出编码，不执行系统命令
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
    except:
        pass  # 如果设置失败，继续运行


class PortManager:
    """
    智能端口管理器
    基于Context7 Python socket最佳实践实现
    
    主要功能:
    1. 智能端口可用性检测
    2. 自动寻找可用端口
    3. 端口冲突解决
    4. 端口占用进程识别
    """
    
    def __init__(self):
        """初始化端口管理器"""
        self.logger = None
        try:
            from logger import get_logger
            self.logger = get_logger(__name__)
        except:
            # 如果logger模块不可用，使用print作为备选
            pass
        
    def _log_info(self, message: str):
        """内部日志方法"""
        if self.logger:
            self.logger.info(message)
        else:
            print(f"[INFO] {message}")
    
    def _log_debug(self, message: str):
        """内部调试日志方法"""
        if self.logger:
            self.logger.debug(message)
    
    def _log_warning(self, message: str):
        """内部警告日志方法"""
        if self.logger:
            self.logger.warning(message)
        else:
            print(f"[WARNING] {message}")
    
    def _log_error(self, message: str):
        """内部错误日志方法"""
        if self.logger:
            self.logger.error(message)
        else:
            print(f"[ERROR] {message}")
        
    def is_port_available(self, host: str, port: int) -> bool:
        """
        检查指定端口是否可用
        基于Context7 socket.bind()最佳实践
        
        Args:
            host: 主机地址
            port: 端口号
            
        Returns:
            bool: 端口是否可用
        """
        try:
            # 基于Context7最佳实践：使用临时socket测试端口可用性
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                # 设置SO_REUSEADDR避免TIME_WAIT状态影响
                test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # 尝试绑定端口
                test_socket.bind((host, port))
                return True
                
        except OSError as e:
            # 端口被占用或其他网络错误
            self._log_debug(f"端口 {host}:{port} 不可用: {e}")
            return False
        except Exception as e:
            self._log_error(f"检查端口可用性时发生错误: {e}")
            return False
    
    def find_available_port(self, host: str, preferred_port: int, 
                          port_range: int = 100) -> Optional[int]:
        """
        智能寻找可用端口
        基于Context7 find_unused_port最佳实践
        
        Args:
            host: 主机地址
            preferred_port: 首选端口
            port_range: 搜索范围
            
        Returns:
            Optional[int]: 可用端口号，如果找不到则返回None
        """
        try:
            # 首先检查首选端口
            if self.is_port_available(host, preferred_port):
                self._log_info(f"✅ 首选端口 {preferred_port} 可用")
                return preferred_port
            
            self._log_warning(f"⚠️  端口{preferred_port}被占用，正在寻找替代端口...")
            
            # 搜索可用端口
            for offset in range(1, port_range + 1):
                candidate_port = preferred_port + offset
                
                # 跳过系统保留端口和常用端口
                if self._is_reserved_port(candidate_port):
                    continue
                
                if self.is_port_available(host, candidate_port):
                    self._log_info(f"✅ 找到可用端口: {candidate_port}")
                    return candidate_port
            
            # 如果向上搜索失败，尝试向下搜索
            for offset in range(1, min(preferred_port - 1024, port_range) + 1):
                candidate_port = preferred_port - offset
                
                if candidate_port < 1024:  # 避免系统端口
                    break
                    
                if self._is_reserved_port(candidate_port):
                    continue
                
                if self.is_port_available(host, candidate_port):
                    self._log_info(f"✅ 找到可用端口: {candidate_port}")
                    return candidate_port
            
            self._log_error(f"❌ 在范围内未找到可用端口 (基准: {preferred_port}, 范围: ±{port_range})")
            return None
            
        except Exception as e:
            self._log_error(f"寻找可用端口时发生错误: {e}")
            return None
    
    def _is_reserved_port(self, port: int) -> bool:
        """
        检查是否为保留端口
        
        Args:
            port: 端口号
            
        Returns:
            bool: 是否为保留端口
        """
        # 系统保留端口
        if port < 1024:
            return True
        
        # 常用服务端口，避免冲突
        reserved_ports = {
            3306,   # MySQL
            5432,   # PostgreSQL
            6379,   # Redis
            27017,  # MongoDB
            9200,   # Elasticsearch
            5672,   # RabbitMQ
            8000,   # 常用开发端口
            8888,   # Jupyter
            9000,   # 常用开发端口
        }
        
        return port in reserved_ports
    
    def get_port_info(self, port: int) -> List[str]:
        """
        获取端口占用信息
        
        Args:
            port: 端口号
            
        Returns:
            List[str]: 占用进程信息列表
        """
        try:
            if sys.platform.startswith('win'):
                return self._get_port_info_windows(port)
            else:
                return self._get_port_info_unix(port)
        except Exception as e:
            self._log_error(f"获取端口信息时发生错误: {e}")
            return [f"无法获取端口信息: {e}"]
    
    def _get_port_info_windows(self, port: int) -> List[str]:
        """
        获取Windows系统端口占用信息
        
        Args:
            port: 端口号
            
        Returns:
            List[str]: 占用进程信息列表
        """
        try:
            # 使用netstat命令查找端口占用
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return ["无法执行netstat命令"]
            
            port_info = []
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            # 获取进程名称
                            tasklist_result = subprocess.run(
                                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV'],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            
                            if tasklist_result.returncode == 0:
                                lines = tasklist_result.stdout.strip().split('\n')
                                if len(lines) > 1:
                                    # 解析CSV格式的输出
                                    process_line = lines[1].replace('"', '').split(',')
                                    if len(process_line) >= 2:
                                        process_name = process_line[0]
                                        port_info.append(f"{process_name} (PID: {pid})")
                                    else:
                                        port_info.append(f"进程 PID: {pid}")
                                else:
                                    port_info.append(f"进程 PID: {pid}")
                            else:
                                port_info.append(f"进程 PID: {pid}")
                                
                        except subprocess.TimeoutExpired:
                            port_info.append(f"进程 PID: {pid} (查询超时)")
                        except Exception:
                            port_info.append(f"进程 PID: {pid}")
            
            return port_info if port_info else ["端口未被占用"]
            
        except subprocess.TimeoutExpired:
            return ["查询端口信息超时"]
        except Exception as e:
            return [f"查询失败: {e}"]
    
    def _get_port_info_unix(self, port: int) -> List[str]:
        """
        获取Unix/Linux系统端口占用信息
        
        Args:
            port: 端口号
            
        Returns:
            List[str]: 占用进程信息列表
        """
        try:
            # 使用lsof命令查找端口占用
            result = subprocess.run(
                ['lsof', '-i', f':{port}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return ["端口未被占用或无法查询"]
            
            port_info = []
            for line in result.stdout.split('\n')[1:]:  # 跳过标题行
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        process_name = parts[0]
                        pid = parts[1]
                        port_info.append(f"{process_name} (PID: {pid})")
            
            return port_info if port_info else ["端口未被占用"]
            
        except subprocess.TimeoutExpired:
            return ["查询端口信息超时"]
        except FileNotFoundError:
            # lsof命令不存在，尝试使用netstat
            try:
                result = subprocess.run(
                    ['netstat', '-tlnp'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                port_info = []
                for line in result.stdout.split('\n'):
                    if f':{port}' in line:
                        port_info.append(line.strip())
                
                return port_info if port_info else ["端口未被占用"]
                
            except Exception:
                return ["无法查询端口信息"]
        except Exception as e:
            return [f"查询失败: {e}"]
    
    def find_unused_port_ephemeral(self, host: str = 'localhost') -> int:
        """
        使用系统临时端口机制寻找可用端口
        基于Context7 find_unused_port最佳实践
        
        Args:
            host: 主机地址
            
        Returns:
            int: 可用的临时端口号
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # 绑定到端口0，让系统自动分配可用端口
                s.bind((host, 0))
                # 获取系统分配的端口号
                _, port = s.getsockname()
                self._log_debug(f"系统分配的临时端口: {port}")
                return port
                
        except Exception as e:
            self._log_error(f"获取临时端口失败: {e}")
            # 回退到默认端口范围
            return self.find_available_port(host, 8080, 100) or 8080
    
    def check_port_with_details(self, host: str, port: int) -> Tuple[bool, List[str]]:
        """
        详细检查端口状态
        
        Args:
            host: 主机地址
            port: 端口号
            
        Returns:
            Tuple[bool, List[str]]: (是否可用, 详细信息列表)
        """
        is_available = self.is_port_available(host, port)
        
        if is_available:
            return True, [f"✅ 端口 {host}:{port} 可用"]
        else:
            port_info = self.get_port_info(port)
            details = [f"❌ 端口 {host}:{port} 被占用:"]
            details.extend([f"   - {info}" for info in port_info])
            return False, details

class ApplicationManager:
    """
    应用程序管理器 - 负责整个应用的生命周期管理
    
    职责:
    - 环境检测和依赖安装
    - 模块初始化和协调
    - 程序启动和停止
    - 异常处理和资源清理
    """
    
    def __init__(self):
        """初始化应用管理器"""
        # 核心组件实例
        self.analyzer: Optional[object] = None
        self.ws_client: Optional[object] = None
        self.ui_manager: Optional[object] = None
        
        # 运行状态
        self.is_running: bool = False
        self.start_time: Optional[float] = None
        
        # 注册清理函数
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def check_and_install_dependencies(self) -> bool:
        """
        检查并自动安装所需依赖包
        基于Context7最佳实践，从requirements.txt读取依赖
        
        Returns:
            bool: 依赖检查是否成功
        """
        print("正在检查依赖包...")
        
        try:
            # 包名到模块名的映射表 - 解决"身份证名"与"常用名"不一致的问题
            PACKAGE_TO_MODULE_MAP = {
                'websocket-client': 'websocket',
                'Pillow': 'PIL',
                'beautifulsoup4': 'bs4',
                'PyYAML': 'yaml',
                'python-dateutil': 'dateutil',
            }
            
            # 基于Context7最佳实践：从requirements.txt读取依赖
            requirements_file = Path(__file__).parent / 'requirements.txt'
            required_packages = self._parse_requirements_file(requirements_file)
            
            if not required_packages:
                print("[警告] 未找到requirements.txt或文件为空，使用默认依赖列表")
                # 回退到硬编码依赖列表
                required_packages = {
                    'nicegui': 'nicegui>=1.4.0',
                    'websockets': 'websockets>=11.0',
                }
            
            # 内置库（无需安装）
            builtin_modules = ['asyncio', 'json', 'threading', 'time', 'typing']
            
            # 检查并安装第三方包
            for package, version_spec in required_packages.items():
                # 使用映射表获取正确的模块名
                module_name = PACKAGE_TO_MODULE_MAP.get(package, package)
                
                try:
                    importlib.import_module(module_name)
                    print(f"[✓] {package} 已安装")
                except ImportError:
                    print(f"[!] 正在安装 {package}...")
                    try:
                        subprocess.check_call([
                            sys.executable, '-m', 'pip', 'install', 
                            version_spec, '--quiet'
                        ])
                        print(f"[✓] {package} 安装成功")
                    except subprocess.CalledProcessError as e:
                        print(f"[✗] {package} 安装失败: {e}")
                        return False
            
            # 检查内置库
            for module in builtin_modules:
                try:
                    importlib.import_module(module)
                except ImportError as e:
                    print(f"[✗] 内置模块 {module} 不可用: {e}")
                    return False
            
            print("所有依赖包检查完成！")
            return True
            
        except Exception as e:
            print(f"依赖检查过程中发生错误: {e}")
            return False
    
    def _parse_requirements_file(self, requirements_path: Path) -> dict:
        """
        解析requirements.txt文件
        基于Context7最佳实践实现
        
        Args:
            requirements_path: requirements.txt文件路径
            
        Returns:
            dict: 包名到版本规范的映射
        """
        requirements = {}
        
        try:
            if not requirements_path.exists():
                return requirements
            
            with open(requirements_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # 去除空白字符
                    line = line.strip()
                    
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析包规范
                    try:
                        # 基本格式：package>=version 或 package==version
                        if '>=' in line:
                            package, version = line.split('>=', 1)
                            package = package.strip()
                            version = version.strip()
                            requirements[package] = f"{package}>={version}"
                        elif '==' in line:
                            package, version = line.split('==', 1)
                            package = package.strip()
                            version = version.strip()
                            requirements[package] = f"{package}=={version}"
                        elif '>' in line:
                            package, version = line.split('>', 1)
                            package = package.strip()
                            version = version.strip()
                            requirements[package] = f"{package}>{version}"
                        else:
                            # 没有版本规范，使用包名
                            package = line.strip()
                            requirements[package] = package
                            
                    except ValueError as e:
                        print(f"[警告] requirements.txt 第{line_num}行格式错误: {line}")
                        continue
            
            return requirements
            
        except Exception as e:
            print(f"[错误] 解析requirements.txt失败: {e}")
            return {}
    
    def initialize_components(self) -> bool:
        """
        初始化所有核心组件
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            print("初始化核心组件...")
            
            # 导入配置和日志模块
            from config import config
            from logger import get_logger
            
            # 获取主程序logger
            logger = get_logger(__name__)
            logger.info("开始初始化应用组件")
            
            # 1. 初始化业务核心分析器
            print("创建资金费率分析器...")
            from business_core import BusinessCore
            self.analyzer = BusinessCore()
            logger.info("资金费率分析器初始化完成")
            
            # 2. 初始化WebSocket客户端
            print("创建WebSocket客户端...")
            from binance_client import BinanceWebSocketClient
            # 传入正确的数据处理方法而不是整个对象
            # 创建WebSocket客户端，传递正确的参数
            self.ws_client = BinanceWebSocketClient(
                stream_path="/ws/!markPrice@arr@1s",
                data_handler=self.analyzer.update_data
            )
            logger.info("WebSocket客户端初始化完成")
            
            # 3. 初始化UI管理器
            print("创建UI管理器...")
            from ui_manager import UIManager
            self.ui_manager = UIManager(self.analyzer, self.ws_client)
            logger.info("UI管理器初始化完成")
            
            logger.info("所有核心组件初始化成功")
            return True
            
        except ImportError as e:
            print(f"[✗] 导入模块失败: {e}")
            print("请确保所有必需的模块文件存在：config.py, logger.py, business_core.py, binance_client.py, ui_manager.py")
            return False
        except Exception as e:
            print(f"[✗] 初始化组件时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start_services(self) -> bool:
        """
        启动所有服务
        
        Returns:
            bool: 启动是否成功
        """
        try:
            from logger import get_logger
            logger = get_logger(__name__)
            
            print("启动应用服务...")
            
            # 1. 启动数据分析器（关键修复：启动排名更新线程）
            print("启动数据分析器...")
            self.analyzer.start()
            logger.info("✅ 数据分析器已启动")
            
            # 2. 创建Web界面（先启动NiceGUI以建立事件循环）
            print("创建Web界面...")
            self.ui_manager.create_interface()
            logger.info("✅ Web界面创建完成")
            
            # 3. 在NiceGUI的事件循环中启动WebSocket连接
            print("准备连接币安WebSocket...")
            # WebSocket将在NiceGUI启动后的事件循环中启动
            
            self.is_running = True
            self.start_time = time.time()
            
            print("程序启动成功！")
            print("浏览器将自动打开监控界面")
            print("如果浏览器未自动打开，请手动访问: http://localhost:8080")
            print()
            print("💡 使用提示:")
            print("   - 保持此窗口打开，关闭窗口将停止程序")
            print("   - 按 Ctrl+C 可安全退出程序")
            print("   - 程序会自动连接币安API并实时更新数据")
            print()
            
            return True
            
        except Exception as e:
            print(f"[✗] 启动服务时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_application(self, port: Optional[int] = None) -> None:
        """
        运行主应用程序 - 集成智能端口管理
        
        Args:
            port: 可选的端口号，如果不指定则使用配置文件中的端口
        """
        try:
            from config import config
            from logger import get_logger
            
            logger = get_logger(__name__)
            
            # 检测调试模式
            debug_mode = self._is_debug_mode()
            if debug_mode:
                print("🔧 调试模式: 可在编辑器中直接运行和调试")
                print("💡 提示: 可以在关键代码位置设置断点进行调试")
                print("-" * 50)
            
            # 创建端口管理器实例
            port_manager = PortManager()
            
            # 智能端口管理
            preferred_port = port if port is not None else config.UI_PORT
            
            print(f"🔍 检查端口可用性...")
            available, details = port_manager.check_port_with_details(config.UI_HOST, preferred_port)
            
            if not available:
                print(f"[警告] ⚠️  端口{preferred_port}可能被占用")
                for detail in details:
                    if "占用" in detail:
                        print(f"[信息] 💡 {detail}")
                
                print(f"[信息] 🔍 正在寻找可用端口...")
                actual_port = port_manager.find_available_port(config.UI_HOST, preferred_port, 50)
                
                if actual_port is None:
                    print(f"[错误] ❌ 无法找到可用端口，尝试使用系统临时端口...")
                    actual_port = port_manager.find_unused_port_ephemeral(config.UI_HOST)
                
                if actual_port != preferred_port:
                    print(f"[信息] ✅ 已切换到端口: {actual_port}")
                    print(f"[信息] 🌐 请访问: http://{config.UI_HOST}:{actual_port}")
            else:
                actual_port = preferred_port
                print(f"[信息] ✅ 端口 {preferred_port} 可用")
            
            logger.info(f"启动NiceGUI Web应用 - 端口: {actual_port}")
            
            # 启动NiceGUI应用
            ui.run(
                host=config.UI_HOST,
                port=actual_port,
                title=config.UI_TITLE,
                dark=config.UI_DARK_MODE,
                show=True,  # 自动打开浏览器，方便小白用户
                reload=False,  # 禁用自动重载，适合生产环境
                native=False   # 不使用原生窗口
            )
            
        except KeyboardInterrupt:
            print("\n程序被用户中断")
        except Exception as e:
            print(f"运行应用时发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def run(self, port: Optional[int] = None) -> None:
        """
        便捷的运行方法，支持端口参数
        
        Args:
            port: 可选的端口号
        """
        try:
            # 1. 检查并安装依赖
            if not self.check_and_install_dependencies():
                print("依赖安装失败，程序退出")
                return
            
            print("正在启动应用...")
            
            # 2. 初始化核心组件
            if not self.initialize_components():
                print("组件初始化失败，程序退出")
                return
            
            # 3. 启动服务
            if not self.start_services():
                print("服务启动失败，程序退出")
                return
            
            # 4. 运行主应用
            self.run_application(port)
            
        except KeyboardInterrupt:
            print("\n程序被用户中断")
        except Exception as e:
            print(f"程序运行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("程序已退出")
    
    def _is_debug_mode(self) -> bool:
        """
        检测是否在调试模式下运行
        
        Returns:
            bool: 是否为调试模式
        """
        try:
            import inspect
            
            # 检查调用栈中是否有调试器相关的帧
            frame = inspect.currentframe()
            while frame:
                filename = frame.f_code.co_filename
                if any(debug_indicator in filename.lower() for debug_indicator in 
                       ['pdb', 'debugger', 'pydev', 'vscode', 'pycharm']):
                    return True
                frame = frame.f_back
            
            # 检查是否有调试相关的环境变量
            import os
            debug_vars = ['PYTHONDEBUG', 'PYCHARM_HOSTED', 'VSCODE_PID']
            if any(var in os.environ for var in debug_vars):
                return True
            
            return False
            
        except:
            return False
    
    def _signal_handler(self, signum, frame):
        """
        信号处理器
        
        Args:
            signum: 信号编号
            frame: 当前帧
        """
        print(f"\n接收到信号 {signum}，正在优雅关闭程序...")
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self) -> None:
        """
        清理资源
        """
        try:
            if not self.is_running:
                return
            
            print("正在清理资源...")
            
            # 停止数据分析器（关键修复：停止排名更新线程）
            if self.analyzer:
                self.analyzer.stop()
                print("✅ 数据分析器已停止")
            
            # 停止UI更新
            if self.ui_manager:
                self.ui_manager.stop_updates()
                print("✅ UI更新已停止")
            
            # 停止WebSocket客户端
            if self.ws_client:
                try:
                    # 获取当前事件循环并执行异步的stop方法
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，创建一个任务来执行stop
                        loop.create_task(self.ws_client.stop())
                    else:
                        # 如果事件循环已停止，使用run_until_complete
                        loop.run_until_complete(self.ws_client.stop())
                except RuntimeError:
                    # 如果没有正在运行的事件循环，创建新的事件循环来执行
                    try:
                        asyncio.run(self.ws_client.stop())
                    except Exception as e:
                        print(f"⚠️ WebSocket客户端停止时出现异常: {e}")
                except Exception as e:
                    print(f"⚠️ WebSocket客户端停止时出现异常: {e}")
                
                print("✅ WebSocket客户端已停止")
            
            self.is_running = False
            print("资源清理完成")
            
        except Exception as e:
            print(f"清理资源时发生错误: {e}")

def main():
    """
    主程序入口函数
    """
    print("=" * 50)
    print("    币安资金费率波动TOP5监控工具")
    print("=" * 50)
    print()
    
    # 创建应用管理器
    global app_manager
    app_manager = ApplicationManager()
    
    try:
        # 1. 检查并安装依赖
        if not app_manager.check_and_install_dependencies():
            print("依赖安装失败，程序退出")
            return 1
        
        print("正在启动应用...")
        
        # 2. 初始化核心组件
        if not app_manager.initialize_components():
            print("组件初始化失败，程序退出")
            return 1
        
        # 3. 启动服务
        if not app_manager.start_services():
            print("服务启动失败，程序退出")
            return 1
        
        # 4. 运行主应用
        app_manager.run_application()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        return 0
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("程序已退出")

# 程序入口点
if __name__ == "__main__":
    sys.exit(main())