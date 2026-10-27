// Unit tests of control-plane/start.cjs: the keys of the control plane from
// files, and the build chosen for the base path.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {secretsFromFiles, basePath, builtBasePath, selectServer} = require('./start.cjs')

const secret = content => {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cp-')), 'secret')
  fs.writeFileSync(file, content)
  return file
}

test('a file becomes the variable and the file variable goes', () => {
  const environment = secretsFromFiles({HINDSIGHT_CP_DATAPLANE_API_KEY_FILE: secret('tenant-key\n')})
  assert.deepEqual(environment, {HINDSIGHT_CP_DATAPLANE_API_KEY: 'tenant-key'})
})

test('every control plane file variable is read', () => {
  const environment = secretsFromFiles({
    HINDSIGHT_CP_DATAPLANE_API_KEY_FILE: secret('tenant-key'),
    HINDSIGHT_CP_ACCESS_KEY_FILE: secret('access-key'),
  })
  assert.equal(environment.HINDSIGHT_CP_DATAPLANE_API_KEY, 'tenant-key')
  assert.equal(environment.HINDSIGHT_CP_ACCESS_KEY, 'access-key')
})

test('foreign file variables stay untouched', () => {
  const environment = secretsFromFiles({OTHER_KEY_FILE: '/run/secrets/other'})
  assert.deepEqual(environment, {OTHER_KEY_FILE: '/run/secrets/other'})
})

test('both sources for one key stop the start', () => {
  assert.throws(() => secretsFromFiles({HINDSIGHT_CP_ACCESS_KEY: 'a', HINDSIGHT_CP_ACCESS_KEY_FILE: secret('b')}),
    /HINDSIGHT_CP_ACCESS_KEY and HINDSIGHT_CP_ACCESS_KEY_FILE are both set/)
})

test('a missing file stops the start and names it', () => {
  assert.throws(() => secretsFromFiles({HINDSIGHT_CP_ACCESS_KEY_FILE: '/nonexistent/secret'}),
    /HINDSIGHT_CP_ACCESS_KEY_FILE names \/nonexistent\/secret, which cannot be read: ENOENT/)
})

test('an empty file stops the start', () => {
  assert.throws(() => secretsFromFiles({HINDSIGHT_CP_ACCESS_KEY_FILE: secret('  \n')}), /which is empty/)
})

test('an empty file variable is ignored', () => {
  assert.deepEqual(secretsFromFiles({HINDSIGHT_CP_ACCESS_KEY_FILE: ''}), {})
})

// two standalone builds as the image carries them: the root build, and the
// build for a base path with the routes manifest Next.js writes
const builds = built => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-builds-'))
  const root = path.join(directory, 'control-plane')
  const base = path.join(directory, 'control-plane-base-path')
  fs.mkdirSync(path.join(base, '.next'), {recursive: true})
  fs.mkdirSync(root)
  fs.writeFileSync(path.join(base, '.next', 'routes-manifest.json'), JSON.stringify({version: 3, basePath: built}))
  return {root, basePath: base}
}

test('the base path is normalised as Next.js takes it', () => {
  assert.equal(basePath(undefined), '')
  assert.equal(basePath(''), '')
  assert.equal(basePath('/'), '')
  assert.equal(basePath('  '), '')
  assert.equal(basePath('/hindsight'), '/hindsight')
  assert.equal(basePath('/hindsight/'), '/hindsight')
  assert.equal(basePath('hindsight'), '/hindsight')
  assert.equal(basePath('/tools/hindsight'), '/tools/hindsight')
})

test('a base path that is no path stops the start and names it', () => {
  for (const value of ['//evil.example', '/a b', '/../etc', '/./x', 'https://evil.example/x', '/x<script>', '/a//b']) {
    assert.throws(() => basePath(value), /HINDSIGHT_BASE_PATH is .* which is no path such as \/hindsight/, value)
  }
})

test('without a base path the root build runs', () => {
  const directories = builds('/hindsight')
  for (const value of [undefined, '', '/']) {
    const environment = value === undefined ? {} : {HINDSIGHT_BASE_PATH: value}
    assert.deepEqual(selectServer(environment, directories), {server: path.join(directories.root, 'server.js'), basePath: ''})
    assert.equal(environment.NEXT_PUBLIC_BASE_PATH, undefined)
  }
})

test('the base path the image is built for runs the build for it', () => {
  const directories = builds('/hindsight')
  for (const value of ['/hindsight', '/hindsight/', 'hindsight']) {
    const environment = {HINDSIGHT_BASE_PATH: value}
    assert.deepEqual(selectServer(environment, directories),
      {server: path.join(directories.basePath, 'server.js'), basePath: '/hindsight'})
    assert.equal(environment.NEXT_PUBLIC_BASE_PATH, '/hindsight')
  }
})

test('a base path the image is not built for stops the start and names the build argument', () => {
  assert.throws(() => selectServer({HINDSIGHT_BASE_PATH: '/elsewhere'}, builds('/hindsight')),
    /HINDSIGHT_BASE_PATH is \/elsewhere, and this image is built for \/hindsight; set HINDSIGHT_BASE_PATH=\/hindsight, or build the image with --build-arg HINDSIGHT_BASE_PATH=\/elsewhere/)
})

test('a build without its routes manifest stops the start and names the file', () => {
  const directories = builds('/hindsight')
  fs.rmSync(path.join(directories.basePath, '.next', 'routes-manifest.json'))
  assert.throws(() => builtBasePath(directories.basePath), /has no readable .*routes-manifest\.json: ENOENT/)
  assert.throws(() => selectServer({HINDSIGHT_BASE_PATH: '/hindsight'}, directories), /routes-manifest\.json/)
})
