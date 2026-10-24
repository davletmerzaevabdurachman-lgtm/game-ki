import os, json, re, hmac, uuid, math, html as html_lib
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(ROOT / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
SYSTEM = """You are Game KI Studio, a senior Roblox Luau engineer, level designer, and browser-game developer.
Return one valid JSON object only, without Markdown fences, with fields:
- roblox_code: string
- web_simulation: string
- roblox_scene: object with name, theme, spawn ([x,y,z]), and parts (array of up to 70 part objects).
Each part has name, size ([x,y,z]), position ([x,y,z]), color ([r,g,b] 0..1), material (Plastic, SmoothPlastic, Neon, Wood, WoodPlanks, Concrete, Slate, Brick, Metal, Grass), can_collide (boolean), transparency (0..1), yaw (degrees). Create 25-60 meaningful editable 3D level parts fitting the requested genre: navigable floor/roads, paths, buildings/platforms, obstacles, cover, boundaries, landmarks, spawn marker, color palette and visual hierarchy. No single-cube placeholder map.
ROBLOX OUTPUT: roblox_code contains TWO complete scripts separated by exactly these markers:
--[[GAME_KI_SERVER_SCRIPT]]
<complete server Script source>
--[[GAME_KI_CLIENT_SCRIPT]]
<complete LocalScript source>
The roblox_scene geometry is saved directly into the place file and exists under workspace at runtime. Do not clear, replace or duplicate it in scripts. Server script owns dynamic gameplay and state: objectives, enemies/targets, health/damage, rewards, progression, RemoteEvents, spawn validation, win/lose/round logic. Client script builds a polished Roblox HUD and input controls, uses the existing world and communicates with server-created RemoteEvents. Validate RemoteEvent inputs on the server, rate-limit actions, and never trust client state. Use Roblox APIs correctly, clean up instances and avoid unbounded loops. No placeholders/TODOs, external require(assetId), exploit executors, unauthorized injection, credential theft, remote code loading or fake publish claims. Original game content only.
ROBLOX-NATIVE IN-GAME LOOK AND FUNCTION (CRITICAL):
The Roblox deliverable must look and behave like a real, native Roblox experience when opened in Roblox Player—not like an HTML game or a picture of Roblox. Use actual Roblox Instances and Luau; never fake the Roblox world with a ScreenGui-only scene. The editable roblox_scene parts are the physical 3D world under Workspace.
- Use the Roblox player's real avatar/Character, Humanoid and HumanoidRootPart. Do not replace the avatar with a custom fake body. Keep Roblox's default third-person camera and default movement controls unless the requested genre genuinely needs a different camera; never unnecessarily set CurrentCamera.CameraType to Scriptable or recreate WASD/camera controls.
- Respect Roblox scale and blocky/stylized 3D design. Build clear navigable routes, actual walkable floors, believable doors/openings, cover, stairs/ramps where needed, boundaries and a SpawnLocation. Avoid oversized solid cubes pretending to be buildings or pathways that lead nowhere. Use native Parts, Materials, colors, PointLights/SurfaceLights and Lighting effects where they actually improve the world. Prefer a polished, readable Roblox aesthetic over photorealistic effects or external assets.
- The server Script must create/own authoritative gameplay objects and game state. Use actual Roblox Models/Parts/Humanoids for NPCs and enemies, real collisions/health/rewards/objectives, and reliable character-spawn/death handling. Create RemoteEvents on the server in ReplicatedStorage before clients wait for them. Validate all client requests and enforce server authority. Avoid client-created authoritative enemies or client-only wins.
- The LocalScript must build native Roblox UI under the player's PlayerGui using ScreenGui, Frames, TextLabels and real TextButtons. Use scalable sizing/constraints for desktop and mobile; buttons must call working gameplay actions. React to CharacterAdded/PlayerGui availability with WaitForChild/timeouts safely. Use Roblox input services only for actions the genre actually needs. Do not draw a fake browser UI inside Roblox.
- Use real engine APIs and correct Roblox service/property names. Include a full playable start-to-finish loop, sensible respawns/restarts, clear feedback and cleanup. Mentally walk through the complete game from server startup to a new player joining, spawning, playing, dying/winning and rejoining. Prefer Roblox-native, dependency-free features; no external require(assetId), packages, network-loaded code, fake controls or placeholder logic.
GAME QUALITY BAR: make a real playable gameplay loop, not a static showcase. Fit the requested title/genre. Include a meaningful objective, progression, combat/interactions where appropriate, visible feedback, loss/win state, restart/round loop, readable UI and responsive controls. Avoid requiring external assets; build with native Parts, UI and original code.
SECRET 6787 GAME MENU: For this Zombie Survival project, build a visible but initially locked in-game button labelled "SECRET CONSOLE" or "SYSTEM". When clicked, show an access-code input. Entering exactly "6787" unlocks a slick neon green/cyan hacker-themed "HACKER CONSOLE" panel with clear labels, status readouts and buttons for a small allowlisted set of fun modifiers that ONLY affect this experience: HEAL/RESTORE, OVERDRIVE (temporary speed boost), PURGE CURRENT WAVE, BONUS CREDITS, and NIGHT VISION. Make those actions actually work and give feedback, rather than making a decorative fake menu. In Roblox, the server must validate the code and each allowlisted action through a RemoteEvent, keep unlock state per player, rate-limit requests, reject unknown commands, and clean up player state when they leave. Code 6787 is an intentionally discoverable game easter egg, not secure authentication. It must only modify the current game; never make tools for exploiting or hacking other Roblox games. Implement the same code-entry easter egg and working actions in the HTML5 demo.
ZOMBIE SURVIVAL QUALITY: When the prompt is zombie/survival/horror themed, create a detailed rainy ruined city/safehouse map with several buildings/alleys, street cover, barricades, supply crates, neon accent lighting, a protected spawn/safehouse, and distinct routes. Gameplay should include escalating zombie waves, different enemy types/speeds/health, ammo/reload, pickups, health, credits/XP or upgrade progression and a stronger boss every few waves. Avoid excessive realistic gore: stylized arcade horror.
WEB OUTPUT: web_simulation is a complete standalone HTML5 document beginning with <!doctype html>, containing html/head/body and inline JavaScript. It must be genuinely playable immediately in the sandbox: implement the same core loop and game theme, movement, aim/attack, collisions/obstacles, enemy/objective behavior, health/ammo/progress feedback, win/lose or round progression, restart, and the working 6787 menu. Keyboard and pointer/touch input plus responsive on-screen controls. Inline CSS/JS only; no external assets/libraries/network/fetch/WebSocket/cookies/localStorage/dynamic imports/external fonts. Do not return a decorative mockup in place of gameplay.
For edits preserve and extend existing scripts, HTML and scene context. Before output, check that both Luau scripts are complete and HTML logic is real and complete. Return only valid JSON."""

# Strict Structured Outputs schema supported by Groq's GPT-OSS models.
# This prevents invalid JSON when Luau/HTML contains quotes, backslashes and newlines.
GAME_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "roblox_code": {"type": "string"},
        "web_simulation": {"type": "string"},
        "roblox_scene": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "theme": {"type": "string"},
                "spawn": {"type": "array", "items": {"type": "number"}},
                "parts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "size": {"type": "array", "items": {"type": "number"}},
                            "position": {"type": "array", "items": {"type": "number"}},
                            "color": {"type": "array", "items": {"type": "number"}},
                            "material": {"type": "string"},
                            "can_collide": {"type": "boolean"},
                            "transparency": {"type": "number"},
                            "yaw": {"type": "number"}
                        },
                        "required": ["name", "size", "position", "color", "material",
                                     "can_collide", "transparency", "yaw"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["name", "theme", "spawn", "parts"],
            "additionalProperties": False
        }
    },
    "required": ["roblox_code", "web_simulation", "roblox_scene"],
    "additionalProperties": False
}


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
            temperature=0.2, max_completion_tokens=48000,
            response_format={"type": "json_schema", "json_schema": {
                "name": "game_build", "strict": True, "schema": GAME_JSON_SCHEMA
            }})
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
                                           temperature=0.2, max_output_tokens=48000))
    return response.text


