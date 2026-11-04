const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const { chromium, expect } = require('playwright/test')
const { requireTestMailbox, verificationCode } = require('./mailbox.cjs')

async function run() {
  requireTestMailbox()
  const origin = process.env.FRONTEND_URL || 'http://localhost:3000'
  const email = `email-browser-${crypto.randomBytes(4).toString('hex')}@example.com`
  const browser = await chromium.launch({ headless: true })
  try {
    const context = await browser.newContext()
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${origin}/register`)
    await page.fill('#fullName', 'Email verification')
    await page.fill('#email', email)
    await page.fill('#password', 'Password123!')
    await page
      .getByRole('button', { name: 'Зарегистрироваться', exact: true })
      .click()
    await expect(page.locator('#verificationCode')).toBeVisible()
    assert.equal(
      (await context.cookies()).some(cookie => cookie.name === 'access_token'),
      false,
    )
    await expect(
      page.getByRole('button', { name: /Отправить повторно через/ }),
    ).toBeDisabled()
    const code = await verificationCode(email)
    await page.fill(
      '#verificationCode',
      code === '000000' ? '111111' : '000000',
    )
    await page
      .getByRole('button', { name: 'Подтвердить почту', exact: true })
      .click()
    await expect(
      page.getByRole('alert').filter({ hasText: 'Неверный код подтверждения' }),
    ).toBeVisible()
    assert.equal(
      (await context.cookies()).some(cookie => cookie.name === 'access_token'),
      false,
    )
    await page.fill('#verificationCode', code)
    await page
      .getByRole('button', { name: 'Подтвердить почту', exact: true })
      .click()
    await page.waitForURL(`${origin}/companies`)
    assert.ok(
      (await context.cookies()).some(
        cookie => cookie.name === 'access_token' && cookie.httpOnly,
      ),
    )
    assert.deepEqual(errors, [])
    console.log(
      'PASS email UI: no session before code, cooldown, invalid code error, successful verification',
    )
  } finally {
    await browser.close()
  }
}

run().catch(error => {
  process.exitCode = 1
  console.error(error.message)
})
