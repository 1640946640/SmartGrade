import os
from PIL import Image
from app.config import Config
import logging

logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def allowed_answer_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_ANSWER_EXTENSIONS

def merge_images_vertically(image_paths, output_path):
    """
    垂直合并多张图片
    """
    try:
        images = [Image.open(x) for x in image_paths]
        if not images:
            return False
            
        # 获取最大宽度和总高度
        widths, heights = zip(*(i.size for i in images))
        max_width = max(widths)
        total_height = sum(heights)

        # 创建新图片（白色背景）
        new_im = Image.new('RGB', (max_width, total_height), (255, 255, 255))

        y_offset = 0
        for im in images:
            # 居中对齐
            x_offset = (max_width - im.width) // 2
            new_im.paste(im, (x_offset, y_offset))
            y_offset += im.height

        new_im.save(output_path)
        return True
    except Exception as e:
        logger.error(f"Error merging images: {e}")
        return False
