"""Focus Tycoon - a Python/pygame version of the app.

The package layout mirrors the original structure:

    model    - game data (task, quest, game state, calendar, homework)
    service  - the Gemini task splitting and the ICS calendar import
    persist  - saving / loading (~/.focustycoon/save.json)
    portal   - the school-portal scraper (Logineo / IServ)
    tycoon   - the 2D Tycoon engine (model, simulation, juice, UI)
    ui       - the shared pygame interface (navbar + two pages)
    util     - small helpers (dotenv, Java-compatible hash, fonts)
"""
