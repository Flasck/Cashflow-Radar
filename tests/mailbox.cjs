async function verificationCode(email) {
  const base = process.env.TEST_MAILBOX_URL
  if (!base) {
    throw new Error(
      'Set TEST_MAILBOX_URL to a test-only mailbox; do not send synthetic registrations through real SMTP',
    )
  }
  const url = new URL(base)
  url.searchParams.set('email', email)
  const response = await fetch(url, { signal: AbortSignal.timeout(5000) })
  if (!response.ok) throw new Error('Test mailbox request failed')
  const { code } = await response.json()
  if (typeof code !== 'string' || !/^[0-9]{6}$/.test(code)) {
    throw new Error('Test mailbox returned an invalid verification code')
  }
  return code
}

async function verifyPage(page, email) {
  await page.locator('#verificationCode').waitFor()
  await page.fill('#verificationCode', await verificationCode(email))
  await page
    .getByRole('button', { name: 'Подтвердить почту', exact: true })
    .click()
}

function requireTestMailbox() {
  if (!process.env.TEST_MAILBOX_URL)
    throw new Error(
      'Set TEST_MAILBOX_URL before running synthetic registration tests',
    )
}

module.exports = { verificationCode, verifyPage, requireTestMailbox }
