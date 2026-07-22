"""Very small translation helper.

The app is written in English. A dropdown at the top lets the user switch
between German (the default) and English. Every visible label goes through
translate(key). If a key is missing we simply show the key itself, so nothing
ever crashes because of a typo.

To add a language later, add another entry to TRANSLATIONS.
"""

from __future__ import annotations

# The language that is currently shown. German is the default.
_current_language = "de"

# The languages the dropdown offers, in order.
AVAILABLE_LANGUAGES = [("en", "English"), ("de", "Deutsch")]

TRANSLATIONS = {
    "en": {
        # navigation
        "nav_tasks": "Tasks",
        "nav_tycoon": "Tycoon",
        "gold_suffix": "Gold",
        "tutorial": "Tutorial",
        "language": "Language",
        # Sound toggle button in the navbar.
        "sound_on": "Sound: On",
        "sound_off": "Sound: Off",
        # composer
        "plan_new_task": "Plan a new task",
        "composer_subtitle": "Type a big task and let it be split into doable steps.",
        "title_label": "Title",
        "title_placeholder": "Title of the task ...",
        "break_into_steps": "Break into steps",
        "description_label": "Description & context for the AI (optional)",
        "description_placeholder": "Details, goal, constraints ...",
        "split_label": "How much to split",
        "split_none": "Do not split (1 task)",
        "split_fine": "Fine",
        "split_medium": "Medium",
        "split_coarse": "Coarse",
        "submit": "Submit",
        "estimated_time_label": "Estimated time (minutes, optional)",
        "estimated_time_placeholder": "e.g. 45",
        "ai_estimate": "AI estimate",
        "what_first": "What should I do first?",
        "reset_all": "Reset all data",
        "import_calendar": "Import from calendar (.ics)",
        "connect_portal": "Connect portal",
        "sync_portal": "Sync portal",
        # lists
        "to_do": "To do",
        "done": "Done",
        "no_open_quests": "No open quests yet. Type a big task above and split it into steps.",
        "nothing_done": "Nothing finished yet. A fully finished section shows up here.",
        "recommended": "RECOMMENDED",
        "completed_short": "✓ Done",
        "done_button": "Done",
        "finished_badge": "FINISHED",
        "steps_done_earned": "{count} steps finished  ·  +{gold} gold earned",
        "portal_homework": "PORTAL HOMEWORK",
        "split_button": "Split up",
        "due": "due {date}",
        "meta_line": "Split: {level}   ·   {minutes} min   ·   +{gold} gold",
        # Same line, but for steps that have no estimated time at all.
        "meta_line_no_time": "Split: {level}   ·   +{gold} gold",
        # dialogs
        "cancel": "Cancel",
        "confirm": "Confirm",
        "connect": "Connect",
        "reset_title": "Reset data",
        "reset_confirm": "Really delete ALL data?",
        "reset_warning1": "Gold, tasks and the whole Tycoon progress will be",
        "reset_warning2": "reset for good. This cannot be undone.",
        "portal_school_url": "School URL",
        "portal_username": "Username",
        "portal_password": "Password",
        "portal_logineo_url": "Logineo URL",
        "portal_iserv_url": "IServ URL",
        "portal_hint": "One login for both portals - it uses the same username and password.",
        "calendar_source_label": "File path or subscription URL",
        "calendar_source_placeholder": "Path to a .ics file OR a webcal:// / https:// URL",
        "connect_portal_title": "Connect school portal",
        "import_calendar_title": "Import calendar",
    },
    "de": {
        "nav_tasks": "Aufgaben",
        "nav_tycoon": "Tycoon",
        "gold_suffix": "Gold",
        "tutorial": "Anleitung",
        "language": "Sprache",
        # Sound toggle button in the navbar.
        "sound_on": "Ton: An",
        "sound_off": "Ton: Aus",
        "plan_new_task": "Neue Aufgabe planen",
        "composer_subtitle": "Gib eine grosse Aufgabe ein und lass sie in Schritte zerlegen.",
        "title_label": "Titel",
        "title_placeholder": "Titel der Aufgabe ...",
        "break_into_steps": "In Schritte zerlegen",
        "description_label": "Beschreibung & Kontext fuer die KI (optional)",
        "description_placeholder": "Details, Ziel, Randbedingungen ...",
        "split_label": "Wie stark zerteilen",
        "split_none": "Nicht zerteilen (1 Aufgabe)",
        "split_fine": "Fein",
        "split_medium": "Mittel",
        "split_coarse": "Grob",
        "submit": "Absenden",
        "estimated_time_label": "Geschaetzte Zeit (Minuten, optional)",
        "estimated_time_placeholder": "z. B. 45",
        "ai_estimate": "KI schaetzen",
        "what_first": "Was mache ich zuerst?",
        "reset_all": "Alle Daten zuruecksetzen",
        "import_calendar": "Aus Kalender importieren (.ics)",
        "connect_portal": "Portal verbinden",
        "sync_portal": "Portal synchronisieren",
        "to_do": "Zu erledigen",
        "done": "Erledigt",
        "no_open_quests": "Noch keine offenen Quests. Gib oben eine grosse Aufgabe ein und lass sie zerlegen.",
        "nothing_done": "Noch nichts abgeschlossen. Ein komplett erledigter Abschnitt landet hier.",
        "recommended": "EMPFOHLEN",
        "completed_short": "✓ Erledigt",
        "done_button": "Erledigt",
        "finished_badge": "ABGESCHLOSSEN",
        "steps_done_earned": "{count} Schritte abgeschlossen  ·  +{gold} Gold verdient",
        "portal_homework": "PORTAL-HAUSAUFGABE",
        "split_button": "Aufteilen",
        "due": "faellig {date}",
        "meta_line": "Zerteilung: {level}   ·   {minutes} Min   ·   +{gold} Gold",
        # Same line, but for steps that have no estimated time at all.
        "meta_line_no_time": "Zerteilung: {level}   ·   +{gold} Gold",
        "cancel": "Abbrechen",
        "confirm": "Bestaetigen",
        "connect": "Verbinden",
        "reset_title": "Daten zuruecksetzen",
        "reset_confirm": "Wirklich ALLE Daten loeschen?",
        "reset_warning1": "Gold, Aufgaben und der komplette Tycoon-Fortschritt werden",
        "reset_warning2": "unwiderruflich zurueckgesetzt. Das kann nicht rueckgaengig gemacht werden.",
        "portal_school_url": "Schul-URL",
        "portal_username": "Benutzername",
        "portal_password": "Passwort",
        "portal_logineo_url": "Logineo-URL",
        "portal_iserv_url": "IServ-URL",
        "portal_hint": "Eine Anmeldung fuer beide Portale - gleicher Benutzername und gleiches Passwort.",
        "calendar_source_label": "Dateipfad oder Abo-URL",
        "calendar_source_placeholder": "Pfad zu einer .ics-Datei ODER eine webcal:// / https:// URL",
        "connect_portal_title": "Schul-Portal verbinden",
        "import_calendar_title": "Kalender importieren",
    },
}