ROBLOX_COMPONENT_SYSTEM = """You are a senior Roblox Studio and Luau gameplay engineer.
Return ONLY raw Roblox Luau source code, not JSON and not Markdown code fences.
The output must contain two complete scripts separated with these exact marker lines:
--[[GAME_KI_SERVER_SCRIPT]]
<server Script source>
--[[GAME_KI_CLIENT_SCRIPT]]
<client LocalScript source>

Create a real playable Roblox experience using Roblox's actual engine. The editable 3D scene already exists in Workspace; do not delete, replace, or duplicate it. Use the real Roblox Character, Humanoid and HumanoidRootPart with the normal Roblox third-person camera and default movement controls. Do not replace the avatar or fake the game as a GUI.

Server code owns real gameplay state, NPCs/enemies, damage, rewards, objectives, respawn and win/lose logic. Use actual Roblox Instances, Models, Parts and Humanoids as appropriate. Create RemoteEvents under ReplicatedStorage on the server before the client waits for them. Validate all client requests on the server, rate-limit action events and never trust client-provided health, rewards or enemy state. Implement a useful full loop (join, spawn, play, progress, die/win, respawn/restart). Avoid unbounded loops and clean up connections/instances.

Client code builds a native Roblox HUD under PlayerGui with ScreenGui, Frames, TextLabels and functional TextButtons; use responsive scale/constraints for PC and mobile. Interact with server-authoritative gameplay through the RemoteEvents. Do not create HTML/browser elements in Roblox. Use correct Roblox APIs; don't depend on external assets, packages, external require IDs, remote code loading, exploit tools or placeholders.

For zombie/survival/horror games, implement escalating zombie waves, distinct enemy types, health, ammo/reload, pickups, credits/XP, safehouse and a stronger boss every few waves. Use actual in-game NPCs and reliable targeting/collisions.
When the user's prompt requests the 6787 secret/hacker console, include a visible locked button, a code-entry panel accepting exactly 6787, and working HEAL/RESTORE, OVERDRIVE, PURGE WAVE, BONUS CREDITS, AMMO and NIGHT VISION actions. Validate the code and allowlisted actions on the server, keep unlock state per player, rate-limit calls, and only affect this game's state. This is an intentional game easter egg, not a tool for other Roblox games.
Keep code complete but concise enough to execute reliably. Respect the user's specific game idea. No TODOs or fake claims.
"""

