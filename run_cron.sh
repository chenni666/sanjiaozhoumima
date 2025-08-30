#!/usr/bin/env bash
# 作为 1Panel 定时任务的入口脚本
# 功能：
# - 切换到脚本所在目录
# - 优先使用本项目下的 .venv/python 运行 main.py
# - 若无 .venv 则回退到系统 python3 或 python

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TS() { date '+%Y-%m-%d %H:%M:%S'; }

# 准备日志目录与当日日志文件（同时输出到控制台与文件）
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cron_$(date +%F).log"
# 将后续输出同步到日志
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[$(TS)] 执行 [cronjob-刷新密码] 任务开始 [START]"
echo "[$(TS)] 进入目录: $SCRIPT_DIR"
cd "$SCRIPT_DIR"

PY=""
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PY="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "找不到可用的 Python 解释器" >&2
  exit 127
fi

echo "[$(TS)] 使用解释器: $PY ($($PY --version 2>&1))"

START_TS=$(date +%s)
set +e
PYTHONUNBUFFERED=1 "$PY" -u "$SCRIPT_DIR/main.py" 2>&1 | tee -a "$LOG_FILE"
STATUS=${PIPESTATUS[0]}
set -e
END_TS=$(date +%s)
DURATION=$(( END_TS - START_TS ))

if [ $STATUS -eq 0 ]; then
  echo "[$(TS)] 任务结束 [OK] 用时 ${DURATION}s，日志: $LOG_FILE"
  exit 0
else
  echo "[$(TS)] 任务结束 [FAIL] 用时 ${DURATION}s，退出码: $STATUS，日志: $LOG_FILE" >&2
  exit $STATUS
fi
