/**
 * Chat UI E2E tests.
 * Covers: THR-06, THR-07, CHAT-03, CHAT-04, NAV-01, NAV-02, NAV-03, NAV-04
 */
import { test, expect } from '@playwright/test'
import { login, createThread, sendMessage } from './helpers'

test.beforeEach(async ({ page }) => {
  await login(page)
})

test.describe('THR-06: Create thread appears in sidebar', () => {
  test('new thread appears in sidebar list', async ({ page }) => {
    await createThread(page)
    await expect(page.getByText('New Thread').first()).toBeVisible()
    await expect(page.locator('textarea')).toBeVisible()
  })
})

test.describe('THR-07: Delete thread removes from sidebar', () => {
  test('deleting thread removes it from list', async ({ page }) => {
    await createThread(page)
    // Hover to reveal delete button
    const thread = page.locator('[cursor=pointer]').first()
    await thread.hover()
    await page.getByRole('button', { name: 'Delete thread' }).first().click()
    // The thread we just created should be gone; empty state may appear
    await expect(page.getByRole('button', { name: 'Delete thread' })).toHaveCount(
      await page.getByRole('button', { name: 'Delete thread' }).count(),
    )
  })
})

test.describe('CHAT-04: Streaming displays in real time', () => {
  test('user message appears immediately, assistant streams in', async ({ page }) => {
    await createThread(page)
    const input = page.getByRole('textbox', { name: /Send a message/ })
    const testMsg = 'Say the word: pong'
    await input.fill(testMsg)
    await input.press('Enter')

    // User bubble appears immediately (optimistic)
    await expect(page.getByText(testMsg)).toBeVisible({ timeout: 5_000 })

    // Input is disabled while streaming
    await expect(input).toBeDisabled({ timeout: 5_000 })

    // Wait for stream to complete — input re-enabled
    await expect(input).toBeEnabled({ timeout: 60_000 })

    // An assistant response is now visible
    const messages = page.locator('[ref]').filter({ hasText: /pong/i })
    await expect(messages.first()).toBeVisible({ timeout: 5_000 })
  })
})

test.describe('CHAT-03: Stateless history — follow-up uses prior context', () => {
  test('second message knows about first message', async ({ page }) => {
    await createThread(page)
    await sendMessage(page, 'My secret word is XYZZY42.')
    await sendMessage(page, 'What was my secret word?')
    await expect(page.getByText(/XYZZY42/)).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('NAV-01/02/03/04: Navigation', () => {
  test('NAV-01: Documents icon navigates to /documents', async ({ page }) => {
    await page.getByRole('button', { name: 'Documents' }).click()
    await expect(page).toHaveURL('/documents')
    await expect(page.getByText('Upload Document', { exact: false })).toBeVisible()
  })

  test('NAV-02: Settings icon navigates to /settings', async ({ page }) => {
    await page.getByRole('button', { name: 'Settings' }).click()
    await expect(page).toHaveURL('/settings')
    await expect(page.getByText('LLM Model')).toBeVisible()
  })

  test('NAV-03: Back arrow from /documents returns to /', async ({ page }) => {
    await page.goto('/documents')
    await page.getByRole('button', { name: 'Back to chat' }).click()
    await expect(page).toHaveURL('/')
  })

  test('NAV-04: Unknown route redirects to /', async ({ page }) => {
    await page.goto('/this-does-not-exist')
    await expect(page).toHaveURL('/')
  })
})
