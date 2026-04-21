import { test, expect } from '@playwright/test';

/**
 * Opens Foxglove Studio or Lichtblick with a Foxglove WebSocket data source (foxglove_bridge).
 * Prerequisite: `ros2 run foxglove_bridge foxglove_bridge` (default :8765).
 *
 * - Full URL override: HERMES_STUDIO_VIEW_URL or HERMES_FOXGLOVE_VIEW_URL
 * - Backend: HERMES_VIZ_BACKEND=foxglove | lichtblick (default foxglove)
 * - WebSocket: FOXGLOVE_WS_URL (default ws://127.0.0.1:8765)
 * - Saved layout (share link の layoutId): HERMES_LAYOUT_ID or HERMES_STUDIO_LAYOUT_ID
 * - Hold after load (ms): HERMES_RECORD_MS (default 25000)
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

function withLayoutId(url: string): string {
  const layoutId =
    process.env.HERMES_LAYOUT_ID?.trim() ||
    process.env.HERMES_STUDIO_LAYOUT_ID?.trim();
  if (!layoutId) return url;
  const u = new URL(url);
  u.searchParams.set('layoutId', layoutId);
  return u.toString();
}

const recordMs = Math.min(
  120_000,
  Math.max(5_000, Number(process.env.HERMES_RECORD_MS ?? 25_000) || 25_000),
);

const url = withLayoutId(
  process.env.HERMES_STUDIO_VIEW_URL ??
    process.env.HERMES_FOXGLOVE_VIEW_URL ??
    defaultStudioUrl(),
);

test('open studio (Foxglove or Lichtblick) with local foxglove_bridge', async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  // Allow WASM / connection attempt; extend if your machine is slow.
  await page.waitForTimeout(recordMs);
  await expect(page.locator('body')).toBeVisible();
});
