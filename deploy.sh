#!/bin/bash

# SmartGrade Linux 部署脚本
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

# 检查是否为root用户（非必需，但某些操作可能需要sudo）
check_sudo() {
    if [ "$EUID" -eq 0 ]; then
        log_warn "不建议以root用户运行此脚本。请使用普通用户。"
        read -p "是否继续？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS=$DISTRIB_ID
        VERSION=$DISTRIB_RELEASE
    else
        log_error "无法检测操作系统"
        exit 1
    fi
    
    log_info "检测到操作系统: $OS $VERSION"
}

# 安装系统依赖
install_system_deps() {
    log_step "安装系统依赖..."
    
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv build-essential cmake pkg-config \
            libjpeg-dev libtiff5-dev libpng-dev libavcodec-dev libavformat-dev \
            libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev \
            libatlas-base-dev gfortran libhdf5-dev libhdf5-serial-dev
        
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "fedora" ]]; then
        if [[ "$OS" == "fedora" ]]; then
            sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ make cmake \
                opencv-devel libjpeg-turbo-devel libpng-devel libtiff-devel gtk3-devel \
                atlas-devel hdf5-devel
        else
            sudo yum install -y python3 python3-pip python3-devel gcc gcc-c++ make cmake \
                opencv-devel libjpeg-turbo-devel libpng-devel libtiff-devel gtk3-devel \
                atlas-devel hdf5-devel
        fi
    else
        log_warn "未知的操作系统: $OS。请手动安装以下依赖："
        echo "  - Python 3.8+"
        echo "  - pip"
        echo "  - build-essential (或等效的编译工具)"
        echo "  - OpenCV系统依赖"
        read -p "按回车键继续..."
    fi
}

# 创建虚拟环境
create_venv() {
    log_step "创建Python虚拟环境..."
    
    if [ ! -d "smartgrade-env" ]; then
        python3 -m venv smartgrade-env
        log_info "虚拟环境创建成功"
    else
        log_info "虚拟环境已存在，跳过创建"
    fi
    
    # 激活虚拟环境（在子shell中）
    source smartgrade-env/bin/activate
}

# 安装Python依赖
install_python_deps() {
    log_step "安装Python依赖..."
    
    source smartgrade-env/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖（使用清华源加速）
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    log_info "Python依赖安装完成"
}

# 配置环境变量
setup_env() {
    log_step "配置环境变量..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info "已创建 .env 配置文件模板"
            log_warn "请编辑 .env 文件并填入你的API密钥"
        else
            log_error "未找到 .env.example 文件"
            exit 1
        fi
    else
        log_info ".env 文件已存在"
    fi
    
    # 设置文件权限
    chmod 600 .env
}

# 创建必要的目录
create_directories() {
    log_step "创建必要目录..."
    
    mkdir -p static/uploads
    mkdir -p static/grading  
    mkdir -p answers
    mkdir -p logs
    
    log_info "目录创建完成"
}

# 测试安装
test_installation() {
    log_step "测试安装..."
    
    source smartgrade-env/bin/activate
    
    # 简单的导入测试
    python -c "import cv2; print('OpenCV版本:', cv2.__version__)"
    python -c "import paddle; print('PaddlePaddle版本:', paddle.__version__)"
    python -c "from paddleocr import PaddleOCR; print('PaddleOCR导入成功')"
    
    log_info "基本依赖测试通过"
}

# 主函数
main() {
    log_info "开始部署 SmartGrade 智能试卷批改系统..."
    
    check_sudo
    detect_os
    install_system_deps
    create_venv
    install_python_deps
    setup_env
    create_directories
    test_installation
    
    log_info "========================================"
    log_info "部署完成！"
    log_info "========================================"
    log_info "下一步操作："
    log_info "1. 编辑 .env 文件，填入你的API密钥"
    log_info "2. 运行 ./start.sh 启动服务"
    log_info "3. 访问 http://localhost:5000 查看应用"
    log_info "========================================"
}

# 执行主函数
main "$@"