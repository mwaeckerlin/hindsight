// Unit tests of control-plane/prepare-base-path.cjs: the build argument and the
// patch of the upstream layout, on the layout of the upstream release.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const {checkBasePath, patchLayout, patchMiddleware} = require('./prepare-base-path.cjs')

const LAYOUT = fs.readFileSync(path.join(__dirname, 'fixtures', 'layout.tsx'), 'utf8')
const MIDDLEWARE = fs.readFileSync(path.join(__dirname, 'fixtures', 'middleware.ts'), 'utf8')
const MATCHER = String.raw`"/((?!_next|_vercel|.*\\.(?:png|jpe?g|gif|svg|webp|ico|css|js|map|woff2?|ttf|eot|txt|xml|json)$).*)"`

test('the middleware also runs for the bare base path, which leads to the login', () => {
  const patched = patchMiddleware(MIDDLEWARE)
  assert.ok(patched.includes(`matcher: [\n    "/",\n    ${MATCHER},\n  ],\n`), patched.slice(-600))
})

test('a middleware upstream changed stops the build and names the line', () => {
  assert.throws(() => patchMiddleware(MIDDLEWARE.replace('matcher:\n', 'matcher: \n')), /middleware\.ts carries .* 0 times instead of once/)
  assert.throws(() => patchMiddleware(patchMiddleware(MIDDLEWARE)), /0 times instead of once/)
})

test('the metadata URLs of the upstream layout go through withBasePath', () => {
  const patched = patchLayout(LAYOUT)
  assert.match(patched, /^import "\.\/globals\.css";\nimport \{ withBasePath \} from "@\/lib\/base-path";\n/m)
  assert.match(patched, /icon: withBasePath\("\/favicon\.png"\),/)
  assert.match(patched, /apple: withBasePath\("\/apple-touch-icon\.png"\),/)
  assert.match(patched, /manifest: withBasePath\("\/manifest\.json"\),/)
  assert.doesNotMatch(patched, /: "\/[^"]*\.(png|json)"/)
})

test('a layout upstream changed stops the build and names the line', () => {
  assert.throws(() => patchLayout(LAYOUT.replace('icon: "/favicon.png",', 'icon: withBasePath("/favicon.png"),')),
    /carries "icon: \\"\/favicon\.png\\"," 0 times instead of once/)
  assert.throws(() => patchLayout(patchLayout(LAYOUT)), /0 times instead of once|2 times instead of once/)
})

test('the build argument is a base path in the form the start takes', () => {
  assert.equal(checkBasePath('/hindsight'), '/hindsight')
  assert.equal(checkBasePath('/tools/hindsight'), '/tools/hindsight')
  for (const value of [undefined, '', '/', 'hindsight', '/hindsight/', '/a b', '//evil.example']) {
    assert.throws(() => checkBasePath(value), /HINDSIGHT_BASE_PATH|no path such as/, String(value))
  }
})
