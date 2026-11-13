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
