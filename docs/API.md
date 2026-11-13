# 统一靶场 API 契约（v1）

所有「控制台型」靶场（`02-jinja-chain`、`03-mako-chain`、`04-tornado-chain`、`05-jinja-sandbox`、
`06-blind-ssti`、`08-freemarker-memshell`）实现同一套 HTTP API，前端 `frontend/` 只依赖本契约。

> 这是**冻结契约**。新增靶场必须实现它，前端不得依赖契约之外的字段。
> 所有响应均为 `application/json; charset=utf-8`，除非特别说明。

---

## 1. 基础

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 靶场控制台页面（由 `frontend/` 构建产物提供） |
| GET | `/healthz` | 健康检查，返回 `200`，body `ok`（纯文本） |
| GET | `/api/lab-info` | 靶场元信息（**前端启动时唯一必需的调用**） |
| GET | `/api/engines` | 该靶场支持的模板引擎列表 |
| GET | `/api/levels` | 关卡列表，query 可选 `engine` |
| POST | `/api/render` | 提交模板并渲染（核心接口） |
| GET | `/api/god/source` | 上帝模式：取当前关卡的出题源码 |
| POST | `/api/admin/reset` | 重写 `/flag`，需请求头 `X-Reset-Token` |

---

## 2. `GET /api/lab-info`

```jsonc
{
  "id": "jinja-chain",                  // 靶场目录名（去掉序号前缀）
  "title": "Jinja2 WAF 链",
  "subtitle": "13 关递增过滤，逐层绕过",
  "engine": "jinja",                    // 默认引擎 id；单引擎靶场即唯一引擎
  "engine_title": "Jinja2",
  "description": "本靶场用同一套 13 关 WAF 链……",
  "no_egress": false,                   // true = 容器已切断出网（内存马/盲注靶场）
  "no_egress_note": "容器已禁止出网：反弹 shell / DNSLog 均不可用，必须走内存马或文件回显。",
  "flag_path": "/flag",
  "flag_format": "flag{...}",
  "theme": {                            // 前端据此注入主题，缺省用 cyber
    "name": "cyber",
    "accent": "#00e5ff",
    "accent2": "#ff2bd6",
    "glow": "rgba(0,229,255,0.55)"
  },
  "doc_url": "/docs/lab.md",            // 容器内自带的题解文档（可 404）
  "hint": "先确定引擎：`{{7*7}}`、`${7*7}`、`<%= 7*7 %>` 哪一个生效。",
  "engines": [                          // 供前端渲染引擎切换器；单引擎时前端隐藏切换器
    { "id": "jinja", "title": "Jinja2" }
  ],
  "levels": [
    {
      "id": "0",                        // 字符串，稳定标识
      "title": "L1 - 无过滤",
      "summary": "无过滤",               // 一句话概述
      "description": "用户输入原样进入 render_template_string。",
      "blind": false,                   // true = 只回显 correct / wrong
      "no_egress": false,               // true = 本关额外切断出网
      "waf": {                          // null 表示无过滤；否则为机器可读的过滤规则摘要
        "kind": "substring",            // substring | chars | regex | prefix | combo
        "items": ["__", "os", "flag"],
        "note": "命中任一子串即返回 WAF"
      },
      "hint": "本关可用 `|attr` 绕过点号……"
    }
  ]
}
```

> `levels` 同时出现在 `/api/lab-info` 与 `/api/levels` 中，字段完全一致。
> 前端**只**用 `lab-info` 就能完成初始化（含 levels），`/api/levels` 是给脚本/CLI 用的。

---

## 3. `POST /api/render`

请求体（JSON；同时兼容 `application/x-www-form-urlencoded`）：

```jsonc
{
  "engine": "jinja",                    // 省略则用 lab-info.engine
  "level": "0",                         // 省略则用 levels[0].id
  "mode": "practice",                   // practice（默认）| god
  "template": "{{7*7}}"
}
```

响应：

```jsonc
{
  "ok": true,                           // 练习模式下：无异常即 true；盲关则看 correct
  "output": "49",                       // 练习模式回显（盲关只有 "correct"/"wrong"）
  "truncated": false,
  "flag_found": false,                  // output 中含 /flag 内容时为 true
  "engine": "jinja",
  "level": "0",
  "mode": "practice",

  // ---- 仅 mode=god 时出现的字段 ----
  "template_after_waf": "{{7*7}}",      // WAF 处理后的真实模板（前缀/替换可见）
  "raw_output": "49",                   // 未经盲关包装的真实渲染输出
  "error": null,                        // 异常字符串
  "exception_type": null,               // 异常类名
  "source_class": "JinjaLevel01",       // 出题用的关卡类名
  "source_file": "ssti_core/levels/jinja.py"
}
```

