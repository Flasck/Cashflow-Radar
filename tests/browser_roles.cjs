/**
 * Standalone CommonJS Playwright role & invitation flow test for Cashflow Radar.
 * Tests actual frontend invitation, RBAC boundaries, and role transitions:
 * 1. Owner registers and creates company via UI.
 * 2. Owner navigates to Settings -> Members and creates invitation for viewer.
 * 3. Secret invite link is retrieved from DOM without logging tokens.
 * 4. Unauthenticated invitee visits /invite#token=... and attempts accept -> 401 error displayed.
 * 5. Token is retained in sessionStorage; invitee registers account and logs in.
 * 6. Invitee accepts invitation -> joins company as viewer.
 * 7. Invitee verifies read access (transactions, forecast) and absence of write controls (+ Add operation, Import).
 * 8. Invitee attempts foreign company access -> returns 404.
 * 9. Owner promotes viewer to treasurer via Settings UI.
 * 10. Invitee reloads and verifies write controls appear, successfully creating an operation.
 *
 * Runnable via document toolchain wrapper:
 *   node "C:\Users\Admin\.config\opencode\toolchains\documents\run-node.cjs" tests/browser_roles.cjs
 */

const { chromium } = require('playwright')
const crypto = require('crypto')
const fs = require('node:fs/promises')

const FRONTEND_URL = (
  process.env.FRONTEND_URL || 'http://localhost:3000'
).replace(/\/$/, '')
const ACTION_TIMEOUT = 10000
const NAVIGATION_TIMEOUT = 15000

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

