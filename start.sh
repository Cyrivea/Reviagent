cd ~/Reviagent

echo "====== [Reviagent] 正在以生产级 ASGI 模式启动 ======"
# 第一次使用 ：chmod +x ~/Reviagent/start.sh
# chmod +x 的意思是 Change Mode + Executable（添加可执行权限）。
uvicorn api:app --host 127.0.0.1 --port 8000 --workers 4 --loop uvloop