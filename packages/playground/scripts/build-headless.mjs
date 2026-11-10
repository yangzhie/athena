import { build } from 'esbuild'
await build({ entryPoints: ['src/server/cli.ts'], bundle: true, platform: 'node', format: 'esm', target: 'node22', outfile: 'dist/headless.mjs', jsx: 'automatic' })
