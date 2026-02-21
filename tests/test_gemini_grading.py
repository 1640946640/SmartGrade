#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用 Gemini 3 Pro 对试卷进行批改的验证脚本
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from app.services.grading_service import ExamGrader

load_dotenv()

def grade_with_gemini(image_path: str, question_count: int = 3, default_max_score: float = 10.0):
    """
    使用 Gemini 3 Pro 对试卷进行批改
    
    Args:
        image_path: 试卷图片路径
        question_count: 题目数量（留空或 None 则自动识别）
        default_max_score: 每题默认满分
        
    Returns:
        批改报告字典
    """
    grader = ExamGrader(api_keys={
        'gemini-3-pro': os.getenv("XHUOAI_API_KEY"),
        'qwen-vl-max': os.getenv("DASHSCOPE_API_KEY")
    })
    
    report = grader.grade_exam_with_multiple_models(
        image_path=image_path,
        question_count=question_count,
        max_score=default_max_score,
        selected_models=['gemini-3-pro']
    )
    return report

def main():
    """
    主函数：调用 Gemini 批改，并输出结果摘要
    """
    # 优先使用 test_images 目录下的样例
    # 注意：脚本现在在 tests/ 目录下，所以要向上找
    candidates = [
        os.path.join('..', 'test_images', '1.jpg'),
        os.path.join('..', 'static', 'uploads', '1.jpg')
    ]
    image_path = None
    for p in candidates:
        if os.path.exists(p):
            image_path = p
            break
    
    if not image_path:
        print("❌ 未找到可用的测试图片，请将一张试卷图片放置到 test_images/1.jpg 后再试")
        return
    
    print(f"📄 使用图片: {image_path}")
    print("🧪 正在使用 Gemini 3 Pro 进行批改...")
    report = grade_with_gemini(image_path=image_path, question_count=3, default_max_score=10.0)
    
    if not report.get('success'):
        print(f"❌ 批改失败: {report.get('error', '未知错误')}")
        return
    
    final = report['final_results']
    print("\n✅ 批改成功")
    print(f"- 总分: {final['total_score']} / {final['max_total_score']}")
    print(f"- 正确率: {final['accuracy']:.2%}")
    print(f"- 正确题数: {final['correct_count']} / {final['total_count']}")
    
    print("\n📊 逐题汇总（Gemini 3 Pro）：")
    for qid, detail in final['details'].items():
        print(f"  题目 {qid}: {detail['score']}/{detail['max_score']} - {detail['comment']}")

if __name__ == "__main__":
    main()
