#!/usr/bin/env node
/*
 * Prepare the upstream control plane source for a build below a base path.
 *
 * Checks that the base path is one the start accepts in exactly this form,
 * then patches src/app/layout.tsx: Next.js puts the base path in front of its
 * pages and assets, but leaves the icon and manifest URLs of the metadata as
 * written (next/dist/lib/metadata/resolvers/resolve-icons and
 * metadata-elements), and upstream writes them root-absolute. The patch wraps
 * them in upstream's own withBasePath (src/lib/base-path.ts).
 *
 * It also patches src/middleware.ts: Next.js puts the base path in front of the
 * matcher of the middleware, and upstream's matcher "/((?!_next…).*)" then
 * matches every path below /hindsight/ but not /hindsight itself, so the bare
 * base path got a 404 instead of the redirect to the login (measured on
 * 2026-10-27 with release 1.1.0: /hindsight 404 without a middleware rewrite,
 * /hindsight/login 200 with one). The matcher "/" adds the base path itself.
 *
 * When upstream changes these lines, the patch stops the build and names the
 * line, so it is looked at again.
 *
 *     prepare-base-path.cjs <control plane source directory> <base path>
 */
const fs = require('node:fs')
const path = require('node:path')

const {basePath} = require('./start.cjs')

const LAYOUT = path.join('src', 'app', 'layout.tsx')
const REPLACEMENTS = [
  ['import "./globals.css";\n', 'import "./globals.css";\nimport { withBasePath } from "@/lib/base-path";\n'],
  ['icon: "/favicon.png",', 'icon: withBasePath("/favicon.png"),'],
  ['apple: "/apple-touch-icon.png",', 'apple: withBasePath("/apple-touch-icon.png"),'],
  ['manifest: "/manifest.json",', 'manifest: withBasePath("/manifest.json"),'],
]
const MIDDLEWARE = path.join('src', 'middleware.ts')
const MATCHER = String.raw`"/((?!_next|_vercel|.*\\.(?:png|jpe?g|gif|svg|webp|ico|css|js|map|woff2?|ttf|eot|txt|xml|json)$).*)"`
const MIDDLEWARE_REPLACEMENTS = [
  [`matcher:\n    ${MATCHER},\n`, `matcher: [\n    "/",\n    ${MATCHER},\n  ],\n`],
]

const checkBasePath = value => {
  if (!value || basePath(value) !== value) {
    throw new Error(`prepare-base-path: the build argument HINDSIGHT_BASE_PATH is ${JSON.stringify(value)}; ` +
      `it must be a path such as /hindsight, with a leading slash and no trailing slash`)
  }
  return value
}

const patchText = (file, replacements, text) => {
  for (const [original, patched] of replacements) {
    const count = text.split(original).length - 1
    if (count !== 1) {
      throw new Error(`prepare-base-path: ${file} carries ${JSON.stringify(original.trim())} ${count} times instead of once; ` +
        'upstream changed this code, check whether the patch is still needed')
    }
    text = text.replace(original, patched)
  }
  return text
}

const patchLayout = text => patchText(LAYOUT, REPLACEMENTS, text)
const patchMiddleware = text => patchText(MIDDLEWARE, MIDDLEWARE_REPLACEMENTS, text)

const main = () => {
  const [source, value] = process.argv.slice(2)
  try {
    checkBasePath(value)
    const layout = path.join(source, LAYOUT)
    fs.writeFileSync(layout, patchLayout(fs.readFileSync(layout, 'utf8')))
    const middleware = path.join(source, MIDDLEWARE)
    fs.writeFileSync(middleware, patchMiddleware(fs.readFileSync(middleware, 'utf8')))
  } catch (error) {
    console.error(error.message)
    process.exit(1)
  }
}

module.exports = {checkBasePath, patchLayout, patchMiddleware}

if (require.main === module) main()
