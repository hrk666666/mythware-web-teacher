@echo off
REM 极域教师端 - Windows打包脚本
REM 运行此脚本前请先安装依赖: pip install -r requirements.txt

echo ========================================
echo   极域教师端 - exe打包工具
echo ========================================
echo.

REM 打包教师端主程序
echo [1/2] 打包教师端主程序...
pyinstaller --onefile --name "MythwareTeacher" --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    app.py

echo.
echo [2/2] 打包学生端代理...
pyinstaller --onefile --name "MythwareStudentAgent" ^
    student_agent.py

echo.
echo ========================================
echo   打包完成！
echo   教师端: dist\MythwareTeacher.exe
echo   学生代理: dist\MythwareStudentAgent.exe
echo ========================================
pause
