import os, json, re, hmac, uuid, html as html_lib
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__, template_folder=str(ROOT / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
SYSTEM = """You are Game KI Studio, a senior Roblox Luau engineer and browser-game developer.
Return exactly one JSON object with two string fields: roblox_code and web_simulation. No Markdown fences.
Both outputs must implement the user's requested game and be complete, not pseudocode or TODOs.
ROBLOX OUTPUT: roblox_code must contain TWO complete scripts in this exact format:
--[[GAME_KI_SERVER_SCRIPT]]
<complete Script source for ServerScriptService>
--[[GAME_KI_CLIENT_SCRIPT]]
<complete LocalScript source for StarterPlayer > StarterPlayerScripts>
The server script creates the world, spawn, objectives and server-owned game state. The client script creates player HUD/controls and sends requests through RemoteEvents created by the server. Server validates every RemoteEvent action and never trusts client state. Use no external assets, require(assetId), exploit executors, unauthorized injection, credential theft or remote code loading. Original content only.
WEB OUTPUT: web_simulation is a complete standalone HTML5 document beginning with <!doctype html>, containing html, head, body, and an inline script. It must be playable immediately in a sandboxed iframe: render the actual game, update state, react to keyboard and pointer/touch input, show a visible objective, clear feedback and a restart control. Implement the same core loop as the Roblox version. Inline CSS and JS only; no external assets/libraries, network/fetch, WebSocket, cookies, localStorage, dynamic imports or external fonts. Responsive design and on-screen mobile controls. Keep the game concise enough to fit; do not omit core gameplay. Check the logic for syntax errors before returning.
For edits, preserve and extend the given project instead of starting over. Return only the JSON object."""

def err(message, status):
    return jsonify({"error": message}), status

def authorized():
    expected = os.environ.get("STUDIO_ACCESS_PASSWORD", "").strip()
    supplied = request.headers.get("X-Studio-Password", "").strip()
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))

def auth_error():
    missing = not os.environ.get("STUDIO_ACCESS_PASSWORD", "").strip()
    return err("Setze STUDIO_ACCESS_PASSWORD in Vercel Environment Variables." if missing else "Studio-Passwort falsch.", 503 if missing else 401)

def ai(prompt, provider):
    if provider == "groq":
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GROQ_API_KEY fehlt in Vercel.")
        response = Groq(api_key=key, timeout=160, max_retries=1).chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.2, max_completion_tokens=24000,
            response_format={"type": "json_object"})
        return response.choices[0].message.content
    from google import genai
    from google.genai import types
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY fehlt in Vercel.")
    response = genai.Client(api_key=key).models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM, response_mime_type="application/json",
                                           temperature=0.2, max_output_tokens=24000))
    return response.text

def parse_ai(raw):
    text = (raw or "").strip()
    ticks = chr(96) * 3
    if text.startswith(ticks):
        text = re.sub("^" + ticks + "(?:json)?\\s*", "", text, count=1, flags=re.I)
        text = re.sub("\\s*" + ticks + "$", "", text, count=1)
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Die KI lieferte kein gültiges JSON.")
        data = json.loads(text[start:end + 1])
    if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or not data[k].strip() for k in ("roblox_code", "web_simulation")):
        raise ValueError("KI-Antwort benötigt roblox_code und web_simulation.")
    if len(data["roblox_code"]) > 220000 or len(data["web_simulation"]) > 350000:
        raise ValueError("KI-Antwort zu groß.")
    return {"roblox_code": data["roblox_code"].strip(), "web_simulation": data["web_simulation"].strip()}

def normalize_html(source):
    text = (source or "").strip()
    ticks = chr(96) * 3
    if text.startswith(ticks):
        text = re.sub("^" + ticks + "(?:html|htm)?\\s*", "", text, count=1, flags=re.I)
        text = re.sub("\\s*" + ticks + "$", "", text, count=1)
    lower = text.lower()
    if "<script" not in lower or "</script>" not in lower:
        raise ValueError("Die HTML-Demo enthält kein vollständiges JavaScript.")
    if not ("<!doctype html" in lower or "<html" in lower):
        text = "<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Game KI Demo</title></head><body>" + text + "</body></html>"
    elif "</html>" not in lower:
        text += "\n</body></html>"
    return text

