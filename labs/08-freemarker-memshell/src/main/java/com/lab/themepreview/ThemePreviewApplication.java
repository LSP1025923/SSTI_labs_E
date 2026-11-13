package com.lab.themepreview;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 「主题预览」—— 一个很典型的小型多租户 SaaS 后台：
 * 运营同学在后台写 FreeMarker / Thymeleaf 模板片段，前端实时预览效果。
 *
 * 为了让运营能调用任何工具类 / 在模板里直接 new 对象，模板被配置成
 * 「不受限类解析」（见 FreemarkerConfig），这就是本靶场的漏洞起点。
 */
@SpringBootApplication
public class ThemePreviewApplication {
    public static void main(String[] args) {
        SpringApplication.run(ThemePreviewApplication.class, args);
    }
}
