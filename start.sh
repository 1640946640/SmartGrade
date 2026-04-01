#!/bin/bash

# SmartGrade 启动脚本
# 作者: SmartGrade Team
# 版本: 1.0

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查必要文件
check_files() {
    if [ ! -f "run.py" ]; then
        log_error "未找到 run.py 文件，请确保在项目根目录运行此脚本"
        exit 1
    fi
    
    if [ ! -d "smartgrade-env" ]; then
        log_error "未找到虚拟环境目录。请先运行 ./deploy.sh"
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        log_error "未找到 .env 配置文件。请先配置API密钥"
        exit 1
    fi
}

# 检查端口是否被占用
check_port() {
    PORT=${1:-5000}
    if lsof -i :$PORT > /dev/null 2>&1; then
        log_warn "端口 $PORT 已被占用"
        read -p "是否继续？这可能会导致服务启动失败 (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 创建日志目录
setup_logging() {
    mkdir -p logs
}

# 启动服务
start_service() {
    local port=${1:-5000}
    local host=${2:-"0.0.0.0"}
    
    log_step "激活虚拟环境..."
    source smartgrade-env/bin/activate
    
    log_step "启动 SmartGrade 服务..."
    log_info "访问地址: http://$host:$port"
    log_info "日志文件: logs/app.log"
    
    # 创建日志文件
    touch logs/app.log
    
    # 启动服务（后台运行）
    nohup python run.py > logs/app.log 2>&1 &
    SERVICE_PID=$!
    
    # 保存PID到文件
    echo $SERVICE_PID > smartgrade.pid
    
    log_info "服务已启动，PID: $SERVICE_PID"
    log_info "使用 ./stop.sh 停止服务"
}

# 显示使用帮助
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -p, --port PORT     指定端口 (默认: 5000)"
    echo "  -h, --host HOST     指定主机 (默认: 0.0.0.0)"
    echo "  --help             显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 使用默认设置启动"
    echo "  $0 -p 8080           # 在端口8080上启动"
    echo "  $0 -h 127.0.0.1 -p 5000  # 仅本地访问"
}

# 解析命令行参数
PORT=5000
HOST="0.0.0.0"

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 主函数
main() {
    log_info "启动 SmartGrade 智能试卷批改系统..."
    
    check_files
    check_port $PORT
    setup_logging
    start_service $PORT $HOST
    
    log_info "========================================"
    log_info "服务正在运行！"
    log_info "访问 http://$HOST:$PORT 开始使用"
    log_info "========================================"
}

# 执行主函数
main "$@"