async function runBrowserRoles() {
  const runId = crypto.randomBytes(4).toString('hex')
  const prefix = `verify-${runId}`

  console.log('='.repeat(70))
  console.log(' Cashflow Radar Browser Roles & Invitation Flow Test')
  console.log(' Run ID        :', runId)
  console.log(' Prefix        :', prefix)
  console.log(' Target URL    :', FRONTEND_URL)
  console.log('='.repeat(70))

  let browser
  let ownerContext
  let inviteeContext
  let inviteePage
  const pageErrors = []
  let expectAuth401 = false

  const hookPageErrors = (page, roleName) => {
    page.on('pageerror', err => {
      pageErrors.push(`[${roleName} PageError] ${sanitize(err.message)}`)
    })
    page.on('console', msg => {
      if (msg.type() === 'error') {
        const text = msg.text()
        if (
          expectAuth401 &&
          roleName === 'Invitee' &&
          text.includes('401') &&
          (text.includes('invitations/accept') ||
            text.includes('Unauthorized') ||
            text.includes('status of 401'))
        ) {
          // Expected 401 on unauthenticated invite accept
          return
        }
        pageErrors.push(`[${roleName} ConsoleError] ${sanitize(text)}`)
      }
    })
  }

  try {
    browser = await chromium.launch({ headless: true })

    // -------------------------------------------------------------------------
    // Phase 1: Owner Registration & Company Creation
    // -------------------------------------------------------------------------
    console.log('[1/7] Owner: Registering and creating company...')
    ownerContext = await browser.newContext({
      viewport: { width: 1280, height: 720 },
    })
    const ownerPage = await ownerContext.newPage()
    ownerPage.setDefaultTimeout(ACTION_TIMEOUT)
    ownerPage.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT)
    hookPageErrors(ownerPage, 'Owner')

    const { verifyPage, requireTestMailbox } = require('./mailbox.cjs')
    requireTestMailbox()
    await ownerPage.goto(`${FRONTEND_URL}/register`)
    await ownerPage.fill('#fullName', `${prefix} Owner`)
    await ownerPage.fill('#email', `${prefix}_owner@example.com`)
    await ownerPage.fill('#password', 'Password123!')
    await ownerPage.click('button[type="submit"]')
    await verifyPage(ownerPage, `${prefix}_owner@example.com`)

    await ownerPage.waitForURL(url => new URL(url).pathname === '/companies', {
      timeout: NAVIGATION_TIMEOUT,
    })

    await ownerPage.click('button:has-text("Создать компанию")')
    await ownerPage.fill('#companyName', `${prefix} Roles Corp`)
    await ownerPage.click('button:has-text("Создать")')

    await ownerPage.waitForURL(/\/companies\/\d+\/transactions/, {
      timeout: NAVIGATION_TIMEOUT,
    })
    const match = ownerPage.url().match(/\/companies\/(\d+)\/transactions/)
    if (!match)
      throw new Error(`Could not parse company ID from URL: ${ownerPage.url()}`)
    const companyId = match[1]
    console.log(`[+] Company created with ID: ${companyId}`)

    // -------------------------------------------------------------------------
    // Phase 2: Owner Creates Viewer Invitation via UI
    // -------------------------------------------------------------------------
    console.log(
      '[2/7] Owner: Generating viewer invitation link via Settings UI...',
    )
    await ownerPage.goto(`${FRONTEND_URL}/companies/${companyId}/settings`)

    // Switch to Members tab
    await ownerPage.click('button:has-text("Участники")')

    // Fill invitation form
    const inviteeEmail = `${prefix}_invitee@example.com`
    await ownerPage.fill('#invEmail', inviteeEmail)
    await ownerPage.selectOption('#invRole', 'viewer')

    const [inviteRes] = await Promise.all([
      ownerPage.waitForResponse(
        res =>
          res.url().includes(`/companies/${companyId}/invitations`) &&
          res.request().method() === 'POST',
        { timeout: ACTION_TIMEOUT },
      ),
      ownerPage.click('button:has-text("Создать ссылку")'),
    ])
    if (!inviteRes.ok()) {
      throw new Error(
        `Invitation creation failed with status ${inviteRes.status()}`,
      )
    }

    // Retrieve invite link from DOM input without logging secret token
    const inviteInput = ownerPage.locator('.notice-success input.form-input')
    await inviteInput.waitFor({ state: 'visible', timeout: ACTION_TIMEOUT })
    let inviteUrl = await inviteInput.inputValue()
    if (!inviteUrl || !inviteUrl.includes('/invite#token=')) {
      throw new Error('Invitation URL was not generated in the DOM input')
    }
    console.log(
      '[+] Invitation link successfully created and retrieved from DOM input',
    )
    const oldInviteUrl = inviteUrl
    ownerPage.on('dialog', dialog => dialog.accept())
    const historyTable = ownerPage
      .locator('table')
      .filter({ has: ownerPage.locator('th', { hasText: 'Статус' }) })
    await historyTable
      .getByRole('button', { name: 'Продлить', exact: true })
      .click()
    await ownerPage.waitForFunction(old => {
      const input = document.querySelector('.notice-success input.form-input')
      return input && input.value && input.value !== old
    }, oldInviteUrl)
    inviteUrl = await inviteInput.inputValue()
    await historyTable.getByText('Отозвано', { exact: true }).waitFor()
    console.log(
      '[+] Renewal generated a different link and retained the revoked original',
    )

    // -------------------------------------------------------------------------
    // Phase 3: Unauthenticated Invitee Visits Invite -> 401 Rejection
    // -------------------------------------------------------------------------
    console.log('[3/7] Invitee: Visiting invite link while unauthenticated...')
    inviteeContext = await browser.newContext({
      viewport: { width: 1280, height: 720 },
    })
    inviteePage = await inviteeContext.newPage()
    inviteePage.setDefaultTimeout(ACTION_TIMEOUT)
    inviteePage.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT)
    hookPageErrors(inviteePage, 'Invitee')

    const targetInviteUrl = inviteUrl.startsWith('http')
      ? inviteUrl
      : `${FRONTEND_URL}${inviteUrl.startsWith('/') ? '' : '/'}${inviteUrl}`

    await inviteePage.goto(targetInviteUrl)
    await inviteePage.waitForSelector(
      'button:has-text("Принять приглашение")',
      { timeout: ACTION_TIMEOUT },
    )

    // Expecting 401 on unauthenticated accept attempt
    expectAuth401 = true
    const [accept401Res] = await Promise.all([
      inviteePage.waitForResponse(
        res =>
          res.url().includes('/api/invitations/accept') && res.status() === 401,
        {
          timeout: ACTION_TIMEOUT,
        },
      ),
      inviteePage.click('button:has-text("Принять приглашение")'),
    ])

    if (accept401Res.status() !== 401) {
      throw new Error(
        `Expected 401 on unauthenticated invite accept, got ${accept401Res.status()}`,
      )
    }

    // Verify error notice is displayed and user remains on /invite
    const errorNotice = inviteePage.locator('.notice-error')
    await errorNotice.waitFor({ state: 'visible', timeout: ACTION_TIMEOUT })
    const errorText = await errorNotice.textContent()
    if (!/войти|войдите/.test(errorText)) {
      throw new Error(
        `Expected auth requirement notice on /invite, got: ${errorText}`,
      )
    }
    expectAuth401 = false
    console.log(
      '[+] Unauthenticated invite accept properly rejected with 401 notice',
    )

    // -------------------------------------------------------------------------
    // Phase 4: Invitee Registers, Retains Token in sessionStorage, Accepts
    // -------------------------------------------------------------------------
    console.log(
      '[4/7] Invitee: Registering account and accepting invitation...',
    )
    // Click register link from invite page
    await inviteePage.click('a:has-text("Зарегистрироваться")')
    await inviteePage.waitForSelector('#fullName', { timeout: ACTION_TIMEOUT })

    await inviteePage.fill('#fullName', `${prefix} Invitee`)
    await inviteePage.fill('#email', inviteeEmail)
    await inviteePage.fill('#password', 'Password123!')
    await inviteePage.click('button[type="submit"]')
    await verifyPage(inviteePage, inviteeEmail)

    // Due to sessionStorage radar_invite_token, register auto-redirects back to /invite
    await inviteePage.waitForSelector(
      'button:has-text("Принять приглашение")',
      { timeout: NAVIGATION_TIMEOUT },
    )

    const recipientCsrf = (await inviteeContext.cookies()).find(
      cookie => cookie.name === 'csrf_token',
    ).value
    const oldToken = new URL(oldInviteUrl, FRONTEND_URL).hash.slice(
      '#token='.length,
    )
    const oldLinkResponse = await inviteeContext.request.post(
      `${FRONTEND_URL}/api/invitations/accept`,
      {
        headers: { Origin: FRONTEND_URL, 'X-CSRF-Token': recipientCsrf },
        data: { token: oldToken },
      },
    )
    if (oldLinkResponse.status() !== 409)
      throw new Error('Renewed invitation original link was not invalidated')
    const [declineResponse] = await Promise.all([
      inviteePage.waitForResponse(res =>
        res.url().endsWith('/api/invitations/decline'),
      ),
      inviteePage
        .getByRole('button', { name: 'Отклонить приглашение', exact: true })
        .click(),
    ])
    if (declineResponse.status() !== 200)
      throw new Error('Invitation decline failed')
    await inviteePage
      .getByText('Приглашение отклонено.', { exact: false })
      .waitFor()
    if (
      await inviteePage.evaluate(
        () => sessionStorage.getItem('radar_invite_token') !== null,
      )
    ) {
      throw new Error('Declined invitation token retained in sessionStorage')
    }
    const companiesResponse = await inviteeContext.request.get(
      `${FRONTEND_URL}/api/companies`,
    )
    if (
      (await companiesResponse.json()).some(
        company => String(company.id) === companyId,
      )
    ) {
      throw new Error('Decline incorrectly created membership')
    }
    await ownerPage.reload()
    await ownerPage.getByRole('button', { name: /Участники/ }).click()
    await historyTable.getByText('Отклонено', { exact: true }).waitFor()
    if (await historyTable.getByRole('button').count())
      throw new Error('Terminal history exposes mutation buttons')
    await ownerPage.fill('#invEmail', inviteeEmail)
    await ownerPage.selectOption('#invRole', 'viewer')
    await ownerPage
      .getByRole('button', { name: 'Создать ссылку', exact: true })
      .click()
    await inviteInput.waitFor()
    inviteUrl = await inviteInput.inputValue()
    await inviteePage.goto(inviteUrl)
    console.log(
      '[+] Decline retained history, cleared the token and did not grant access; fresh invitation created',
    )

    const [acceptSuccessRes] = await Promise.all([
      inviteePage.waitForResponse(
        res =>
          res.url().includes('/api/invitations/accept') &&
          (res.status() === 200 || res.status() === 201),
        { timeout: ACTION_TIMEOUT },
      ),
      inviteePage.click('button:has-text("Принять приглашение")'),
    ])
    if (!acceptSuccessRes.ok()) {
      throw new Error(
        `Authenticated invite accept failed with status ${acceptSuccessRes.status()}`,
      )
    }

    await inviteePage.waitForSelector('h1:has-text("Журнал операций")', {
      timeout: NAVIGATION_TIMEOUT,
    })
    console.log(
      '[+] Authenticated invite accepted, redirected to company transactions',
    )

    // -------------------------------------------------------------------------
    // Phase 5: Verify Viewer Boundaries (Read OK, Write Controls Absent)
    // -------------------------------------------------------------------------
    console.log(
      '[5/7] Invitee: Verifying Viewer role permissions and UI boundaries...',
    )
    // Check role badge shows 'Наблюдатель'
    const roleBadge = inviteePage.locator('.badge-role')
    const badgeText = await roleBadge.textContent()
    if (!badgeText.includes('Наблюдатель')) {
      throw new Error(`Expected role badge 'Наблюдатель', got '${badgeText}'`)
    }

    // Verify read pages are accessible
    await inviteePage.goto(`${FRONTEND_URL}/companies/${companyId}/forecast`)
    await inviteePage.waitForSelector(
      'h1:has-text("Прогноз денежных потоков")',
      { timeout: ACTION_TIMEOUT },
    )

    await inviteePage.goto(`${FRONTEND_URL}/companies`)
    const compRow = inviteePage.locator('.ledger-table td', {
      hasText: `${prefix} Roles Corp`,
    })
    if ((await compRow.count()) === 0) {
      throw new Error(
        'Viewer could not find joined company in /companies listing',
      )
    }

    // Verify write controls are ABSENT on transactions page
    await inviteePage.goto(
      `${FRONTEND_URL}/companies/${companyId}/transactions`,
    )
    await inviteePage.waitForSelector('h1:has-text("Журнал операций")', {
      timeout: ACTION_TIMEOUT,
    })

    const addTxBtn = inviteePage.locator('a:has-text("+ Добавить операцию")')
    if ((await addTxBtn.count()) > 0) {
      throw new Error(
        'Viewer should not see "+ Добавить операцию" write control',
      )
    }

    const importBtn = inviteePage.locator('a:has-text("Загрузить файл")')
    if ((await importBtn.count()) > 0) {
      throw new Error('Viewer should not see "Загрузить файл" import control')
    }

    // Verify foreign company access returns 404
    const foreignRes = await inviteeContext.request.get(
      `${FRONTEND_URL}/api/companies/999999/transactions`,
    )
    if (foreignRes.status() !== 404) {
      throw new Error(
        `Expected 404 for unassociated foreign company, got ${foreignRes.status()}`,
      )
    }
    console.log(
      '[+] Viewer read access verified; write controls absent; foreign company returns 404',
    )

    // -------------------------------------------------------------------------
    // Phase 6: Owner Promotes Viewer to Treasurer
    // -------------------------------------------------------------------------
    console.log('[6/7] Owner: Promoting invitee from Viewer to Treasurer...')
    await ownerPage.goto(`${FRONTEND_URL}/companies/${companyId}/settings`)
    await ownerPage.click('button:has-text("Участники")')
    await historyTable.getByText('Принято', { exact: true }).waitFor()

    // Find invitee row in members table (distinguished from pending invitations by role select)
    const memberRow = ownerPage.locator('.ledger-table tbody tr', {
      hasText: inviteeEmail,
      has: ownerPage.locator('select.form-select'),
    })
    await memberRow.waitFor({ state: 'visible', timeout: ACTION_TIMEOUT })

    const roleSelect = memberRow.locator('select.form-select')
    const [rolePatchRes] = await Promise.all([
      ownerPage.waitForResponse(
        res =>
          res.url().includes(`/companies/${companyId}/members/`) &&
          res.request().method() === 'PATCH',
        { timeout: ACTION_TIMEOUT },
      ),
      roleSelect.selectOption('treasurer'),
    ])
    if (!rolePatchRes.ok()) {
      throw new Error(
        `Role promotion failed with status ${rolePatchRes.status()}`,
      )
    }
    console.log('[+] Invitee promoted to Treasurer in UI')

    // -------------------------------------------------------------------------
    // Phase 7: Invitee (as Treasurer) Writes New Transaction via UI
    // -------------------------------------------------------------------------
    console.log(
      '[7/7] Invitee: Reloading and creating transaction as Treasurer...',
    )
    await inviteePage.goto(
      `${FRONTEND_URL}/companies/${companyId}/transactions`,
    )
    await inviteePage.waitForSelector('h1:has-text("Журнал операций")', {
      timeout: ACTION_TIMEOUT,
    })

    // Header role should now be 'Казначей'
    const newRoleBadge = inviteePage.locator('.badge-role')
    const newBadgeText = await newRoleBadge.textContent()
    if (!newBadgeText.includes('Казначей')) {
      throw new Error(
        `Expected role badge 'Казначей' after promotion, got '${newBadgeText}'`,
      )
    }

    // Write control '+ Добавить операцию' must now be visible
    const newAddBtn = inviteePage.locator('a:has-text("+ Добавить операцию")')
    await newAddBtn.waitFor({ state: 'visible', timeout: ACTION_TIMEOUT })
    await newAddBtn.click()
    await inviteePage.waitForSelector('#txAmount', { timeout: ACTION_TIMEOUT })
    await inviteePage.fill('#txAmount', '77000.00')
    await inviteePage.fill('#txPurpose', `${prefix} Treasurer Payment`)

    const [createTxRes] = await Promise.all([
      inviteePage.waitForResponse(
        res =>
          res.url().includes(`/companies/${companyId}/transactions`) &&
          res.request().method() === 'POST',
        { timeout: ACTION_TIMEOUT },
      ),
      inviteePage.click('button:has-text("Сохранить")'),
    ])
    if (!createTxRes.ok()) {
      throw new Error(
        `Treasurer transaction creation failed with status ${createTxRes.status()}`,
      )
    }

    await inviteePage.waitForSelector('h1:has-text("Журнал операций")', {
      timeout: NAVIGATION_TIMEOUT,
    })
    const txCell = inviteePage.locator('.ledger-table td', {
      hasText: `${prefix} Treasurer Payment`,
    })
    if ((await txCell.count()) === 0) {
      throw new Error('Created payment not found in ledger table cells')
    }
    console.log(
      '[+] Treasurer successfully created and verified transaction in UI',
    )

    await ownerPage.reload()
    await ownerPage.getByRole('button', { name: /Участники/ }).click()
    await ownerPage.fill('#invEmail', `${prefix}_revoked@example.com`)
    await ownerPage
      .getByRole('button', { name: 'Создать ссылку', exact: true })
      .click()
    const revokeRow = historyTable
      .locator('tbody tr')
      .filter({ hasText: `${prefix}_revoked@example.com` })
    await revokeRow
      .getByRole('button', { name: 'Отозвать', exact: true })
      .click()
    await revokeRow.getByText('Отозвано', { exact: true }).waitFor()
    if (await revokeRow.getByRole('button').count())
      throw new Error('Revoked invitation exposes mutation buttons')
    await fs.mkdir('artifacts/browser', { recursive: true })
    await ownerPage.screenshot({
      path: 'artifacts/browser/invitation-history-1280.png',
      fullPage: true,
    })
    await ownerPage.setViewportSize({ width: 375, height: 812 })
    await ownerPage.locator('.ledger-wrapper').evaluateAll(elements =>
      elements.forEach(element => {
        element.scrollLeft = 0
      }),
    )
    if (
      await ownerPage.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    ) {
      throw new Error('Invitation history overflows the mobile viewport')
    }
    await ownerPage.screenshot({
      path: 'artifacts/browser/invitation-history-375.png',
      fullPage: true,
    })
    console.log(
      '[+] Revoke retained history; mobile history stays within 375px; screenshot saved',
    )

    // -------------------------------------------------------------------------
    // Verification of zero unexpected errors
    // -------------------------------------------------------------------------
    if (pageErrors.length > 0) {
      throw new Error(
        `Collected ${pageErrors.length} unexpected browser error(s):\n  ` +
          pageErrors.join('\n  '),
      )
    }

    console.log('='.repeat(70))
    console.log('[+] ALL BROWSER ROLES & INVITATION CHECKS PASSED.')
    console.log(
      `[+] Retained demo fixture: ${prefix} Roles Corp (run ID: ${runId})`,
    )
    console.log('='.repeat(70))
  } catch (err) {
    process.exitCode = 1
    console.error('[-] Browser roles test failed:', sanitize(err.message))
    if (inviteePage) {
      const diagnosticUrl = new URL(inviteePage.url())
      console.error(
        'Invitee current page:',
        diagnosticUrl.origin + diagnosticUrl.pathname,
      )
      try {
        const bodySnippet = await inviteePage.evaluate(() =>
          document.body.innerText.slice(0, 300),
        )
        console.error('Invitee body snippet:', bodySnippet)
      } catch (_) {}
    }
    if (pageErrors.length > 0) {
      console.error('Collected errors during session:')
      pageErrors.slice(0, 5).forEach(e => console.error('  ', e))
    }
  } finally {
    if (ownerContext) await ownerContext.close().catch(() => {})
    if (inviteeContext) await inviteeContext.close().catch(() => {})
    if (browser) await browser.close().catch(() => {})
  }
}

runBrowserRoles().catch(err => {
  process.exitCode = 1
  console.error(
    '[-] Unhandled exception in browser roles runner:',
    sanitize(err.message),
  )
})