# The tutorial is a list of pages. Each page has a title and a list of text lines.
TUTORIAL_PAGES = {
    "en": [
        {"title": "Welcome to Focus Tycoon",
         "lines": [
             "Focus Tycoon turns your real tasks into a game.",
             "",
             "1. On the TASKS page you type a big task.",
             "2. The AI splits it into small, doable steps.",
             "3. Finishing a step gives you GOLD.",
             "4. On the TYCOON page you spend that gold to grow",
             "   a world of floating islands.",
             "",
             "Use the arrows below to page through this guide.",
         ]},
        {"title": "The Tasks page",
         "lines": [
             "- Type a short title, and optionally a longer description.",
             "- Choose how much to split the task:",
             "    Do not split = keep it as one task",
             "    Fine   = many tiny steps",
             "    Medium = a few balanced steps",
             "    Coarse = few big chunks",
             "- Press Submit to let the AI break it down.",
             "- Tick 'Done' on a step to earn gold.",
             "- 'What should I do first?' picks the quickest step.",
         ]},
        {"title": "The Tycoon page",
         "lines": [
             "- Click a producer's disc to CHEER it: this costs gold,",
             "  fills its tank and it produces resources for a while.",
             "- Click the button under a producer to UPGRADE it.",
             "  Upgrades cost resources (never gold).",
             "- Click a locked island to unlock it with gold.",
             "",
             "Gold is shared with the Tasks page, so finishing tasks",
             "is the only way to power your Tycoon.",
         ]},
        {"title": "AI key (needed for splitting)",
         "lines": [
             "The AI needs a free Google Gemini key.",
             "",
             "1. Get a key at aistudio.google.com/app/apikey",
             "2. Copy the file '.env.example' to '.env'.",
             "3. Open '.env' and put your key after GEMINI_API_KEY=",
             "",
             "The '.env' file stays on your computer and is never",
             "uploaded. Without a key, splitting shows an error.",
             "",
             "Alternative: set GEMINI_API_KEY as a normal system/user",
             "environment variable instead - it works without any file",
             "and always takes priority over '.env'.",
         ]},
        {"title": "Optional: school portal",
         "lines": [
             "To import homework from Logineo NRW or IServ:",
             "",
             "1. Copy 'portal.env.example' to 'portal.env' (or put it",
             "   in your home folder under .focustycoon).",
             "2. Set PORTAL_ENCRYPTION_KEY to a long random text.",
             "3. In the app press 'Connect portal', fill in your",
             "   username, password and the school URL(s).",
             "",
             "One login covers both portals. Your password is stored",
             "only in encrypted form.",
         ]},
    ],
    "de": [
        {"title": "Willkommen bei Focus Tycoon",
         "lines": [
             "Focus Tycoon macht aus deinen echten Aufgaben ein Spiel.",
             "",
             "1. Auf der Seite AUFGABEN gibst du eine grosse Aufgabe ein.",
             "2. Die KI zerlegt sie in kleine, machbare Schritte.",
             "3. Ein erledigter Schritt bringt dir GOLD.",
             "4. Auf der Seite TYCOON gibst du das Gold aus, um eine",
             "   Welt aus schwebenden Inseln aufzubauen.",
             "",
             "Mit den Pfeilen unten blaetterst du durch die Anleitung.",
         ]},
        {"title": "Die Aufgaben-Seite",
         "lines": [
             "- Gib einen kurzen Titel und optional eine Beschreibung ein.",
             "- Waehle, wie stark die Aufgabe zerteilt wird:",
             "    Nicht zerteilen = eine einzige Aufgabe",
             "    Fein   = viele winzige Schritte",
             "    Mittel = wenige ausgewogene Schritte",
             "    Grob   = wenige grosse Bloecke",
             "- Druecke Absenden, damit die KI zerlegt.",
             "- Hake 'Erledigt' an einem Schritt ab, um Gold zu verdienen.",
             "- 'Was mache ich zuerst?' waehlt den schnellsten Schritt.",
         ]},
        {"title": "Die Tycoon-Seite",
         "lines": [
             "- Klick auf die Scheibe eines Produktors, um ihn ANZUFEUERN:",
             "  das kostet Gold, fuellt den Tank und er produziert eine Weile.",
             "- Klick auf den Button unter einem Produktor zum AUSBAUEN.",
             "  Ausbauen kostet Ressourcen (nie Gold).",
             "- Klick auf eine gesperrte Insel, um sie mit Gold freizuschalten.",
             "",
             "Gold ist mit der Aufgaben-Seite geteilt - nur erledigte",
             "Aufgaben treiben deinen Tycoon an.",
         ]},
        {"title": "KI-Schluessel (fuer das Zerlegen noetig)",
         "lines": [
             "Die KI braucht einen kostenlosen Google-Gemini-Schluessel.",
             "",
             "1. Hol dir einen Schluessel: aistudio.google.com/app/apikey",
             "2. Kopiere die Datei '.env.example' zu '.env'.",
             "3. Oeffne '.env' und schreibe deinen Schluessel hinter",
             "   GEMINI_API_KEY=",
             "",
             "Die '.env'-Datei bleibt auf deinem Rechner und wird nie",
             "hochgeladen. Ohne Schluessel zeigt das Zerlegen einen Fehler.",
             "",
             "Alternative: Setze GEMINI_API_KEY als normale System-/",
             "Benutzer-Umgebungsvariable - dann brauchst du keine Datei,",
             "und sie hat immer Vorrang vor der '.env'.",
         ]},
        {"title": "Optional: Schul-Portal",
         "lines": [
             "Um Hausaufgaben aus Logineo NRW oder IServ zu importieren:",
             "",
             "1. Kopiere 'portal.env.example' zu 'portal.env' (oder lege",
             "   es im Home-Ordner unter .focustycoon ab).",
             "2. Setze PORTAL_ENCRYPTION_KEY auf einen langen Zufallstext.",
             "3. Druecke in der App 'Portal verbinden' und trage",
             "   Benutzername, Passwort und die Schul-URL(s) ein.",
             "",
             "Eine Anmeldung deckt beide Portale ab. Dein Passwort wird",
             "nur verschluesselt gespeichert.",
         ]},
    ],
}


def get_tutorial_pages():
    return TUTORIAL_PAGES.get(_current_language, TUTORIAL_PAGES["en"])


def set_language(language_code):
    global _current_language
    if language_code in TRANSLATIONS:
        _current_language = language_code


def get_language():
    return _current_language


def translate(key):
    table = TRANSLATIONS.get(_current_language, TRANSLATIONS["en"])
    if key in table:
        return table[key]
    # Fall back to English, then to the key itself.
    return TRANSLATIONS["en"].get(key, key)
