import { test, expect } from '@playwright/test';

/**
 * Opens Foxglove Studio or Lichtblick with a Foxglove WebSocket data source (foxglove_bridge).
 * Prerequisite: `ros2 run foxglove_bridge foxglove_bridge` (default :8765).
 *
 * - Full URL override: HERMES_STUDIO_VIEW_URL or HERMES_FOXGLOVE_VIEW_URL
 * - Backend: HERMES_VIZ_BACKEND=foxglove | lichtblick (default foxglove)
 * - WebSocket: FOXGLOVE_WS_URL (default ws://127.0.0.1:8765)
 */
const wsEncoded = encodeURIComponent(process.env.FOXGLOVE_WS_URL ?? 'ws://127.0.0.1:8765');

function defaultStudioUrl(): string {
  const backend = (process.env.HERMES_VIZ_BACKEND ?? 'foxglove').toLowerCase();
  if (backend === 'lichtblick') {
    // GitHub Pages は `~/view` が 404 になるため、ルートにクエリを付ける。
    return `https://lichtblick-suite.github.io/lichtblick/?ds=foxglove-websocket&ds.url=${wsEncoded}`;
  }
  return `https://app.foxglove.dev/~/view?ds=foxglove-websocket&ds.url=${wsEncoded}`;
}

const url =
  process.env.HERMES_STUDIO_VIEW_URL ??
  process.env.HERMES_FOXGLOVE_VIEW_URL ??
  defaultStudioUrl();

test('open studio (Foxglove or Lichtblick) with local foxglove_bridge', async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  // Allow WASM / connection attempt; extend if your machine is slow.
  await page.waitForTimeout(25_000);
  await expect(page.locator('body')).toBeVisible();
});
