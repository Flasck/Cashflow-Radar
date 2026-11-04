/**
 * Standalone CommonJS Playwright workflow test for Cashflow Radar.
 * Covers full core browser flow without third-party dependencies:
 * - Registration of unique fictional user & company
 * - Transaction create (+/- sign sync), edit, delete (with DELETE 204 response assert)
 * - CSV import templates HTTP 200 check via browser context request
 * - Invalid CSV preview rejection & valid CSV preview/commit with artifacts/demo-transactions.csv
 * - Forecast POST 200 response check, 30-day points table verification
 * - Authenticated '/' redirect strictly to '/companies'
 * - SSR verification without JavaScript (in-memory storageState, table td DOM assertion)
 * - Mobile 375px horizontal overflow check on auth and ledger pages
 *
 * Runnable via document toolchain wrapper:
 *   node "C:\Users\Admin\.config\opencode\toolchains\documents\run-node.cjs" tests/browser_workflow.cjs
 */

const { chromium } = require('playwright')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')

const FRONTEND_URL = (
  process.env.FRONTEND_URL || 'http://localhost:3000'
).replace(/\/$/, '')
const ACTION_TIMEOUT = 10000
const NAVIGATION_TIMEOUT = 15000
const FORECAST_TIMEOUT = 30000

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

function getDemoCsvPath() {
  const diskPath = path.resolve(__dirname, '../artifacts/demo-transactions.csv')
  if (!fs.existsSync(diskPath)) {
    throw new Error(
      `Required fixture missing: ${diskPath}. Run 'python scripts/generate-demo.py' first.`,
    )
  }
  return diskPath
}

