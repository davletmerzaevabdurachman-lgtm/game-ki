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
- Groq/Gemini generieren Roblox-Server-/Client-Luau, eine spielbare HTML-Demo und eine bearbeitbare 3D-Level-Szene
- Die HTML-Ausgabe wird geprüft; bei fehlendem Dokument wird die KI zur Reparatur aufgefordert und bei weiterem Fehler eine lokale Spiel-Demo geladen
- Das isolierte Iframe meldet JavaScript-Laufzeitfehler zurück und versucht eine einmalige automatische Reparatur; außerdem gibt es eine manuelle Schaltfläche „Demo reparieren“
- Isolierte Live-Vorschau und Code kopieren / Download
- Der Generator schreibt die Level-Parts direkt in die `.rbxlx`-Place-Datei; sie sind schon im Roblox-Studio-Edit-Modus sichtbar. Server- und Client-Scripts landen getrennt in `ServerScriptService` und `StarterPlayerScripts`
- Roblox-Live-Tab mit den offiziellen öffentlichen Experience-Daten, Spielerzahlen, Besuchen, Thumbnail und Direktlink zur echten Roblox-Experience
- Direkte Roblox-Place-Veröffentlichung über Open Cloud nach bewusster Bestätigung

**Architektur:** `app.py` ist der einzige Flask-Einstiegspunkt; alle Web-Routen (`/`, `/status`, `/generate`, `/starter-game`, `/roblox-preview`, `/publish-generated`, `/upload`) werden von derselben Anwendung bedient. `templates/` enthält das Dashboard und das spielbare Fallback-Game.

**Wichtig:** Open Cloud veröffentlicht eine komplette XML-Place-Datei mit einer bearbeitbaren Blockout-Level-Geometrie plus Server- und Client-Scripts. Das ersetzt den Inhalt der ausgewählten Place-Version; deshalb erst in einem Test-Place prüfen. Die Browseransicht kann den nativen Roblox-3D-Player nicht in ein fremdes Website-iframe einbetten. Der Roblox-Live-Tab zeigt die offizielle Experience-Vorschau und öffnet bei Bedarf den echten Roblox-Player. KI-generierte Scripts immer testen, denn automatisches Hochladen allein garantiert keine fehlerfreie Spielmechanik.