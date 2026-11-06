import { test, expect } from '@playwright/test';

test('homepage has title and heading', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/TIFF Merger/);
  await expect(page.getByRole('heading', { name: 'TIFF Merger' })).toBeVisible();
});

test('dropzone accepts drag and drop of TIFF files', async ({ page }) => {
  await page.goto('/');
  const dropzone = page.getByRole('button', { name: /add tiff files/i });
  await expect(dropzone).toBeVisible();
  await expect(dropzone).toHaveAttribute('aria-label');
});

test('merge button is disabled initially', async ({ page }) => {
  await page.goto('/');
  const mergeButton = page.getByRole('button', { name: /merge tiffs/i });
  await expect(mergeButton).toBeDisabled();
});

test('semantic HTML structure', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible();
  await expect(page.locator('h1')).toBeVisible();
});
