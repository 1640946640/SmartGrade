#!/bin/bash

# SmartGrade 停止脚本
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

# 检查PID文件
check_pid_file() {
    if [ ! -f "smartgrade.pid" ]; then
        log_warn "未找到 smartgrade.pid 文件，服务可能未运行"
        return 1
    fi
    
    PID=$(cat smartgrade.pid)
    if [ -z "$PID" ]; then
        log_warn "PID文件为空"
        return 1
    fi
    
    return 0
}

# 检查进程是否存在
check_process() {
    local pid=$1
    if kill -0 $pid 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# 停止服务
stop_service() {
    if ! check_pid_file; then
        log_info "尝试通过端口查找进程..."
        # 尝试通过端口5000查找Python进程
        PID=$(lsof -i :5000 -t | head -1)
        if [ -z "$PID" ]; then
            log_warn "未找到运行中的SmartGrade服务"
            return 0
        fi
        log_info "通过端口找到进程 PID: $PID"
    else
        PID=$(cat smartgrade.pid)
    fi
    
    if check_process $PID; then
        log_step "停止服务 (PID: $PID)..."
        kill $PID
        
        # 等待进程结束
        for i in {1..10}; do
            if ! check_process $PID; then
                break
            fi
            sleep 1
        done
        
        if check_process $PID; then
            log_warn "正常停止失败，强制终止..."
            kill -9 $PID
        fi
        
        log_info "服务已停止"
    else
        log_info "服务未在运行"
    fi
    
    # 清理PID文件
    if [ -f "smartgrade.pid" ]; then
        rm -f smartgrade.pid
    fi
}

# 主函数
main() {
    log_info "停止 SmartGrade 智能试卷批改系统..."
    
    stop_service
    
    log_info "========================================"
    log_info "服务已停止"
    log_info "========================================"
}

# 执行主函数
main "$@"