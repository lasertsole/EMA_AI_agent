#!/bin/bash


CURRENT_DIR=$(pwd)

# 第一步，尝试启动ollama 本地llm模型给viking使用,如果启动失败则跳过
echo "正在检查 Ollama 服务状态..."

# 定义检查函数
check_ollama_running() {
    if command -v curl &> /dev/null; then
        curl -s http://localhost:11434/api/tags > /dev/null 2>&1
        return $?
    else
        # 如果没有 curl，尝试使用 netstat (Windows)
        netstat -an 2>/dev/null | grep -q ":11434" || ss -tuln 2>/dev/null | grep -q ":11434"
        return $?
    fi
}

# 检查 Ollama 是否已安装
if command -v ollama &> /dev/null; then
    echo "✓ Ollama 已安装"

    # 检查服务是否已在运行
    if check_ollama_running; then
        echo "✓ Ollama 服务已在运行，跳过启动步骤"
    else
        echo "正在启动 Ollama 服务..."

        # 在后台启动 Ollama 服务
        start ollama serve > /dev/null 2>&1 &

        OLLAMA_PID=$!

        # 等待服务启动（最多等待 10 秒）
        echo "等待 Ollama 服务启动..."
        for i in {1..10}; do
            sleep 1
            if check_ollama_running; then
                echo "✓ Ollama 服务已成功启动 (PID: $OLLAMA_PID)"
                break
            fi

            if [ $i -eq 10 ]; then
                echo "⚠️  Ollama 服务启动超时，将跳过此步骤"
            fi
        done
    fi
else
    echo "⚠️  Ollama 未安装，跳过本地模型服务"
    echo "💡 如需使用，请安装 Ollama: https://ollama.ai"
fi

echo ""

sleep 5

# 第三步，打开主程序，并挂置shell前台
cd "${CURRENT_DIR}"
source ./.venv/Scripts/activate || { echo "激活虚拟环境失败，脚本已停止"; exit 1; } # 激活虚拟环境
./.venv/Scripts/python -m server --fast --disable-openapi || { echo "运行服务端时发生错误，脚本已停止"; exit 1; } &

# 第四步，打开主程序，并挂置shell前台
./.venv/Scripts/python -m streamlit run client/core.py || { echo "运行客户端程序时发生错误，脚本已停止"; exit 1; }