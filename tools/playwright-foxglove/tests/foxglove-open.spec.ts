import { test, expect } from '@playwright/test';

/**
 * Opens Foxglove with a Foxglove WebSocket data source (foxglove_bridge).
 * Prerequisite: `ros2 run foxglove_bridge foxglove_bridge` (default :8765).
 *
 * Override URL: HERMES_FOXGLOVE_VIEW_URL=... npm run record
 */
const url =
  process.env.HERMES_FOXGLOVE_VIEW_URL ??
  'https://app.foxglove.dev/~/view?ds=foxglove-websocket&ds.url=' +
    encodeURIComponent(process.env.FOXGLOVE_WS_URL ?? 'ws://127.0.0.1:8765');

test('open Foxglove Studio with local foxglove_bridge', async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  // Allow WASM / connection attempt; extend if your machine is slow.
  await page.waitForTimeout(25_000);
  await expect(page.locator('body')).toBeVisible();
});
