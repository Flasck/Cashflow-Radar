const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function run() {
  const { requireTestMailbox, verificationCode } = require('./mailbox.cjs')
  requireTestMailbox()
  const runId = crypto.randomBytes(4).toString('hex')
  const origin = process.env.FRONTEND_URL || 'http://localhost:3000'
  const browser = await chromium.launch({ headless: true })
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    const registration = await context.request.post(
      `${origin}/api/auth/register`,
      {
        headers: { Origin: origin },
        data: {
          full_name: 'Forecast verification',
          email: `forecast-browser-${runId}@example.com`,
          password: crypto.randomBytes(24).toString('hex'),
        },
      },
    )
    assert.equal(registration.status(), 201)
    const verified = await context.request.post(
      `${origin}/api/auth/verify-email`,
      {
        headers: { Origin: origin },
        data: {
          email: `forecast-browser-${runId}@example.com`,
          code: await verificationCode(`forecast-browser-${runId}@example.com`),
        },
      },
    )
    assert.equal(verified.status(), 200)
    const cookies = await context.cookies()
    const csrf = cookies.find(cookie => cookie.name === 'csrf_token')
    assert.ok(csrf)
    const headers = { Origin: origin, 'X-CSRF-Token': csrf.value }
    const companyResponse = await context.request.post(
      `${origin}/api/companies`,
      {
        headers,
        data: { name: `Forecast browser ${runId}` },
      },
    )
    assert.equal(companyResponse.status(), 201)
    const company = await companyResponse.json()
    const base = `${origin}/api/companies/${company.id}`
    console.log(
      `Own retained fictional fixture: forecast-browser-${runId}, company ${company.id}`,
    )
    const fixture = fs.readFileSync(
      path.join(__dirname, '..', 'artifacts', 'demo-transactions.csv'),
    )
    const previewResponse = await context.request.post(
      `${base}/imports/preview`,
      {
        headers,
        multipart: {
          file: { name: 'demo.csv', mimeType: 'text/csv', buffer: fixture },
        },
      },
    )
    assert.equal(previewResponse.status(), 200)
    const preview = await previewResponse.json()
    assert.equal(preview.can_commit, true)
    const rows = preview.rows.map(
      ({ operation_date, amount, direction, category_name, purpose }) => ({
        operation_date,
        amount,
        direction,
        category_name,
        purpose,
      }),
    )
    const committed = await context.request.post(`${base}/imports/commit`, {
      headers,
      data: { rows },
    })
    assert.equal(committed.status(), 201)
    await page.goto(`${origin}/companies/${company.id}/forecast`)
    const build = page.getByRole('button', {
      name: 'Построить прогноз',
      exact: true,
    })
    const responsePromise = page.waitForResponse(
      response =>
        response.url() === `${base}/forecast` &&
        response.request().method() === 'POST',
    )
    await build.click()
    assert.equal((await responsePromise).status(), 200)
    await page.getByText('Модель:', { exact: false }).waitFor()
    const evidence = path.join(__dirname, '..', 'artifacts', 'browser')
    fs.mkdirSync(evidence, { recursive: true })
    await page.screenshot({
      path: path.join(evidence, 'forecast-1280.png'),
      fullPage: true,
    })
    await page.setViewportSize({ width: 375, height: 812 })
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 1,
      ),
      false,
    )
    const roleBadge = await page.locator('.badge-role').boundingBox()
    assert.ok(
      roleBadge && roleBadge.x >= 0 && roleBadge.x + roleBadge.width <= 375,
      'Company role badge must be visible inside the mobile viewport, not clipped',
    )
    await page
      .getByText('График можно прокрутить по горизонтали', { exact: true })
      .waitFor()
    await page.screenshot({
      path: path.join(evidence, 'forecast-375.png'),
      fullPage: true,
    })
    assert.equal(
      await page
        .getByRole('img', {
          name: 'График фактического денежного потока и рассчитанного прогноза',
          exact: true,
        })
        .evaluate(svg => {
          const container = svg.parentElement
          container.scrollLeft = container.scrollWidth
          return container.scrollLeft > 0
        }),
      true,
      'Mobile chart must allow scrolling to forecast points',
    )
    await page.screenshot({
      path: path.join(evidence, 'forecast-375-scrolled.png'),
      fullPage: true,
    })
    await page.setViewportSize({ width: 1280, height: 800 })
    console.log(
      'PASS real forecast and mobile chart; screenshots retained in artifacts/browser',
    )

    await page.getByRole('button', { name: '7 дней', exact: true }).click()
    await page
      .getByText('Горизонт изменен. Нажмите «Построить прогноз» для расчета.', {
        exact: true,
      })
      .waitFor()
    console.log('PASS forecast parameter changes mark result stale')

    await page.route(`${base}/forecast`, route =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'ENGINE_UNAVAILABLE',
            message: 'Сервис прогноза временно недоступен',
            fields: {},
          },
        }),
      }),
    )
    await build.click()
    await page
      .getByRole('alert')
      .filter({ hasText: 'Сервис прогноза временно недоступен' })
      .waitFor()
    assert.equal(await page.getByText('Модель:', { exact: false }).count(), 0)
    assert.equal(
      await page
        .getByRole('img', {
          name: 'График фактического денежного потока и рассчитанного прогноза',
          exact: true,
        })
        .count(),
      0,
    )
    assert.deepEqual(errors, [])
    console.log(
      'PASS failed rerun removes prior forecast instead of presenting it as current',
    )
  } finally {
    await browser.close()
  }
}

run().catch(error => {
  process.exitCode = 1
  console.error(error.message)
})
