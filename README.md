# Game KI Studio

ChatGPT-ähnliches KI-Game-Studio mit Groq/Gemini, Browser-Spielvorschau und Roblox Open Cloud Publishing.

## Vercel Setup

**Wichtig für das Routing:** Vercel erkennt die Flask-Anwendung automatisch anhand von `app.py`. Lass die Catch-all-`rewrites` weg; sie können dazu führen, dass Flask nur `/api/index.py` sieht und deshalb „Route nicht gefunden“ meldet. `vercel.json` bündelt die Templates mit der Funktion.

Lege in **Vercel → Project → Settings → Environment Variables** an:

- `STUDIO_ACCESS_PASSWORD` — **erforderlich**, starkes Passwort für das Studio
- `GROQ_API_KEY` — optional, wenn du Groq nutzen möchtest
- `GEMINI_API_KEY` — optional, wenn du Gemini nutzen möchtest
- Optional: `GROQ_MODEL`, `GEMINI_MODEL`

Speichere die Variablen und deploye erneut. Öffne danach die Website und trage unter **Studio-Einstellungen** das gleiche `STUDIO_ACCESS_PASSWORD` ein.

**Roblox:** API-Key, Universe-ID und Place-ID kannst du im selben Einstellungsfenster eingeben. Sie bleiben nur in der aktuellen Browser-Sitzung und werden ausschließlich an den Publish-Endpunkt geschickt — nicht an Groq/Gemini und nicht in den Projektverlauf. Alternativ kannst du `ROBLOX_API_KEY`, `ROBLOX_UNIVERSE_ID` und `ROBLOX_PLACE_ID` in Vercel setzen, damit sie serverseitig bereitstehen. Der Open-Cloud-Key braucht die Berechtigung zum Veröffentlichen von Place-Versionen für die ausgewählte Experience.

## Features

- Roblox-inspiriertes Studio-Layout mit Workspace, Live-Viewport, Explorer/Properties, Prompt-Chat, Luau-Tab und Verlauf der letzten zwölf Projekte
- Eine direkt spielbare Starter-Arena wird bereits beim Öffnen angezeigt
- Groq/Gemini generieren Luau und eine spielbare HTML-Demo
- Die HTML-Ausgabe wird geprüft; bei fehlendem Dokument wird die KI zur Reparatur aufgefordert und bei weiterem Fehler eine lokale Spiel-Demo geladen
- Das isolierte Iframe meldet JavaScript-Laufzeitfehler zurück und versucht eine einmalige automatische Reparatur; außerdem gibt es eine manuelle Schaltfläche „Demo reparieren“
- Isolierte Live-Vorschau und Code kopieren / Download
- Roblox-Code kann Server- und Client-Script-Marker enthalten; beim Open-Cloud-Publishing werden die Skripte auf `ServerScriptService` und `StarterPlayerScripts` getrennt
- Direkte Roblox Place-Veröffentlichung über Roblox Open Cloud nach bewusster Bestätigung

**Architektur:** `app.py` ist der einzige Flask-Einstiegspunkt; alle Web-Routen (`/`, `/status`, `/generate`, `/starter-game`, `/publish-generated`, `/upload`) werden von derselben Anwendung bedient. `templates/` enthält das Dashboard und das spielbare Fallback-Game.

**Wichtig:** Das direkte Publishing erstellt eine kompakte XML-Place-Datei mit einem ServerScriptService-Script. Es ersetzt die veröffentlichte Version des konfigurierten Places. Teste und prüfe KI-generierten Code vor dem Veröffentlichen; bei einer von Roblox abgelehnten Datei muss sie in Roblox Studio geöffnet und veröffentlicht werden.