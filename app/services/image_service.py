import cv2
import numpy as np
import os
import logging
import dashscope

# 获取日志记录器
logger = logging.getLogger(__name__)

# 临时目录
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

class ImageProcessor:
    def __init__(self, api_key=None):
        """
        初始化图像处理器
        
        Args:
            api_key: VLM API密钥 (兼容旧接口，实际不使用)
        """
        # 确保临时目录存在
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        if api_key:
            try:
                dashscope.api_key = api_key
            except:
                pass
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        预处理试卷图像
        
        Args:
            image_path: 图像路径
        
        Returns:
            预处理后的图像
        """
        # 读取图像 (支持中文路径)
        try:
            # 使用 numpy 读取文件，然后解码，解决 Windows 中文路径问题
            img_array = np.fromfile(image_path, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except Exception as e:
            logger.warning(f"使用imdecode读取失败，尝试直接读取: {e}")
            img = cv2.imread(image_path)
            
        if img is None:
            raise ValueError(f"无法读取图像: {image_path}")
        
        # 转换为灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 去噪
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # 对比度增强
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # 锐化
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # 转换回BGR（用于VLM）
        sharpened_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
        
        return sharpened_bgr
    
    def save_processed_image(self, image: np.ndarray, output_dir: str) -> str:
        """
        保存处理后的图像
        
        Args:
            image: 图像数组
            output_dir: 输出目录
        
        Returns:
            保存的文件路径
        """
        os.makedirs(output_dir, exist_ok=True)
        filename = f"processed_{os.urandom(8).hex()}.jpg"
        output_path = os.path.join(output_dir, filename)
        cv2.imwrite(output_path, image)
        return output_path

    def mark_exam_image(self, image_path: str, grading_results: dict, output_path: str = None) -> str:
        """
        在试卷图片上标记对错
        （用户已放弃此功能，直接返回原图路径）
        """
        logger.info(f"提示: 用户已禁用自动标记功能，返回原始图片。")
        return image_path
