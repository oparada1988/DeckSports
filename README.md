<p align="center">
  <img src="assets/banner.png" alt="DeckSports Banner" width="100%">
</p>

# DeckSports

DeckSports is a sports scoreboard and live game tracking plugin for [StreamController](https://github.com/StreamController/StreamController). It displays real-time match scores, game clocks, quarters, and team branding directly across your Stream Deck keys without needing external browser tabs or second monitors.

---

## 3-Button Scoreboard Layout

DeckSports features a 3-button modular scoreboard designed to link together horizontally across any row on your keypad:

<p align="center">
  <img src="assets/scoreboard.gif" alt="DeckSports 3-Button Scoreboard Demo" width="85%">
</p>

* **Left Button (Away Team)**: Displays the visiting team's primary color, logo watermark, live score, and record.
* **Middle Button (Game Hub & Clock)**: Displays the league logo header, current quarter / inning / period, remaining game clock, and a live possession arrow (`◀ BALL` or `BALL ▶`).
* **Right Button (Home Team)**: Displays the host team's primary color, logo watermark, live score, and record.

### Key Capabilities:
* **Automatic Row Pairing**: Simply place a Game Hub in the middle and Team Score actions to the left and right. Side buttons automatically detect and pair with the Game Hub on their row (left = Away, right = Home).
* **Multiple Game Rows**: Stack multiple matches from different leagues across rows on the same profile without conflicts.
* **Standalone 1-Button Mode**: If only a single key is used, the Game Hub automatically packs the matchup summary, team logos, and live scores into one key.
* **Post-Game Summary**: Once a game concludes, the middle button displays a bold red **FINAL** badge, leaving the final scores clearly visible on the side keys.

---

## Supported Leagues

DeckSports tracks live matchups, schedules, and scores for the following leagues:

* **NFL** (Football) — Scores, live game clock, quarters, possession arrow, down & distance
* **NBA** (Basketball) — Scores, live game clock, quarters, season records
* **MLB** (Baseball) — Scores, inning half (Top / Bottom), outs
* **MLS** (Soccer) — Scores, match minutes clock, halves
* **NHL** (Hockey) — Scores, live clock, periods
* **UFL** (Football) — Scores, live game clock, quarters, possession arrow
* **NCAA Football & Basketball** — Top 25 & Division I live matchups
* **WNBA** (Basketball) — Scores, live game clock, quarters

---

## Setup

1. Add a **Game Hub / Clock** action to any key on your deck.
2. In the action sidebar, select the **Sports League** and your **Followed Team**.
3. Add a **Team Score / Logo** action to the keys immediately to the left and right of the Game Hub.
4. The side keys will automatically sync with the Game Hub.
5. Tap any key at any time to trigger an instant score refresh.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
