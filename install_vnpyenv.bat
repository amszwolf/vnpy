@ECHO OFF
REM VeighNa 安装脚本 - 适配 vnpyenv conda 环境
REM 在 vnpyenv 环境下运行此脚本

ECHO ============================================================
ECHO VeighNa 环境安装脚本 (vnpyenv)
ECHO ============================================================
ECHO.

REM 检查是否在 vnpyenv 环境中
python -c "import sys; assert 'vnpyenv' in sys.executable or 'vnpyenv' in sys.prefix, '请在 vnpyenv 环境中运行此脚本'" 2>nul
IF ERRORLEVEL 1 (
    ECHO 错误: 请先激活 vnpyenv 环境
    ECHO 运行: conda activate vnpyenv
    PAUSE
    EXIT /B 1
)

ECHO [1/4] 检查当前环境...
python --version
python -c "import sys; print(f'Python路径: {sys.executable}')"
ECHO.

ECHO [2/4] 升级 pip 和 wheel...
python -m pip install --upgrade pip wheel --index-url https://pypi.vnpy.com
IF ERRORLEVEL 1 (
    ECHO 警告: pip 升级失败，继续安装...
)
ECHO.

ECHO [3/4] 安装 ta-lib (如果未安装)...
python -c "import talib" 2>nul
IF ERRORLEVEL 1 (
    ECHO 正在安装 ta-lib...
    python -m pip install --extra-index-url https://pypi.vnpy.com ta_lib==0.6.4
    IF ERRORLEVEL 1 (
        ECHO 错误: ta-lib 安装失败
        PAUSE
        EXIT /B 1
    )
    ECHO ✓ ta-lib 安装成功
) ELSE (
    python -c "import talib; print(f'✓ ta-lib 已安装 (版本: {talib.__version__})')"
)
ECHO.

ECHO [4/4] 安装/更新 VeighNa...
python -m pip install -e . --index-url https://pypi.vnpy.com
IF ERRORLEVEL 1 (
    ECHO 错误: VeighNa 安装失败
    PAUSE
    EXIT /B 1
)
ECHO.

ECHO ============================================================
ECHO ✓ 安装完成！
ECHO ============================================================
ECHO.
ECHO 验证安装:
python -c "import vnpy; print(f'veighna 版本: {vnpy.__version__}')"
python -c "import talib; print(f'ta-lib 版本: {talib.__version__}')"
ECHO.
PAUSE

