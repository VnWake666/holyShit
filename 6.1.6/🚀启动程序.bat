@echo off
setlocal enabledelayedexpansion

REM ==================== 编码和环境设置 ====================
REM 设置UTF-8编码支持中文和Emoji
chcp 65001 >nul 2>&1
title 🚀 币安资金费率波动TOP5监控工具 v3.0

REM ==================== 欢迎界面 ====================
cls
echo.
echo ================================================================
echo                   🚀 币安资金费率波动TOP5监控工具
echo ================================================================
echo                        智能启动系统 v3.0
echo ================================================================
echo.

REM ==================== Python环境检测 ====================
echo 📋 检查Python运行环境...
echo.

python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do (
        echo [成功] ✅ Python环境正常 ^(版本: %%v^)
    )
    echo.
    echo 🚀 启动币安资金费率监控工具...
    echo.
    echo 💡 启动说明:
    echo    • 程序将自动检查并安装依赖包
    echo    • 程序将自动处理端口冲突问题
    echo    • 程序启动后将自动打开浏览器界面
    echo    • 按 Ctrl+C 可安全退出程序
    echo    • 保持此窗口打开以维持程序运行
    echo.
    echo ⏳ 正在启动，请稍候...
    echo ================================================================
    echo.
    
    REM 启动主程序 - 让main.py处理所有复杂逻辑
    python main.py
    set "EXIT_CODE=!errorlevel!"
    
    REM 处理程序退出状态
    echo.
    echo ================================================================
    if !EXIT_CODE! equ 0 (
        echo                    ✅ 程序正常退出
        echo ================================================================
        echo.
        echo 🎉 感谢使用币安资金费率监控工具！
        echo 💝 如果觉得好用，请推荐给朋友们~
        echo.
    ) else (
        echo                    ❌ 程序异常退出
        echo ================================================================
        echo.
        echo 🔍 可能的原因:
        echo    • 网络连接中断 - 无法连接币安API
        echo    • 系统资源不足 - 内存或CPU占用过高
        echo    • 程序文件损坏 - 核心模块文件缺失或损坏
        echo    • 防火墙阻止 - 网络访问被限制
        echo.
        echo 🛠️  建议解决方案:
        echo    1. 检查网络连接是否正常
        echo    2. 重启电脑后重新运行程序
        echo    3. 临时关闭防火墙或杀毒软件
        echo    4. 重新下载程序文件
        echo.
    )
) else (
    echo [错误] ❌ 未检测到Python环境
    echo.
    goto :python_install_guide
)

echo ================================================================
echo.
echo 按任意键关闭窗口...
pause >nul
exit /b !EXIT_CODE!

REM ==================== Python安装指南 ====================
:python_install_guide
echo ================================================================
echo                    🐍 Python安装指南
echo ================================================================
echo.
echo 📥 请按以下步骤安装Python:
echo.
echo 1. 🌐 访问Python官方网站:
echo    https://www.python.org/downloads/
echo.
echo 2. 📦 下载Python 3.8或更高版本
echo    推荐下载最新稳定版本
echo.
echo 3. ⚙️  安装时的重要设置:
echo    ✅ 务必勾选 "Add Python to PATH"
echo    ✅ 选择 "Install for all users" (可选)
echo    ✅ 选择 "Add Python to environment variables"
echo.
echo 4. 🔄 安装完成后:
echo    • 重启命令提示符或重启电脑
echo    • 重新运行此启动脚本
echo.
echo 💡 验证安装: 在命令行输入 python --version
echo    如果显示版本号，说明安装成功
echo.
echo ================================================================
echo.
echo 按任意键关闭窗口...
pause >nul
exit /b 1
