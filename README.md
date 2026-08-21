<p align="center">
  <img src="assets/banner.png" alt="DeckSports Banner" width="100%">
</p>

# DeckSports for StreamController

DeckSports is a live sports scoreboard and interactive game tracking plugin for [StreamController](https://github.com/StreamController/StreamController). It delivers real-time scores, game clocks, player leader headshots, situational radars, head-to-head stat comparisons, quarter-by-quarter line scores, official TV broadcast logos, and multi-key scoring celebration animations directly to your Stream Deck keypad without requiring extra browser windows or second monitors.

This plugin was created in collaboration with [Mattdubs9699](https://github.com/Mattdubs9699). Special thanks for contributing to the architecture, visual design concepts, and sports API workflow integrations.

---

## Key Features

* **Modular 3-Button Scoreboard**: Combines three adjacent keys into a single horizontal scoreboard (Visiting Team | Master Game Clock | Host Team).
* **Multi-Key Scoring Celebration Engine**: Full-row dynamic animated celebrations across your Stream Deck keypad for touchdowns, field goals, home runs, goals, and slam dunks.
* **Full-Screen Interactive Game Hub**: One-tap access to an in-depth game dashboard displaying live player leaders, situational radars, quarter-by-quarter line scores, and head-to-head team stats.
* **Hardware-Aware Auto-Provisioning**: Detects connected Stream Deck models (Stream Deck XL with 32 keys or Stream Deck MK.2 with 15 keys) and provisions 100% unique, pre-configured dashboard pages automatically.
* **Dynamic Match Synchronization**: Tapping any team's Game Hub key dynamically binds all dashboard tiles to that exact matchup in real time.
* **Player Leader Cards with 3-Second Hero Peek**: Displays compact athlete headshots, names, jersey numbers, and live in-game metrics with an on-demand 3-second enlarged portrait zoom on tap.
* **Official TV Broadcast Network Logos**: Dedicated broadcast tile featuring transparent high-contrast logos for 25 major networks (ESPN, FOX, CBS, NBC, ABC, TNT, TBS, Prime Video, Apple TV+, Peacock, and more).
* **Situational Radar**: Real-time Down and Distance, Ball Spot, Red Zone alerts, Count and Outs, Occupied Bases diamonds, and Hockey Power Play timers.
* **Head-to-Head Comparisons**: Compare Total Yards, 3rd Down Efficiency, Turnovers, Fouls, Time of Possession, Standings, and Next Match schedules.
* **Optimized Performance**: In-memory font caching and non-blocking asynchronous rendering deliver instant page transitions.

---

## 3-Button Scoreboard

DeckSports is designed to link three keys across any row on your keypad:

<p align="center">
  <img src="assets/scoreboard.gif" alt="DeckSports 3-Button Scoreboard Demo" width="85%">
</p>

* **Left Key (Visiting Team)**: Displays team branding, primary colors, live score, and record.
* **Center Key (Master Clock)**: Displays the league logo, game period, remaining clock, and possession arrow. Tapping this key opens the full-screen Game Hub dashboard.
* **Right Key (Host Team)**: Displays team branding, primary colors, live score, and record.

### Key Capabilities
* **Automatic Row Pairing**: Place the Game Hub action in the middle and Team Score actions to the left and right. The side keys automatically pair with the center hub on the same row.
* **Multiple Game Rows**: Track multiple matches from different leagues across different rows on the same profile.
* **Standalone 1-Button Mode**: When used on a single key, the Game Hub packs the matchup summary, team logos, and live score into one button.
* **Final Game Status**: When a game concludes, the center button shows a Final badge while preserving the final scores on the side keys.

---

## Multi-Key Scoring Celebrations

DeckSports includes a built-in celebration manager that renders high-contrast, multi-key animations whenever a team scores:

* **Touchdowns**: Dynamic gradient team color sweeps with endcap team logos, scorer headshot portrait, yardage badge, and scoring play summary.
* **Field Goals**: Full-perspective 3D uprights animation with team logo padded stanchion, parabolic ball flight, tip strobe flashes ("IT'S GOOD!"), and distance indicators.
* **Home Runs & Grand Slams**: Diamond lighting animations, team banners, and exit velocity badges.
* **Goals & Power Plays**: Hockey and soccer goal sweeps with flashing siren lights and assist leader callouts.
* **Baskets & Slam Dunks**: Fast-break neon court sweeps with player headshots and point tallies.
* **UFL Rules Support**: Dedicated animations for 4-point mega field goals (>58 yards) with lightning effects, as well as 1, 2, and 3-point scrimmage play conversions.

---

## Full-Screen Game Hub Dashboards

Tapping the center Game Hub key opens a dedicated dashboard page pre-configured for your deck hardware. All 32 keys on the XL and 15 keys on the MK.2 are 100% unique without any duplicate tiles.

### Stream Deck XL Dashboard (32 Keys)

<p align="center">
  <img src="assets/gamehub_xl.png" alt="DeckSports Stream Deck XL Dashboard" width="90%">
</p>

* **Row 1 (Header & Scoreboard)**:
  * Key 1: `< EXIT` (Return to Main Profile)
  * Key 2: Away Full Line Score (Quarter-by-quarter breakdown)
  * Key 3: Away Team Score & Primary Logo
  * Key 4: Master Clock & Game Status Center Hub
  * Key 5: Home Team Score & Primary Logo
  * Key 6: Home Full Line Score (Quarter-by-quarter breakdown)
  * Key 7: Stadium Venue & Live Weather
  * Key 8: Official TV Broadcast Network Logo
* **Row 2 (Player Leaders & Live Play Radar)**:
  * Keys 1–3: Away Category Leaders (Passing / Points, Rushing / Rebounds, Receiving / Assists)
  * Key 4: Down and Distance / Count and Outs Radar
  * Key 5: Ball Spot / Red Zone / Base Runners Radar
  * Keys 6–8: Home Category Leaders (Passing / Points, Rushing / Rebounds, Receiving / Assists)
* **Row 3 (Head-to-Head Statistics & Scoring)**:
  * Key 1: Total Yards / Field Goal % / Hits
  * Key 2: 3rd Down Efficiency / 3-Point % / Shots on Goal
  * Key 3: Turnovers / Fouls / Penalty Minutes
  * Key 4: Time of Possession / Formations
  * Key 5: Last Scoring Play Summary
  * Key 6: League Standings & Division Race
  * Key 7: Next Upcoming Match Schedule
  * Key 8: Current Drive / Power Play Radar
* **Row 4 (Quarter Breakdown & Extra Stats)**:
  * Keys 1–4: Quarter 1, 2, 3, and 4 Period Line Scores
  * Key 5: Overtime / Extra Period Line Score
  * Key 6: Field Goals / Rebounds / Extra Stats
  * Key 7: Penalty Minutes / Free Throw % / Power Play
  * Key 8: Combined Venue, Weather, and TV Summary

---

### Stream Deck MK.2 Dashboard (15 Keys)

<p align="center">
  <img src="assets/gamehub_mk2.png" alt="DeckSports Stream Deck MK.2 Dashboard" width="70%">
</p>

* **Row 1**: Exit Button, Away Score/Logo, Centered Game Clock, Home Score/Logo, Venue / TV Broadcast Information.
* **Row 2**: Away Primary Leader, Down and Distance, Ball Spot / Red Zone, Drive Information, Home Primary Leader.
* **Row 3**: Total Yards Comparison, 3rd Down Efficiency, Last Scoring Play, Turnovers, Division Standings.

---

## Player Leader Cards with 3-Second Hero Peek

Player Leader cards provide detailed athlete tracking without screen clutter:

* **Default Resting State (Static & Compact)**:
  * Top header with team abbreviation and category in team colors (e.g. `LV PASSING`, `LAL POINTS`).
  * Circular `36x36px` athlete headshot avatar on the left.
  * Athlete name and jersey number on the right.
  * Complete live performance metrics in the footer (e.g. `166 YD 0 TD`, `32 PTS 8 AST`).
  * Completely static with zero automatic cycling to eliminate visual distraction.
* **On-Press 3-Second Hero Peek**:
  * Tapping any player key instantly displays an enlarged `54x54px` circular athlete portrait with team halo framing, gold jersey number badge, and full name.
  * Automatically reverts back to the compact resting stat card after 3.0 seconds.

---

## Supported Leagues

DeckSports features a sport-adaptive engine supporting 8 major leagues:

| League | Sport | Live Metrics Tracked |
| :--- | :--- | :--- |
| **NFL** | Football | Scores, Clock, Quarters, Possession, Down & Distance, Red Zone, Category Leaders, Total Yards, Turnovers |
| **NBA** | Basketball | Scores, Clock, Quarters/Halves, Bonus/Penalty, Points/Rebounds/Assists Leaders, Field Goal %, 3-Point % |
| **MLB** | Baseball | Scores, Innings, Count, Outs, Base Runners Diamond, Pitching/Batting Stats, Hits, Errors |
| **NHL** | Hockey | Scores, Clock, Periods, Power Play Timer, Empty Net, Goals/Assists/Saves Leaders, Shots on Goal |
| **MLS** | Soccer | Scores, Match Minutes, Halves, Stoppage Time, Cards, Goals/Assists, Possession %, Shots on Target |
| **UFL** | Football | Scores, Clock, Quarters, Possession Arrow, Down & Distance, Red Zone Alerts, 4-Point Kicks |
| **NCAA** | College Football & Basketball | Division I & Top 25 live scoreboards, tournament rankings, game clocks |
| **WNBA** | Basketball | Scores, Clock, Quarters, Category Leaders, Team Shooting % |

---

## Installation & Setup

1. **Install Plugin**: Clone or download the repository into your StreamController plugins directory:
   ```bash
   git clone https://github.com/oparada1988/DeckSports.git ~/.var/app/com.core447.StreamController/data/plugins/com_oparada1988_DeckSports
   ```
2. **Setup the 3-Button Scoreboard**:
   * Add a **Game Hub / Clock** action to any key.
   * In the settings sidebar, select your **League** and **Followed Team**.
   * Add **Team Score / Logo** actions to the keys directly to the left and right. They will pair automatically.
3. **Open the Game Hub Dashboard**:
   * Tap the center **Game Hub** key at any time to open the full-screen interactive dashboard.
   * Tap the **`< EXIT`** button on the top-left key to return to your main profile.

---

## Credits & Collaboration

* **Oscar Parada** ([@oparada1988](https://github.com/oparada1988)) — Lead Developer
* **Matt** ([@Mattdubs9699](https://github.com/Mattdubs9699)) — Co-Creator, Feature Architecture & Sports API Collaboration
* **AI Assistance** — Developed with AI pair programming assistance for architecture design, API normalization, performance optimizations, and UI assets.
* Built for the **[StreamController](https://github.com/StreamController/StreamController)** application by Core447.

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
