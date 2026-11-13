#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# 【历史存档，不参与运行】SSTI_labs_E 最初的单挑战实现。
#
# 这是本仓库重构前根目录下的 server.py，原样保留以便对照：
#   * 关键词黑名单 UNSAFE_KEYWORDS 与危险函数正则表
#   * 裸 jinja2.Environment(loader=BaseLoader()) + 业务变量
#   * 前端与后端同端口（Flask 提供 React 构建产物）
#
# 现在它被拆成了：
#   labs/01-jinja-waf-fenjing/app.py   —— 同一套过滤规则的现代实现（可运行）
#   shared/ssti_core/engines/jinja.py  —— jinja_plain 渲染器（等价于这里的 render_template）
#   frontend/                          —— 统一前端（替代原本的 src/ + public/）
#
# 保留它的原因：仓库里 2025 年的那份 writeup 描述的正是这份代码的行为，
# 删掉就没有对照物了。
# =============================================================================
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eecho's SSTI CTF Challenge Server
Python Server-Side Template Injection Challenge with WAF
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from jinja2 import Template, Environment, BaseLoader
import re
import os
import random
import string

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# WAF规则 - 禁止的关键词
UNSAFE_KEYWORDS = ['__', 'import', 'os', 'sys', 'eval', 'subprocess', 'popen', 'system', '%2f', '%2F', 'flag', 'cat', '?']

# 生成随机flag
def generate_flag():
    """生成随机flag"""
    prefix = "Eecho{"
    suffix = "}"
    # 生成32位随机字符串
    random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    return f"{prefix}{random_chars}{suffix}"

# 创建flag文件
def create_flag_file():
    """创建flag文件"""
    flag = generate_flag()
    with open('flag.txt', 'w') as f:
        f.write(flag)
    return flag

