#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多模型批改功能测试脚本
用于测试ExamGrader的多模型综合批改功能
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from app.services.grading_service import ExamGrader
from app.services.image_service import ImageProcessor
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_single_model():
    """测试单个模型批改"""
    print("=" * 60)
    print("测试1: 单个模型批改")
    print("=" * 60)
    
    # 检查测试图片是否存在
    test_image = os.path.join("..", "static", "uploads", "daan1.jpg")
    if not os.path.exists(test_image):
        # 尝试备用路径
        test_image = os.path.join("..", "test_images", "1.jpg")
    
    if not os.path.exists(test_image):
        print(f"❌ 测试图片不存在: {test_image}")
        print("请先上传一张测试图片到 static/uploads/ 目录或确保 test_images/1.jpg 存在")
        return False
    
    # 创建批改器实例
    grader = ExamGrader()
    
    # 测试Qwen-VL模型
    print("\n📝 使用Qwen-VL模型批改第1题...")
    try:
        result = grader.grade_with_model(
            image_path=test_image,
            model_name="qwen-vl-max",
            question_number=1,
            max_score=10
        )
        print(f"✅ 批改成功！")
        print(f"   得分: {result['score']}/{result['max_score']}")
        print(f"   是否正确: {result['is_correct']}")
        print(f"   评语: {result['comment']}")
    except Exception as e:
        print(f"❌ 批改失败: {str(e)}")
        return False
    
    return True

def test_multiple_models():
    """测试多个模型批改同一道题"""
    print("\n" + "=" * 60)
    print("测试2: 多个模型批改同一道题")
    print("=" * 60)
    
    test_image = os.path.join("..", "static", "uploads", "daan1.jpg")
    if not os.path.exists(test_image):
         test_image = os.path.join("..", "test_images", "1.jpg")

    if not os.path.exists(test_image):
        print(f"❌ 测试图片不存在: {test_image}")
        return False
    
    grader = ExamGrader()
    models = ["qwen-vl-max", "gpt-4v"]
    
    results = {}
    for model in models:
        print(f"\n📝 使用{model}模型批改第1题...")
        try:
            result = grader.grade_with_model(
                image_path=test_image,
                model_name=model,
                question_number=1,
                max_score=10
            )
            results[model] = result
            print(f"✅ {model} 得分: {result['score']}/{result['max_score']}")
        except Exception as e:
            print(f"❌ {model} 批改失败: {str(e)}")
            results[model] = None
    
    # 比较结果
    print("\n📊 各模型评分对比:")
    print("-" * 60)
    valid_results = {k: v for k, v in results.items() if v is not None}
    for model, result in valid_results.items():
        print(f"{model:15s}: {result['score']:5.1f} / {result['max_score']}")
    
    if len(valid_results) > 1:
        scores = [r['score'] for r in valid_results.values()]
        avg_score = sum(scores) / len(scores)
        print("-" * 60)
        print(f"{'平均':15s}: {avg_score:5.1f}")
    
    return len(valid_results) > 0

def test_full_exam_grading():
    """测试完整试卷批改"""
    print("\n" + "=" * 60)
    print("测试3: 完整试卷批改（多模型综合）")
    print("=" * 60)
    
    test_image = os.path.join("..", "static", "uploads", "daan1.jpg")
    if not os.path.exists(test_image):
         test_image = os.path.join("..", "test_images", "1.jpg")

    if not os.path.exists(test_image):
        print(f"❌ 测试图片不存在: {test_image}")
        return False
    
    grader = ExamGrader()
    
    print(f"\n📝 开始批改试卷（3道题，每题10分）...")
    try:
        result = grader.grade_exam_with_multiple_models(
            image_path=test_image,
            question_count=3,
            max_score=10
        )
        
        print(f"\n✅ 批改完成！")
        print(f"\n📊 总分统计:")
        print(f"   总得分: {result['final_results']['total_score']}")
        print(f"   满分: {result['final_results']['max_total_score']}")
        print(f"   正确率: {result['final_results']['accuracy'] * 100:.1f}%")
        print(f"   正确题数: {result['final_results']['correct_count']}")
        
        print(f"\n📊 各模型总得分:")
        for model, score in result['model_results'].items():
            print(f"   {model}: {score}")
        
        print(f"\n📝 详细批改结果:")
        for q_id, item in result['final_results']['details'].items():
            print(f"\n   题目 {item['question_id']}:")
            print(f"     最终得分: {item['score']}/{item['max_score']}")
            print(f"     是否正确: {'✓' if item['is_correct'] else '✗'}")
            print(f"     评语: {item['comment']}")
            if item.get('model_scores'):
                print(f"     各模型评分:")
                for model, model_result in item['model_scores'].items():
                    print(f"       {model}: {model_result['score']}")
        
        # 保存结果
        output_file = "test_grading_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存到: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 批改失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_image_preprocessing():
    """测试图像预处理"""
    print("\n" + "=" * 60)
    print("测试4: 图像预处理")
    print("=" * 60)
    
    test_image = os.path.join("..", "static", "uploads", "daan1.jpg")
    if not os.path.exists(test_image):
         test_image = os.path.join("..", "test_images", "1.jpg")

    if not os.path.exists(test_image):
        print(f"❌ 测试图片不存在: {test_image}")
        return False
    
    # Renamed to ImageProcessor
    analyzer = ImageProcessor()
    
    print(f"\n🔧 预处理图像...")
    try:
        processed_image = analyzer.preprocess_image(test_image)
        print(f"✅ 预处理成功！")
        print(f"   原始图片: {test_image}")
        print(f"   处理后图片: {processed_image.shape}")
        
        # 保存处理后的图片
        output_dir = os.path.join("..", "static", "uploads")
        os.makedirs(output_dir, exist_ok=True)
        output_path = analyzer.save_processed_image(processed_image, output_dir)
        print(f"   已保存到: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 预处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_api_keys():
    """检查API密钥配置"""
    print("=" * 60)
    print("检查API密钥配置")
    print("=" * 60)
    
    keys = {
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY")
    }
    
    all_configured = True
    for key_name, key_value in keys.items():
        if key_value:
            print(f"✅ {key_name}: 已配置")
        else:
            print(f"❌ {key_name}: 未配置")
            all_configured = False
    
    if not all_configured:
        print("\n⚠️  警告: 部分API密钥未配置，相关模型将无法使用")
        print("请在.env文件中配置以下API密钥:")
        print("   - DASHSCOPE_API_KEY (用于Qwen-VL)")
        print("   - OPENAI_API_KEY (用于GPT-4V)")
        print("   - ANTHROPIC_API_KEY (用于Claude)")
    
    return all_configured

def main():
    """主测试函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "多模型批改功能测试" + " " * 25 + "║")
    print("╚" + "=" * 58 + "╝")
    
    # 检查API密钥
    api_keys_ok = check_api_keys()
    
    if not api_keys_ok:
        print("\n⚠️  是否继续测试？（部分功能可能不可用）")
        response = input("输入 y 继续，其他键退出: ")
        if response.lower() != 'y':
            print("测试已取消")
            return
    
    # 运行测试
    tests = [
        ("图像预处理", test_image_preprocessing),
        ("单个模型批改", test_single_model),
        ("多个模型对比", test_multiple_models),
        ("完整试卷批改", test_full_exam_grading)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 发生异常: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} {test_name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息")

if __name__ == "__main__":
    main()
