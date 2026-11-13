"""控制台型靶场的 Flask 应用工厂。

一个靶场容器的 ``app.py`` 通常只有十几行 —— 全部编排都在这里：

* 静态前端（``frontend/`` 的构建产物，由 Dockerfile 拷到 ``./public``）
* 契约里的全部 ``/api/*``
* ``/docs/*``：容器内自带的题目文档
* 前端构建产物缺失时的**降级控制台**（纯 HTML，无构建依赖）

场景型靶场（模拟真实业务）可以只调用 :func:`register_lab_api`，
自己接管页面渲染。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterable

from flask import Flask, abort, jsonify, request, send_from_directory

from ssti_core import flagutil
from ssti_core.config import Config
from ssti_core.labmeta import LabMeta
from ssti_core.level import Level, find_level, group_engines

#: 练习模式允许的 mode 取值
_MODES = ("practice", "god")


def _sanitize_mode(raw: Any) -> str:
    value = str(raw or "practice").strip().lower()
    return value if value in _MODES else "practice"


def _payload() -> dict[str, Any]:
    """兼容 JSON 与表单两种提交方式（方便 curl / 脚本 / 前端混用）。"""
    if request.is_json:
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            return data
    return dict(request.form or {})


def _resolve_levels(levels: list[Level], engine: str | None) -> list[Level]:
    """按引擎过滤关卡；引擎不存在时返回全部。"""
    if not engine:
        return list(levels)
    subset = [lv for lv in levels if lv.engine == engine]
    return subset or list(levels)


def lab_info_payload(meta: LabMeta, levels: list[Level]) -> dict[str, Any]:
    return meta.to_json(levels, engines=group_engines(levels))


def register_lab_api(
    app: Flask,
    meta: LabMeta,
    levels: Iterable[Level],
    *,
    engine_titles: dict[str, str] | None = None,
    docs_folder: str | os.PathLike[str] | None = None,
) -> None:
    """把契约里的 ``/api/*`` 与 ``/healthz`` 挂到既有 Flask 应用上。

    只注册接口，不碰页面路由 —— 场景型靶场用它来自定义业务页面而不冲突。
    """
    level_list = list(levels)
    titles = dict(engine_titles or {})
    if meta.engine_title:
        titles.setdefault(meta.engine, meta.engine_title)

    if docs_folder:
        docs_dir = Path(docs_folder).resolve()
        if docs_dir.is_dir():

            @app.get("/docs/<path:path>")
            def serve_docs(path: str):
                target = (docs_dir / path).resolve()
                if not str(target).startswith(str(docs_dir)) or not target.is_file():
                    abort(404)
                return send_from_directory(docs_dir, path)

    @app.get("/healthz")
    def healthz():  # pragma: no cover - 极简
        return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/api/lab-info")
    def api_lab_info():
        return jsonify(lab_info_payload(meta, level_list))

    @app.get("/api/engines")
    def api_engines():
        return jsonify({"engines": group_engines(level_list, titles)})

    @app.get("/api/levels")
    def api_levels():
        engine = request.args.get("engine")
        subset = _resolve_levels(level_list, engine)
        return jsonify({"engine": engine or meta.engine, "levels": [lv.to_json() for lv in subset]})

    @app.post("/api/render")
    def api_render():
        body = _payload()
        engine = str(body.get("engine") or request.args.get("engine") or meta.engine)
        mode = _sanitize_mode(body.get("mode") or request.args.get("mode"))
        raw_level = body.get("level")
        if raw_level is None:
            raw_level = request.args.get("level")
        template = body.get("template")
        if template is None:
            template = request.args.get("template", "")
        if not isinstance(template, str):
            template = str(template)

        subset = _resolve_levels(level_list, engine)
        level = find_level(subset, None if raw_level is None else str(raw_level))
        result = level.render(template)

        found = flagutil.flag_found_in(result.practice_output) or flagutil.flag_found_in(
            result.raw_output
        )
        payload = result.to_json(
            god=(mode == "god"),
            flag_found=found,
            engine=level.engine,
            level=level.level_id,
            mode=mode,
            source_class=level.factory_name or level.title,
            source_file=level.source_file,
        )
        if mode == "god" and level.blind:
            # 盲关在上帝模式下额外给出「若成功本应输出什么」，与参考项目一致
            payload.setdefault("raw_output", result.raw_output)
        return jsonify(payload)

    @app.get("/api/god/source")
    def api_god_source():
        engine = request.args.get("engine") or meta.engine
        level_id = request.args.get("level")
        subset = _resolve_levels(level_list, engine)
        level = find_level(subset, None if level_id is None else str(level_id))
        if not level.source:
            return jsonify({"ok": False, "error": "该关卡未提供源码（打包环境不可用）"}), 500
        return jsonify(
            {
                "ok": True,
                "path": level.factory_name or level.title,
                "source": level.source,
                "waf": level.waf.to_json(),
            }
        )

    @app.post("/api/admin/reset")
    def api_admin_reset():
        token = request.headers.get("X-Reset-Token", "")
        if not Config.RESET_TOKEN:
            return jsonify({"ok": False, "error": "RESET_TOKEN 未配置，拒绝重置"}), 403
        if token != Config.RESET_TOKEN:
            return jsonify({"ok": False, "error": "令牌错误"}), 403
        try:
            flagutil.write_flag_file(Config.FLAG_PATH)
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "message": "已重写 /flag（来自当前环境变量优先级）"})


def mount_console(
    app: Flask,
    static_folder: str | os.PathLike[str] = "public",
    mount_path: str = "/console",
) -> None:
    """把统一前端挂到指定路径。

    场景型靶场（模拟真实业务）用 ``/`` 放自己的页面，把控制台挂到 ``/console``，
    这样每个靶场既有真实业务界面，也能用统一控制台做题。
    前端构建时 ``base: './'``，所以相对路径的静态资源在任意挂载点都能加载；
    而 ``/api/*`` 是同源绝对路径，不受挂载点影响。
    """
    static_dir = Path(static_folder).resolve()
    index_file = static_dir / "index.html"
    mount = "/" + mount_path.strip("/")

    @app.get(mount + "/")
    @app.get(mount)
    def console_index():
        if index_file.is_file():
            return send_from_directory(static_dir, "index.html")
        return FALLBACK_CONSOLE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get(mount + "/<path:path>")
    def console_asset(path: str):
        candidate = (static_dir / path).resolve()
        if str(candidate).startswith(str(static_dir)) and candidate.is_file():
            return send_from_directory(static_dir, path)
        if index_file.is_file():
            return send_from_directory(static_dir, "index.html")
        abort(404)


def create_lab_app(
    meta: LabMeta,
    levels: Iterable[Level],
    *,
    static_folder: str | os.PathLike[str] = "public",
    docs_folder: str | os.PathLike[str] | None = "docs",
    engine_titles: dict[str, str] | None = None,
    extra_routes: Callable[[Flask], None] | None = None,
) -> Flask:
    """创建控制台型靶场应用。"""
    level_list = list(levels)
    app = Flask(__name__, static_folder=None)
    app.config["JSON_AS_ASCII"] = False
    app.config["LAB_META"] = meta

    register_lab_api(app, meta, level_list, engine_titles=engine_titles, docs_folder=docs_folder)

    if extra_routes is not None:
        extra_routes(app)

    static_dir = Path(static_folder).resolve()
    index_file = static_dir / "index.html"

    @app.get("/")
    def index():
        if index_file.is_file():
            return send_from_directory(static_dir, "index.html")
        return FALLBACK_CONSOLE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/<path:path>")
    def static_or_spa(path: str):
        if path.startswith("api/") or path == "healthz":
            return jsonify({"ok": False, "error": "not found"}), 404
        candidate = (static_dir / path).resolve()
        if str(candidate).startswith(str(static_dir)) and candidate.is_file():
            return send_from_directory(static_dir, path)
        # SPA：未知路径交回前端路由
        if index_file.is_file():
            return send_from_directory(static_dir, "index.html")
        abort(404)

    return app


def run(app: Flask) -> None:  # pragma: no cover - 入口辅助
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)


# ---------------------------------------------------------------------------
# 降级控制台：前端构建产物缺失时仍能完整做题。
# 刻意保持单文件、零依赖、零外链（容器内不出网也能用）。
# ---------------------------------------------------------------------------
FALLBACK_CONSOLE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SSTI Lab</title>
<style>
 :root{--accent:#00e5ff;--accent2:#ff2bd6;--bg:#05070d;--panel:#0b1020;--line:#1d2740;--fg:#dbe7ff}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 system-ui,"Segoe UI",sans-serif}
 header{padding:18px 22px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,rgba(0,229,255,.12),transparent)}
 h1{margin:0;font-size:20px;letter-spacing:.5px}
 h1 span{color:var(--accent)}
 .sub{opacity:.7;font-size:12px;margin-top:4px}
 .wrap{display:grid;grid-template-columns:280px 1fr;gap:16px;padding:16px 22px}
 @media(max-width:820px){.wrap{grid-template-columns:1fr}}
 .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
 .lvl{padding:8px 10px;border-radius:8px;cursor:pointer;border:1px solid transparent}
 .lvl:hover{background:rgba(255,255,255,.04)}
 .lvl.on{border-color:var(--accent);background:rgba(0,229,255,.08)}
 .lvl b{display:block;font-size:13px}
 .lvl small{opacity:.65}
 .badge{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;margin-left:6px}
 .blind{background:rgba(255,43,214,.18);color:var(--accent2)}
 .noeg{background:rgba(255,77,109,.2);color:#ff8fa3}
 textarea{width:100%;min-height:150px;background:#05080f;color:var(--fg);border:1px solid var(--line);
   border-radius:8px;padding:10px;font:13px/1.5 ui-monospace,Consolas,monospace;resize:vertical}
 button{background:var(--accent);color:#03121a;border:0;border-radius:8px;padding:9px 18px;font-weight:700;cursor:pointer}
 button:disabled{opacity:.45;cursor:not-allowed}
 pre{background:#05080f;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;
   max-height:420px;white-space:pre-wrap;word-break:break-all;font:13px/1.5 ui-monospace,Consolas,monospace}
 .flag{border-color:#39ff88;color:#39ff88}
 .err{color:#ff8fa3}
 .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0}
 .hint{opacity:.75;font-size:12px;border-left:2px solid var(--accent);padding-left:10px;margin-top:10px}
 code{background:rgba(255,255,255,.07);padding:1px 5px;border-radius:4px}
</style></head><body>
<header>
  <h1 id="title">SSTI <span>Lab</span></h1>
  <div class="sub" id="subtitle">正在加载 /api/lab-info …</div>
</header>
<div class="wrap">
  <div class="panel"><div id="levels"></div>
    <div class="hint" id="hint"></div>
  </div>
  <div>
    <div class="panel">
      <div id="desc" style="opacity:.85;margin-bottom:8px"></div>
      <div id="wafbox"></div>
      <textarea id="tpl" placeholder="{{7*7}}"></textarea>
      <div class="row">
        <button id="go">渲染</button>
        <label><input type="checkbox" id="god"> 上帝模式</label>
        <button id="src" style="background:transparent;color:var(--accent);border:1px solid var(--accent)">关卡源码</button>
      </div>
    </div>
    <div class="panel" style="margin-top:14px">
      <div id="msg" style="margin-bottom:8px"></div>
      <pre id="out">（尚未渲染）</pre>
      <pre id="godout" style="display:none"></pre>
    </div>
  </div>
</div>
<script>
(function(){
  var S={info:null,level:null,engine:null};
  var $=function(id){return document.getElementById(id)};
  function esc(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c]})}
  function theme(t){
    if(!t)return;
    var r=document.documentElement.style;
    if(t.accent)r.setProperty("--accent",t.accent);
    if(t.accent2)r.setProperty("--accent2",t.accent2);
  }
  function renderLevels(){
    var box=$("levels");box.innerHTML="";
    (S.info.levels||[]).forEach(function(lv){
      var d=document.createElement("div");
      d.className="lvl"+(S.level&&lv.id===S.level.id?" on":"");
      d.innerHTML="<b>"+esc(lv.title)+
        (lv.blind?'<span class="badge blind">盲</span>':"")+
        (lv.no_egress?'<span class="badge noeg">不出网</span>':"")+
        "</b><small>"+esc(lv.summary||"")+"</small>";
      d.onclick=function(){pick(lv.id)};
      box.appendChild(d);
    });
  }
  function pick(id){
    S.level=(S.info.levels||[]).filter(function(l){return l.id===id})[0]||S.info.levels[0];
    renderLevels();
    $("desc").textContent=S.level.description||"";
    $("hint").textContent=S.level.hint?("思路：" + S.level.hint):"";
    var w=S.level.waf;
    $("wafbox").innerHTML=w?('<div class="hint">过滤规则（'+esc(w.kind)+'）：<code>'+
      esc((w.items||[]).join(" "))+'</code><br>'+esc(w.note||"")+'</div>'):"";
  }
  function post(){
    var body={engine:S.engine,level:S.level.id,
      mode:$("god").checked?"god":"practice",template:$("tpl").value};
    $("go").disabled=true;$("msg").textContent="渲染中…";
    fetch("/api/render",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(body)}).then(function(r){return r.json()}).then(function(j){
      $("msg").innerHTML=(j.flag_found?'<b class="flag">🎉 拿到 flag 了！</b> ':"")+
        (j.ok?'<span style="color:#39ff88">ok</span>':'<span class="err">failed</span>')+
        (j.error?' <span class="err">'+esc(j.exception_type)+"</span>":"");
      $("out").textContent=j.output===""?"（空输出）":j.output;
      var g=$("godout");
      if($("god").checked){
        g.style.display="block";
        g.textContent=["template_after_waf: "+(j.template_after_waf||""),
          "raw_output: "+(j.raw_output||""),
          "error: "+(j.error||"-"),
          "exception_type: "+(j.exception_type||"-"),
          "source_class: "+(j.source_class||"-")].join("\\n");
      }else{g.style.display="none"}
    }).catch(function(e){$("msg").innerHTML='<span class="err">请求失败: '+esc(e)+"</span>"})
    .then(function(){$("go").disabled=false});
  }
  $("go").onclick=post;
  $("tpl").addEventListener("keydown",function(e){
    if((e.ctrlKey||e.metaKey)&&e.key==="Enter"){e.preventDefault();post()}});
  $("src").onclick=function(){
    fetch("/api/god/source?engine="+encodeURIComponent(S.engine)+"&level="+encodeURIComponent(S.level.id))
      .then(function(r){return r.json()}).then(function(j){
        var g=$("godout");g.style.display="block";
        g.textContent=j.ok?j.source:("源码不可用: "+(j.error||""));
      });
  };
  $("god").onchange=function(){if(!$("god").checked)$("godout").style.display="none"};
  fetch("/api/lab-info").then(function(r){return r.json()}).then(function(j){
    S.info=j;S.engine=j.engine;theme(j.theme);
    $("title").innerHTML=esc(j.title)+' <span>'+esc(j.id)+"</span>";
    $("subtitle").textContent=(j.subtitle||"")+(j.no_egress?"　⛔ 不出网：": "")+
      (j.no_egress?(j.no_egress_note||""):"");
    if(!j.levels||!j.levels.length){$("levels").textContent="该靶场未定义关卡";return}
    pick(j.levels[0].id);
  }).catch(function(e){
    $("subtitle").innerHTML='<span class="err">无法加载 /api/lab-info：'+esc(e)+"</span>";
  });
})();
</script></body></html>
"""