# WAF检查函数
def check_waf(template_str):
    """
    检查模板是否包含被禁止的关键词
    返回: (is_safe, error_message)
    """
    template_lower = template_str.lower()
    
    for keyword in UNSAFE_KEYWORDS:
        if keyword.lower() in template_lower:
            return False, f"WAF检测到禁止的关键词: {keyword}"
    
    # 额外的安全检查
    dangerous_patterns = [
        r'class\s*\(',  # 类构造
        r'globals\s*\(',  # globals函数
        r'locals\s*\(',  # locals函数
        r'getattr\s*\(',  # getattr函数
        r'setattr\s*\(',  # setattr函数
        r'delattr\s*\(',  # delattr函数
        r'hasattr\s*\(',  # hasattr函数
        r'open\s*\(',  # open函数
        r'file\s*\(',  # file函数
        r'exec\s*\(',  # exec函数
        r'compile\s*\(',  # compile函数
        r'eval\s*\(',  # eval函数
        r'input\s*\(',  # input函数
        r'raw_input\s*\(',  # raw_input函数
        r'help\s*\(',  # help函数
        r'vars\s*\(',  # vars函数
        r'dir\s*\(',  # dir函数
        r'type\s*\(',  # type函数
        r'isinstance\s*\(',  # isinstance函数
        r'issubclass\s*\(',  # issubclass函数
        r'super\s*\(',  # super函数
        r'property\s*\(',  # property函数
        r'staticmethod\s*\(',  # staticmethod函数
        r'classmethod\s*\(',  # classmethod函数
        r'__import__\s*\(',  # __import__函数
        r'__builtins__',  # __builtins__
        r'__class__',  # __class__
        r'__bases__',  # __bases__
        r'__subclasses__',  # __subclasses__
        r'__mro__',  # __mro__
        r'__dict__',  # __dict__
        r'__init__',  # __init__
        r'__new__',  # __new__
        r'__call__',  # __call__
        r'__getitem__',  # __getitem__
        r'__setitem__',  # __setitem__
        r'__delitem__',  # __delitem__
        r'__getattr__',  # __getattr__
        r'__setattr__',  # __setattr__
        r'__delattr__',  # __delattr__
        r'__getattribute__',  # __getattribute__
        r'__contains__',  # __contains__
        r'__iter__',  # __iter__
        r'__next__',  # __next__
        r'__enter__',  # __enter__
        r'__exit__',  # __exit__
        r'__len__',  # __len__
        r'__str__',  # __str__
        r'__repr__',  # __repr__
        r'__format__',  # __format__
        r'__hash__',  # __hash__
        r'__bool__',  # __bool__
        r'__int__',  # __int__
        r'__float__',  # __float__
        r'__complex__',  # __complex__
        r'__index__',  # __index__
        r'__round__',  # __round__
        r'__floor__',  # __floor__
        r'__ceil__',  # __ceil__
        r'__trunc__',  # __trunc__
        r'__abs__',  # __abs__
        r'__pos__',  # __pos__
        r'__neg__',  # __neg__
        r'__add__',  # __add__
        r'__sub__',  # __sub__
        r'__mul__',  # __mul__
        r'__truediv__',  # __truediv__
        r'__floordiv__',  # __floordiv__
        r'__mod__',  # __mod__
        r'__divmod__',  # __divmod__
        r'__pow__',  # __pow__
        r'__lshift__',  # __lshift__
        r'__rshift__',  # __rshift__
        r'__and__',  # __and__
        r'__xor__',  # __xor__
        r'__or__',  # __or__
        r'__radd__',  # __radd__
        r'__rsub__',  # __rsub__
        r'__rmul__',  # __rmul__
        r'__rtruediv__',  # __rtruediv__
        r'__rfloordiv__',  # __rfloordiv__
        r'__rmod__',  # __rmod__
        r'__rdivmod__',  # __rdivmod__
        r'__rpow__',  # __rpow__
        r'__rlshift__',  # __rlshift__
        r'__rrshift__',  # __rrshift__
        r'__rand__',  # __rand__
        r'__rxor__',  # __rxor__
        r'__ror__',  # __ror__
        r'__iadd__',  # __iadd__
        r'__isub__',  # __isub__
        r'__imul__',  # __imul__
        r'__itruediv__',  # __itruediv__
        r'__ifloordiv__',  # __ifloordiv__
        r'__imod__',  # __imod__
        r'__ipow__',  # __ipow__
        r'__ilshift__',  # __ilshift__
        r'__irshift__',  # __irshift__
        r'__iand__',  # __iand__
        r'__ixor__',  # __ixor__
        r'__ior__',  # __ior__
        r'__eq__',  # __eq__
        r'__ne__',  # __ne__
        r'__lt__',  # __lt__
        r'__le__',  # __le__
        r'__gt__',  # __gt__
        r'__ge__',  # __ge__
        r'__cmp__',  # __cmp__
        r'__rcmp__',  # __rcmp__
        r'__nonzero__',  # __nonzero__
        r'__unicode__',  # __unicode__
        r'__sizeof__',  # __sizeof__
        r'__reduce__',  # __reduce__
        r'__reduce_ex__',  # __reduce_ex__
        r'__getstate__',  # __getstate__
        r'__setstate__',  # __setstate__
        r'__copy__',  # __copy__
        r'__deepcopy__',  # __deepcopy__
        r'__getnewargs__',  # __getnewargs__
        r'__getnewargs_ex__',  # __getnewargs_ex__
        r'__subclasshook__',  # __subclasshook__
        r'__abstractmethods__',  # __abstractmethods__
        r'__abstractmethod__',  # __abstractmethod__
        r'__slots__',  # __slots__
        r'__weakref__',  # __weakref__
        r'__doc__',  # __doc__
        r'__module__',  # __module__
        r'__name__',  # __name__
        r'__qualname__',  # __qualname__
        r'__annotations__',  # __annotations__
        r'__defaults__',  # __defaults__
        r'__kwdefaults__',  # __kwdefaults__
        r'__code__',  # __code__
        r'__globals__',  # __globals__
        r'__closure__',  # __closure__
        r'__func__',  # __func__
        r'__self__',  # __self__
        r'__objclass__',  # __objclass__
        r'__wrapped__',  # __wrapped__
        r'__signature__',  # __signature__
        r'__text_signature__',  # __text_signature__
        r'__kwonlydefaults__',  # __kwonlydefaults__
        r'__kwonlyargcount__',  # __kwonlyargcount__
        r'__argcount__',  # __argcount__
        r'__posonlyargcount__',  # __posonlyargcount__
        r'__varnames__',  # __varnames__
        r'__name__',  # __name__
        r'__qualname__',  # __qualname__
        r'__module__',  # __module__
        r'__doc__',  # __doc__
        r'__annotations__',  # __annotations__
        r'__defaults__',  # __defaults__
        r'__kwdefaults__',  # __kwdefaults__
        r'__code__',  # __code__
        r'__globals__',  # __globals__
        r'__closure__',  # __closure__
        r'__func__',  # __func__
        r'__self__',  # __self__
        r'__objclass__',  # __objclass__
        r'__wrapped__',  # __wrapped__
        r'__signature__',  # __signature__
        r'__text_signature__',  # __text_signature__
        r'__kwonlydefaults__',  # __kwonlydefaults__
        r'__kwonlyargcount__',  # __kwonlyargcount__
        r'__argcount__',  # __argcount__
        r'__posonlyargcount__',  # __posonlyargcount__
        r'__varnames__',  # __varnames__
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, template_str, re.IGNORECASE):
            return False, f"WAF检测到危险的模式: {pattern}"
    
    return True, ""

