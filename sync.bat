@echo off
cd /d D:\files
git add .
git commit -m "同步更新 %date% %time%"
git push
pause