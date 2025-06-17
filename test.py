#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Eecho's SSTI CTF Challenge功能
"""

import requests
import json

def test_basic_templates():
    """测试基础模板"""
    url = "http://localhost:5000/render"
    
    test_cases = [
        {
            "name": "基础变量",
            "template": "Hello {{ name }}!",
            "expected": "Hello Eecho!"
        },
        {
            "name": "数学运算",
            "template": "1 + 1 = {{ 1 + 1 }}",
            "expected": "1 + 1 = 2"
        },
        {
            "name": "列表长度",
            "template": "列表长度: {{ numbers | length }}",
            "expected": "列表长度: 5"
        },
        {
            "name": "字符串操作",
            "template": "{{ string | upper }}",
            "expected": "HELLO WORLD"
        }
    ]
    
    print("🧪 测试基础模板...")
    for test in test_cases:
        try:
            response = requests.post(url, json={"template": test["template"]})
            if response.status_code == 200:
                result = response.json()
                print(f"✅ {test['name']}: {result['result']}")
            else:
                print(f"❌ {test['name']}: {response.text}")
        except Exception as e:
            print(f"❌ {test['name']}: 连接失败 - {e}")

def test_waf_rules():
    """测试WAF规则"""
    url = "http://localhost:5000/render"
    
    blocked_keywords = [
        "{{ config }}",
        "{{ request }}",
        "{{ session }}",
        "{{ g }}",
        "{{ url_for }}",
        "{{ get_flashed_messages }}",
        "{{ config.items() }}",
        "{{ config.values() }}",
        "{{ config.keys() }}",
        "{{ config.__class__ }}",
        "{{ config.__class__.__init__ }}",
        "{{ config.__class__.__bases__ }}",
        "{{ config.__class__.__subclasses__ }}",
        "{{ ''.__class__ }}",
        "{{ ''.__class__.__bases__ }}",
        "{{ ''.__class__.__bases__[0].__subclasses__ }}",
        "{{ ''.__class__.__bases__[0].__subclasses__() }}",
        "{{ ''.__class__.__bases__[0].__subclasses__()[40] }}",
        "{{ ''.__class__.__bases__[0].__subclasses__()[40]('/etc/passwd').read() }}",
        "{{ ''.__class__.__bases__[0].__subclasses__()[40]('flag.txt').read() }}",
    ]
    
    print("\n🛡️ 测试WAF规则...")
    for i, template in enumerate(blocked_keywords):
        try:
            response = requests.post(url, json={"template": template})
            if response.status_code == 403:
                print(f"✅ WAF阻止: {template[:50]}...")
            else:
                print(f"⚠️  WAF未阻止: {template[:50]}...")
        except Exception as e:
            print(f"❌ 连接失败: {e}")

def test_server_status():
    """测试服务器状态"""
    try:
        response = requests.get("http://localhost:5000/status")
        if response.status_code == 200:
            status = response.json()
            print(f"\n📊 服务器状态: {status['status']}")
            print(f"🛡️  WAF规则数量: {len(status['waf_rules'])}")
            print(f"🎯 Flag文件存在: {status['flag_exists']}")
        else:
            print("❌ 无法获取服务器状态")
    except Exception as e:
        print(f"❌ 连接服务器失败: {e}")

if __name__ == "__main__":
    print("🚀 Eecho's SSTI CTF Challenge 测试")
    print("=" * 50)
    
    # 测试服务器状态
    test_server_status()
    
    # 测试基础模板
    test_basic_templates()
    
    # 测试WAF规则
    test_waf_rules()
    
    print("\n✅ 测试完成！") 