WEB_COMPONENT_SYSTEM = """You are an expert HTML5 gameplay engineer. Return ONLY a complete standalone HTML document, starting with <!doctype html>. No Markdown fences, no JSON wrapper and no explanation.
Build an immediately playable, polished browser demo that matches the user's game idea. Inline CSS and JavaScript only: no external dependencies, assets, fonts, network calls, fetch, WebSocket, cookies, localStorage or dynamic imports. The game must have a real gameplay loop: responsive playfield, character movement, input/attack or interaction, collision/obstacles, enemies/objectives, health/progress feedback, win/lose or round progression and restart. Support keyboard and pointer/touch with usable mobile controls.
When the user's prompt requests zombie survival, implement escalating zombie waves, ammo/reload, health, pickups, progress/rewards, tougher boss waves and a visibly playable ruined-city/safehouse setting.
When the user's prompt requests the 6787 secret/hacker console, implement a working initially locked console, a code input accepting exactly 6787, and functional HEAL/RESTORE, OVERDRIVE, PURGE WAVE, BONUS CREDITS, AMMO and NIGHT VISION modifiers with feedback. These actions may only affect this browser demo.
Make the controls and objective obvious. Avoid static mockups; ensure the canvas/game loop is fully implemented and restart works. Keep HTML compact enough to fit in a single response.
"""

def _strip_generated_fence(raw, kind):
    text = (raw or "").strip()
    if text.startswith(chr(96) * 3):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith(chr(96) * 3):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if kind == "html" and not text.lower().startswith("<!doctype html") and "<html" in text.lower():
        text = text[text.lower().find("<html"):]
    return text

def ai_component(prompt, provider, kind):
    """Generate one artifact as raw text to avoid serializing huge code/HTML into one JSON response."""
    if kind == "roblox":
        instruction, max_tokens = ROBLOX_COMPONENT_SYSTEM, 16000
    elif kind == "html":
        instruction, max_tokens = WEB_COMPONENT_SYSTEM, 16000
    else:
        raise ValueError("Unbekannter Generierungsbaustein.")
    if provider == "groq":
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GROQ_API_KEY fehlt in Vercel.")
        response = Groq(api_key=key, timeout=55, max_retries=0).chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": instruction},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            max_completion_tokens=max_tokens,
        )
        raw = response.choices[0].message.content
    else:
        from google import genai
        from google.genai import types
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY fehlt in Vercel.")
        response = genai.Client(api_key=key).models.generate_content(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.2,
                max_output_tokens=max_tokens,
            ),
        )
        raw = response.text
    result = _strip_generated_fence(raw, kind)
    if not result:
        raise ValueError(("Roblox-Luau" if kind == "roblox" else "HTML-Demo") + " blieb leer.")
    return result

