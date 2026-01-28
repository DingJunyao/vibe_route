import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig((configEnv) => {
  const env = loadEnv(configEnv.mode, process.cwd(), '')

  return {
    plugins: [
      vue(),
      AutoImport({
        resolvers: [ElementPlusResolver()],
        imports: ['vue', 'vue-router', 'pinia'],
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
      // 内网穿透配置
      ...(env.VITE_ORIGIN && { origin: env.VITE_ORIGIN }),
      ...(env.VITE_ALLOWED_HOSTS && {
        allowedHosts: env.VITE_ALLOWED_HOSTS.split(',').map((h: string) => h.trim())
      }),
      // 内网穿透环境下禁用 HMR（设为 false）
      ...(env.VITE_DISABLE_HMR === 'true' ? { hmr: false } : {
        hmr: {
          ...(env.VITE_HMR_HOST && { host: env.VITE_HMR_HOST }),
          ...(env.VITE_HMR_PORT && { clientPort: parseInt(env.VITE_HMR_PORT) }),
          ...(env.VITE_HMR_PROTOCOL && { protocol: env.VITE_HMR_PROTOCOL }),
          path: '/__vite_hmr',
        },
      }),
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
