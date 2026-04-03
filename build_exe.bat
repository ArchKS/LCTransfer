@echo off
echo.
echo ===========================================
echo       正在进行清理旧的打包文件...
echo ===========================================
echo.

:: 清理旧的打包文件夹和 spec 文件
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
if exist "LocalFileTransfer.spec" del /q "LocalFileTransfer.spec"

echo.
echo ===========================================
echo       正在打包为可执行文件 (EXE)
echo ===========================================
echo.

:: 确保安装了 pyinstaller
pip install pyinstaller

:: 检查是否有自定义图标文件
set ICON_CMD=
if exist "icon.ico" (
    set ICON_CMD=--icon="icon.ico"
    echo 使用自定义图标: icon.ico
) else (
    echo [提示] 未找到 icon.ico，使用系统默认图标
)

:: 打包命令
:: --onefile: 打包为单个 exe
:: --add-data: 将 index.html 包含在 exe 中
:: --noconsole: 如果不需要命令行窗口可以加上，但对于调试有用，暂时保留
:: --name: 指定生成的文件名
:: --clean: 清理缓存
pyinstaller --onefile ^
            --clean ^
            --add-data "index.html;." ^
            --hidden-import engineio.async_drivers.threading ^
            %ICON_CMD% ^
            --name LocalFileTransfer ^
            app.py

echo.
echo ===========================================
echo 打包完成！请在 "dist" 文件夹中查找 LocalFileTransfer.exe
echo ===========================================
echo.
echo [注意] 如果你看到图标没变，可能是 Windows 图标缓存导致的。
echo 请尝试将生成的 EXE 文件移动到另一个文件夹，或者重启资源管理器。
echo.
pause

echo.
echo ===========================================
echo 打包完成！请在 "dist" 文件夹中查找 LocalFileTransfer.exe
echo ===========================================
echo.
pause
