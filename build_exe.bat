@echo off
echo.
echo ===========================================
echo      Clean Old Package...
echo ===========================================
echo.

:: 清理旧的打包文件夹和 spec 文件
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
if exist "LCTransfer.spec" del /q "LCTransfer.spec"

echo.
echo ===========================================
echo       Making Executable File (EXE)
echo ===========================================
echo.

:: 确保安装了 pyinstaller
pip install pyinstaller

:: 检查是否有自定义图标文件
set ICON_CMD=
if exist "icon.ico" (
    set ICON_CMD=--icon="icon.ico"
    echo Use custom icon: icon.ico
) else (
    echo [Tip] Can not find icon.ico, Use Default Icon
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
            --add-data "qrcode.min.js;." ^
            --add-data "socket.io.js;." ^
            --add-data "all.min.css;." ^
            --add-data "css2.css;." ^
            --hidden-import engineio.async_drivers.threading ^
            %ICON_CMD% ^
            --name LCTransfer ^
            app.py

echo.
echo ===========================================
echo Package Finish! Please Find LCTransfer.exe in "dist" Folder
echo ===========================================
echo.
echo [Note] If you see the icon hasn't changed, it might be due to Windows icon cache.
echo Please try moving the generated EXE file to another folder, or restart Explorer.
echo.
pause

echo.
echo ===========================================
echo Package Finish! Please Find LCTransfer.exe in "dist" Folder
echo ===========================================
echo.
pause


:: 清理旧的打包文件夹和 spec 文件
@REM if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
if exist "LCTransfer.spec" del /q "LCTransfer.spec"