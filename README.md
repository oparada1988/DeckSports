<p align="center">
  <img src="assets/banner.png" alt="DeckSports Banner" width="100%">
</p>

<p align="center">
  <strong>The Ultimate Real-Time Sports Scoreboard & Match Hub for StreamController</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/StreamController-1.5.0%2B-blueviolet?style=flat-square" alt="StreamController">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Version-1.0.0-orange?style=flat-square" alt="Version">
</p>

---

## 📖 Overview

**DeckSports** brings live sports scoreboards, game clocks, possession tracking, and team branding directly to your Stream Deck keypad using **StreamController**. Whether you are working, gaming, or streaming, track your favorite teams across all major sports leagues in real time without needing an open browser tab or second monitor.

<p align="center">
  <img src="assets/scoreboard.gif" alt="DeckSports Live Scoreboard Demo" width="90%">
</p>

---

## ✨ Key Highlights & Features

### 🏆 3-Button True Scoreboard Layout
Transform 3 adjacent Stream Deck keys into an authentic broadcast scoreboard:
* **Left Key (Team A / Away)**: Visiting team primary color banner, watermark team crest, 34px bold live score, and season record.
* **Middle Key (Game Hub / Master Clock)**: League logo header, period/quarter (`Q4`, `Top 9th`), game clock (`04:12`), and dynamic possession indicator (`◀ BALL` / `BALL ▶`).
* **Right Key (Team B / Home)**: Host team primary color banner, watermark team crest, 34px bold live score, and season record.

### 🔄 Smart Auto-Pairing & Row Isolation
* **Zero Configuration Linking**: Team Score actions automatically identify the Game Hub on their **same row (`my_y == hub_y`)**. Placing a score tile to the left of a hub tracks the Away team; placing one to the right tracks the Home team.
* **Stacked Multi-Sport Layouts**: Create multi-sport dashboards simultaneously (e.g., Row 1 for NFL, Row 2 for NBA, Row 3 for MLB) with zero cross-talk or manual key ID linking.

### 🔴 Adaptive Standalone vs. 3-Button Mode
* **3-Button Mode**: Post-game Game Hub displays a bold, clean red **`FINAL`** (or `FINAL / OT`), allowing the left and right keys to display the final scores without redundant clutter.
* **1-Button Standalone Mode**: When used as a single key without satellite score keys, the Game Hub automatically packs the final scores, mini team logos, and matchup summary into an all-in-one compact badge.

### ⚡ Ultra-Low Latency & Zero Lag Architecture
* **Shared League Scoreboard Caching**: ESPN scoreboard API responses are cached per league. If you follow 3 different NFL games on your deck, DeckSports fetches the NFL scoreboard **once** and updates all 3 matches concurrently.
* **Non-Blocking Image Caching**: Team logos and league emblems are downloaded asynchronously in the background and cached locally to disk (`~/.cache/DeckSports/logos/`).
* **Hardware Canvas Rendering**: All numbers, logos, and colored header banners are composited directly into bitmap key buffers with Pillow and bundled TrueType fonts, ensuring high contrast and zero UI label clipping.

---

## 🏟️ Supported Leagues

| League | Name | Data / Clocks |
| :---: | :--- | :--- |
| **NFL** | National Football League | Scores, Q1–Q4 / OT, Live Game Clock, Possession, Down & Distance |
| **NBA** | National Basketball Association | Scores, Q1–Q4 / OT, Game Clock, Records |
| **MLB** | Major League Baseball | Scores, Top/Bottom Inning, Outs & Inning State |
| **MLS** | Major League Soccer | Scores, 1st/2nd Half, Match Minutes Clock |
| **NHL** | National Hockey League | Scores, P1–P3 / OT / SO, Clock |
| **UFL** | United Football League | Scores, Quarters, Game Clock, Possession |
| **NCAA FB** | College Football | Top 25 & Division I Live Match Scores |
| **NCAA MBB** | Men's College Basketball | Top 25 & Division I Live Match Scores |
| **WNBA** | Women's National Basketball | Scores, Quarters, Game Clock, Records |

---

## 🎮 Included Actions

### 1. `Game Hub / Clock`
* **Purpose**: Master schedule tracker, game clock, and coordinator.
* **Configuration**:
  * **Sports League**: Choose between NFL, NBA, MLB, MLS, NHL, UFL, NCAA FB, NCAA MBB, WNBA.
  * **Main / Followed Team**: Select your followed team from an auto-populated searchable list.
  * **Live Refresh Rate**: Choose Adaptive (15s live / 10m off), 10s Fast, 15s Standard, 30s, or 60s.
  * **Scoreboard Alignment**: Away Left / Home Right (Broadcast standard) or Always Followed Team on Left.
* **Press Action**: Instant forced refresh.

### 2. `Team Score / Logo`
* **Purpose**: Displays the team's live score, high-resolution logo watermark, season record, and official color bar.
* **Configuration**:
  * **Team Slot / Side**: `Auto (Sync with nearest Game Hub on row: Left=Away, Right=Home)`, `Team A / Away`, or `Team B / Home`.
* **Press Action**: Instant forced refresh of the paired game.

---

## 📥 Installation

### Option 1: Via StreamController Store (Recommended)
1. Open **StreamController**.
2. Navigate to the **Store** page.
3. Search for **DeckSports** and click **Install**.

### Option 2: Via Custom Plugin URL
1. In StreamController, open **Store ➔ Install Custom Plugin**.
2. Enter the repository URL:
   ```text
   https://github.com/oparada1988/DeckSports
   ```
3. Click **Install** and restart StreamController.

### Option 3: Manual Installation (Development)
Clone this repository directly into your StreamController plugins directory:

```bash
git clone https://github.com/oparada1988/DeckSports.git ~/.var/app/com.core447.StreamController/data/plugins/com_oparada1988_DeckSports
```

---

## 📂 Project Structure

```text
DeckSports/
├── manifest.json                        # StreamController plugin manifest
├── main.py                              # Plugin entry point & action registrations
├── actions/
│   ├── GameHubAction/
│   │   └── GameHubAction.py             # Master coordinator, clock, and possession
│   └── TeamScoreAction/
│       └── TeamScoreAction.py           # Live team score, logo, and record badge
├── backend/
│   ├── Leagues.py                       # League configurations and ESPN API slugs
│   └── SportsService.py                 # Multi-instance caching & ESPN data engine
├── assets/
│   ├── banner.png                       # High-resolution store banner (1000x360)
│   ├── scoreboard.gif                   # Showcase animation for documentation
│   ├── info.png                         # Plugin icon
│   └── fonts/
│       └── ScoreFont-Bold.ttf           # Bundled high-contrast TrueType font
└── locales/
    └── en_US.json                       # English localization dictionary
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/oparada1988/DeckSports/issues) if you want to contribute.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
