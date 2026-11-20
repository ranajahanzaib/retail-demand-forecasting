import { expect, test } from '@playwright/test';

test.describe('Retail Demand Forecasting Showcase & Verification', () => {
  test.use({
    viewport: { width: 1440, height: 960 },
  });

  test('explores product forecasts, tests prediction intervals, and runs demand shift simulations', async ({
    page,
  }) => {
    await page.goto('/');

    // 1. Verify Header and Engine connectivity
    await expect(page.getByRole('heading', { name: 'Forecast overview' })).toBeVisible();
    await expect(page.getByText('SYNTHETIC DEMO')).toBeVisible();
    await expect(page.getByText('API connected')).toBeVisible();

    // 2. Product Explorer
    const productSelect = page.getByLabel('Select product');
    await expect(productSelect.locator('option')).toHaveCount(22);
    await productSelect.selectOption({ index: 1 }); // DEMO-002

    // Check backend API response
    const forecastResponse = await page.request.get('/api/forecasts/DEMO-002');
    expect(forecastResponse.ok()).toBeTruthy();
    const historyResponse = await page.request.get('/api/products/DEMO-002/history');
    expect(historyResponse.ok()).toBeTruthy();
    expect((await historyResponse.json()).items.length).toBeGreaterThan(8);

    // Verify Chart rendering
    await expect(page.locator('.recharts-line-curve').first()).toBeVisible();
    await expect(page.getByText('Forecast origin', { exact: false })).toBeVisible();

    // Toggle prediction interval
    await page.getByRole('button', { name: '90% band' }).click();
    await expect(page.getByRole('button', { name: '90% band' })).toHaveClass(/chosen/);

    // 3. Scenario Lab Simulator
    await expect(page.locator('.sim-result b').first()).not.toContainText('—');
    await expect(page.getByText('Change:', { exact: false })).toBeVisible();

    // Click One-week shock
    await page.getByRole('button', { name: 'One-week shock' }).click();
    await expect(page.locator('.sim-result b').nth(1)).not.toContainText('—');
    await expect(page.getByText('Scenario sensitivity only', { exact: false })).toBeVisible();

    // Reset to sustained shift for overview capture
    await page.getByRole('button', { name: 'Sustained shift' }).click();

    // Capture primary showcase screenshots
    await page.screenshot({ path: '../../docs/screenshots/overview.png', fullPage: true });
    await page.screenshot({ path: '../../docs/screenshots/dashboard.png', fullPage: false });
    await page.screenshot({ path: '../../docs/images/dashboard-demo.png', fullPage: true });

    // Focused capture of the Scenario Lab panel
    const simPanel = page.locator('.sim-panel');
    await simPanel.screenshot({ path: '../../docs/screenshots/feature-scenario-lab.png' });
  });

  test('navigates product catalog and inspects specific products', async ({ page }) => {
    await page.goto('/');

    // Navigate to Products view
    await page.getByRole('button', { name: 'Products' }).click();
    await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible();
    await expect(page.getByText('Product directory')).toBeVisible();

    // Verify table has products listed
    const productRows = page.locator('tbody tr');
    await expect(productRows).toHaveCount(22);

    // Capture Products catalog screenshot
    await page.screenshot({ path: '../../docs/screenshots/products.png', fullPage: true });

    // Click Inspect on DEMO-003
    const inspectBtn = productRows.nth(2).locator('.inspect-btn');
    await inspectBtn.click();

    // Verify transitioned back to Overview with DEMO-003 selected
    await expect(page.getByRole('heading', { name: 'Forecast overview' })).toBeVisible();
    const productSelect = page.getByLabel('Select product');
    await expect(productSelect).toHaveValue('DEMO-003');
  });

  test('reviews model comparison against baselines across horizons and SKUs', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: 'Model comparison' }).click();
    await expect(page.getByRole('heading', { name: 'Model comparison' })).toBeVisible();
    await expect(page.getByText('Metrics on identical forecast records')).toBeVisible();

    // Verify model comparison table shows LightGBM and baselines
    await expect(page.locator('tbody tr td').filter({ hasText: 'LightGBM' }).first()).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Trailing 4-week mean' }).first()).toBeVisible();
    await expect(page.getByText('MAE by forecast week')).toBeVisible();
    await expect(page.getByText('Product-level holdout MAE')).toBeVisible();

    await page.screenshot({ path: '../../docs/screenshots/model-comparison.png', fullPage: true });
  });

  test('inspects model reliability, feature importance, and interval coverage', async ({
    page,
  }) => {
    await page.goto('/');

    await page.getByRole('button', { name: 'Reliability' }).click();
    await expect(page.getByRole('heading', { name: 'Reliability' })).toBeVisible();
    await expect(page.getByText('Feature gain and explanations')).toBeVisible();
    await expect(page.getByText('Coverage by forecast horizon')).toBeVisible();

    // Check feature importance rankings
    await expect(page.getByText('mean 4')).toBeVisible();
    await expect(page.getByText('lag 1')).toBeVisible();

    await page.screenshot({ path: '../../docs/screenshots/reliability.png', fullPage: true });
  });

  test('audits chronological backtesting records and filters folds', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: 'Backtesting' }).click();
    await expect(page.getByRole('heading', { name: 'Backtesting' })).toBeVisible();
    await expect(page.getByText('Historical forecast records')).toBeVisible();

    // Filter by Final holdout
    const foldSelect = page.getByLabel('Backtest fold');
    await foldSelect.selectOption('final_test');

    await page.screenshot({ path: '../../docs/screenshots/backtesting.png', fullPage: true });
  });

  test('reviews data quality and ingestion audit manifest', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: 'Data quality' }).click();
    await expect(page.getByRole('heading', { name: 'Data quality' })).toBeVisible();
    await expect(page.getByText('Transaction preparation')).toBeVisible();
    await expect(page.getByText('retention pct')).toBeVisible();
    await expect(page.getByText('DATASET DOI')).toBeVisible();

    await page.screenshot({ path: '../../docs/screenshots/data-quality.png', fullPage: true });
  });

  test('captures authentic terminal CLI execution demonstration', async ({ page }) => {
    await page.goto(`file://${process.cwd()}/e2e/cli-demo.html`);
    const terminal = page.locator('.terminal');
    await expect(terminal).toBeVisible();
    await terminal.screenshot({ path: '../../docs/screenshots/cli-demo.png' });
  });
});
