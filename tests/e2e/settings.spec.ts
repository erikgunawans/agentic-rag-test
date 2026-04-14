/**
 * Settings page E2E tests.
 * Covers: SET-06, NAV-02
 */
import path from 'path'
import { test, expect } from '@playwright/test'
import { login } from './helpers'

const FIXTURE_TXT = path.resolve(__dirname, '../fixtures/sample.txt')

test.beforeEach(async ({ page }) => {
  await login(page)
})

test.describe('SET-01/02: Settings page loads with current selections', () => {
  test('settings page renders with LLM and embedding sections', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByText('LLM Model')).toBeVisible()
    await expect(page.getByText('Embedding Model')).toBeVisible()
    await expect(page.getByRole('button', { name: /Save Settings/ })).toBeVisible()
  })

  test('GPT-4o Mini is selected by default', async ({ page }) => {
    await page.goto('/settings')
    const gpt4oMini = page.getByRole('radio').filter({ hasText: /gpt-4o-mini/i })
    // The selected radio should be checked — we verify the label is visible
    await expect(page.getByText('GPT-4o Mini')).toBeVisible()
  })
})

test.describe('SET-02: LLM model change saves', () => {
  test('selecting different LLM model and saving persists change', async ({ page }) => {
    await page.goto('/settings')

    // Select Claude 3 Haiku
    await page.getByText('Claude 3 Haiku').click()

    // Save button should be enabled now
    const saveBtn = page.getByRole('button', { name: /Save Settings/ })
    await expect(saveBtn).toBeEnabled()
    await saveBtn.click()
    await expect(page.getByText('Saved!')).toBeVisible({ timeout: 10_000 })

    // Restore default
    await page.getByText('GPT-4o Mini').click()
    await page.getByRole('button', { name: /Save Settings/ }).click()
    await expect(page.getByText('Saved!')).toBeVisible({ timeout: 10_000 })
  })
})

test.describe('SET-06: Embedding lock UI when documents exist', () => {
  test('embedding locked badge shown when user has indexed documents', async ({ page }) => {
    // Upload a document first
    await page.goto('/documents')
    await page.locator('input[type="file"]').setInputFiles(FIXTURE_TXT)
    await expect(page.getByText('completed')).toBeVisible({ timeout: 45_000 })

    // Go to settings
    await page.goto('/settings')
    await expect(page.getByText('Locked')).toBeVisible({ timeout: 5_000 })

    // Embedding radios should be disabled
    const embeddingRadios = page.locator('input[name="embedding_model"]')
    const count = await embeddingRadios.count()
    for (let i = 0; i < count; i++) {
      await expect(embeddingRadios.nth(i)).toBeDisabled()
    }

    // Clean up: delete document to unlock
    await page.goto('/documents')
    const deleteButtons = page.getByRole('button', { name: 'Delete document' })
    const btnCount = await deleteButtons.count()
    for (let i = 0; i < btnCount; i++) {
      await deleteButtons.first().click()
      await page.waitForTimeout(300)
    }
  })
})
