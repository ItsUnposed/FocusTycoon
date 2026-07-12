# Focus Tycoon — Python / pygame

Turn your real tasks into a game. On the **Tasks** page you type a big task and the
AI (Google Gemini) splits it into small steps by how much you want to split it;
finishing a step earns **gold**. On the **Tycoon** page you spend that same gold to
grow a world of floating islands.

The app defaults to **German**, with a **language dropdown (Deutsch / English)** at the
top to switch. The source code itself is always written in English (see `CLAUDE.md`).

## Start

Easiest: double-click **`start.bat`** (Windows). It installs the dependencies on the
first run and opens the game.

Manually:

```bat
pip install -r requirements.txt
python run.py
```

Console demo of the split-level weighting (no window):

```bat
python run.py demo
```

## AI key (required for splitting)

There is **no offline fallback** any more: the app always uses the real AI. If it
cannot be reached it retries for one minute and then shows a clear error.

Set a free Google Gemini key so splitting works:

1. Get a key at <https://aistudio.google.com/app/apikey>.
2. Copy `.env.example` to `.env`.
3. Put your key after `GEMINI_API_KEY=` in `.env`.

`.env` stays on your computer and is git-ignored, so no key ends up on GitHub.

## Controls

- **Navbar:** switch between *Tasks* and *Tycoon*, open the **Tutorial**, pick the
  **language**.
- **Tasks:** type a title (+ optional description), choose **How much to split**
  (*Do not split (1 task)* / *Fine* / *Medium* / *Coarse*) and press **Submit**
  ("Break into steps"). Tick *Done* on a step to earn gold.
- **Tycoon:** click a producer's disc to **cheer** it (costs gold, fills the tank).
  Click the button below a producer to **upgrade** it (costs resources, never gold).
  Click a locked island to unlock it (costs gold).
- **F11** toggles fullscreen; the window is resizable; **Esc** closes a dialog or
  leaves fullscreen; a scrollbar (or the mouse wheel) scrolls the tasks page.

## School portal (Logineo NRW / IServ)

Optional. Homework from the portal shows up as a "portal homework" card that you can
split on demand. **One login covers both portals** (same username and password, two
URLs). Passwords are stored only in encrypted form (AES-256-GCM).

1. Copy `portal.env.example` to `portal.env` (or put it in `~/.focustycoon/`).
2. Set `PORTAL_ENCRYPTION_KEY` to a long random string.
3. In the app press **Connect portal**, fill in the username, password and the
   Logineo and/or IServ URL, then **Sync portal**.

## Balancing

The economy is tuned so that fully maxing out the Tycoon takes about **50 to 100
days** of active play at 1–2 finished tasks per day. Cheering is expensive and the
tank burns slowly; upgrades cost produced resources. Producers only ever spend
resources on an **upgrade** — starting or cheering a producer never removes resources.

## Layout

| Folder | Contents |
|--------|----------|
| `model/` | Task, Quest, GameState, calendar / homework data |
| `service/` | Gemini task splitting, ICS calendar import |
| `persist/` | Saving / loading |
| `portal/` | School-portal scraper (Logineo / IServ), encrypted credentials |
| `tycoon/` | Tycoon engine (model, simulation, juice) + the pygame map / HUD |
| `ui/` | Navbar + tasks page + embedded Tycoon page |
| `util/` | .env reader, Java-compatible hash, fonts |
| `i18n.py` | English / German text and the tutorial pages |

## Roadmap

Planned work and known rough edges are tracked in [`TODO.md`](TODO.md).

## Notes

- Tested with **Python 3.14**, which uses `pygame-ce` (same API as `pygame`, but it
  has wheels for new Python versions). The portal needs `cryptography`.
- The code style rules (English code, no decorators, no `lambda`, descriptive names,
  generous comments) are written down in [`CLAUDE.md`](CLAUDE.md).
