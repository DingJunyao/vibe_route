import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')

  return {
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: [
        'vue',
        'vue-router',
        'pinia',
      ],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 内网穿透配置：设置服务器的原始访问地址
    ...(env.VITE_ORIGIN && { origin: env.VITE_ORIGIN }),
    // 允许的主机列表
    ...(env.VITE_ALLOWED_HOSTS && {
      allowedHosts: env.VITE_ALLOWED_HOSTS.split(',').map((h: string) => h.trim())
    }),
    // HMR 配置，确保从局域网/域名访问时 WebSocket 连接正常
    hmr: {
      ...(env.VITE_HMR_HOST && { host: env.VITE_HMR_HOST }),
      ...(env.VITE_HMR_PORT && { clientPort: parseInt(env.VITE_HMR_PORT) }),
      ...(env.VITE_HMR_PROTOCOL && { protocol: env.VITE_HMR_PROTOCOL }),
      path: '/__vite_hmr',
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