def game_fallback(prompt):
    path = ROOT / "templates" / "fallback-game.html"
    try:
        page = path.read_text(encoding="utf-8")
    except OSError:
        page = "<!doctype html><html><head><meta charset='utf-8'></head><body><canvas id='g' width='720' height='400'></canvas><script>let c=document.querySelector('canvas'),x=c.getContext('2d'),p={x:360,y:200};onkeydown=e=>{p.x+=e.key==='ArrowRight'?10:e.key==='ArrowLeft'?-10:0;p.y+=e.key==='ArrowDown'?10:e.key==='ArrowUp'?-10:0;x.clearRect(0,0,720,400);x.fillStyle='#6cf';x.fillRect(p.x,p.y,25,25)};x.fillStyle='#6cf';x.fillRect(p.x,p.y,25,25)</script></body></html>"
    title = html_lib.escape(" ".join((prompt or "Survival Arena").split())[:72])
    return page.replace("Game KI · Survival Arena", title or "Game KI · Survival Arena")

def ensure_playable(prompt, provider, data):
    try:
        data["web_simulation"] = normalize_html(data["web_simulation"])
        return data
    except ValueError:
        repair_prompt = (
            "Your last web_simulation was missing or invalid. Repair it into a complete standalone playable HTML game. "
            "Return the same two-field JSON schema. Keep roblox_code unchanged. The HTML must start with doctype html, "
            "contain head/body and a complete inline script, and work in a sandboxed iframe without external network, assets, "
            "libraries, cookies or storage. Original request:\n" + prompt[:4500] +
            "\nExisting Luau (preserve):\n" + data["roblox_code"][:40000] +
            "\nBroken HTML to repair:\n" + data["web_simulation"][:40000]
        )
        try:
            repaired = parse_ai(ai(repair_prompt, provider))
            repaired["web_simulation"] = normalize_html(repaired["web_simulation"])
            return repaired
        except Exception as exc:
            app.logger.warning("Preview repair failed (%s); using playable fallback", type(exc).__name__)
            data["web_simulation"] = game_fallback(prompt)
            return data

def roblox_env():
    key = os.environ.get("ROBLOX_API_KEY", "").strip()
    universe = os.environ.get("ROBLOX_UNIVERSE_ID", "").strip()
    place = os.environ.get("ROBLOX_PLACE_ID", "").strip()
    if not all((key, universe, place)):
        raise RuntimeError("ROBLOX_API_KEY, ROBLOX_UNIVERSE_ID und ROBLOX_PLACE_ID müssen in Vercel gesetzt sein.")
    if not (universe.isdigit() and 1 <= len(universe) <= 24) or not (place.isdigit() and 1 <= len(place) <= 24):
        raise ValueError("Roblox-IDs müssen numerisch sein.")
    return key, universe, place

def split_roblox_code(source):
    server_marker = "--[[GAME_KI_SERVER_SCRIPT]]"
    client_marker = "--[[GAME_KI_CLIENT_SCRIPT]]"
    if server_marker not in source:
        return source.strip(), ""
    server_part = source.split(server_marker, 1)[1]
    if client_marker in server_part:
        server_code, client_code = server_part.split(client_marker, 1)
    else:
        server_code, client_code = server_part, ""
    server_code, client_code = server_code.strip(), client_code.strip()
    if not server_code:
        raise ValueError("Der Luau-Code enthält keinen Server-Script-Abschnitt.")
    if len(server_code) > 180000 or len(client_code) > 100000:
        raise ValueError("Roblox-Script-Abschnitt ist zu groß.")
    return server_code, client_code