async function runBrowserWorkflow() {
  const runId = crypto.randomBytes(4).toString('hex')
  const prefix = `verify-${runId}`
  const demoCsvPath = getDemoCsvPath()

  console.log('='.repeat(70))
  console.log(' Cashflow Radar Full Browser Workflow Test')
  console.log(' Run ID        :', runId)
  console.log(' Prefix        :', prefix)
  console.log(' Target URL    :', FRONTEND_URL)
  console.log(' Demo Fixture  :', demoCsvPath)
  console.log('='.repeat(70))

  let browser
  let context
  const pageErrors = []

  try {
    browser = await chromium.launch({ headless: true })
    context = await browser.newContext({
      viewport: { width: 1280, height: 720 },
    })

    const page = await context.newPage()
    page.setDefaultTimeout(ACTION_TIMEOUT)
    page.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT)

    page.on('pageerror', err => {
      pageErrors.push(`[PageError] ${sanitize(err.message)}`)
    })
    page.on('console', msg => {
      if (msg.type() === 'error') {
        pageErrors.push(`[ConsoleError] ${sanitize(msg.text())}`)
      }
    })

    // 1. Registration
    console.log('[1/8] Registering user and creating company...')
    const { verifyPage, requireTestMailbox } = require('./mailbox.cjs')
    requireTestMailbox()
    await page.goto(`${FRONTEND_URL}/register`)
    await page.fill('#fullName', `${prefix} User`)
    await page.fill('#email', `${prefix}@example.com`)
    await page.fill('#password', 'Password123!')
    await page.click('button[type="submit"]')
    await verifyPage(page, `${prefix}@example.com`)

    await page.waitForURL(url => new URL(url).pathname === '/companies', {
      timeout: NAVIGATION_TIMEOUT,
    })

    // 2. Create Company
    await page.click('button:has-text("Создать компанию")')
    await page.fill('#companyName', `${prefix} Company`)
    await page.click('button:has-text("Создать")')

    await page.waitForURL(/\/companies\/\d+\/transactions/, {
      timeout: NAVIGATION_TIMEOUT,
    })
    const match = page.url().match(/\/companies\/(\d+)\/transactions/)
    if (!match)
      throw new Error(`Could not parse company ID from URL: ${page.url()}`)
    const companyId = match[1]
    console.log(`[+] Created company ID: ${companyId}`)

    // 3. Root redirect verification (strictly to /companies)
    console.log(
      '[2/8] Verifying authenticated root "/" redirect to "/companies"...',
    )
    await page.goto(`${FRONTEND_URL}/`)
    await page.waitForURL(url => new URL(url).pathname === '/companies', {
      timeout: NAVIGATION_TIMEOUT,
    })

    // 4. Transaction create with +/- sign sync
    console.log('[3/8] Creating transaction with +/- sign sync...')
    await page.goto(`${FRONTEND_URL}/companies/${companyId}/transactions/new`)
    await page.waitForSelector('#txAmount')

    // Test sign sync: typing '-' should activate outflow button
    await page.fill('#txAmount', '-2500.00')
    await page
      .locator('button.btn-primary:has-text("− Выплата")')
      .waitFor({ state: 'visible', timeout: 5000 })

    // Switch to inflow and save transaction
    await page.click('button:has-text("+ Поступление")')
    await page
      .locator('button.btn-primary:has-text("+ Поступление")')
      .waitFor({ state: 'visible', timeout: 5000 })
    await page.fill('#txAmount', '12500.00')
    await page.fill('#txPurpose', `${prefix} Revenue`)
    await page.click('button:has-text("Сохранить")')

    await page.waitForURL(
      url => new URL(url).pathname === `/companies/${companyId}/transactions`,
      {
        timeout: NAVIGATION_TIMEOUT,
      },
    )
    const createdCell = page.locator('.ledger-table td', {
      hasText: `${prefix} Revenue`,
    })
    if ((await createdCell.count()) === 0) {
      throw new Error(
        'Created transaction purpose not found in ledger table cells',
      )
    }
    console.log('[+] Transaction created and verified in ledger')

    // 5. Edit transaction
    console.log('[4/8] Editing transaction...')
    const editRow = page.locator('.ledger-table tbody tr', {
      hasText: `${prefix} Revenue`,
    })
    await editRow.locator('a:has-text("Изменить")').click()
    await page.waitForURL(
      new RegExp(`/companies/${companyId}/transactions/\\d+`),
      { timeout: NAVIGATION_TIMEOUT },
    )
    await page.fill('#txPurpose', `${prefix} Updated Revenue`)
    await page.click('button:has-text("Сохранить изменения")')

    await page.waitForURL(
      url => new URL(url).pathname === `/companies/${companyId}/transactions`,
      {
        timeout: NAVIGATION_TIMEOUT,
      },
    )
    const updatedCell = page.locator('.ledger-table td', {
      hasText: `${prefix} Updated Revenue`,
    })
    if ((await updatedCell.count()) === 0) {
      throw new Error(
        'Updated transaction purpose not found in ledger table cells',
      )
    }
    console.log('[+] Transaction edited successfully')

    // 6. CSV/XLSX template HTTP 200 & CSV import flow (invalid + valid)
    console.log(
      '[5/8] Testing import templates and CSV preview/commit with fixture...',
    )
    const csvTmplRes = await context.request.get(
      `${FRONTEND_URL}/api/companies/${companyId}/imports/template?format=csv`,
    )
    if (csvTmplRes.status() !== 200)
      throw new Error(`CSV template returned HTTP ${csvTmplRes.status()}`)
    const xlsxTmplRes = await context.request.get(
      `${FRONTEND_URL}/api/companies/${companyId}/imports/template?format=xlsx`,
    )
    if (xlsxTmplRes.status() !== 200)
      throw new Error(`XLSX template returned HTTP ${xlsxTmplRes.status()}`)

    await page.goto(`${FRONTEND_URL}/companies/${companyId}/import`)

    // Invalid CSV preview test (conflicting negative inflow)
    await page.setInputFiles('#importFile', {
      name: 'invalid.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        'date,amount,direction\n2026-10-01,-500.00,inflow\n',
        'utf-8',
      ),
    })
    await page.click('button:has-text("Проверить файл")')
    await page.waitForSelector('.notice-error')
    const commitBtn = page.locator('button:has-text("Добавить")')
    if (await commitBtn.isEnabled()) {
      throw new Error(
        'Commit button should be disabled for invalid CSV preview',
      )
    }

    // Return to upload step
    await page.click('button:has-text("Выбрать другой файл")')

    // Valid CSV preview & commit with artifacts/demo-transactions.csv
    await page.setInputFiles('#importFile', demoCsvPath)
    await page.click('button:has-text("Проверить файл")')
    await page.waitForSelector('.totals-ribbon')

    const commitValidBtn = page.locator('button:has-text("Добавить")')
    await commitValidBtn.click()
    await page.waitForSelector('text=Импорт успешно завершен')
    await page.click('button:has-text("Перейти в журнал операций")')
    await page.waitForURL(
      url => new URL(url).pathname === `/companies/${companyId}/transactions`,
      {
        timeout: NAVIGATION_TIMEOUT,
      },
    )
    console.log('[+] Demo CSV fixture imported and committed')

    // 7. Delete transaction (verify DELETE 204/200 and disappearance)
    console.log('[6/8] Deleting transaction...')
    const targetRow = page.locator('.ledger-table tbody tr', {
      hasText: `${prefix} Updated Revenue`,
    })
    await targetRow.locator('a:has-text("Изменить")').click()
    await page.waitForURL(
      new RegExp(`/companies/${companyId}/transactions/\\d+`),
      { timeout: NAVIGATION_TIMEOUT },
    )

    await page.click('button:has-text("Удалить операцию")')
    const [delRes] = await Promise.all([
      page.waitForResponse(
        res =>
          res.url().includes('/transactions/') &&
          res.request().method() === 'DELETE' &&
          (res.status() === 200 || res.status() === 204),
        { timeout: ACTION_TIMEOUT },
      ),
      page.click('button:has-text("Да, удалить безвозвратно")'),
    ])
    if (!delRes.ok())
      throw new Error(`Delete transaction returned status ${delRes.status()}`)

    await page.waitForURL(
      url => new URL(url).pathname === `/companies/${companyId}/transactions`,
      {
        timeout: NAVIGATION_TIMEOUT,
      },
    )
    const deletedCell = page.locator('.ledger-table td', {
      hasText: `${prefix} Updated Revenue`,
    })
    if ((await deletedCell.count()) > 0) {
      throw new Error('Deleted transaction is still present in ledger table')
    }
    console.log(
      '[+] Transaction deletion confirmed by DELETE response and table update',
    )

    // 8. Forecast strict view & 30-day points table
    console.log('[7/8] Generating forecast (waiting for POST /forecast 200)...')
    await page.goto(`${FRONTEND_URL}/companies/${companyId}/forecast`)
    const [forecastRes] = await Promise.all([
      page.waitForResponse(
        res =>
          res.url().includes('/forecast') &&
          res.request().method() === 'POST' &&
          res.status() === 200,
        { timeout: FORECAST_TIMEOUT },
      ),
      page.click('button:has-text("Построить прогноз")'),
    ])
    if (!forecastRes.ok())
      throw new Error(
        `Forecast request failed with status ${forecastRes.status()}`,
      )

    await page.waitForSelector('span:has-text("Модель:")', {
      timeout: ACTION_TIMEOUT,
    })
    await page.click('button:has-text("Показать значения таблицей")')
    await page.waitForSelector('.ledger-table tbody tr', {
      timeout: ACTION_TIMEOUT,
    })
    const forecastRowCount = await page
      .locator('.ledger-table tbody tr')
      .count()
    if (forecastRowCount !== 30) {
      throw new Error(
        `Expected 30 forecast points in table, got ${forecastRowCount}`,
      )
    }
    console.log(
      `[+] Forecast POST 200 received and verified ${forecastRowCount} points in table`,
    )

    // 9. SSR verification (No-JS context, in-memory storageState, DOM td assertion)
    console.log('[8/8] Verifying SSR without JavaScript...')
    const inMemoryState = await context.storageState()
    const ssrContext = await browser.newContext({
      javaScriptEnabled: false,
      storageState: inMemoryState,
    })
    const ssrPage = await ssrContext.newPage()

    // Check SSR on /companies: company name in table td
    await ssrPage.goto(`${FRONTEND_URL}/companies`)
    const ssrCompanyCell = ssrPage.locator('table.ledger-table td', {
      hasText: `${prefix} Company`,
    })
    if ((await ssrCompanyCell.count()) === 0) {
      throw new Error(
        'SSR failed: Company name not rendered in HTML table DOM cells',
      )
    }

    // Check SSR on /companies/[id]/transactions: fixture purpose in table td
    await ssrPage.goto(`${FRONTEND_URL}/companies/${companyId}/transactions`)
    const ssrTxCell = ssrPage.locator('table.ledger-table td', {
      hasText: 'Учебный пример: вымышленное поступление',
    })
    if ((await ssrTxCell.count()) === 0) {
      throw new Error(
        'SSR failed: Imported transaction purpose not rendered in HTML table DOM cells',
      )
    }
    await ssrContext.close()
    console.log('[+] SSR table DOM cells verified without JavaScript')

    // 10. Mobile 375px responsiveness on auth and ledger pages
    await page.setViewportSize({ width: 375, height: 667 })
    for (const testUrl of [
      `${FRONTEND_URL}/login`,
      `${FRONTEND_URL}/companies/${companyId}/transactions`,
    ]) {
      await page.goto(testUrl)
      const hasDocOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth + 1
      })
      if (hasDocOverflow) {
        throw new Error(
          `Mobile 375px: document horizontal scroll exceeds viewport at ${testUrl}`,
        )
      }
    }
    console.log(
      '[+] Mobile 375px verified on login and ledger without page horizontal overflow',
    )

    // Assert zero collected errors before declaring PASS
    if (pageErrors.length > 0) {
      throw new Error(
        `Collected ${pageErrors.length} unhandled browser error(s) during session:\n  ` +
          pageErrors.join('\n  '),
      )
    }

    console.log('='.repeat(70))
    console.log('[+] ALL BROWSER WORKFLOW CHECKS PASSED.')
    console.log(
      `[+] Retained demo fixture: ${prefix} Company (run ID: ${runId})`,
    )
    console.log('='.repeat(70))
  } catch (err) {
    process.exitCode = 1
    console.error('[-] Browser workflow failed:', sanitize(err.message))
    if (pageErrors.length > 0) {
      console.error('Collected errors during session:')
      pageErrors.slice(0, 5).forEach(e => console.error('  ', e))
    }
  } finally {
    if (context) await context.close().catch(() => {})
    if (browser) await browser.close().catch(() => {})
  }
}

runBrowserWorkflow().catch(err => {
  process.exitCode = 1
  console.error('[-] Browser workflow failed:', sanitize(err.message))
})
