#!/usr/bin/env node
/*
 * Start the Hindsight control plane with its secrets read from files, at the
 * root or below a base path.
 *
 * The control plane reads its settings from HINDSIGHT_CP_* environment
 * variables, keys included, once when its server module loads. The image
 * takes the keys as Docker secrets instead: for every variable NAME_FILE that
 * is set, the content of that file becomes NAME and NAME_FILE is removed,
 * as bin/start.py does for the API. Then the upstream standalone server runs
 * in this process.
 *
 *     HINDSIGHT_CP_DATAPLANE_API_KEY_FILE=/run/secrets/hindsight_tenant_key
 *     HINDSIGHT_CP_ACCESS_KEY_FILE=/run/secrets/hindsight_cp_access_key
 *
 * A NAME that is set as well as NAME_FILE stops the start: two sources for
 * one key leave it open which one is in use.
 *
 * Next.js builds its base path into the pages and bundles, so the image
 * carries two builds of the same release: the one at the root, and one built
 * for the base path of the build argument HINDSIGHT_BASE_PATH. Without the
 * variable HINDSIGHT_BASE_PATH the root build runs; with it, the build for
 * the base path runs, and a base path the image is not built for stops the
 * start.
 *
 *     start.cjs            start the control plane
 *     start.cjs --health   exit 0 when it answers, for HEALTHCHECK
 */
const fs = require('node:fs')
const path = require('node:path')

const PREFIX = 'HINDSIGHT_CP_'
const SUFFIX = '_FILE'
const ROOT_BUILD = '/app/control-plane'
const BASE_PATH_BUILD = '/app/control-plane-base-path'
const SEGMENT = /^[A-Za-z0-9._~-]+$/

const secretsFromFiles = environment => {
  const names = Object.keys(environment).filter(name => name.startsWith(PREFIX) && name.endsWith(SUFFIX)).sort()
  for (const name of names) {
    const target = name.slice(0, -SUFFIX.length)
    const file = environment[name]
    delete environment[name]
    if (!file) continue
    if (environment[target]) throw new Error(`control-plane: ${target} and ${name} are both set; set one of them`)
    let value
    try {
      value = fs.readFileSync(file, 'utf8').trim()
    } catch (error) {
      throw new Error(`control-plane: ${name} names ${file}, which cannot be read: ${error.code}`)
    }
    if (!value) throw new Error(`control-plane: ${name} names ${file}, which is empty`)
    environment[target] = value
  }
  return environment
}

// The base path as Next.js takes it: one leading slash, no trailing slash, and
// empty for the root, normalised as upstream's normalizeBasePath does.
const basePath = value => {
  const trimmed = (value || '').trim().replace(/\/+$/, '')
  if (!trimmed) return ''
  const normalised = trimmed.startsWith('/') ? trimmed : `/${trimmed}`
  const segments = normalised.slice(1).split('/')
  if (segments.some(segment => !SEGMENT.test(segment) || segment === '.' || segment === '..')) {
    throw new Error(`control-plane: HINDSIGHT_BASE_PATH is ${JSON.stringify(value)}, which is no path such as /hindsight; ` +
      'its segments may carry letters, digits and the characters . _ ~ -')
  }
  return normalised
}

// The base path a standalone build serves, from the routes manifest Next.js
// writes with the build.
const builtBasePath = build => {
  const manifest = path.join(build, '.next', 'routes-manifest.json')
  try {
    return JSON.parse(fs.readFileSync(manifest, 'utf8')).basePath || ''
  } catch (error) {
    throw new Error(`control-plane: the build for a base path has no readable ${manifest}: ${error.code || error.message}`)
  }
}

// The server to run for HINDSIGHT_BASE_PATH, and the base path it serves.
const selectServer = (environment, builds = {root: ROOT_BUILD, basePath: BASE_PATH_BUILD}) => {
  const wanted = basePath(environment.HINDSIGHT_BASE_PATH)
  if (!wanted) return {server: path.join(builds.root, 'server.js'), basePath: ''}
  const built = builtBasePath(builds.basePath)
  if (wanted !== built) {
    throw new Error(`control-plane: HINDSIGHT_BASE_PATH is ${wanted}, and this image is built for ${built || 'the root'}; ` +
      `set HINDSIGHT_BASE_PATH=${built}, or build the image with --build-arg HINDSIGHT_BASE_PATH=${wanted}`)
  }
  environment.NEXT_PUBLIC_BASE_PATH = wanted
  return {server: path.join(builds.basePath, 'server.js'), basePath: wanted}
}

const health = async () => {
  const port = process.env.PORT || '9999'
  try {
    const base = basePath(process.env.HINDSIGHT_BASE_PATH)
    const response = await fetch(`http://127.0.0.1:${port}${base || '/'}`, {redirect: 'manual', signal: AbortSignal.timeout(5000)})
    return response.status < 500 ? 0 : 1
  } catch {
    return 1
  }
}

const main = async () => {
  if (process.argv[2] === '--health') process.exit(await health())
  let server
  try {
    secretsFromFiles(process.env)
    server = selectServer(process.env).server
  } catch (error) {
    console.error(error.message)
    process.exit(1)
  }
  process.chdir(path.dirname(server))
  require(server)
}

module.exports = {secretsFromFiles, basePath, builtBasePath, selectServer}

if (require.main === module) main()
