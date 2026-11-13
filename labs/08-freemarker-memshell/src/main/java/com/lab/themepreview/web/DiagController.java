package com.lab.themepreview.web;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.ServletContext;
import java.io.Serializable;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 出题/排障用的只读诊断端点：把 ServletContext 到 Tomcat StandardContext 的
 * 反射路径「摊开」，方便确认容器版本差异（Tomcat 9 里是
 * ApplicationContextFacade.context -> ApplicationContext.context -> StandardContext）。
 *
 * 它不注册任何东西，也不读 /flag —— 拿不到 flag。
 */
@RestController
public class DiagController {

    @GetMapping(value = "/api/diag/context", produces = MediaType.APPLICATION_JSON_VALUE + ";charset=UTF-8")
    public Map<String, Object> diag(javax.servlet.http.HttpServletRequest request) {
        javax.servlet.ServletContext ctx = request.getServletContext();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("servletContextClass", ctx.getClass().getName());
        List<Map<String, Object>> chain = new ArrayList<>();

        Object o = ctx;
        for (int depth = 0; depth < 4 && o != null; depth++) {
            Map<String, Object> step = new LinkedHashMap<>();
            step.put("depth", depth);
            step.put("class", o.getClass().getName());
            step.put("interfaces", names(o.getClass().getInterfaces()));
            step.put("serializable", o instanceof Serializable);
            step.put("tostring", String.valueOf(o));

            Field f = findField(o.getClass(), "context");
            if (f == null) {
                step.put("field_context", "NOT FOUND");
                step.put("declared_fields", fieldNames(o.getClass()));
                chain.add(step);
                break;
            }
            step.put("field_context_declared_in", f.getDeclaringClass().getName());
            step.put("field_context_type", f.getType().getName());
            step.put("field_context_modifiers", java.lang.reflect.Modifier.toString(f.getModifiers()));
            try {
                f.setAccessible(true);
                Object next = f.get(o);
                step.put("read_ok", true);
                step.put("value_class", next == null ? "null" : next.getClass().getName());
                chain.add(step);
                if (next == null) {
                    break;
                }
                o = next;
                if (o.getClass().getName().equals("org.apache.catalina.core.StandardContext")) {
                    Map<String, Object> done = new LinkedHashMap<>();
                    done.put("depth", depth + 1);
                    done.put("class", o.getClass().getName());
                    done.put("reached_StandardContext", true);
                    done.put("addFilterDef", hasMethod(o.getClass(), "addFilterDef"));
                    done.put("addFilterMap", hasMethod(o.getClass(), "addFilterMap"));
                    done.put("filterStart", hasMethod(o.getClass(), "filterStart"));
                    chain.add(done);
                    break;
                }
            } catch (Throwable t) {
                step.put("read_ok", false);
                step.put("read_error", t.getClass().getName() + ": " + t.getMessage());
                chain.add(step);
                break;
            }
        }
        out.put("chain", chain);
        return out;
    }

    private static List<String> names(Class<?>[] cs) {
        List<String> l = new ArrayList<>();
        for (Class<?> c : cs) {
            l.add(c.getName());
        }
        return l;
    }

    private static List<String> fieldNames(Class<?> c) {
        List<String> l = new ArrayList<>();
        while (c != null && l.size() < 40) {
            for (Field f : c.getDeclaredFields()) {
                l.add(f.getDeclaringClass().getSimpleName() + "." + f.getName() + ":" + f.getType().getSimpleName());
            }
            c = c.getSuperclass();
        }
        return l;
    }

    private static Field findField(Class<?> c, String name) {
        while (c != null) {
            try {
                return c.getDeclaredField(name);
            } catch (NoSuchFieldException e) {
                c = c.getSuperclass();
            }
        }
        return null;
    }

    private static boolean hasMethod(Class<?> c, String name) {
        for (Method m : c.getMethods()) {
            if (m.getName().equals(name)) {
                return true;
            }
        }
        return false;
    }
}
