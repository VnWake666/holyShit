#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产级日志管理模块
提供统一的日志配置和管理功能，支持可配置的文件日志和全局异常捕获
"""

import logging
import logging.handlers
import sys
import os
from typing import Optional
from config import config

class Logger:
    """生产级日志管理器"""
    
    _loggers = {}  # 存储已创建的logger实例
    _initialized = False  # 标记是否已初始化
    _exception_hook_installed = False  # 标记是否已安装异常钩子
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取指定名称的logger实例
        
        Args:
            name: logger名称，通常使用模块名
            
        Returns:
            配置好的logger实例
        """
        if not cls._initialized:
            cls._setup_logging()
            cls._initialized = True
            
        if name not in cls._loggers:
            cls._loggers[name] = cls._create_logger(name)
        return cls._loggers[name]
    
    @classmethod
    def _setup_logging(cls):
        """设置全局日志配置"""
        # 安装全局异常钩子（仅安装一次）
        if not cls._exception_hook_installed:
            cls._install_exception_hook()
            cls._exception_hook_installed = True
    
    @classmethod
    def _install_exception_hook(cls):
        """安装全局异常钩子，捕获所有未处理的异常"""
        original_excepthook = sys.excepthook
        
        def exception_handler(exc_type, exc_value, exc_traceback):
            """全局异常处理器"""
            # 获取根logger来记录致命错误
            root_logger = logging.getLogger('FATAL_ERROR')
            
            # 确保根logger有基本的控制台处理器
            if not root_logger.handlers:
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setLevel(logging.ERROR)
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)
                
                # 如果启用了文件日志，也添加文件处理器
                if config.LOG_TO_FILE:
                    file_handler = cls._create_file_handler()
                    if file_handler:
                        root_logger.addHandler(file_handler)
                
                root_logger.setLevel(logging.ERROR)
                root_logger.propagate = False
            
            # 记录致命错误
            root_logger.critical(
                f"未捕获的异常导致程序崩溃: {exc_type.__name__}: {exc_value}",
                exc_info=(exc_type, exc_value, exc_traceback)
            )
            
            # 调用原始的异常处理器
            original_excepthook(exc_type, exc_value, exc_traceback)
        
        sys.excepthook = exception_handler
    
    @classmethod
    def _create_logger(cls, name: str) -> logging.Logger:
        """
        创建新的logger实例
        
        Args:
            name: logger名称
            
        Returns:
            配置好的logger实例
        """
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        
        # 避免重复添加handler
        if not logger.handlers:
            # 创建控制台handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
            
            # 创建格式化器
            formatter = logging.Formatter(
                config.LOG_FORMAT,
                datefmt=config.LOG_DATE_FORMAT
            )
            console_handler.setFormatter(formatter)
            
            # 添加控制台handler到logger
            logger.addHandler(console_handler)
            
            # 如果启用了文件日志，添加文件handler
            if config.LOG_TO_FILE:
                file_handler = cls._create_file_handler()
                if file_handler:
                    logger.addHandler(file_handler)
            
            # 防止日志向上传播（避免重复输出）
            logger.propagate = False
        
        return logger
    
    @classmethod
    def _create_file_handler(cls) -> Optional[logging.handlers.RotatingFileHandler]:
        """
        创建文件日志处理器
        
        Returns:
            配置好的RotatingFileHandler实例，如果创建失败则返回None
        """
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(config.LOG_FILE_PATH)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # 创建RotatingFileHandler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=config.LOG_FILE_PATH,
                maxBytes=config.LOG_FILE_MAX_BYTES,
                backupCount=config.LOG_FILE_BACKUP_COUNT,
                encoding='utf-8'
            )
            
            # 设置文件handler的级别和格式
            file_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
            
            # 为文件日志使用更详细的格式
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                datefmt=config.LOG_DATE_FORMAT
            )
            file_handler.setFormatter(file_formatter)
            
            return file_handler
            
        except Exception as e:
            # 如果文件handler创建失败，在控制台输出警告但不影响程序运行
            print(f"警告: 无法创建文件日志处理器: {e}", file=sys.stderr)
            return None

# 便捷函数：获取当前模块的logger
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取logger实例的便捷函数
    
    Args:
        name: logger名称，如果为None则使用调用者的模块名
        
    Returns:
        logger实例
    """
    if name is None:
        # 获取调用者的模块名
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return Logger.get_logger(name)

# 测试代码
if __name__ == "__main__":
    # 测试日志功能
    test_logger = get_logger("test")
    
    test_logger.debug("这是调试信息")
    test_logger.info("这是普通信息")
    test_logger.warning("这是警告信息")
    test_logger.error("这是错误信息")
    test_logger.critical("这是严重错误信息")
    
    print("日志测试完成")
    
    # 测试全局异常捕获（取消注释以测试）
    # raise Exception("测试全局异常捕获")