import logging
import logging.handlers
import sys
import os
import glob
import time
from datetime import datetime

class EndpointFilter(logging.Filter):
    def __init__(self, excluded_endpoints):
        super().__init__()
        self.excluded_endpoints = excluded_endpoints

    def filter(self, record):
        msg = record.getMessage()
        for endpoint in self.excluded_endpoints:
            if endpoint in msg:
                return False
        return True

def cleanup_old_logs(log_dir, current_log_file, limit=10):
    """
    清理旧日志文件，保留最新的limit个文件。
    """
    try:
        # 获取目录下所有的日志文件
        # 匹配格式 app_YYYY-MM-DD_HH-MM-SS.log
        pattern = os.path.join(log_dir, "app_*.log")
        files = glob.glob(pattern)
        
        # 如果当前日志文件还不存在（第一次运行今天），它可能不在files里
        # 如果已存在，它在files里
        
        # 按创建时间排序 (或者文件名排序，因为文件名包含日期)
        files.sort()
        
        # 我们希望最终保留的文件列表包含 current_log_file
        # 如果 current_log_file 还没创建，我们将会有 len(files) + 1 个文件
        # 所以如果 len(files) >= limit 且 current_log_file 不在 files 中，我们需要删除最早的
        # 如果 len(files) > limit，肯定要删除
        
        # 简单策略：
        # 1. 过滤掉非标准命名的文件（如果有）
        # 2. 将所有文件按时间排序
        # 3. 如果当前文件已经存在于列表中，则保留 limit 个
        # 4. 如果当前文件不存在于列表中，则保留 limit - 1 个，以便为新文件腾出空间
        
        # 检查当前文件是否已存在
        current_exists = current_log_file in files
        
        target_count = limit if current_exists else limit - 1
        
        if len(files) > target_count:
            # 需要删除的文件数量
            num_to_delete = len(files) - target_count
            for i in range(num_to_delete):
                file_to_remove = files[i]
                # 双重检查，不要删除当前正在使用的文件（理论上files[i]是最早的，不会是今天的，除非limit=1）
                if file_to_remove != current_log_file:
                    try:
                        os.remove(file_to_remove)
                        print(f"Removed old log file: {file_to_remove}")
                    except OSError as e:
                        print(f"Error removing file {file_to_remove}: {e}")
                        
    except Exception as e:
        print(f"Error during log cleanup: {e}")

def setup_logging():
    # 1. 确保logs文件夹存在
    log_dir = os.path.join(os.getcwd(), 'logs')
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    except OSError as e:
        print(f"Failed to create log directory: {e}")
        # 如果无法创建目录，回退到控制台日志
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger('bishe')

    # 2. 确定日志文件名
    # 检查最近的日志文件，如果时间差在5秒内（通常是Flask Reload导致的重启），则复用
    current_time_dt = datetime.now()
    
    # 查找最新的日志文件
    pattern = os.path.join(log_dir, "app_*.log")
    files = glob.glob(pattern)
    files.sort()
    
    reuse_existing = False
    log_filename = None
    
    if files:
        latest_file = files[-1]
        basename = os.path.basename(latest_file)
        try:
            # 解析文件名中的时间
            # 格式: app_YYYY-MM-DD_HH-MM-SS.log
            time_str = basename[4:-4]
            file_time = datetime.strptime(time_str, "%Y-%m-%d_%H-%M-%S")
            
            # 计算时间差
            delta = current_time_dt - file_time
            if 0 <= delta.total_seconds() < 5: # 5秒内的文件复用
                log_filename = basename
                reuse_existing = True
        except Exception:
            pass # 解析失败则创建新文件
            
    if not reuse_existing:
        current_time_str = current_time_dt.strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"app_{current_time_str}.log"
        
    log_filepath = os.path.join(log_dir, log_filename)
    
    # 3. 执行日志清理 (每次启动时检查)
    cleanup_old_logs(log_dir, log_filepath, limit=10)

    # 4. 配置日志记录器
    # 创建Formatter
    # 格式要求：包含时间戳、日志级别、模块名、行号和日志消息
    # 示例：[2023-11-15 14:30:45,123] INFO module_name:42 - This is a log message
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s %(module)s:%(lineno)d - %(message)s'
    )
    
    # 创建Handler
    # 要求：采用RotatingFileHandler实现日志轮转机制
    # 这里我们使用RotatingFileHandler，设置一个较大的maxBytes，防止单文件过大
    # 虽然主要的轮转是按天（文件名）进行的，但RotatingFileHandler提供了额外的单文件大小限制保护
    handler = logging.handlers.RotatingFileHandler(
        log_filepath,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,              # 单个日期文件内部轮转保留5个备份
        encoding='utf-8'
    )
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除旧的handlers (防止重复添加)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)
    
    # 同时保留控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 获取 werkzeug 日志记录器并添加过滤器
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(EndpointFilter(['/progress/', '/static/']))

    return logging.getLogger('bishe')