# 渲染模板
def render_template(template_str):
    """
    安全渲染Jinja2模板
    返回: (success, result, flag_found)
    """
    try:
        # 创建安全的Jinja2环境
        env = Environment(loader=BaseLoader())
        
        # 添加一些安全的全局变量
        context = {
            'name': 'Eecho',
            'version': '1.0.0',
            'challenge': 'SSTI CTF',
            'numbers': [1, 2, 3, 4, 5],
            'string': 'Hello World',
            'dict': {'key': 'value', 'test': 'data'},
            'list': ['a', 'b', 'c', 'd', 'e'],
            'true': True,
            'false': False,
            'none': None,
            'int': 42,
            'float': 3.14,
        }
        
        # 编译模板
        template = env.from_string(template_str)
        
        # 渲染模板
        result = template.render(**context)
        
        # 检查是否包含flag
        flag_found = False
        if os.path.exists('flag.txt'):
            with open('flag.txt', 'r') as f:
                flag_content = f.read().strip()
                if flag_content in result:
                    flag_found = True
        
        return True, result, flag_found
        
    except Exception as e:
        return False, str(e), False

@app.route('/')
def index():
    """主页 - 提供React应用"""
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """提供静态文件"""
    return send_from_directory('public', path)

@app.route('/render', methods=['POST'])
def render():
    """渲染模板接口"""
    try:
        data = request.get_json()
        
        if not data or 'template' not in data:
            return jsonify({'error': '缺少模板参数'}), 400
        
        template_str = data['template']
        
        # WAF检查
        is_safe, error_msg = check_waf(template_str)
        if not is_safe:
            return jsonify({'error': error_msg}), 403
        
        # 渲染模板
        success, result, flag_found = render_template(template_str)
        
        if not success:
            return jsonify({'error': f'模板渲染失败: {result}'}), 500
        
        response_data = {
            'result': result,
            'flag': flag_found
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/status')
def status():
    """服务器状态"""
    return jsonify({
        'status': 'running',
        'waf_rules': UNSAFE_KEYWORDS,
        'flag_exists': os.path.exists('flag.txt')
    })

if __name__ == '__main__':
    # 创建flag文件
    flag = create_flag_file()
    print(f"🚀 Eecho's SSTI CTF Challenge 启动中...")
    print(f"🎯 Flag已生成: {flag}")
    print(f"🛡️  WAF规则: {UNSAFE_KEYWORDS}")
    print(f"🌐 服务器运行在: http://localhost:5000")
    print(f"📝 渲染接口: http://localhost:5000/render")
    
    app.run(host='0.0.0.0', port=5000, debug=False) 