def place_xml(source, title):
    server_code, client_code = split_roblox_code(source)
    root = ET.Element("roblox", {
        "xmlns:xmime": "http://www.w3.org/2005/05/xmlmime",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation": "http://www.roblox.com/roblox.xsd",
        "version": "4"
    })
    def add(parent, cls, name):
        obj = ET.SubElement(parent, "Item", {"class": cls, "referent": "RBX" + uuid.uuid4().hex.upper()})
        props = ET.SubElement(obj, "Properties")
        ET.SubElement(props, "string", {"name": "Name"}).text = name
        return obj, props
    add(root, "Workspace", "Workspace")
    add(root, "ReplicatedStorage", "ReplicatedStorage")
    service, _ = add(root, "ServerScriptService", "ServerScriptService")
    _, props = add(service, "Script", "GameKI_Server")
    ET.SubElement(props, "ProtectedString", {"name": "Source"}).text = server_code
    ET.SubElement(props, "bool", {"name": "Disabled"}).text = "false"
    if client_code:
        starter_player, _ = add(root, "StarterPlayer", "StarterPlayer")
        player_scripts, _ = add(starter_player, "StarterPlayerScripts", "StarterPlayerScripts")
        _, client_props = add(player_scripts, "LocalScript", "GameKI_Client")
        ET.SubElement(client_props, "ProtectedString", {"name": "Source"}).text = client_code
        ET.SubElement(client_props, "bool", {"name": "Disabled"}).text = "false"
    output = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    parsed = ET.fromstring(output)
    if parsed.tag != "roblox" or not parsed.findall(".//ProtectedString[@name='Source']"):
        raise ValueError("Place-XML konnte nicht erstellt werden.")
    return output

def publish_bytes(payload, content_type="application/xml"):
    key, universe, place = roblox_env()
    try:
        response = requests.post(
            "https://apis.roblox.com/universes/v1/" + universe + "/places/" + place + "/versions",
            params={"versionType": "Published"},
            headers={"x-api-key": key, "Content-Type": content_type},
            data=payload, timeout=(10, 120))
    except requests.Timeout:
        return err("Zeitüberschreitung bei Roblox. Prüfe dein Creator Dashboard.", 504)
    except requests.RequestException:
        return err("Roblox Open Cloud ist nicht erreichbar.", 502)
    if not response.ok:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:400]
        app.logger.warning("Roblox publish rejected HTTP %s", response.status_code)
        return jsonify({"error": "Roblox hat die Veröffentlichung abgelehnt (HTTP " + str(response.status_code) + ").",
                        "details": str(detail)[:600]}), 502
    try:
        result = response.json()
    except ValueError:
        result = {}
    return jsonify({"ok": True, "versionNumber": result.get("versionNumber"), "placeId": place})

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/starter-game")
def starter_game():
    response = Response(game_fallback("Survival Arena"), mimetype="text/html")
    response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/status")
def status():
    return jsonify({
        "protected": bool(os.environ.get("STUDIO_ACCESS_PASSWORD", "").strip()),
        "groqConfiguredOnServer": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "geminiConfiguredOnServer": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "robloxConfiguredOnServer": all(os.environ.get(k, "").strip() for k in ("ROBLOX_API_KEY", "ROBLOX_UNIVERSE_ID", "ROBLOX_PLACE_ID"))
    })

