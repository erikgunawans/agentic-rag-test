import { Page, expect } from '@playwright/test'

export const TEST_EMAIL = 'test@test.com'
export const TEST_PASSWORD = '!*-3-3?3uZ?b$v&'

/** Log in with the test account and wait for the chat page to load. */
export async function login(page: Page) {
  await page.goto('/auth')
  await page.getByRole('textbox', { name: 'Email' }).fill(TEST_EMAIL)
  await page.getByRole('textbox', { name: 'Password' }).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Log In' }).last().click()
  await expect(page).toHaveURL('/', { timeout: 15_000 })
}

/** Sign out from any page. */
export async function logout(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL('/auth', { timeout: 10_000 })
}

/** Create a new chat thread and return to the chat page with it active. */
export async function createThread(page: Page) {
  await page.getByRole('button', { name: 'New Thread' }).click()
  await expect(page.locator('textarea')).toBeVisible({ timeout: 5_000 })
}

/** Send a message and wait for the stream to complete (done=true). */
export async function sendMessage(page: Page, message: string) {
  const input = page.getByRole('textbox', { name: /Send a message/ })
  await input.fill(message)
  await input.press('Enter')
  // Wait for input to be re-enabled (stream complete)
  await expect(input).toBeEnabled({ timeout: 60_000 })
}
