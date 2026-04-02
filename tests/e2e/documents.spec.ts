/**
 * Documents page E2E tests.
 * Covers: DOC-07, DOC-08, RAG-01
 */
import path from 'path'
import { test, expect } from '@playwright/test'
import { login } from './helpers'

const FIXTURE_TXT = path.resolve(__dirname, '../fixtures/sample.txt')

test.beforeEach(async ({ page }) => {
  await login(page)
  await page.goto('/documents')
})

test.describe('DOC-08: Upload and delete via UI', () => {
  test('uploaded file appears in list', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles(FIXTURE_TXT)

    // Document should appear in list
    await expect(page.getByText('sample.txt')).toBeVisible({ timeout: 10_000 })
  })

  test('deleted file disappears from list', async ({ page }) => {
    // Upload first
    await page.locator('input[type="file"]').setInputFiles(FIXTURE_TXT)
    await expect(page.getByText('sample.txt')).toBeVisible({ timeout: 10_000 })

    // Delete
    await page.getByRole('button', { name: 'Delete document' }).first().click()
    await expect(page.getByText('sample.txt')).not.toBeVisible({ timeout: 10_000 })
  })
})

test.describe('DOC-07: Realtime status updates', () => {
  test('status changes from pending to completed without page refresh', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(FIXTURE_TXT)

    // Should reach completed without reloading
    await expect(page.getByText('completed')).toBeVisible({ timeout: 45_000 })
  })
})

test.describe('RAG-01: Document content retrieved in chat', () => {
  test('ask about document content, response references it', async ({ page }) => {
    // Upload document
    await page.locator('input[type="file"]').setInputFiles(FIXTURE_TXT)
    await expect(page.getByText('completed')).toBeVisible({ timeout: 45_000 })

    // Navigate to chat
    await page.getByRole('button', { name: 'Go to Chat' }).click()
    await expect(page).toHaveURL('/')

    // Create thread and ask about document content
    await page.getByRole('button', { name: 'New Thread' }).click()
    const input = page.getByRole('textbox', { name: /Send a message/ })
    await input.fill('What is the capital of France according to the documents?')
    await input.press('Enter')

    // Wait for response
    await expect(input).toBeEnabled({ timeout: 60_000 })
    await expect(page.getByText(/Paris/i)).toBeVisible({ timeout: 10_000 })

    // Clean up: delete the document
    await page.goto('/documents')
    const deleteButtons = page.getByRole('button', { name: 'Delete document' })
    const count = await deleteButtons.count()
    for (let i = 0; i < count; i++) {
      await deleteButtons.first().click()
      await page.waitForTimeout(500)
    }
  })
})
