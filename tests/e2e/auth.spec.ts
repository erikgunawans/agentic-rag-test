/**
 * Authentication E2E tests.
 * Covers: AUTH-01 through AUTH-06
 */
import { test, expect } from '@playwright/test'
import { login, logout, TEST_EMAIL, TEST_PASSWORD } from './helpers'

test.describe('AUTH-01: Unauthenticated redirect', () => {
  test('navigating to / redirects to /auth', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL('/auth')
    await expect(page.getByRole('heading', { name: 'RAG Chat' })).toBeVisible()
  })

  test('navigating to /documents redirects to /auth when logged out', async ({ page }) => {
    await page.goto('/documents')
    await expect(page).toHaveURL('/auth')
  })

  test('navigating to /settings redirects to /auth when logged out', async ({ page }) => {
    await page.goto('/settings')
    await expect(page).toHaveURL('/auth')
  })
})

test.describe('AUTH-02: Invalid login shows error', () => {
  test('wrong credentials shows error message', async ({ page }) => {
    await page.goto('/auth')
    await page.getByRole('textbox', { name: 'Email' }).fill('wrong@example.com')
    await page.getByRole('textbox', { name: 'Password' }).fill('wrongpassword')
    await page.getByRole('button', { name: 'Log In' }).last().click()
    await expect(page.getByText('Invalid login credentials')).toBeVisible({ timeout: 10_000 })
    await expect(page).toHaveURL('/auth')
  })
})

test.describe('AUTH-03: Valid login', () => {
  test('correct credentials redirect to chat page', async ({ page }) => {
    await login(page)
    await expect(page.getByText('RAG Chat')).toBeVisible()
    await expect(page.getByRole('button', { name: 'New Thread' })).toBeVisible()
  })
})

test.describe('AUTH-04: Session persistence', () => {
  test('refreshing the page stays logged in', async ({ page }) => {
    await login(page)
    await page.reload()
    await expect(page).toHaveURL('/')
    await expect(page.getByRole('button', { name: 'New Thread' })).toBeVisible({ timeout: 10_000 })
  })
})

test.describe('AUTH-05: Sign out', () => {
  test('sign out redirects to /auth', async ({ page }) => {
    await login(page)
    await logout(page)
    await expect(page.getByRole('heading', { name: 'RAG Chat' })).toBeVisible()
  })
})

test.describe('AUTH-06: Unknown route fallback', () => {
  test('/nonexistent redirects to / when logged in', async ({ page }) => {
    await login(page)
    await page.goto('/nonexistent')
    await expect(page).toHaveURL('/')
  })
})
