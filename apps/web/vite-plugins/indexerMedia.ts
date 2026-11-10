import { createReadStream, statSync } from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

const TYPES: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.m4v': 'video/mp4',
  '.mov': 'video/quicktime',
  '.webm': 'video/webm',
  '.mkv': 'video/x-matroska',
  '.mp3': 'audio/mpeg',
  '.m4a': 'audio/mp4',
  '.wav': 'audio/wav',
}

/**
 * Dev server only: streams lecture recordings from workers/indexer/data so the
 * side panel can play locally indexed clips.
 *
 *   GET /indexer-media?clips=<folder>&media=<path relative to that folder>
 *
 * Supports Range requests so the player can seek. Refuses anything outside the
 * data folder. Never part of a build: recordings are lecturer IP.
 */
export function indexerMedia(dataDir: string): Plugin {
  const root = path.resolve(dataDir)
  return {
    name: 'athena-indexer-media',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/indexer-media', (req, res) => {
        const url = new URL(req.url ?? '/', 'http://localhost')
        const folder = url.searchParams.get('clips') ?? ''
        const media = url.searchParams.get('media') ?? ''
        const file = path.resolve(root, folder, media)
        const type = TYPES[path.extname(file).toLowerCase()]

        if (!file.startsWith(root + path.sep) || !type) {
          res.statusCode = 403
          return res.end()
        }
        let size: number
        try {
          size = statSync(file).size
        } catch {
          res.statusCode = 404
          return res.end()
        }

        res.setHeader('Content-Type', type)
        res.setHeader('Accept-Ranges', 'bytes')
        res.setHeader('Cache-Control', 'no-store')

        const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? '')
        if (!range) {
          res.setHeader('Content-Length', size)
          return createReadStream(file).pipe(res)
        }
        let start = range[1] ? Number(range[1]) : size - Number(range[2])
        let end = range[1] && range[2] ? Number(range[2]) : size - 1
        start = Math.max(0, start)
        end = Math.min(end, size - 1)
        if (start > end) {
          res.statusCode = 416
          res.setHeader('Content-Range', `bytes */${size}`)
          return res.end()
        }
        res.statusCode = 206
        res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`)
        res.setHeader('Content-Length', end - start + 1)
        createReadStream(file, { start, end }).pipe(res)
      })
    },
  }
}
