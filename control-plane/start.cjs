#!/usr/bin/env node
/*
 * Start the Hindsight control plane with its secrets read from files.
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
 *     start.cjs            start the control plane
 *     start.cjs --health   exit 0 when it answers, for HEALTHCHECK
 */
const fs = require('node:fs')
const path = require('node:path')

const PREFIX = 'HINDSIGHT_CP_'
const SUFFIX = '_FILE'
const SERVER = '/app/control-plane/server.js'

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

const health = async () => {
  const port = process.env.PORT || '9999'
  try {
    const response = await fetch(`http://127.0.0.1:${port}/`, {redirect: 'manual', signal: AbortSignal.timeout(5000)})
    return response.status < 500 ? 0 : 1
  } catch {
    return 1
  }
}

const main = async () => {
  if (process.argv[2] === '--health') process.exit(await health())
  try {
    secretsFromFiles(process.env)
  } catch (error) {
    console.error(error.message)
    process.exit(1)
  }
  process.chdir(path.dirname(SERVER))
  require(SERVER)
}

module.exports = {secretsFromFiles}

if (require.main === module) main()