@app.post("/generate")
def generate():
    if not authorized():
        return auth_error()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("JSON-Auftrag fehlt.", 400)
    prompt, provider = data.get("prompt"), data.get("provider", "groq")
    if not isinstance(prompt, str) or not prompt.strip():
        return err("Beschreibe dein Spiel.", 400)
    if len(prompt) > 12000:
        return err("Prompt maximal 12.000 Zeichen.", 413)
    if provider not in ("groq", "gemini"):
        return err("KI-Anbieter muss Groq oder Gemini sein.", 400)
    previous = data.get("previous")
    if previous is not None:
        if not isinstance(previous, dict):
            return err("Projektkontext ungültig.", 400)
        code, web_demo, original = previous.get("roblox_code", ""), previous.get("web_simulation", ""), previous.get("original_prompt", "")
        if not all(isinstance(x, str) for x in (code, web_demo, original)) or len(code) > 100000 or len(web_demo) > 100000:
            return err("Projektkontext ungültig oder zu groß.", 413)
        if code or web_demo:
            prompt = ("Erweitere das bestehende Projekt, starte nicht neu. Ursprünglicher Auftrag: " + original[:4000] +
                      "\nBisheriger Luau-Code:\n" + code + "\nBisherige HTML-Demo:\n" + web_demo + "\nNeue Änderung:\n" + prompt)
    try:
        try:
            result = parse_ai(ai(prompt.strip(), provider))
        except ValueError:
            result = parse_ai(ai("Return a valid JSON object with roblox_code and web_simulation for this request, with complete runnable HTML. No Markdown. Request:\n" + prompt[:10000], provider))
        result = ensure_playable(prompt.strip(), provider, result)
        return jsonify({"roblox_code": result["roblox_code"], "web_simulation": result["web_simulation"]})
    except RuntimeError as exc:
        return err(str(exc), 503)
    except ValueError as exc:
        return err(str(exc), 502)
    except Exception as exc:
        app.logger.warning("AI provider %s failed: %s", provider, type(exc).__name__)
        return err("KI-Generierung fehlgeschlagen: " + str(exc)[:250], 502)

@app.post("/publish-generated")
def publish_generated():
    if not authorized():
        return auth_error()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("roblox_code"), str):
        return err("Roblox-Code fehlt.", 400)
    if data.get("confirm_replace") is not True:
        return err("Bestätige, dass die veröffentlichte Place-Version ersetzt werden darf.", 400)
    if len(data["roblox_code"]) > 220000:
        return err("Luau-Code zu groß.", 413)
    try:
        payload = place_xml(data["roblox_code"], str(data.get("game_name", "Game KI"))[:90])
        if len(payload) > 4 * 1024 * 1024:
            return err("Place-Datei größer als 4 MiB.", 413)
        return publish_bytes(payload)
    except RuntimeError as exc:
        return err(str(exc), 503)
    except ValueError as exc:
        return err(str(exc), 400)

@app.post("/upload")
def upload():
    if not authorized():
        return auth_error()
    try:
        _key, _universe, _place = roblox_env()
    except RuntimeError as exc:
        return err(str(exc), 503)
    except ValueError as exc:
        return err(str(exc), 400)
    file = request.files.get("place_file")
    if file is None or not file.filename:
        return err("Wähle eine .rbxl- oder .rbxlx-Datei.", 400)
    extension = Path(file.filename.rsplit("/", 1)[-1].rsplit(chr(92), 1)[-1]).suffix.lower()
    if extension not in (".rbxl", ".rbxlx"):
        return err("Nur .rbxl/.rbxlx werden unterstützt.", 415)
    payload = file.read(4 * 1024 * 1024 + 1)
    if not payload:
        return err("Datei leer.", 400)
    if len(payload) > 4 * 1024 * 1024:
        return err("Datei größer als 4 MiB.", 413)
    if extension == ".rbxlx":
        try:
            root = ET.fromstring(payload)
            if root.tag != "roblox" or root.get("version") != "4":
                return err("Ungültige RBXLX-Datei.", 400)
        except ET.ParseError:
            return err("RBXLX enthält ungültiges XML.", 400)
        content_type = "application/xml"
    else:
        if not payload.startswith(b"<roblox!"):
            return err("Ungültige binäre Place-Datei.", 400)
        content_type = "application/octet-stream"
    return publish_bytes(payload, content_type)

@app.errorhandler(RequestEntityTooLarge)
def too_large(_exc):
    return err("Request überschreitet 4 MiB.", 413)

@app.errorhandler(404)
def not_found(_exc):
    return err("Route nicht gefunden.", 404)