def generate_components(prompt, provider):
    """Generate Roblox scripts and the browser demo independently, in parallel, without huge JSON escaping."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        code_job = pool.submit(ai_component, prompt, provider, "roblox")
        html_job = pool.submit(ai_component, prompt, provider, "html")
        roblox_code = code_job.result()
        web_simulation = html_job.result()
    return {
        "roblox_code": roblox_code,
        "web_simulation": normalize_html(web_simulation),
        # The scene is serialized directly into the Roblox place. Genre-aware scenes
        # ensure a usable physical level even if a model response omits geometry.
        "roblox_scene": default_scene(prompt),
    }


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
    scene = data.get("roblox_scene")
    if isinstance(scene, str):
        try:
            scene = json.loads(scene)
        except ValueError:
            scene = None
    if not isinstance(scene, dict):
        scene = None
    return {"roblox_code": data["roblox_code"].strip(),
            "web_simulation": data["web_simulation"].strip(),
            "roblox_scene": scene}


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

def _scene_part(name, size, position, color, material="Concrete", collide=True, yaw=0):
    return {"name": name, "size": size, "position": position, "color": color,
            "anchored": True, "can_collide": collide, "material": material,
            "transparency": 0, "yaw": yaw}


def default_scene(prompt):
    """Build a visible editable level if the model did not return a usable scene plan."""
    lower=(prompt or "").lower()
    parts=[]
    def add(name,size,pos,color,mat="Concrete",collide=True,yaw=0):
        parts.append(_scene_part(name,size,pos,color,mat,collide,yaw))
    if any(w in lower for w in ("obby","parkour","checkpoint","hindernis")):
        theme,spawn="obby",[0,5,52]
        add("IslandGround",[150,4,150],[0,-3,0],[.18,.20,.28],"Slate")
        add("StartPlatform",[24,2,20],[0,2,52],[.18,.66,.95],"SmoothPlastic")
        colors=[[.55,.35,.98],[.16,.82,.96],[.35,.88,.53],[1,.58,.18]]
        for i in range(14):
            add("ParkourPlatform_%02d"%i,[7+i%3,1.2,6],[(i%3-1)*8,3+(i%4)*1.8,43-i*7],colors[i%4],"Neon" if i%4==0 else "SmoothPlastic",True,(i*11)%30-15)
        add("FinishIsland",[24,2,18],[0,8,-57],[.28,.86,.48],"SmoothPlastic")
        for i in range(6): add("LavaHazard_%02d"%i,[8,.5,5],[(i%3-1)*12,-1,8-i*13],[1,.14,.08],"Neon",False)
        for x in (-65,65): add("IslandEdge",[3,9,130],[x,2,0],[.16,.18,.26],"Slate")
    elif any(w in lower for w in ("race","racing","car","drift","rennen")):
        theme,spawn="racing",[0,3,91]
        add("RaceGround",[220,4,220],[0,-3,0],[.16,.36,.20],"Grass")
        add("RaceRoad",[24,.6,180],[0,-.8,0],[.11,.12,.15],"Concrete")
        for z in range(-80,90,14): add("RoadDash",[.6,.12,7],[0,-.43,z],[1,.82,.35],"Neon",False)
        for x in (-14,14): add("TrackBarrier",[2,4,185],[x,1,-1],[.9,.23,.18],"SmoothPlastic")
        for i in range(12): add("RacePylon_%02d"%i,[4,4,4],[(-1 if i%2 else 1)*(27+i%3*8),1,-70+i*13],[1,.56,.16],"Neon")
        for x in (-10,10): add("StartGatePost",[2,12,2],[x,5,78],[.22,.68,1],"Neon")
        add("StartGateTop",[22,2,2],[0,12,78],[.22,.68,1],"Neon")
    elif any(w in lower for w in ("tycoon","simulator","farm","shop","cash","factory")):
        theme,spawn="tycoon",[0,3,54]
        add("TycoonIsland",[150,4,150],[0,-3,0],[.16,.25,.21],"Grass")
        add("MainPlot",[50,1,50],[0,0,0],[.42,.45,.50],"Concrete")
        for x in (-26,26): add("PlotBorder",[2,5,54],[x,2,0],[.18,.21,.25],"Metal")
        for z in (-26,26): add("PlotBorder",[54,5,2],[0,2,z],[.18,.21,.25],"Metal")
        for i,pos in enumerate([[-14,2,-12],[0,2,-12],[14,2,-12],[-14,2,7],[0,2,7],[14,2,7]]):
            add("Machine_%02d"%i,[7,4+i%3*2,7],pos,[[.34,.7,.96],[.61,.42,.96],[.28,.82,.54]][i%3],"Metal")
        add("SpawnPlatform",[18,1,15],[0,1,54],[.2,.72,.48],"SmoothPlastic")
        for i in range(8): add("Tree_%02d"%i,[3,10,3],[(-1 if i%2 else 1)*(45+i%3*5),4,-35+i*10],[.22,.42,.23],"Wood")
    else:
        theme="zombie-survival" if any(w in lower for w in ("zombie","survival","horror","undead")) else "arena"
        spawn=[0,4,76] if theme=="zombie-survival" else [0,4,65]
        add("WorldGround",[220,4,220],[0,-3,0],[.19,.21,.23],"Concrete")
        add("MainRoad",[18,.4,190],[0,-.7,0],[.08,.09,.11],"Concrete")
        for x in (-11,11): add("Sidewalk",[5,.8,188],[x,-.32,0],[.33,.34,.32],"Concrete")
        buildings=[(-42,10,-55,24,22,28),(42,14,-53,28,30,32),(-48,9,-5,22,20,26),(48,12,-4,25,26,30),(-42,15,47,28,32,28),(43,11,48,25,24,33),(-72,8,3,16,18,22),(72,8,8,16,18,22)]
        for i,(x,y,z,sx,sy,sz) in enumerate(buildings):
            add("RuinedBuilding_%02d"%i,[sx,sy,sz],[x,y,z],[[.22,.25,.28],[.28,.27,.25],[.20,.24,.25]][i%3],"Concrete")
            add("BrokenRoof_%02d"%i,[sx+2,1.2,sz+2],[x,y+sy/2+.7,z],[.13,.15,.17],"Slate")
            for wx in (-1,1): add("DarkWindow_%02d"%i,[.25,3,4],[x+wx*(sx/2+.12),y+1,z],[.08,.17,.21],"SmoothPlastic",False)
        for i in range(12):
            x=(-1 if i%2 else 1)*(5+(i%3)*4); z=-65+i*11
            add("RoadBarricade_%02d"%i,[5,2.8,2],[x,.3,z],[.62,.18,.13] if i%3==0 else [.27,.29,.31],"Metal",True,(i%5)*8-16)
        for i in range(8): add("SupplyCrate_%02d"%i,[3.5,3,3.5],[(-1 if i%2 else 1)*(20+i%3*4),.5,-48+i*13],[.31,.34,.27],"Wood")
        add("SafeZoneFloor",[26,.8,20],[0,0,78],[.15,.34,.25],"SmoothPlastic")
        for x in (-13,13): add("SafeZoneWall",[1,7,20],[x,3,78],[.22,.52,.34],"Metal")
        add("SafeZoneRear",[26,7,1],[0,3,88],[.22,.48,.32],"Metal")
        add("WatchTower",[6,13,6],[-25,6,75],[.25,.28,.30],"Metal")
        add("TowerDeck",[13,1,13],[-25,13,75],[.32,.35,.35],"WoodPlanks")
        for x in (-90,90): add("PerimeterWall",[3,9,170],[x,2,0],[.15,.18,.21],"Concrete")
    add("SpawnMarker",[7,.4,7],[spawn[0],.1,spawn[2]],[.22,.84,.48],"Neon",False)
    return {"name":"Generated "+theme,"theme":theme,"spawn":spawn,"parts":parts[:70]}


def normalize_scene(raw_scene, prompt):
    if isinstance(raw_scene,str):
        try: raw_scene=json.loads(raw_scene)
        except ValueError: raw_scene=None
    if not isinstance(raw_scene,dict) or not isinstance(raw_scene.get("parts"),list):
        return default_scene(prompt)
    allowed={"Plastic","SmoothPlastic","Neon","Wood","WoodPlanks","Concrete","Slate","Brick","Metal","Grass"}
    def nums(values,default,low,high):
        if not isinstance(values,(list,tuple)) or len(values)<3: values=default
        out=[]
        for i in range(3):
            try: n=float(values[i])
            except (TypeError,ValueError): n=float(default[i])
            if not math.isfinite(n): n=float(default[i])
            out.append(max(low,min(high,n)))
        return out
    parts=[]
    for raw in raw_scene["parts"][:70]:
        if not isinstance(raw,dict): continue
        size=nums(raw.get("size"),[4,2,4],.5,500)
        pos=nums(raw.get("position"),[0,1,0],-500,500)
        color=nums(raw.get("color"),[.35,.38,.42],0,255)
        if max(color)>1: color=[v/255 for v in color]
        color=[max(0,min(1,v)) for v in color]
        material=str(raw.get("material","Concrete"))
        if material not in allowed: material="Concrete"
        try: transparency=float(raw.get("transparency",0))
        except (TypeError,ValueError): transparency=0
        try: yaw=float(raw.get("yaw",0))
        except (TypeError,ValueError): yaw=0
        if not math.isfinite(transparency): transparency=0
        if not math.isfinite(yaw): yaw=0
        name=re.sub(r"[\x00-\x1f]","",str(raw.get("name","LevelPart")))[:80].strip() or "LevelPart"
        parts.append({"name":name,"size":size,"position":pos,"color":color,"material":material,
                      "anchored":True,"can_collide":bool(raw.get("can_collide",True)),
                      "transparency":max(0,min(1,transparency)),"yaw":max(-180,min(180,yaw))})
    if len(parts)<20: return default_scene(prompt)
    if not any(("ground" in p["name"].lower() or "floor" in p["name"].lower() or "terrain" in p["name"].lower()) and p["size"][0]>=60 and p["size"][2]>=60 for p in parts):
        parts.insert(0,_scene_part("GameKI_Ground",[180,4,180],[0,-3,0],[.22,.24,.27],"Concrete"))
    spawn=nums(raw_scene.get("spawn"),[0,4,30],-500,500)
    spawn[1]=max(1,min(200,spawn[1]))
    return {"name":re.sub(r"[\x00-\x1f]","",str(raw_scene.get("name","Game KI World")))[:80],
            "theme":re.sub(r"[\x00-\x1f]","",str(raw_scene.get("theme","custom")))[:50],
            "spawn":spawn,"parts":parts[:70]}


def validate_secret_console(prompt, data):
    """Fail a requested 6787 easter egg closed instead of silently returning a fake menu."""
    low_prompt = (prompt or "").lower()
    if "6787" not in low_prompt or not any(word in low_prompt for word in ("zombie", "hacker", "secret console", "hacker console", "outbreak")):
        return
    code = str(data.get("roblox_code", "")).lower()
    web = str(data.get("web_simulation", "")).lower()
    def has(text, *terms):
        return any(term in text for term in terms)
    issues = []
    for label, variants in (
        ("restore/heal", ("heal", "restore")),
        ("overdrive", ("overdrive",)),
        ("purge wave", ("purge",)),
        ("credits", ("credits", "credit")),
        ("ammo", ("ammo", "munition")),
        ("night vision", ("night vision", "night_vision", "nightvision")),
    ):
        if not has(code, *variants):
            issues.append("Roblox: " + label)
        if not has(web, *variants):
            issues.append("Browser-Demo: " + label)
    if "6787" not in code:
        issues.append("Roblox: Zugangscode 6787")
    if "6787" not in web:
        issues.append("Browser-Demo: Zugangscode 6787")
    if not has(code, "onserverevent") or not has(code, "remoteevent"):
        issues.append("Roblox: serverseitige RemoteEvent-Validierung")
    if not has(web, "hacker console", "secret console") or not has(web, "input") or not has(web, "unlock"):
        issues.append("Browser-Demo: bedienbare Geheimcode-Konsole")
    if issues:
        raise ValueError("Die angeforderte 6787-Konsole ist unvollständig: " + ", ".join(issues[:12]))


def ensure_playable(prompt, provider, data):
    data["roblox_scene"]=normalize_scene(data.get("roblox_scene"),prompt)
    try:
        data["web_simulation"]=normalize_html(data["web_simulation"])
        return data
    except ValueError:
        repair_prompt=("Repair this project as one valid JSON object with roblox_code, web_simulation, and roblox_scene. "
            "Keep complete server/client scripts and the original game idea; return a complete playable standalone HTML5 game and 20-60 editable scene parts. "
            "No Markdown, network or external assets. Request:\n"+prompt[:4500]+
            "\nExisting Roblox scripts:\n"+data["roblox_code"][:40000]+
            "\nExisting scene JSON:\n"+json.dumps(data["roblox_scene"],ensure_ascii=False)[:16000]+
            "\nBroken HTML:\n"+data["web_simulation"][:40000])
        try:
            repaired=parse_ai(ai(repair_prompt,provider))
            repaired["web_simulation"]=normalize_html(repaired["web_simulation"])
            repaired["roblox_scene"]=normalize_scene(repaired.get("roblox_scene") or data.get("roblox_scene"),prompt)
            return repaired
        except Exception as exc:
            app.logger.warning("Preview repair failed (%s); using playable fallback",type(exc).__name__)
            data["web_simulation"]=game_fallback(prompt)
            return data


def roblox_env(config=None):
    """Resolve Roblox Open Cloud settings from the publish request or server env.
    The browser-provided API key is used only for the current publish request and
    is never forwarded to either AI provider or written to server-side storage.
    """
    config = config if isinstance(config, dict) else {}
    key = str(config.get("api_key") or os.environ.get("ROBLOX_API_KEY", "")).strip()
    universe = str(config.get("universe_id") or os.environ.get("ROBLOX_UNIVERSE_ID", "")).strip()
    place = str(config.get("place_id") or os.environ.get("ROBLOX_PLACE_ID", "")).strip()
    if not all((key, universe, place)):
        raise RuntimeError(
            "Trage Roblox API-Key, Universe-ID und Place-ID in den Studio-Einstellungen ein "
            "oder konfiguriere die ROBLOX_* Variablen in Vercel."
        )
    if len(key) > 1024 or any(ord(ch) < 32 for ch in key):
        raise ValueError("Der Roblox API-Key hat ein ungültiges Format.")
    if not (universe.isdigit() and 1 <= len(universe) <= 24) or not (place.isdigit() and 1 <= len(place) <= 24):
        raise ValueError("Roblox Universe-ID und Place-ID müssen numerisch sein.")
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

def validate_roblox_scripts(source):
    if "--[[GAME_KI_SERVER_SCRIPT]]" not in source or "--[[GAME_KI_CLIENT_SCRIPT]]" not in source:
        raise ValueError("Die KI lieferte keine getrennten Roblox-Server- und Client-Scripts. Bitte erneut generieren.")
    server_code, client_code=split_roblox_code(source)
    if len(server_code)<140 or len(client_code)<140:
        raise ValueError("Die Roblox-Scripts sind unvollständig. Bitte erneut generieren.")
    lowered=(server_code+"\n"+client_code).lower()
    if any(x in lowered for x in ("todo: implement","your code here","not implemented","add code here")):
        raise ValueError("Die KI lieferte Platzhalter statt vollständiger Roblox-Scripts. Bitte erneut generieren.")
    return {"server":server_code,"client":client_code}


def place_xml(source, title, scene=None):
    scripts=validate_roblox_scripts(source)
    scene=normalize_scene(scene,title)
    root=ET.Element("roblox",{
        "xmlns:xmime":"http://www.w3.org/2005/05/xmlmime",
        "xmlns:xsi":"http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation":"http://www.roblox.com/roblox.xsd",
        "version":"4"})
    def add(parent,cls,name):
        obj=ET.SubElement(parent,"Item",{"class":cls,"referent":"RBX"+uuid.uuid4().hex.upper()})
        props=ET.SubElement(obj,"Properties")
        ET.SubElement(props,"string",{"name":"Name"}).text=name
        return obj,props
    def add_vector(parent,values,name):
        node=ET.SubElement(parent,"Vector3",{"name":name})
        for key,val in zip(("X","Y","Z"),values): ET.SubElement(node,key).text=str(round(float(val),4))
    def add_color(parent,values,name="Color"):
        node=ET.SubElement(parent,"Color3",{"name":name})
        for key,val in zip(("R","G","B"),values): ET.SubElement(node,key).text=str(round(max(0,min(1,float(val))),4))
    def add_cframe(parent,position,yaw):
        node=ET.SubElement(parent,"CoordinateFrame",{"name":"CFrame"})
        angle=math.radians(float(yaw)); c=math.cos(angle); s=math.sin(angle)
        values={"X":position[0],"Y":position[1],"Z":position[2],"R00":c,"R01":0,"R02":s,
                "R10":0,"R11":1,"R12":0,"R20":-s,"R21":0,"R22":c}
        for key,val in values.items(): ET.SubElement(node,key).text=str(round(float(val),5))
    materials={"Plastic":256,"SmoothPlastic":272,"Neon":288,"Wood":512,"WoodPlanks":528,
               "Slate":800,"Concrete":816,"Brick":848,"Metal":1088,"Grass":1280}
    def add_part(parent,part,cls="Part"):
        obj=ET.SubElement(parent,"Item",{"class":cls,"referent":"RBX"+uuid.uuid4().hex.upper()})
        props=ET.SubElement(obj,"Properties")
        ET.SubElement(props,"bool",{"name":"Anchored"}).text="true"
        ET.SubElement(props,"bool",{"name":"CanCollide"}).text="true" if part.get("can_collide",True) else "false"
        add_cframe(props,part["position"],part.get("yaw",0))
        add_color(props,part["color"])
        ET.SubElement(props,"token",{"name":"Material"}).text=str(materials.get(part.get("material"),816))
        ET.SubElement(props,"string",{"name":"Name"}).text=str(part["name"])[:80]
        ET.SubElement(props,"float",{"name":"Reflectance"}).text="0"
        ET.SubElement(props,"float",{"name":"Transparency"}).text=str(round(float(part.get("transparency",0)),3))
        add_vector(props,part["size"],"size")
        return obj

    workspace,workspace_props=add(root,"Workspace","Workspace")
    ET.SubElement(workspace_props,"float",{"name":"Gravity"}).text="196.2"
    for part in scene["parts"][:70]: add_part(workspace,part)
    sx,sy,sz=scene["spawn"]
    spawn={"name":"GameKI_SpawnLocation","size":[7,1,7],"position":[sx,sy,sz],
           "color":[.18,.78,.45],"material":"Neon","can_collide":True,"transparency":0,"yaw":0}
    spawn_item=add_part(workspace,spawn,"SpawnLocation")
    spawn_props=spawn_item.find("Properties")
    ET.SubElement(spawn_props,"bool",{"name":"Neutral"}).text="true"
    ET.SubElement(spawn_props,"float",{"name":"Duration"}).text="0"
    add(root,"ReplicatedStorage","ReplicatedStorage")
    lighting,lighting_props=add(root,"Lighting","Lighting")
    ET.SubElement(lighting_props,"float",{"name":"Brightness"}).text="2"
    add_color(lighting_props,[.28,.30,.34],"Ambient")
    server_service,_=add(root,"ServerScriptService","ServerScriptService")
    _,server_props=add(server_service,"Script","GameKI_Server")
    ET.SubElement(server_props,"ProtectedString",{"name":"Source"}).text=scripts["server"]
    ET.SubElement(server_props,"bool",{"name":"Disabled"}).text="false"
    starter_player,starter_player_props=add(root,"StarterPlayer","StarterPlayer")
    # Keep the real Roblox avatar and its native third-person camera/control stack.
    ET.SubElement(starter_player_props,"float",{"name":"CameraMinZoomDistance"}).text="0.5"
    ET.SubElement(starter_player_props,"float",{"name":"CameraMaxZoomDistance"}).text="24"
    ET.SubElement(starter_player_props,"bool",{"name":"LoadCharacterAppearance"}).text="true"
    ET.SubElement(starter_player_props,"bool",{"name":"EnableMouseLockOption"}).text="true"
    player_scripts,_=add(starter_player,"StarterPlayerScripts","StarterPlayerScripts")
    _,client_props=add(player_scripts,"LocalScript","GameKI_Client")
    ET.SubElement(client_props,"ProtectedString",{"name":"Source"}).text=scripts["client"]
    ET.SubElement(client_props,"bool",{"name":"Disabled"}).text="false"
    output=ET.tostring(root,encoding="utf-8",xml_declaration=True)
    parsed=ET.fromstring(output)
    if len(parsed.findall(".//Item[@class='Part']"))<20:
        raise ValueError("Die Place-Datei hat zu wenig 3D-Level-Geometrie. Mindestens 20 bearbeitbare Parts sind erforderlich.")
    if len(parsed.findall(".//ProtectedString[@name='Source']"))<2:
        raise ValueError("Die Place-Datei enthält nicht beide Roblox-Scripts.")
    return output


def publish_bytes(payload, content_type="application/xml", config=None):
    key, universe, place = roblox_env(config)
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
            detail=response.json()
        except ValueError:
            detail=response.text[:400]
        app.logger.warning("Roblox publish rejected HTTP %s",response.status_code)
        if response.status_code in (401,403):
            message=("Roblox lehnt den Schlüssel für die angeforderte Experience ab. "
                     "Die API-Berechtigung universe-places mit Write muss genau für die Experience freigegeben sein, "
                     "zu der die gesendete Universe ID gehört. Prüfe außerdem, ob die Place ID zu dieser Universe ID gehört "
                     "und ob Game KI den aktuellen Schlüssel verwendet.")
            # Echo only non-secret identifiers so a scope failure can be diagnosed without exposing credentials.
            return jsonify({
                "error":message,
                "details":str(detail)[:600],
                "universeId":universe,
                "placeId":place
            }),response.status_code
        return jsonify({"error":"Roblox hat die Veröffentlichung abgelehnt (HTTP "+str(response.status_code)+").",
                        "details":str(detail)[:600]}),502
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


@app.get("/resolve-place")
def resolve_place():
    """Resolve a Roblox Place ID to its owning Universe ID using Roblox's public endpoint."""
    if not authorized():
        return auth_error()
    place = str(request.args.get("place_id", "")).strip()
    if not (place.isdigit() and 1 <= len(place) <= 24):
        return err("Place ID muss eine gültige Zahl sein.", 400)
    try:
        response = requests.get(
            "https://apis.roblox.com/universes/v1/places/" + place + "/universe",
            timeout=(5, 12),
        )
        if response.status_code == 404:
            return err("Roblox findet zu dieser Place ID keine Experience. Prüfe die ID.", 404)
        if not response.ok:
            return err("Roblox konnte die Universe ID gerade nicht ermitteln (HTTP " + str(response.status_code) + ").", 502)
        payload = response.json()
        universe = str(payload.get("universeId", "")).strip()
        if not (universe.isdigit() and 1 <= len(universe) <= 24):
            return err("Roblox hat keine gültige Universe ID für diese Place ID zurückgegeben.", 502)
        return jsonify({"place_id": place, "universe_id": universe})
    except requests.Timeout:
        return err("Zeitüberschreitung beim Ermitteln der Universe ID. Versuche es erneut.", 504)
    except requests.RequestException:
        return err("Roblox ist gerade nicht erreichbar, um die Universe ID zu ermitteln.", 502)
    except (ValueError, TypeError):
        return err("Roblox hat ungültige Daten für diese Place ID zurückgegeben.", 502)


