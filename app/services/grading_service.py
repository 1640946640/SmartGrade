import cv2
import numpy as np
import os
import json
import http.client
import base64
from typing import Dict, List
import dashscope
from dashscope import MultiModalConversation
from PIL import Image, ImageOps
import concurrent.futures
import logging
from docx import Document
import shutil
import time

from app.services.image_service import ImageProcessor, TEMP_DIR
from app.config import Config

# 获取日志记录器
logger = logging.getLogger(__name__)

# 全局任务状态存储
grading_tasks = {}

class ExamGrader:
    def __init__(self, api_keys=None):
        """
        初始化试卷批改器（支持多模型）
        
        Args:
            api_keys: VLM API密钥字典，格式为 {模型名: API密钥}
        """
        self.api_keys = api_keys or {}
        
        # 如果没有提供密钥，尝试从环境变量获取
        if not self.api_keys:
            self.api_keys = {
                'qwen-vl-max': os.getenv("DASHSCOPE_API_KEY"),
                'claude': os.getenv("ANTHROPIC_API_KEY"),
                'gemini-3-pro': os.getenv("XHUOAI_API_KEY")
            }
        
        # 移除None值
        self.api_keys = {k: v for k, v in self.api_keys.items() if v}
        # XHuoAI 基址
        self.xhuoai_base_url = os.getenv("XHUOAI_BASE_URL", "https://api.xhuoai.com/v1")
    
    def read_answer_document(self, file_path: str) -> str:
        """
        读取标准答案文档内容
        """
        try:
            if not file_path or not os.path.exists(file_path):
                return ""
                
            if file_path.lower().endswith('.docx'):
                doc = Document(file_path)
                full_text = []
                for para in doc.paragraphs:
                    full_text.append(para.text)
                return '\n'.join(full_text)
            else:
                logger.warning(f"暂不支持直接解析 .doc 格式，请使用 .docx: {file_path}")
                return ""
        except Exception as e:
            logger.error(f"读取标准答案失败: {e}")
            return ""

    def extract_group_scores_from_text(self, text: str) -> Dict[str, float]:
        """
        从文本（参考答案）中提取大题分值规则
        """
        rules = {}
        if not text:
            return rules
            
        import re
        
        patterns = [
            r'[一二三四五六七八九十]+[、\.]\s*([^\n（(]+)[（(].*?每[题空小][^\d]*(\d+\.?\d*)分',
            r'(\d+)\.\s*([^\n（(]+)[（(].*?每[题空小][^\d]*(\d+\.?\d*)分'
        ]
        
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            
            for pat in patterns:
                matches = re.search(pat, line)
                if matches:
                    try:
                        group_name_raw = matches.group(1).strip()
                        score = float(matches.group(2))
                        
                        key = None
                        if "填空" in group_name_raw: key = "填空"
                        elif "选择" in group_name_raw: key = "选择"
                        elif "判断" in group_name_raw: key = "判断"
                        elif "简答" in group_name_raw: key = "简答"
                        elif "计算" in group_name_raw: key = "计算"
                        elif "分析" in group_name_raw: key = "分析"
                        elif "设计" in group_name_raw: key = "设计"
                        elif "编程" in group_name_raw: key = "编程"
                        
                        if key:
                            rules[key] = score
                    except:
                        pass
                        
        return rules

    def check_available_models(self) -> List[Dict]:
        """
        检查模型可用性
        """
        models = [
            {'id': 'qwen-vl-max', 'name': 'Qwen-VL-Max (阿里云)', 'status': 'checking'},
            {'id': 'gemini-3-pro', 'name': 'Gemini 3 Pro (XhuoAI)', 'status': 'checking'},
            {'id': 'glm-4v', 'name': 'GLM-4V (智谱AI)', 'status': 'checking'}
        ]
        
        results = []
        for model in models:
            model_id = model['id']
            if model_id in self.api_keys:
                model['status'] = 'available'
                model['available'] = True
            else:
                model['status'] = 'unavailable'
                model['available'] = False
                model['error'] = '未配置 API Key'
            results.append(model)
            
        return results

    def grade_with_model(self, image_path: str, model_name: str, 
                       question_number: int, max_score: float = 10, group_name: str = None, answer_content: str = None) -> Dict:
        """
        使用指定模型批改单道题
        """
        if model_name not in self.api_keys:
            return {
                'success': False,
                'error': f'未找到{model_name}的API密钥',
                'score': 0,
                'is_correct': False,
                'comment': 'API密钥未配置'
            }
        
        api_key = self.api_keys[model_name]
        
        try:
            # 预处理图像
            processor = ImageProcessor(api_key=api_key)
            processed_img = processor.preprocess_image(image_path)
            
            # 保存预处理后的图像（临时）
            temp_path = os.path.join(TEMP_DIR, f"temp_{os.path.basename(image_path)}")
            cv2.imwrite(temp_path, processed_img)
            
            # 构造提示词
            question_desc = f"第{question_number}题"
            if group_name:
                question_desc = f"{group_name} 中的 {question_desc}"
            
            answer_prompt_part = ""
            if answer_content:
                answer_prompt_part = f"""
【标准答案参考】：
以下是提供的标准答案文档内容，请从中检索与{question_desc}相关的答案：
--------------------------------
{answer_content}
--------------------------------
请注意：
1. 【最高优先级规则】：如果学生答案与标准答案一致（或意思完全相同），**必须判定为正确**，并给出满分。即使你认为标准答案有误，也请以标准答案为准，除非标准答案明显是排版错误（如乱码）。
2. 对于【客观题】（如选择题、判断题），请【严格对照】上述标准答案进行批改。
3. 对于【主观题】（如填空题、简答题、计算题），请【参考】上述标准答案的解题思路和关键点进行打分。
4. 只有在标准答案中完全找不到该题对应答案时，才依靠你自己的知识进行判断，并在评语中说明“未在标准答案中找到对应条目”。
"""

            prompt = f"""你是一名专业阅卷老师，请批改{question_desc}。

满分：{max_score}分
{answer_prompt_part}

重要提示：
1. 请仔细观察试卷图片，特别注意试卷可能是双栏布局（左右两栏），请在整个试卷中寻找。
2. 找到{question_desc}的题目内容和学生的答案。
3. 如果试卷中没有{question_desc}，或者题目内容不清晰，请明确指出。
4. 不要编造或想象题目内容，只基于图片中实际可见的内容进行批改。
5. 如果无法识别题目内容，请给出低分并说明原因。
6. 【特别注意涂改】：在批改选择题时，如果发现学生有涂改痕迹（例如划掉一个选项，改选另一个），请务必识别【最终保留】的答案。通常被划掉、打叉或涂黑的是作废答案。请仔细分辨，以学生最终意图展示的答案为准进行评分。如果涂改过于潦草无法确定最终答案，请判错并在评语中说明"涂改不清，无法判断"。
7. 【关键：空白卷检测】：请仔细检查答题区域。如果该题只有【打印体】的题目内容（例如题目本身给出的代码框架、填空横线、选择题选项），而没有任何【手写体】的笔迹，必须视为【未作答】，直接判 0 分！
8. 【反幻觉机制 - 严禁脑补】：对于代码填空题或算法设计题，试卷上印刷的原始代码框架（如 `void QuickSort(...) {{ ... }}`）属于题目部分。只有学生【手写】补充进去的代码才是答案。如果图片中没有手写笔迹，绝对不能假装学生写了！
9. 【视觉差异验证】：在识别学生答案时，必须对比“答案笔迹”与“题目印刷字体”的差异。
   - 如果所谓的“学生答案”在字体风格、大小、墨色、排版上与题目完全一致，那它就是题目的一部分！
   - 真正的学生手写体通常会有：笔画不直、字间距不均、行歪斜、涂改、墨色深浅不一等特征。
   - 如果你无法找出这些【不完美】的特征，说明这是打印体，是题目！必须判0分！
10. 【多问检查】：如果一道题包含多个小问（例如 (1)设计算法 (2)分析复杂度），请分别检查每个小问的作答情况。只要有一个小问未作答，该小问就不得分。如果所有小问都没写，直接0分。

请从以下维度评分：
1. 答案正确性（50%）
2. 解题逻辑清晰度（30%）
3. 表达完整性（20%）

评分标准：
- 答案完全正确，逻辑清晰：给满分
- 答案基本正确，有小错误：给80-90%分数
- 答案部分正确：给50-70%分数
- 答案错误：给0-30%分数
- 未作答（无手写痕迹）：给0分
- 题目无法识别或内容不清晰：给0分

请务必先进行详细分析，再给出分数。分析内容请使用清晰的纯文本格式（不要使用Markdown标记，不要出现**、##等符号），要求如下：
1. 使用 "1. 识别题目内容"、"2. 识别学生答案(需验证与打印体的视觉差异)"、"3. 标准答案比对"（如果有标准答案）、"4. 判定对错"、"5. 结论" 作为小标题。
2. 如果涉及数学公式，请使用 LaTeX 格式，但不要使用单独的块级公式（$$），尽量使用行内公式（$）。
3. 列表项请使用 "-" 或序号。
4. 保持段落分明，每个小标题之间空一行。

请以JSON格式返回（**直接返回JSON字符串，不要使用Markdown代码块，不要加```json**）：
{{
  "analysis": "详细解析（纯文本格式字符串，注意转义双引号）",
  "score": 得分（基于上述分析给出分数，0到{max_score}之间的数字）,
  "is_correct": 是否正确（布尔值）,
  "comment": "评语（简短的中文评语，指出优点和不足）"
}}
"""
            # Gemini specific optimization
            if model_name.startswith('gemini'):
                prompt += "\n\nIMPORTANT: OUTPUT ONLY VALID JSON. NO PREAMBLE. NO EXPLANATION TEXT OUTSIDE JSON. KEEP REASONING CONCISE."
            
            abs_path = os.path.abspath(temp_path)
            file_uri = f"file://{abs_path}"
            
            if model_name.startswith('qwen'):
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"image": file_uri},
                            {"text": prompt}
                        ]
                    }
                ]
                response = MultiModalConversation.call(model=model_name, messages=messages)
                
                if hasattr(response, 'output') and hasattr(response.output, 'choices'):
                    if len(response.output.choices) > 0:
                        choice = response.output.choices[0]
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            content_list = choice.message.content
                            if isinstance(content_list, list) and len(content_list) > 0:
                                content_item = content_list[0]
                                if isinstance(content_item, dict):
                                    content = content_item.get('text', '')
                                elif hasattr(content_item, 'text'):
                                    content = content_item.text
                                else:
                                    content = str(content_item)
                            else:
                                content = str(content_list)
                        else:
                            content = str(choice.message)
                    else:
                        content = str(response.output)
                elif isinstance(response, dict):
                    try:
                        output = response.get('output') or {}
                        choices = output.get('choices') or []
                        if choices:
                            message = choices[0].get('message') or {}
                            content_list = message.get('content') or []
                            if isinstance(content_list, list) and content_list:
                                content = content_list[0].get('text', '')
                            else:
                                content = str(content_list)
                        else:
                            content = ""
                    except Exception as e:
                        logger.warning(f"解析响应出错: {e}")
                        content = ""
                else:
                    content = str(response)
                 
            elif model_name.startswith('claude'):
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                
                with open(temp_path, 'rb') as image_file:
                    message = client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/jpeg",
                                            "data": base64.b64encode(image_file.read()).decode()
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": prompt
                                    }
                                ]
                            }
                        ]
                    )
                content = message.content[0].text
            
            elif model_name.startswith('gemini'):
                from openai import OpenAI
                import httpx
                
                logger.info(f"正在初始化 Gemini 客户端 (Base URL: {self.xhuoai_base_url})...")
                client = OpenAI(
                    api_key=api_key,
                    base_url=self.xhuoai_base_url,
                    http_client=httpx.Client(verify=False)
                )
                
                with open(temp_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                logger.info(f"图片读取完成，Base64长度: {len(base64_image)}")
                logger.info(f"正在向 {model_name} 发送请求...")

                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=32000
                    )
                    
                    # 强制使用INFO级别打印完整响应，以便调试
                    logger.info(f"Gemini 原始响应对象: {response}")
                    try:
                        logger.info(f"Gemini JSON dump: {response.model_dump_json()}")
                    except:
                        pass
                    
                    content = ""
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        message = choice.message
                        
                        # 检查是否有 refusal (拒绝回答)
                        if hasattr(message, 'refusal') and message.refusal:
                            logger.warning(f"Gemini 拒绝回答: {message.refusal}")
                        
                        if message and message.content:
                            content = message.content.strip()
                        else:
                            logger.warning(f"Gemini message.content 为空。Message对象: {message}")
                    else:
                        logger.warning(f"Gemini 响应中没有 choices: {response}")

                    if not content:
                        finish_reason = 'Unknown'
                        if hasattr(response, 'choices') and len(response.choices) > 0:
                            finish_reason = response.choices[0].finish_reason
                        logger.warning(f"Gemini 返回内容最终解析为空。Finish Reason: {finish_reason}")
                
                except Exception as api_err:
                    logger.error(f"Gemini API 调用发生异常: {str(api_err)}")
                    content = ""

            elif model_name.startswith('glm'):
                from zhipuai import ZhipuAI
                client = ZhipuAI(api_key=api_key)
                
                with open(temp_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                response = client.chat.completions.create(
                    model="glm-4v",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": base64_image
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                if response.choices and response.choices[0].message.content:
                    content = response.choices[0].message.content
                else:
                    content = ""
                    logger.warning(f"GLM 返回内容为空: {response}")

            else:
                return {
                    'success': False,
                    'error': f'不支持的模型: {model_name}',
                    'score': 0,
                    'is_correct': False,
                    'comment': '模型不支持'
                }
            
            logger.debug(f"\n[Debug] {model_name} 原始响应内容:\n{content}\n" + "-"*50)

            result = self.parse_grading_response(content, max_score)
            
            if result is None:
                logger.error(f"{model_name} 返回内容无法解析: {content[:200]}...")
                return {
                    'success': False,
                    'error': '无法解析模型响应',
                    'score': 0,
                    'is_correct': False,
                    'comment': '模型未返回有效的JSON格式结果'
                }

            result['model_used'] = model_name
            result['max_score'] = max_score
            result['success'] = True
            
            return result
             
        except Exception as e:
            temp_path = os.path.join(TEMP_DIR, f"temp_{os.path.basename(image_path)}")
            try:
                if os.path.exists(temp_path):
                    import time
                    for _ in range(3):
                        try:
                            os.remove(temp_path)
                            break
                        except PermissionError:
                            time.sleep(0.5)
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            return {
                'success': False,
                'error': f'批改失败: {str(e)}',
                'score': 0,
                'is_correct': False,
                'comment': f'模型调用异常: {str(e)}'
            }
    
    def parse_grading_response(self, response_text: str, max_score: float) -> Dict:
        """
        解析批改响应
        """
        import re
        import json
        
        def clean_analysis(analysis_text):
            if not analysis_text:
                return ""
            analysis_text = analysis_text.replace('·', '-').replace('•', '-')
            analysis_text = re.sub(r'\*\*(.*?)\*\*', r'\1', analysis_text)
            analysis_text = re.sub(r'#+\s*', '', analysis_text)
            analysis_text = re.sub(r'(?<!\n)\n(\d+\.\s*[^\n]+?)[:：]?', r'\n\n\1：', analysis_text)
            return analysis_text.strip()

        def try_parse(text):
            try:
                text = text.replace('\t', '\\t')
                result = json.loads(text, strict=False)
                return result
            except json.JSONDecodeError:
                return None
        
        def process_result(result):
            if not result: return None
            if not isinstance(result, dict):
                return None
            if 'score' in result:
                try:
                    score = float(result['score'])
                    result['score'] = max(0, min(score, max_score))
                except:
                    result['score'] = 0
            if 'analysis' in result:
                result['analysis'] = clean_analysis(result['analysis'])
            return result
        
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        code_blocks = re.findall(code_block_pattern, response_text, re.IGNORECASE)
        
        if code_blocks:
            sorted_blocks = sorted(code_blocks, key=len, reverse=True)
            for block in sorted_blocks:
                start = block.find('{')
                end = block.rfind('}')
                if start != -1 and end > start:
                    json_str = block[start:end+1]
                    res = try_parse(json_str)
                    if res:
                        valid_res = process_result(res)
                        if valid_res: return valid_res
        
        try:
            start_idx = response_text.find('{')
            if start_idx != -1:
                end_idx = response_text.rfind('}')
                if end_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx+1]
                    res = try_parse(json_str)
                    if res:
                        valid_res = process_result(res)
                        if valid_res: return valid_res
                else:
                    json_str = response_text[start_idx:]
            else:
                json_str = response_text
        except:
            json_str = response_text
            
        json_str = json_str.rstrip()
        if json_str.count('"') % 2 != 0:
            json_str += '"'
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
            
        res = try_parse(json_str)
        if res:
            return process_result(res)
        
        return None
    
    def extract_json_from_text(self, text: str) -> Dict:
        """
        从文本中提取JSON
        """
        import json
        import re

        if not text:
            return None
        
        # 1. 尝试直接解析
        try:
            return json.loads(text)
        except:
            pass
            
        # 2. 尝试提取Markdown代码块
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(code_block_pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                return json.loads(match)
            except:
                pass
        
        # 3. 尝试提取最外层的大括号
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
                return json.loads(json_str)
        except:
            pass

        # 4. 尝试修复常见错误（例如中文冒号，单引号等）
        try:
            # 替换中文冒号
            text_fixed = text.replace('：', ':')
            # 替换单引号为双引号（注意这可能会破坏内容中的单引号，需谨慎，但作为最后手段可以一试）
            # 更好的做法是只替换键值对的引号，但这很难用简单正则做到。
            # 这里仅尝试解析大括号内容
            start = text_fixed.find('{')
            end = text_fixed.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = text_fixed[start:end+1]
                # 简单的非标准JSON修复：键名没引号的情况（需要第三方库，这里尽量用标准库）
                return json.loads(json_str)
        except:
            pass
            
        return None

    def analyze_exam_structure(self, image_path: str, answer_content: str = None, model_name: str = None) -> Dict:
        """
        分析试卷结构，识别题目数量和分值
        """
        logger.info(f"\n正在分析试卷结构...")
        
        try:
            available_models = list(self.api_keys.keys())
            if not available_models:
                return {
                    'success': False,
                    'error': '没有可用的模型'
                }
            
            # 如果未指定模型或指定模型不可用，使用第一个可用模型
            if not model_name or model_name not in self.api_keys:
                model_name = available_models[0]
            
            logger.info(f"使用模型进行结构分析: {model_name}")
            api_key = self.api_keys[model_name]

            pil_img = Image.open(image_path)
            pil_img = ImageOps.exif_transpose(pil_img)
            processed_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except:
            try:
                img_array = np.fromfile(image_path, np.uint8)
                processed_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            except Exception as e:
                logger.warning(f"使用imdecode读取失败: {e}")
                processed_img = cv2.imread(image_path)
        
        if processed_img is None:
             logger.warning(f"无法读取图像(用于结构分析): {image_path}")
             pass
        
        temp_path = os.path.join(TEMP_DIR, f"temp_structure_{os.path.basename(image_path)}")
        cv2.imwrite(temp_path, processed_img)
        
        abs_path = os.path.abspath(temp_path)
        file_uri = f"file://{abs_path}"
        
        answer_hint = ""
        if answer_content:
            answer_hint = f"""
【参考辅助信息】：
以下是标准答案文档的内容，其中可能包含题号结构和分值说明（如“一、填空题（每题1.5分）”）：
--------------------------------
{answer_content[:3000]}
--------------------------------
请结合图片内容和上述参考信息，更准确地识别分值。如果图片不清，请优先参考上述文本中的分值设定。
"""

        prompt = f"""你是一名专业阅卷老师，请分析这张试卷的结构。

任务：
1. 识别试卷中的所有题目，并精确定位【题号】的位置。
2. 【重点】识别每道题的【分值】。分值通常出现在：
   - 大题标题旁：如 "一、填空题（共15分，每题1.5分）" -> 该大题下所有小题均为 1.5 分。
   - 题目末尾括号：如 "1. ... (5分)" -> 该题 5 分。
   - 参考信息中：如果图片不清，可参考提供的标准答案文本。

这张试卷很可能是【双栏布局】（左栏+右栏），请务必【从左到右，从上到下】扫描整个版面。

请输出一个JSON对象，包含 'groups' 列表。
对于每道小题，请提供 'id' (题号), 'box_2d' (坐标), 和 'score' (分值，可选)。

【关键要求】：
1. 'box_2d' 必须是【题号数字本身】的坐标（例如只框住 "1." 或 "一、" 这些字符），不要框住整道题的文字！
2. 坐标格式为 [ymin, xmin, ymax, xmax]，数值范围 0-1000（归一化坐标）。
3. 如果找不到确切的题号坐标，请不要瞎编，直接返回空列表或不返回 box_2d 字段。
4. 'score' 字段必须是数字（浮点数）：
   - 务必区分【总分】和【每题分值】。如果大题说 "共10题，共20分"，那么每题是 2 分，而不是 20 分！
   - 务必区分【题目数量】和【分值】。不要把 "10小题" 误认为是 "10分"。
   - 如果实在找不到分值，可以设为 null。

{answer_hint}

JSON格式示例：
{{
  "total_questions": 21,
  "groups": [
    {{
      "name": "一、填空题",
      "default_score": 1.5, 
      "questions": [
        {{"id": "1", "type": "填空题", "box_2d": [100, 50, 120, 70], "score": 1.5}}, 
        {{"id": "2", "type": "填空题", "box_2d": [160, 50, 180, 70], "score": 1.5}}
      ]
    }}
  ]
}}
"""
        # Gemini specific optimization
        if model_name and model_name.startswith('gemini'):
            prompt = f"""你是一名专业阅卷老师，请分析这张试卷的结构。
请直接输出JSON格式结果，不要包含任何Markdown标记或解释文字。

任务：
1. 识别试卷中的所有题目，并精确定位【题号】的位置。
2. 【重点】识别每道题的【分值】。
3. 这是一个双栏布局的试卷，请从左到右扫描。

{answer_hint}

JSON格式严格如下：
{{
  "total_questions": 21,
  "groups": [
    {{
      "name": "一、填空题",
      "default_score": 1.5, 
      "questions": [
        {{"id": "1", "type": "填空题", "box_2d": [100, 50, 120, 70], "score": 1.5}}
      ]
    }}
  ]
}}

IMPORTANT: OUTPUT ONLY VALID JSON. NO PREAMBLE. NO EXPLANATION TEXT.
"""
        
        try:
            # model_name and api_key are already set at the beginning of the function
            
            if model_name.startswith('qwen'):
                dashscope.api_key = api_key
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"image": file_uri},
                            {"text": prompt}
                        ]
                    }
                ]
                response = MultiModalConversation.call(model=model_name, messages=messages)
                
                if hasattr(response, 'output') and hasattr(response.output, 'choices'):
                    if len(response.output.choices) > 0:
                        choice = response.output.choices[0]
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            content_list = choice.message.content
                            if isinstance(content_list, list) and len(content_list) > 0:
                                content_item = content_list[0]
                                if isinstance(content_item, dict):
                                    content = content_item.get('text', '')
                                elif hasattr(content_item, 'text'):
                                    content = content_item.text
                                else:
                                    content = str(content_item)
                            else:
                                content = str(content_list)
                        else:
                            content = str(choice.message)
                    else:
                        content = str(response.output)
                elif isinstance(response, dict):
                    try:
                        output = response.get('output') or {}
                        choices = output.get('choices') or []
                        if choices:
                            message = choices[0].get('message') or {}
                            content_list = message.get('content') or []
                            if isinstance(content_list, list) and content_list:
                                content = content_list[0].get('text', '')
                            else:
                                content = str(content_list)
                        else:
                            content = ""
                    except Exception as e:
                        logger.warning(f"解析响应出错: {e}")
                        content = ""
                else:
                    content = str(response)

            elif model_name.startswith('gemini'):
                from openai import OpenAI
                import httpx
                
                logger.info(f"正在初始化 Gemini 客户端 (Base URL: {self.xhuoai_base_url})...")
                client = OpenAI(
                    api_key=api_key,
                    base_url=self.xhuoai_base_url,
                    http_client=httpx.Client(verify=False)
                )
                
                with open(temp_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                logger.info(f"图片读取完成，Base64长度: {len(base64_image)}")
                logger.info(f"正在向 {model_name} 发送请求...")

                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }
                                ]
                        }
                    ],
                    max_tokens=32000
                    )
                    
                    logger.info(f"Gemini 原始响应对象: {response}")
                    try:
                        logger.info(f"Gemini JSON dump: {response.model_dump_json()}")
                    except:
                        pass
                    
                    content = ""
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        message = choice.message
                        
                        if hasattr(message, 'refusal') and message.refusal:
                            logger.warning(f"Gemini 拒绝回答: {message.refusal}")
                        
                        if message and message.content:
                            content = message.content.strip()
                        else:
                            logger.warning(f"Gemini message.content 为空。Message对象: {message}")
                    else:
                        logger.warning(f"Gemini 响应中没有 choices: {response}")

                    if not content:
                        finish_reason = 'Unknown'
                        if hasattr(response, 'choices') and len(response.choices) > 0:
                            finish_reason = response.choices[0].finish_reason
                        logger.warning(f"Gemini 返回内容最终解析为空。Finish Reason: {finish_reason}")
                
                except Exception as api_err:
                    logger.error(f"Gemini API 调用发生异常: {str(api_err)}")
                    content = ""

            elif model_name.startswith('glm'):
                from zhipuai import ZhipuAI
                client = ZhipuAI(api_key=api_key)
                with open(temp_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                response = client.chat.completions.create(
                    model="glm-4v",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": base64_image
                                    }
                                }
                            ]
                        }
                    ]
                )
                if response.choices and response.choices[0].message.content:
                    content = response.choices[0].message.content
                else:
                    content = str(response)
            else:
                return {
                    'success': False,
                    'error': f'不支持的模型: {model_name}'
                }
            
            logger.debug(f"\n[Debug] 试卷结构分析原始响应:\n{content}\n" + "-"*50)
            
            try:
                if os.path.exists(temp_path):
                    for _ in range(3):
                        try:
                            os.remove(temp_path)
                            break
                        except PermissionError:
                            import time
                            time.sleep(0.5)
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            result = self.parse_grading_response(content, 100)
            
            if not result:
                result = self.extract_json_from_text(content)
            
            if not result:
                logger.error(f"❌ 无法解析模型响应为JSON。原始响应前500字符: {content[:500] if content else '空内容'}")
                return {'success': False, 'error': '无法解析模型响应为JSON'}
                
            result['success'] = True
            
            logger.info(f"✅ 试卷结构分析完成")
            logger.info(f"   识别到 {result.get('total_questions', 0)} 道题")
            
            return result
            
        except Exception as e:
            try:
                if os.path.exists(temp_path):
                    for _ in range(3):
                        try:
                            os.remove(temp_path)
                            break
                        except PermissionError:
                            import time
                            time.sleep(0.5)
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            return {
                'success': False,
                'error': f'分析试卷结构失败: {str(e)}'
            }
    
    def grade_exam_with_multiple_models(self, image_path: str,
                                       question_count: int = None,
                                       max_score: float = 10,
                                       selected_models: List[str] = None,
                                       progress_callback=None,
                                       answer_file_path: str = None) -> Dict:
        """
        使用多个模型批改整张试卷
        """
        def update_progress(percent, msg):
            if progress_callback:
                progress_callback(percent, msg)
                
        logger.info(f"\n开始批改试卷: {image_path}")
        update_progress(5, "正在初始化批改引擎...")
        
        answer_content = None
        if answer_file_path:
            logger.info(f"读取标准答案文件: {answer_file_path}")
            answer_content = self.read_answer_document(answer_file_path)
            if answer_content:
                logger.info(f"标准答案内容读取成功 (长度: {len(answer_content)} 字符)")
                text_scores = self.extract_group_scores_from_text(answer_content)
                if text_scores:
                    logger.info(f"从标准答案中提取到分值规则: {text_scores}")
            else:
                logger.warning("标准答案内容为空或读取失败")
                text_scores = {}
        else:
            text_scores = {}
        
        all_results = {}
        model_results = {}
        
        available_keys = list(self.api_keys.keys())
        
        if selected_models:
            available_models = [m for m in selected_models if m in available_keys]
        else:
            available_models = available_keys
            
        if not available_models:
             return {
                'success': False,
                'error': '没有可用的模型，请检查API Key配置或选择的模型',
                'image_path': image_path
            }

        logger.info(f"\n将使用以下模型进行批改: {available_models}")
        
        if question_count is None:
            logger.info("\n未指定题目数量，正在分析试卷结构...")
            update_progress(10, "正在分析试卷结构（这可能需要几秒钟）...")
            
            # Use the first selected model for structure analysis if available
            structure_model = available_models[0] if available_models else None
            
            structure_result = self.analyze_exam_structure(
                image_path, 
                answer_content=answer_content,
                model_name=structure_model
            )
            
            questions_to_grade = []
            
            if not structure_result.get('success', False):
                logger.error(f"❌ 分析试卷结构失败: {structure_result.get('error', '未知错误')}")
                questions_to_grade = [{"id": str(i), "group": None, "unique_id": str(i), "score": None} for i in range(1, 11)]
            else:
                if 'groups' in structure_result:
                    for group in structure_result['groups']:
                        group_name = group.get('name', '未知大题')
                        group_default_score = group.get('default_score')
                        
                        for q in group.get('questions', []):
                            q_id = q.get('id', '')
                            box_2d = q.get('box_2d')
                            q_score = q.get('score')
                            if q_score is None:
                                q_score = group_default_score
                            
                            if q_score is None and group_name:
                                for key, score in text_scores.items():
                                    if key in group_name:
                                        q_score = score
                                        break
                            
                            if q_score is None:
                                if "选择" in group_name:
                                    q_score = 3
                                elif "填空" in group_name:
                                    q_score = 2
                                elif "判断" in group_name:
                                    q_score = 2
                            
                            unique_id = f"{group_name}-{q_id}"
                            questions_to_grade.append({
                                "id": q_id,
                                "group": group_name,
                                "unique_id": unique_id,
                                "box_2d": box_2d,
                                "score": q_score
                            })
                else:
                    total_questions = structure_result.get('total_questions', 10)
                    question_numbers = structure_result.get('question_numbers', [str(i) for i in range(1, total_questions + 1)])
                    questions_to_grade = [{"id": str(qn), "group": None, "unique_id": str(qn), "score": None} for qn in question_numbers]
                
                if not questions_to_grade:
                    logger.warning("⚠️ 警告: 试卷分析返回成功但没有找到题目，尝试使用备用逻辑")
                    total_qs = structure_result.get('total_questions', 0)
                    if total_qs > 0:
                        questions_to_grade = [{"id": str(i), "group": None, "unique_id": str(i), "score": None} for i in range(1, total_qs + 1)]

            logger.info(f"✅ 准备批改 {len(questions_to_grade)} 道题")
        else:
            questions_to_grade = [{"id": str(i), "group": None, "unique_id": str(i), "score": None} for i in range(1, question_count + 1)]
        
        default_max_score = max_score if max_score is not None else 10.0
        logger.info(f"默认每题满分: {default_max_score} (当试卷未识别到分值时使用)")
        
        update_progress(20, f"已识别出 {len(questions_to_grade)} 道题，准备逐题批改...")
        
        total_qs_count = len(questions_to_grade)
        
        for index, q_item in enumerate(questions_to_grade):
            q_num = q_item['id']
            group_name = q_item['group']
            unique_id = q_item.get('unique_id', q_num)
            q_item['unique_id'] = unique_id
            
            current_max_score = q_item.get('score')
            if current_max_score is None:
                current_max_score = default_max_score
            else:
                try:
                    current_max_score = float(current_max_score)
                except:
                    current_max_score = default_max_score
            
            desc = f"{group_name} 第{q_num}题 (满分{current_max_score}分)" if group_name else f"第{q_num}题 (满分{current_max_score}分)"
            logger.info(f"\n正在批改 {desc}...")
            
            current_percent = 20 + int((index / total_qs_count) * 70)
            update_progress(current_percent, f"正在批改 {desc}...")
            
            question_results = {}
            
            for model_name in available_models:
                logger.info(f"  使用{model_name}批改...")
                result = self.grade_with_model(
                    image_path, 
                    model_name, 
                    q_num, 
                    current_max_score,
                    group_name=group_name,
                    answer_content=answer_content
                )
                
                if result['success']:
                    question_results[model_name] = result
                    logger.info(f"    ✓ {model_name}: 得分={result['score']}, 正确={result['is_correct']}")
                else:
                    logger.error(f"    ✗ {model_name}: {result.get('error', '失败')}")
                    question_results[model_name] = {
                        'score': 0,
                        'is_correct': False,
                        'comment': result.get('error', '失败')
                    }
            
            all_results[unique_id] = question_results
            
            for model_name, result in question_results.items():
                if model_name not in model_results:
                    model_results[model_name] = 0
                model_results[model_name] += result.get('score', 0)
        
        logger.info(f"\n综合批改结果...")
        update_progress(95, "正在综合多模型评分结果...")
        
        final_results = self.combine_results_v2(all_results, questions_to_grade, default_max_score)
        
        for q_item in questions_to_grade:
            unique_id = q_item.get('unique_id')
            box_2d = q_item.get('box_2d')
            if unique_id in final_results['details']:
                final_results['details'][unique_id]['box_2d'] = box_2d
        
        marked_image_path = self.mark_exam_image(image_path, final_results)
        marked_image_filename = os.path.basename(marked_image_path)
        
        update_progress(100, "批改完成！")
        
        return {
            'success': True,
            'image_path': image_path,
            'marked_image_path': marked_image_path,
            'marked_image_filename': marked_image_filename,
            'question_count': question_count,
            'max_score': default_max_score,
            'all_results': all_results,
            'model_results': model_results,
            'final_results': final_results
        }

    def combine_results_v2(self, all_results: Dict, questions_info: List[Dict], default_max_score: float) -> Dict:
        """
        综合多个模型的批改结果 (V2版本，支持不同题目不同分值)
        """
        final_results = {}
        total_score = 0
        max_total_score = 0
        
        q_info_map = {q.get('unique_id'): q for q in questions_info if q.get('unique_id')}
        
        for q_id, question_results in all_results.items():
            q_info = q_info_map.get(q_id, {})
            current_max_score = q_info.get('score')
            if current_max_score is None:
                current_max_score = default_max_score
            else:
                try:
                    current_max_score = float(current_max_score)
                except:
                    current_max_score = default_max_score
            
            max_total_score += current_max_score
            
            scores = [r['score'] for r in question_results.values()]
            
            if len(scores) > 0:
                avg_score = sum(scores) / len(scores)
                final_score = round(avg_score * 2) / 2
                final_score = max(0, min(final_score, current_max_score))
            else:
                final_score = 0
            
            is_correct = final_score >= current_max_score * 0.6
            
            if is_correct:
                comment = "正确"
            elif final_score >= current_max_score * 0.5:
                comment = "基本正确"
            elif final_score > 0:
                comment = "部分正确"
            else:
                comment = "错误"
            
            analysis = ""
            for res in question_results.values():
                if res.get('analysis'):
                    analysis = res.get('analysis')
                    break
            
            if not analysis:
                 for res in question_results.values():
                    if res.get('comment') and len(res.get('comment')) > len(analysis):
                        analysis = res.get('comment')

            total_score += final_score
            
            final_results[q_id] = {
                'question_id': q_id,
                'score': final_score,
                'max_score': current_max_score,
                'is_correct': is_correct,
                'comment': comment,
                'analysis': analysis,
                'model_scores': question_results,
                'box_2d': q_info.get('box_2d')
            }
            
            if '-' in str(q_id):
                parts = str(q_id).rsplit('-', 1)
                final_results[q_id]['group_name'] = parts[0]
                final_results[q_id]['sub_id'] = parts[1]
        
        return {
            'details': final_results,
            'total_score': total_score,
            'max_total_score': max_total_score,
            'accuracy': total_score / max_total_score if max_total_score > 0 else 0,
            'correct_count': sum(1 for r in final_results.values() if r['is_correct']),
            'total_count': len(final_results)
        }
    
    def mark_exam_image(self, image_path: str, grading_results: Dict, output_path: str = None) -> str:
        """
        在试卷图片上标记对错（代理调用ImageProcessor的方法）
        """
        processor = ImageProcessor()
        return processor.mark_exam_image(image_path, grading_results, output_path)

    def save_grading_report(self, report: Dict, output_path: str):
        """
        保存批改报告
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"批改报告已保存到: {output_path}")

def run_grading_task(task_id, filepath, filename, question_count, max_score, selected_models=None, answer_file_path=None):
    """后台运行批改任务"""
    try:
        grader = ExamGrader()
        
        def progress_callback(percent, message):
            if task_id in grading_tasks:
                grading_tasks[task_id]['progress'] = percent
                grading_tasks[task_id]['message'] = message
                logger.info(f"[Task {task_id}] Progress: {percent}% - {message}")
        
        # 批改试卷
        report = grader.grade_exam_with_multiple_models(
            filepath,
            question_count=question_count,
            max_score=max_score,
            selected_models=selected_models,
            progress_callback=progress_callback,
            answer_file_path=answer_file_path
        )
        
        if report['success']:
            # 保存批改报告
            output_dir = os.path.join(Config.GRADING_FOLDER, 
                                          os.path.splitext(filename)[0])
            os.makedirs(output_dir, exist_ok=True)
            
            report_path = os.path.join(output_dir, 
                                       f"grading_{os.path.splitext(filename)[0]}.json")
            grader.save_grading_report(report, report_path)
            
            # 复制报告到静态目录
            static_report_path = os.path.join(Config.UPLOAD_FOLDER, 
                                                      f"grading_{os.path.splitext(filename)[0]}.json")
            shutil.copy2(report_path, static_report_path)
            
            # 更新任务状态
            grading_tasks[task_id]['status'] = 'completed'
            grading_tasks[task_id]['progress'] = 100
            grading_tasks[task_id]['result_filename'] = filename
            grading_tasks[task_id]['report_path'] = static_report_path
            grading_tasks[task_id]['marked_image_filename'] = report.get('marked_image_filename')
        else:
            grading_tasks[task_id]['status'] = 'error'
            grading_tasks[task_id]['error'] = report.get('error', '未知错误')
            
    except Exception as e:
        import traceback
        logger.error(f"Task Error: {traceback.format_exc()}")
        grading_tasks[task_id]['status'] = 'error'
        grading_tasks[task_id]['error'] = str(e)
