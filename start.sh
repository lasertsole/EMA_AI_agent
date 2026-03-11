#!/bin/bash

# 第一步，尝试启动TTS服务
if [ -f .env ]; then
  echo "检测到.env文件，正在提取配置..."
  GPT_SOVITS_DIR=$(grep "GPT_SOVITS_DIR" .env | awk -F '=' '{print $2}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  if [ -n "$GPT_SOVITS_DIR" ]; then
    echo "成功提取 TTS目录地址GPT_SOVITS_DIR: $GPT_SOVITS_DIR"
  fi
else
  echo ".env 文件不存在，跳过TTS服务"
fi

# 第二步，打开主程序
source ./.venv/Scripts/activate || { echo "激活虚拟环境失败，脚本已停止"; exit 1; }
./.venv/Scripts/python -m streamlit run main.py || { echo "运行主程序时发生错误，脚本已停止"; exit 1; }