**练习模式**下 WAF 命中时返回 `200` + `ok:false` + `output:"WAF"`（与参考项目一致），
前端据 `ok` 显示红/绿。异常时 `output` 为 `[渲染异常] <ExceptionType>`。

---

## 4. 其它接口

```jsonc
// GET /api/engines
{ "engines": [ { "id": "jinja", "title": "Jinja2" } ] }

// GET /api/levels?engine=jinja
{ "engine": "jinja", "levels": [ /* 同 lab-info.levels */ ] }

// GET /api/god/source?engine=jinja&level=0
{ "ok": true, "path": "ssti_core.levels.jinja.JinjaLevel01", "source": "class JinjaLevel01(...):\n    ..." }

// POST /api/admin/reset   请求头 X-Reset-Token: <RESET_TOKEN>
{ "ok": true, "message": "已重写 /flag（来自当前环境变量优先级）" }
```

---

## 5. 场景型靶场（不受本契约约束）

`01-jinja-waf-fenjing`、`07-flask-memshell` 是**场景型**靶场：它们模拟一个真实业务
（登录、笔记、Host 头审计等），页面由靶场自己渲染，不套用上面的控制台。
它们**仍需**提供：

- `GET /healthz` → `200 ok`
- `GET /api/lab-info` → 至少包含 `id / title / description / no_egress / levels[]`，
  其中 `levels[]` 用 `{id,title,description}` 描述攻击链步骤，供总览页展示。
- `/flag` 由 entrypoint 从环境变量写入。

场景型靶场把业务页面放在 `/`，把统一控制台挂在 **`/console/`**（见
`ssti_core.labapp.mount_console`）。检测方式：`GET /console/` 应返回引用
`assets/` 的前端页面；`GET /` 返回业务页面。

---

## 6. 边界与易误解点（实现者与前端都必须按这里来）

这一节是对前面契约的**收敛**，来自实际联调中暴露的歧义。新增实现请勿偏离。

| # | 问题 | 约定 |
|---|------|------|
| 1 | 盲关怎么判断成功？ | **只有一个信号：`ok`。** `echo_mode="bool"` 时后端返回 `ok:true, output:"correct"` 或 `ok:false, output:"wrong"`；`echo_mode="none"` 时 `ok` 仍表示渲染是否抛异常，但 `output` 恒定（`echo_text`），**不要**用它判断结果。前端只需要看 `ok`，并额外展示 `output` 原文。 |
| 2 | `level.id` 的类型 | **字符串**，实现必须保证。前端应做 `String()` 归一后再比较，容忍历史实现里的整数。 |
| 3 | `/api/god/source` 失败时返回什么 | `500` + `{"ok": false, "error": "<原因>"}`。前端要同时容忍「非 2xx」与「2xx 但 `ok:false`」两种形态。 |
| 4 | `theme.glow` 是什么 | **一个 CSS 颜色值**（通常 `rgba(...)`），不是完整的 `box-shadow` 字符串。前端自行拼 `box-shadow`；缺失时用 `accent` 推导一个 rgba 兜底。 |
| 5 | `truncated` 的语义 | 输出**从尾部截断**，前缀保留；上限来自环境变量 `SSTI_MAX_OUTPUT_CHARS`（默认 262144）。被截断时 `output` 末尾会附加 `\n... [输出已截断]`。前端只需给出提示，不需要自己再截。 |
| 6 | `/api/render` 的 4xx/5xx 响应体 | 统一 `{"ok": false, "error": "<原因>"}`；未知 `engine`/`level` **不报错**，按 `find_level` 规则回落到该引擎的第一关。 |
| 7 | `engine_title` 与 `engines[].title` 重复 | `engines[]` 是权威列表，`engine_title` 只是 `lab-info.engine` 的展示名便捷字段。两者冲突时以前者为准。 |
| 8 | 每关的 `no_egress` 有没有说明文字 | 没有。文字说明在 `lab-info.no_egress_note`（靶场级）。前端只给标签、不加 tooltip。 |
| 9 | 关卡 `waf` 的字段 | `kind` ∈ `none` / `prefix` / `substring` / `chars` / `regex` / `combo`；`items` 是 `substrings + chars + regexes` 的合并列表（便于前端一行渲染）；`substrings` / `chars` / `regexes` / `prefix` / `suffix` 为可选细分字段；`waf` 为 `null` 表示无过滤。 |
| 10 | `flag_found` 的判定 | 后端在 `output`（练习模式）与 `raw_output`（上帝模式）里任一出现 `/flag` 内容即置 `true`。**不要**在前端自己判断。 |
| 11 | `mode=god` 时的 `raw_output` | 普通关与 `output` 相同；盲关是**未经 correct/wrong 包装**的真实渲染结果；`echo_mode="none"` 时同样是真实结果（这是上帝模式对出题人的主要价值）。 |

