# Foxglove Studio × turtlesim（ブラウザで「RViz っぽく」見る）

ROS 2 公式ドキュメントでも、ブラウザ向け可視化には **Foxglove Studio** が紹介されています。

- [Visualizing ROS 2 data with Foxglove Studio (Jazzy)](https://docs.ros.org/en/jazzy/How-To-Guides/Visualizing-ROS-2-Data-With-Foxglove-Studio.html)
- [Foxglove + ROS 2](https://docs.foxglove.dev/docs/getting-started/ros2)

**注意:** これは **RViz2 の Web 版ではありません**。3D パネルで矢印マーカーを置けば近いことはできますが、turtlesim の Qt ウィンドウそのものはブラウザに出ません。

## 1. 依存インストール

```bash
sudo apt update
sudo apt install ros-jazzy-foxglove-bridge
```

## 2. Foxglove Bridge を起動

別ターミナルで:

```bash
source /opt/ros/jazzy/setup.bash
ros2 run foxglove_bridge foxglove_bridge
```

既定の WebSocket は **`ws://127.0.0.1:8765`**（ポートは launch / パラメータで変更可）。

## 3. turtlesim（＋任意で hermes）を起動

```bash
source /opt/ros/jazzy/setup.bash
source /path/to/hermes-agent-ros/install/setup.bash
ros2 run turtlesim turtlesim_node
# 例: エージェントまで動かす
# ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=mock
```

## 4. ブラウザで Studio を開く

### 手動

1. Chrome などで [https://app.foxglove.dev/](https://app.foxglove.dev/) を開く  
2. **Open connection** → **Foxglove WebSocket**  
3. URL: `ws://127.0.0.1:8765` → Open  
4. **Add panel** → **Raw Messages**（または **Plot**）で `/turtle1/pose` などを選択  

### ディープリンク（接続まで自動）

URL エンコードされた WebSocket を付けます:

```text
https://app.foxglove.dev/~/view?ds=foxglove-websocket&ds.url=ws%3A%2F%2F127.0.0.1%3A8765
```

HTTPS の Studio から `ws://127.0.0.1` へ繋がらない場合は、**Foxglove デスクトップアプリ**で同じ URL を開くか、[Shareable links](https://docs.foxglove.dev/docs/visualization/shareable-links) の `openIn=desktop` を試してください。

## 5. Playwright で画面録画（デモ動画）

[`tools/playwright-foxglove/`](../../tools/playwright-foxglove/) に最小設定があります。

**事前に** 上記のとおり **foxglove_bridge** と **turtlesim**（＋必要なら hermes）が動いていること。

```bash
cd tools/playwright-foxglove
npm install
npx playwright install chromium
npm run record
```

- 動画: `tools/playwright-foxglove/test-results/` 以下（`.webm`）
- テストは Foxglove の初期画面を数秒表示するだけです。**パネル追加は UI が変わりやすいので手動レイアウト保存**を推奨**（Foxglove の Layout を保存し `layoutId` を URL に付与 — [Shareable links](https://docs.foxglove.dev/docs/visualization/shareable-links)）。

## 代替: Rosbridge

Foxglove 公式は **foxglove_bridge 推奨**ですが、Rosbridge 経由も可能です（[ドキュメント](https://docs.ros.org/en/jazzy/How-To-Guides/Visualizing-ROS-2-Data-With-Foxglove-Studio.html)）。接続先ポートは環境に合わせて `ds.url` を変えてください。
