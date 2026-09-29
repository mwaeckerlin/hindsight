// Unit tests of control-plane/start.cjs: the keys of the control plane from files.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {secretsFromFiles} = require('./start.cjs')

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
