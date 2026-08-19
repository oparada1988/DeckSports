# DeckSports

DeckSports is a sports scoreboard and live game tracking plugin for StreamController.

I created this plugin so I could keep an eye on my favorite teams and live scores directly from my Stream Deck while working or gaming, without needing to keep a browser tab open.

Note: This plugin is currently in early initial development. Core features, API connectors, and UI components are actively being built and refined.

## Planned Features

- 3-Button Game Hub Layout:
  - Left Key: Team A (team logo, colors, record, and live score)
  - Middle Key: Master coordinator and clock. Lets you select which team schedule to follow. Shows the upcoming game date and start time when off-game, and switches to the live game clock plus a possession indicator arrow (pointing to whoever has the ball) during game time.
  - Right Key: Team B (opponent logo, colors, record, and live score)
- Standalone Actions: Options to drop individual score tiles or a simple game clock onto single keys anywhere on your layout.
- Clean Key Graphics: Text, scores, and team colors are drawn directly onto the key images using Pillow, keeping everything legible and preventing accidental label overrides in the StreamController UI.
- Low-Overhead Polling: Centralized background service so multiple buttons on your deck share the same live data without spamming sports APIs.

## Target Leagues

- NFL
- NBA
- MLB
- MLS
- UFL
- NHL
- NCAA Football & Basketball
- WNBA

## Project Structure

```text
DeckSports/
├── manifest.json            # StreamController plugin manifest
├── main.py                  # Plugin entry point and action registration
├── actions/
│   ├── GameHubAction.py     # Main coordinator: team picker, clock, and possession
│   ├── ScoreAction.py       # Live score and team graphics
│   └── TimeLeftAction.py    # Game clock and period tracker
├── backend/
│   └── SportsService.py     # API data fetching and cache manager
└── assets/                  # Team icons and default artwork
```

## Installation

To test or develop locally, clone this repository into your StreamController plugins directory:

```bash
git clone https://github.com/oparada1988/DeckSports.git ~/.var/app/com.core447.StreamController/data/StreamController/plugins/DeckSports
```

Restart StreamController, and you will find DeckSports in the action list.

## Feedback and Contributions

Since this project is in its early stages, suggestions, feature ideas, and pull requests are very welcome. Feel free to open an issue or start a discussion on GitHub.

## License

MIT License
