import { expect, test } from '@playwright/test';

test('selects a product and recomputes the scenario forecast', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Forecast overview' })).toBeVisible();
  await expect(page.getByText('SYNTHETIC DEMO')).toBeVisible();
  const productSelect = page.getByLabel('Select product');
  await expect(productSelect.locator('option')).toHaveCount(22);
  await productSelect.selectOption({ index: 1 });
  const forecastResponse = await page.request.get('/api/forecasts/DEMO-002');
  expect(forecastResponse.ok()).toBeTruthy();
  const historyResponse = await page.request.get('/api/products/DEMO-002/history');
  expect(historyResponse.ok()).toBeTruthy();
  expect((await historyResponse.json()).items.length).toBeGreaterThan(8);
  await expect(page.locator('.recharts-line-curve').first()).toBeVisible();
  await expect(page.getByText('Forecast origin')).toBeVisible();
  await expect(page.locator('.sim-result b').first()).not.toContainText('—');
  await expect(page.getByText('Change:', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'One-week shock' }).click();
  await expect(page.locator('.sim-result b').nth(1)).not.toContainText('—');
  await expect(page.getByText('Scenario sensitivity only', { exact: false })).toBeVisible();
  await page.screenshot({ path: '../../docs/images/dashboard-demo.png', fullPage: true });
});
