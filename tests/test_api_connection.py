#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API连接测试脚本
用于测试各个VLM API的连接状态
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_qwen_vl():
    """测试Qwen-VL连接"""
    print("\n" + "=" * 60)
    print("测试 Qwen-VL (阿里云 DashScope)")
    print("=" * 60)
    
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("❌ 未配置 DASHSCOPE_API_KEY")
        return False
    
    print(f"✅ API密钥已配置: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        import dashscope
        from dashscope import MultiModalConversation
        
        dashscope.api_key = api_key
        
        # 创建一个简单的测试消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"text": "你好，请回复'连接成功'"}
                ]
            }
        ]
        
        print("📡 正在连接...")
        response = MultiModalConversation.call(model="qwen-vl-max", messages=messages)
        
        print(f"✅ 连接成功！")
        print(f"   响应: {response}")
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请运行: pip install dashscope")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        
        # 提供详细的错误诊断
        if "Connection" in str(e) or "10053" in str(e):
            print("\n   🔍 诊断建议:")
            print("   1. 检查网络连接是否正常")
            print("   2. 检查防火墙是否阻止了API连接")
            print("   3. 尝试使用VPN或代理")
            print("   4. 检查API密钥是否正确")
        elif "401" in str(e) or "403" in str(e):
            print("\n   🔍 诊断建议:")
            print("   1. API密钥可能无效或已过期")
            print("   2. 请访问 https://dashscope.console.aliyun.com/ 检查密钥")
        elif "429" in str(e):
            print("\n   🔍 诊断建议:")
            print("   1. API调用频率超限")
            print("   2. 请稍后再试")
        
        return False

def test_zhipu_glm():
    """测试智谱GLM连接"""
    print("\n" + "=" * 60)
    print("测试 GLM-4V (智谱AI)")
    print("=" * 60)
    
    api_key = os.getenv("ZHIPU_API_KEY")
    
    if not api_key:
        print("❌ 未配置 ZHIPU_API_KEY")
        return False
    
    print(f"✅ API密钥已配置: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        from zhipuai import ZhipuAI
        
        client = ZhipuAI(api_key=api_key)
        
        print("📡 正在连接...")
        response = client.chat.completions.create(
            model="glm-4",  # 测试文本模型即可
            messages=[
                {"role": "user", "content": "你好，请回复'连接成功'"}
            ],
        )
        
        print(f"✅ 连接成功！")
        print(f"   响应: {response.choices[0].message.content}")
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请运行: pip install zhipuai")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        
        # 提供详细的错误诊断
        if "401" in str(e) or "403" in str(e):
            print("\n   🔍 诊断建议:")
            print("   1. API密钥可能无效或已过期")
            print("   2. 请访问 https://open.bigmodel.cn/ 检查密钥")
        
        return False

def test_network():
    """测试基本网络连接"""
    print("\n" + "=" * 60)
    print("测试基本网络连接")
    print("=" * 60)
    
    import urllib.request
    import socket
    
    test_urls = [
        ("百度", "https://www.baidu.com"),
        ("阿里云", "https://dashscope.aliyuncs.com"),
        ("OpenAI", "https://api.openai.com")
    ]
    
    results = []
    for name, url in test_urls:
        try:
            print(f"📡 测试 {name} ({url})...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                print(f"   ✅ 连接成功 (状态码: {status})")
                results.append((name, True, None))
        except urllib.error.URLError as e:
            print(f"   ❌ 连接失败: {e}")
            results.append((name, False, str(e)))
        except socket.timeout:
            print(f"   ❌ 连接超时")
            results.append((name, False, "超时"))
        except Exception as e:
            print(f"   ❌ 未知错误: {e}")
            results.append((name, False, str(e)))
    
    return results

def main():
    """主测试函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "API连接诊断工具" + " " * 28 + "║")
    print("╚" + "=" * 58 + "╝")
    
    # 检查API密钥配置
    print("\n📋 API密钥配置状态:")
    keys = {
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ZHIPU_API_KEY": os.getenv("ZHIPU_API_KEY"),
        "XHUOAI_API_KEY": os.getenv("XHUOAI_API_KEY")
    }
    
    for key_name, key_value in keys.items():
        if key_value:
            print(f"   ✅ {key_name}: 已配置")
        else:
            print(f"   ❌ {key_name}: 未配置")
    
    # 测试基本网络连接
    network_results = test_network()
    
    # 测试各个API
    qwen_ok = test_qwen_vl()
    gpt_ok = test_gpt_4v()
    # gemini_ok = test_gemini_pro() # 暂时注释掉，未找到定义
    zhipu_ok = test_zhipu_glm()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    print(f"\n网络连接测试:")
    for name, success, error in network_results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {status} {name}")
        if error:
            print(f"      错误: {error}")
    
    print(f"\nAPI连接测试:")
    print(f"   {'✅ 成功' if qwen_ok else '❌ 失败'} Qwen-VL")
    print(f"   {'✅ 成功' if gpt_ok else '❌ 失败'} GPT-4V")
    # print(f"   {'✅ 成功' if gemini_ok else '❌ 失败'} Gemini 3 Pro")
    print(f"   {'✅ 成功' if zhipu_ok else '❌ 失败'} GLM-4V")
    
    # 提供解决方案
    if not qwen_ok and not gpt_ok and not zhipu_ok:
        print("\n" + "⚠️" * 20)
        print("\n所有API连接都失败了！请检查：")
        print("\n1. 网络连接:")
        print("   - 确保网络连接正常")
        print("   - 尝试访问 https://www.baidu.com")
        print("\n2. 防火墙/代理:")
        print("   - 检查防火墙设置")
        print("   - 尝试使用VPN或代理")
        print("\n3. API密钥:")
        print("   - 确认API密钥正确")
        print("   - 检查API密钥是否过期")
        print("\n4. 地区限制:")
        print("   - 可以尝试使用阿里云DashScope (Qwen-VL)")
        print("\n" + "⚠️" * 20)
    elif qwen_ok:
        print("\n✅ Qwen-VL 连接成功！可以使用该模型进行批改。")
    elif zhipu_ok:
        print("\n✅ GLM-4V 连接成功！可以使用该模型进行批改。")

if __name__ == "__main__":
    main()
