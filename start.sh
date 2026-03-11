#!/bin/bash


CURRENT_DIR=$(pwd)

# 第一步，尝试启动TTS服务（可选）
if [ -f .env ]; then
  echo "检测到.env文件，正在提取配置..."
  GPT_SOVITS_DIR=$(grep "GPT_SOVITS_DIR" .env | awk -F '=' '{print $2}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  if [ -n "$GPT_SOVITS_DIR" ]; then
    GPT_SOVITS_DIR="${GPT_SOVITS_DIR//\\//}" # 将反斜杠转化为正斜杠
    CONFIG_PATH="${CURRENT_DIR}/models/sovits_model/config/tts_infer.yaml"
    INTERPRETER_PATH="${GPT_SOVITS_DIR}/runtime/python.exe"
    API_PATH="${GPT_SOVITS_DIR}/api_v2.py"

    FULL_COMMAND=(
      "$INTERPRETER_PATH"
      "$API_PATH"
      "-a" "127.0.0.1"
      "-p" "9880"
      "-c" "$CONFIG_PATH"
    )

    echo "正在启动TTS服务..."
    cd "${GPT_SOVITS_DIR}"
    "${FULL_COMMAND[@]}" > /dev/null 2>&1 &
    TTS_PID=$!
    if kill -0 $TTS_PID 2>/dev/null; then
      echo "TTS 服务已启动 (PID: $TTS_PID)"
    else
      echo "执行启动 TTS 服务的脚本时发生错误，将跳过 TTS 服务"
    fi
  fi
else
  echo ".env 文件不存在，跳过TTS服务"
fi

# 第二步，打开主程序，并挂置shell前台
cd "${CURRENT_DIR}"
source ./.venv/Scripts/activate || { echo "激活虚拟环境失败，脚本已停止"; exit 1; } # 激活虚拟环境
./.venv/Scripts/python -m streamlit run main.py || { echo "运行主程序时发生错误，脚本已停止"; exit 1; }