@app.get("/roblox-preview")
def roblox_preview():
    if not authorized():
        return auth_error()
    universe=str(request.args.get("universe_id","")).strip()
    place=str(request.args.get("place_id","")).strip()
    if not (universe.isdigit() and 1<=len(universe)<=24 and place.isdigit() and 1<=len(place)<=24):
        return err("Universe ID und Place ID müssen gültige Zahlen sein.",400)
    try:
        game_response=requests.get("https://games.roblox.com/v1/games",params={"universeIds":universe},timeout=(5,12))
        if not game_response.ok:
            return err("Roblox-Spieldaten sind gerade nicht verfügbar (HTTP "+str(game_response.status_code)+").",502)
        results=game_response.json().get("data",[])
        if not results:
            return err("Keine öffentliche Experience für diese Universe ID gefunden. Prüfe die ID und veröffentliche das Spiel.",404)
        game=results[0]
        thumbnail=""
        thumb_response=requests.get("https://thumbnails.roblox.com/v1/games/"+universe+"/thumbnails",
            params={"size":"768x432","format":"Png","isCircular":"false"},timeout=(5,12))
        if thumb_response.ok:
            for item in thumb_response.json().get("data",[]):
                if item.get("state")=="Completed" and item.get("imageUrl"):
                    thumbnail=item["imageUrl"]
                    break
        creator=game.get("creator") if isinstance(game.get("creator"),dict) else {}
        description=re.sub(r"[\x00-\x1f]"," ",str(game.get("description",""))).strip()
        return jsonify({"universeId":universe,"placeId":place,"name":str(game.get("name","Roblox Experience"))[:120],
            "description":description[:900],"creator":str(creator.get("name","Roblox Creator"))[:120],
            "playing":int(game.get("playing",0) or 0),"visits":int(game.get("visits",0) or 0),
            "maxPlayers":int(game.get("maxPlayers",0) or 0),"thumbnailUrl":thumbnail,
            "url":"https://www.roblox.com/games/"+place})
    except requests.Timeout:
        return err("Zeitüberschreitung beim Laden der Roblox-Experience. Versuche es erneut.",504)
    except requests.RequestException:
        return err("Roblox ist gerade nicht erreichbar, um die Experience anzuzeigen.",502)
    except (ValueError,TypeError):
        return err("Roblox hat ungültige Spieldaten zurückgegeben.",502)

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
            scene_context = previous.get("roblox_scene")
            scene_text = json.dumps(scene_context, ensure_ascii=False)[:16000] if isinstance(scene_context, (dict, list)) else ""
            prompt = ("Erweitere das bestehende Projekt, starte nicht neu. Ursprünglicher Auftrag: " + original[:4000]
                      + "\nBisheriger Luau-Code:\n" + code[:35000]
                      + "\nBisherige HTML-Demo:\n" + web_demo[:35000]
                      + "\nBisherige editierbare Roblox-Szene:\n" + scene_text
                      + "\nNeue Änderung:\n" + prompt)

    try:
        result = generate_components(prompt.strip(), provider)
        try:
            validate_roblox_scripts(result["roblox_code"])
            validate_secret_console(prompt.strip(), result)
        except ValueError as initial_error:
            repair_prompt = (
                "Repair the following existing game without changing its idea. Return raw artifacts, NOT JSON. "
                "Fix the validation issue: " + str(initial_error)
                + "\nRequested game:\n" + prompt.strip()[:3500]
                + "\nCurrent Roblox scripts:\n" + result["roblox_code"][:24000]
                + "\nCurrent browser demo:\n" + result["web_simulation"][:24000]
                + "\nReturn complete updated Roblox Luau scripts with both exact markers and a complete standalone playable HTML5 game."
            )
            repaired = generate_components(repair_prompt, provider)
            validate_roblox_scripts(repaired["roblox_code"])
            validate_secret_console(prompt.strip(), repaired)
            result = repaired
        return jsonify({
            "roblox_code": result["roblox_code"],
            "web_simulation": result["web_simulation"],
            "roblox_scene": result["roblox_scene"],
        })
    except RuntimeError as exc:
        return err(str(exc), 503)
    except ValueError as exc:
        return err(str(exc), 502)
    except Exception as exc:
        message = str(exc)
        app.logger.warning("AI provider %s failed: %s", provider, type(exc).__name__)
        lower = message.lower()
        if "json_validate_failed" in lower or "failed to generate json" in lower:
            return err("Der KI-Anbieter hat das große JSON-Paket abgelehnt. Bitte erneut versuchen; die getrennte Generierung sollte diesen Fehler vermeiden.", 502)
        if "timeout" in lower or "timed out" in lower or "deadline" in lower:
            return err("Die KI hat zu lange gebraucht. Versuche es mit einer kürzeren Spielbeschreibung erneut.", 504)
        return err("KI-Generierung fehlgeschlagen (" + provider + "): " + message[:180], 502)

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
        payload = place_xml(data["roblox_code"], str(data.get("game_name", "Game KI"))[:90], data.get("roblox_scene"))
        if len(payload) > 4 * 1024 * 1024:
            return err("Place-Datei größer als 4 MiB.", 413)
        return publish_bytes(payload, config=data.get("roblox_config"))
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
