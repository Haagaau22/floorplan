import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import vue from '@vitejs/plugin-vue'
import { defineConfig, type Plugin, type PreviewServer, type ViteDevServer } from 'vite'

const localDataPath = resolve(process.cwd(), 'data/projects/apartment/floorplan-v2.json')

function localFloorplanApi(): Plugin {
  const install = (server: ViteDevServer | PreviewServer) => {
    server.middlewares.use(async (request, response, next) => {
      const pathname = request.url?.split('?')[0]
      if (request.method !== 'GET' || pathname !== '/api/projects/apartment') {
        next()
        return
      }
      try {
        const payload = await readFile(localDataPath)
        response.statusCode = 200
        response.setHeader('Content-Type', 'application/json; charset=utf-8')
        response.setHeader('Cache-Control', 'no-store')
        response.end(payload)
      } catch (error) {
        response.statusCode = 503
        response.setHeader('Content-Type', 'application/json; charset=utf-8')
        response.end(JSON.stringify({ error: 'local_floorplan_data_unavailable', detail: String(error) }))
      }
    })
  }

  return {
    name: 'local-floorplan-api',
    configureServer: install,
    configurePreviewServer: install,
  }
}

export default defineConfig({
  plugins: [vue(), localFloorplanApi()],
  server: {
    host: '127.0.0.1',
    port: 18606,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 18606,
    strictPort: true,
  },
})
