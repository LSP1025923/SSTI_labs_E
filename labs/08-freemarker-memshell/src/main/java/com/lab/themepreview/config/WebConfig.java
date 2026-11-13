package com.lab.themepreview.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * 首页由 static/index.html 提供。
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addViewControllers(ViewControllerRegistry registry) {
        registry.addViewController("/").setViewName("forward:/index.html");
    }

    /**
     * 把内嵌的 memshell Filter 字节码（base64）读出来，供出题人/玩家核对。
     * 注意：这个端点只吐字节码，不注册任何东西，也不能读了就拿到 flag。
     */
    public static String memshellClassBase64() throws Exception {
        InputStream in = WebConfig.class.getResourceAsStream("/memshell/MemshellFilter.class.b64");
        if (in == null) {
            throw new IllegalStateException("classpath:/memshell/MemshellFilter.class.b64 missing");
        }
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) {
            bos.write(buf, 0, n);
        }
        in.close();
        return new String(bos.toByteArray(), StandardCharsets.UTF_8).replaceAll("\\s", "");
    }
}
