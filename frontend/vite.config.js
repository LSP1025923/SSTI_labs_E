import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * 该构建产物会被拷贝进每一个「控制台型」靶场容器，并从容器根路径 `/` 提供。
 * - base: './'    产物使用相对路径引用资源，放在子路径下也能工作。
 * - outDir: build 产物落在 frontend/build，Dockerfile 再拷贝到镜像的 /app/build。
 *
 * 开发期如果想要本地代理到某个靶场，设置环境变量即可（不在代码里硬编码任何端口）：
 *   $env:VITE_DEV_API_TARGET = 'http://127.0.0.1:<port>'; npm run dev
 */
const devApiTarget = process.env.VITE_DEV_API_TARGET;

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'build',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: false,
    target: 'es2019',
    cssTarget: 'chrome80',
    chunkSizeWarningLimit: 900,
  },
  server: devApiTarget
    ? {
        host: true,
        proxy: {
          '/api': { target: devApiTarget, changeOrigin: true },
        },
      }
    : undefined,
});
