/**
 * Standalone CommonJS Playwright smoke test for Cashflow Radar frontend.
 * Run via the document toolchain wrapper without installing browser dependencies:
 *
 *   node "C:\Users\Admin\.config\opencode\toolchains\documents\run-node.cjs" tests/browser_smoke.cjs
 */

const { chromium } = require('playwright')

const FRONTEND_URL = (
  process.env.FRONTEND_URL || 'http://localhost:3000'
).replace(/\/$/, '')
const ACTION_TIMEOUT = 5000
const NAVIGATION_TIMEOUT = 10000

function sanitize(text) {
  if (!text) return ''
  return String(text)
    .replace(
      /(?:access_token|csrf_token|token|password|secret)=[^&;\s]+/gi,
      '$1=***',
    )
    .replace(
      /"(?:password|token|access_token|csrf_token|secret)"\s*:\s*"[^"]+"/gi,
      '"$1":"***"',
    )
}

async function assertNoNextErrorOverlay(page) {
  const overlayLocators = [
    page.locator('nextjs-portal'),
    page.locator('[data-nextjs-dialog]'),
    page.locator('[data-nextjs-toast]'),
    page.locator('#nextjs__container_errors__'),
  ]
  for (const loc of overlayLocators) {
    if ((await loc.count()) > 0) {
      const isVisible = await loc
        .first()
        .isVisible()
        .catch(() => false)
      if (isVisible) {
        throw new Error('Next.js error overlay detected on page')
      }
    }
  }
}

async function checkNoHorizontalOverflow(page) {
  const hasOverflow = await page.evaluate(() => {
    const el = document.documentElement
    return el.scrollWidth > el.clientWidth + 1
  })
  if (hasOverflow) {
    throw new Error('Horizontal overflow detected at viewport 375px')
  }
}

async function runBrowserSmoke() {
  console.log('='.repeat(70))
  console.log(' Cashflow Radar Frontend Browser Smoke Test')
  console.log(' Target Frontend URL:', FRONTEND_URL)
  console.log('='.repeat(70))

  let browser
  try {
    browser = await chromium.launch({ headless: true })
  } catch (err) {
    console.error('[!] Failed to launch Chromium:', sanitize(err.message))
    process.exit(1)
  }

  let passed = 0
  let failed = 0

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 },
    })
    const page = await context.newPage()

    const pageErrors = []
    page.on('pageerror', err => {
      pageErrors.push(sanitize(err.message))
    })
    page.on('console', msg => {
      if (msg.type() === 'error') {
        const text = sanitize(msg.text())
        // Capture console errors for diagnosis
        pageErrors.push(`[console.error] ${text}`)
      }
    })

    async function runStep(name, fn) {
      pageErrors.length = 0
      process.stdout.write(`[*] ${name} ... `)
      try {
        await fn()
        if (pageErrors.length > 0) {
          const firstErr = pageErrors[0].split('\n')[0]
          console.log(`FAIL (unhandled runtime error: ${firstErr})`)
          failed++
        } else {
          console.log('PASS')
          passed++
        }
      } catch (err) {
        const firstLine = sanitize(err.message).split('\n')[0]
        console.log(`FAIL (${firstLine})`)
        failed++
      }
    }

    // 1. Login page: HTTP 200, form elements, no error overlay
    await runStep(
      '[PAGE-01] Login page loads with HTTP 200 and required form elements',
      async () => {
        const resp = await page.goto(`${FRONTEND_URL}/login`, {
          timeout: NAVIGATION_TIMEOUT,
          waitUntil: 'domcontentloaded',
        })
        if (!resp) throw new Error('No HTTP response received')
        if (resp.status() !== 200)
          throw new Error(`Expected HTTP 200, got ${resp.status()}`)

        await assertNoNextErrorOverlay(page)

        // Web-first locator waits
        const emailInput = page.locator(
          'input[type="email"], input[name="email"]',
        )
        await emailInput.waitFor({ state: 'visible', timeout: ACTION_TIMEOUT })

        const passwordInput = page.locator(
          'input[type="password"], input[name="password"]',
        )
        await passwordInput.waitFor({
          state: 'visible',
          timeout: ACTION_TIMEOUT,
        })

        const submitButton = page.locator(
          'button[type="submit"], input[type="submit"]',
        )
        await submitButton.waitFor({
          state: 'visible',
          timeout: ACTION_TIMEOUT,
        })
      },
    )

    // 2. Register page: HTTP 200, form elements, no error overlay
    await runStep(
      '[PAGE-02] Register page loads with HTTP 200 and required form elements',
      async () => {
        const resp = await page.goto(`${FRONTEND_URL}/register`, {
          timeout: NAVIGATION_TIMEOUT,
          waitUntil: 'domcontentloaded',
        })
        if (!resp) throw new Error('No HTTP response received')
        if (resp.status() !== 200)
          throw new Error(`Expected HTTP 200, got ${resp.status()}`)

        await assertNoNextErrorOverlay(page)

        const emailInput = page.locator(
          'input[type="email"], input[name="email"]',
        )
        await emailInput.waitFor({ state: 'visible', timeout: ACTION_TIMEOUT })

        const passwordInput = page.locator(
          'input[type="password"], input[name="password"]',
        )
        await passwordInput.waitFor({
          state: 'visible',
          timeout: ACTION_TIMEOUT,
        })

        const submitButton = page.locator(
          'button[type="submit"], input[type="submit"]',
        )
        await submitButton.waitFor({
          state: 'visible',
          timeout: ACTION_TIMEOUT,
        })
      },
    )

    // 3. Anonymous navigation to /companies redirects to /login
    await runStep(
      '[PAGE-03] Anonymous /companies request redirects to /login',
      async () => {
        await page.goto(`${FRONTEND_URL}/companies`, {
          timeout: NAVIGATION_TIMEOUT,
          waitUntil: 'domcontentloaded',
        })
        const currentUrl = page.url()
        if (!currentUrl.includes('/login')) {
          throw new Error(
            `Expected redirect to /login, but URL is ${currentUrl}`,
          )
        }
        await assertNoNextErrorOverlay(page)
      },
    )

    // 4. Responsive viewport 375px: no horizontal scrollbar / overflow
    await runStep(
      '[PAGE-04] Viewport 375px mobile responsiveness (no horizontal overflow)',
      async () => {
        await page.setViewportSize({ width: 375, height: 667 })
        await page.goto(`${FRONTEND_URL}/login`, {
          timeout: NAVIGATION_TIMEOUT,
          waitUntil: 'domcontentloaded',
        })
        await checkNoHorizontalOverflow(page)
      },
    )
  } finally {
    if (browser) {
      await browser.close()
    }
  }

  console.log('='.repeat(70))
  console.log(` Browser Smoke Summary: ${passed} passed, ${failed} failed`)
  console.log('='.repeat(70))

  process.exit(failed === 0 ? 0 : 1)
}

runBrowserSmoke().catch(err => {
  console.error('[!] Unexpected failure:', sanitize(err.message))
  process.exit(1)
})
