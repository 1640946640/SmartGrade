# SmartGrade - 智能试卷批改系统

SmartGrade 是一个基于多模态大模型（VLM）的智能试卷批改系统。它能够自动分析试卷结构，识别题目和手写答案，并结合标准答案（支持 Word 文档）进行多维度评分和点评。

系统支持多种先进的视觉大模型，包括 Qwen-VL-Max（通义千问）、Gemini 1.5 Pro (via XHuoAI) 和 GLM-4V（智谱AI），通过多模型协作提高批改准确率。

## 主要功能

- **多模型智能批改**：集成 Qwen-VL、Gemini、GLM-4V 等顶级视觉模型，支持单模型或多模型联合批改。
- **自动结构分析**：自动识别试卷版面（支持双栏布局），定位题号、识别分值和题目区域。
- **标准答案比对**：支持上传 `.docx` 格式的标准答案，系统会自动提取分值规则并进行语义比对。
- **智能评分与评语**：根据答案正确性、逻辑清晰度和表达完整性进行评分，并生成详细的解析和评语。
- **可视化报告**：在试卷原图上标记对错（正确/错误），并生成包含详细分析的 JSON 和 HTML 报告。

## 环境搭建

推荐使用 Conda 创建独立的虚拟环境。

### 1. 创建虚拟环境

请确保已安装 Anaconda 或 Miniconda。

```bash
# 创建名为 smartgrade 的环境，推荐使用 Python 3.10 或更高版本
conda create -n smartgrade python=3.10

# 激活环境
conda activate smartgrade
```

### 2. 一键安装依赖

项目根目录下提供了 `requirements.txt` 文件。建议使用清华源加速下载：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**注意**: 本项目依赖 `paddleocr` 和 `opencv-python-headless` 进行图像处理，如果安装过程中遇到问题，请确保系统已安装相关的 C++ 编译工具。

## 配置与密钥补全

项目使用环境变量来管理大模型的 API 密钥。

1. 在项目根目录下创建一个名为 `.env` 的文件（可以直接复制 `.env.example` 如果有的话，或者参考下方内容）。
2. 将你的 API 密钥填入对应的字段中。

**`.env` 文件内容模板：**

```ini
# Flask Secret Key
SECRET_KEY=your_secret_key_here

# 阿里云 DashScope API Key (用于 Qwen-VL-Max)
# 获取地址: https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 智谱 AI (GLM-4V) API Key
# 获取地址: https://open.bigmodel.cn/
ZHIPU_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx

# XHuoAI API Key (用于 Gemini 3 Pro / 1.5 Pro)
# 获取地址: https://api.xhuoai.com/
XHUOAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
XHUOAI_BASE_URL=https://api.xhuoai.com/v1
```

> **提示**: 你只需要配置你计划使用的模型的 API Key。例如，如果你只打算使用 Qwen-VL，则只需配置 `DASHSCOPE_API_KEY`。

## 项目结构

```text
SmartGrade/
├── app/
│   ├── routes/          # 路由定义 (API 接口与页面路由)
│   ├── services/        # 核心业务逻辑
│   │   ├── grading_service.py  # 批改服务 (调用大模型)
│   │   ├── image_service.py    # 图像处理服务 (OpenCV/PaddleOCR)
│   │   └── report_service.py   # 报告生成服务
│   ├── utils/           # 工具函数 (日志、文件处理)
│   └── config.py        # 应用配置
├── static/              # 静态文件 (上传的试卷、生成的报告、CSS/JS)
├── templates/           # HTML 模板
├── tests/               # 测试脚本
├── run.py               # 项目启动入口
├── requirements.txt     # 项目依赖
└── .env                 # 环境变量配置文件
```

## 运行指南

确保环境已激活且依赖已安装，在项目根目录下运行：

```bash
python run.py
```

启动成功后，控制台会显示访问地址，通常为：
`http://127.0.0.1:5000`

在浏览器中打开该地址即可使用系统。

## 使用流程

1. **上传试卷**：在首页上传学生试卷图片（支持 JPG, PNG）。
2. **上传答案（可选）**：上传对应的标准答案 Word 文档（.docx），系统会自动提取评分标准。
3. **选择模型**：勾选你希望使用的 AI 模型（如 Qwen-VL-Max）。
4. **开始批改**：点击“开始批改”，系统将后台运行。
5. **查看结果**：批改完成后，查看详细的得分、评语以及标记后的试卷图片。

---
*Created for SmartGrade Project.*
