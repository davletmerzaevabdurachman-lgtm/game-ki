# Game KI Studio

ChatGPT-ähnliches KI-Game-Studio mit Groq/Gemini, Browser-Spielvorschau und Roblox Open Cloud Publishing.

## Vercel Setup

Lege in **Vercel → Project → Settings → Environment Variables** an:

- `STUDIO_ACCESS_PASSWORD` — starkes Passwort für das Studio
- `GROQ_API_KEY` — optional, falls du Groq nutzen möchtest
- `GEMINI_API_KEY` — optional, falls du Gemini nutzen möchtest
- `ROBLOX_API_KEY` — Open Cloud API Key mit `universe-places` Write-Recht
- `ROBLOX_UNIVERSE_ID` — Universe ID deiner Experience
- `ROBLOX_PLACE_ID` — Place ID, die veröffentlicht werden soll
- Optional: `GROQ_MODEL`, `GEMINI_MODEL`

Danach in Vercel deployen und in den Website-Einstellungen das `STUDIO_ACCESS_PASSWORD` für diese Browser-Sitzung eingeben. Provider- und Roblox-Schlüssel werden serverseitig gelesen, nicht im Browser eingegeben oder gespeichert.

## Features

- Neue Chat-Sitzungen und lokaler Verlauf der letzten sechs Projekte
- Groq/Gemini generieren Luau und eine spielbare HTML-Demo
- Isolierte Live-Vorschau und Code kopieren / Download
- Direkte Roblox Place-Veröffentlichung aus dem generierten Luau über Roblox Open Cloud, nach bewusster Bestätigung

**Wichtig:** Das direkte Publishing erstellt eine kompakte XML-Place-Datei mit einem ServerScriptService-Script. Es ersetzt die veröffentlichte Version des konfigurierten Places. Teste und prüfe KI-generierten Code vor dem Veröffentlichen; bei einer von Roblox abgelehnten Datei muss sie in Roblox Studio geöffnet und veröffentlicht werden.