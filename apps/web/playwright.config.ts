import { defineConfig, devices } from '@playwright/test';

const apiBaseUrl = 'http://127.0.0.1:8100';
const webBaseUrl = 'http://127.0.0.1:5174';

export default defineConfig({
  testDir: './e2e',
  use: { ...devices['Desktop Chrome'], baseURL: webBaseUrl },
  webServer: [
    {
      command:
        'cd ../api && RETAIL_DEMAND_FORECASTING_ARTIFACTS=../../artifacts/demo uv run uvicorn demandsense.main:app --host 127.0.0.1 --port 8100',
      url: `${apiBaseUrl}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command:
        'VITE_API_PROXY_TARGET=http://127.0.0.1:8100 pnpm dev -- --host 127.0.0.1 --port 5174 --strictPort',
      url: webBaseUrl,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
