# SmartGrade Linux 服务器部署指南

本文档详细说明如何在Linux服务器上部署SmartGrade智能试卷批改系统。

## 📋 部署前准备

### 系统要求
- **操作系统**: Ubuntu 20.04/22.04 LTS 或 CentOS 7/8
- **内存**: 至少 4GB RAM（推荐 8GB+）
- **存储**: 至少 10GB 可用空间
- **Python版本**: Python 3.8 - 3.11（推荐 Python 3.10）

### 必需的API密钥
在部署前，请确保已获取以下至少一个AI服务的API密钥：

| 服务 | 获取地址 | 环境变量 |
|------|----------|----------|
| 阿里云 DashScope (Qwen-VL-Max) | [https://bailian.console.aliyun.com/](https://bailian.console.aliyun.com/) | `DASHSCOPE_API_KEY` |
| 智谱AI (GLM-4V) | [https://open.bigmodel.cn/](https://open.bigmodel.cn/) | `ZHIPU_API_KEY` |
| XHuoAI (Gemini 1.5 Pro) | [https://api.xhuoai.com/](https://api.xhuoai.com/) | `XHUOAI_API_KEY`, `XHUOAI_BASE_URL` |

## 🚀 一键部署脚本使用

项目提供了一键部署脚本，可以自动完成大部分配置工作。

### 1. 下载项目
```bash
git clone https://your-repo-url/SmartGrade.git
cd SmartGrade
```

### 2. 赋予脚本执行权限
```bash
chmod +x deploy.sh start.sh stop.sh
```

### 3. 运行部署脚本
```bash
./deploy.sh
```

部署脚本会自动：
- 检测并安装系统依赖
- 创建Python虚拟环境
- 安装Python依赖包
- 生成环境变量配置模板
- 设置文件权限

### 4. 配置环境变量
编辑 `.env` 文件，填入你的API密钥：
```bash
cp .env.example .env
nano .env
```

### 5. 启动服务
```bash
./start.sh
```

### 6. 停止服务
```bash
./stop.sh
```

## 🔧 手动部署步骤

如果你不想使用一键脚本，可以手动部署：

### 1. 安装系统依赖

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv build-essential cmake pkg-config \
    libjpeg-dev libtiff5-dev libpng-dev libavcodec-dev libavformat-dev \
    libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev \
    libatlas-base-dev gfortran libhdf5-dev libhdf5-serial-dev libhdf5-103
```

**CentOS/RHEL:**
```bash
sudo yum install -y python3 python3-pip python3-devel gcc gcc-c++ make cmake \
    opencv-devel libjpeg-turbo-devel libpng-devel libtiff-devel gtk3-devel \
    atlas-devel hdf5-devel
```

### 2. 创建Python虚拟环境
```bash
python3 -m venv smartgrade-env
source smartgrade-env/bin/activate
```

### 3. 安装Python依赖
```bash
pip install --upgrade pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥
nano .env
```

### 5. 测试运行
```bash
python run.py
```

如果看到类似以下输出，说明部署成功：
```
 * Running on http://127.0.0.1:5000
```

## 🌐 生产环境部署建议

### 使用Gunicorn + Nginx

对于生产环境，建议使用Gunicorn作为WSGI服务器，Nginx作为反向代理。

#### 1. 安装Gunicorn
```bash
pip install gunicorn
```

#### 2. 创建Gunicorn配置文件 `gunicorn.conf.py`
```python
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 300
keepalive = 2
preload_app = True
```

#### 3. 安装和配置Nginx
```bash
# Ubuntu/Debian
sudo apt install nginx

# CentOS/RHEL  
sudo yum install nginx
```

创建Nginx配置文件 `/etc/nginx/sites-available/smartgrade`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/SmartGrade/static;
        expires 30d;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/smartgrade /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 4. 使用Systemd管理服务

创建systemd服务文件 `/etc/systemd/system/smartgrade.service`:
```ini
[Unit]
Description=SmartGrade AI Grading Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/SmartGrade
Environment=PATH=/path/to/SmartGrade/smartgrade-env/bin
ExecStart=/path/to/SmartGrade/smartgrade-env/bin/gunicorn -c gunicorn.conf.py "app:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable smartgrade
sudo systemctl start smartgrade
```

## 🔒 安全配置

### 1. HTTPS配置
建议使用Let's Encrypt免费SSL证书：
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 2. 环境变量安全
- 确保 `.env` 文件权限为 `600`：`chmod 600 .env`
- 不要将 `.env` 文件提交到版本控制系统

### 3. 防火墙配置
```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 📊 监控和日志

### 日志位置
- Flask应用日志：`logs/app.log`
- Gunicorn日志：`logs/gunicorn.log`
- Nginx访问日志：`/var/log/nginx/access.log`
- Nginx错误日志：`/var/log/nginx/error.log`

### 系统监控
建议安装监控工具：
```bash
# 系统监控
sudo apt install htop iotop

# 应用性能监控
pip install psutil
```

## 🔄 更新和维护

### 更新代码
```bash
git pull origin main
source smartgrade-env/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart smartgrade
```

### 备份数据
定期备份上传的文件和批改结果：
```bash
# 备份静态文件
tar -czf backup_$(date +%Y%m%d).tar.gz static/uploads static/grading
```

## ❓ 常见问题解决

### 1. PaddlePaddle安装失败
如果遇到PaddlePaddle安装问题，尝试：
```bash
# 对于CPU版本
pip install paddlepaddle==2.6.0 -i https://pypi.tuna.tsinghua.edu.cn/simple

# 对于GPU版本（需要CUDA）
pip install paddlepaddle-gpu==2.6.0.post118 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
```

### 2. OpenCV相关错误
确保系统依赖已正确安装，或者尝试：
```bash
pip uninstall opencv-python opencv-python-headless
pip install opencv-python-headless==4.9.0.80
```

### 3. 内存不足
如果服务器内存不足，可以：
- 减少Gunicorn工作进程数
- 增加swap空间
- 优化图片处理逻辑

### 4. API调用失败
检查：
- API密钥是否正确
- 网络连接是否正常
- API服务是否可用
- 环境变量是否正确加载

## 📞 技术支持

如果遇到无法解决的问题，请提供：
- 操作系统版本
- Python版本
- 错误日志内容
- 已尝试的解决方案

---
*Happy deploying! 🚀*