import os,json,re,hmac,uuid,xml.etree.ElementTree as ET
from pathlib import Path
import requests
from flask import Flask,jsonify,render_template,request
from werkzeug.exceptions import RequestEntityTooLarge
ROOT=Path(__file__).resolve().parent.parent
app=Flask(__name__,template_folder=str(ROOT/"templates"))
app.config["MAX_CONTENT_LENGTH"]=4*1024*1024
SYSTEM="""You are Game KI Studio. Return only JSON with two strings: roblox_code and web_simulation. roblox_code: complete playable original server-side Luau Script placed in ServerScriptService, creating a world, spawn, objective, instructions and clear win/lose/progression. Validate player actions server-side. Never include exploits, unauthorized injection, credential theft, remote code loading, require(assetId), or code affecting games not owned by the user. web_simulation: complete self-contained playable HTML document with inline CSS/JS, Canvas/Web APIs, keyboard/touch controls, restart, objective and progress/win/lose. No external assets, libraries, network requests, fetch, WebSocket, cookies, localStorage or imports. Both implementations match the prompt. Follow-up edits extend the existing code. Return JSON only."""
def err(s,c): return jsonify({"error":s}),c
def authorized():
 a=os.environ.get("STUDIO_ACCESS_PASSWORD","").strip();b=request.headers.get("X-Studio-Password","").strip()
 return bool(a and b and hmac.compare_digest(a,b))
def autherr():
 missing=not os.environ.get("STUDIO_ACCESS_PASSWORD","").strip()
 return err("Setze STUDIO_ACCESS_PASSWORD in Vercel Environment Variables." if missing else "Studio-Passwort falsch.",503 if missing else 401)
def ai(prompt,provider):
 if provider=="groq":
  from groq import Groq
  key=os.environ.get("GROQ_API_KEY","").strip()
  if not key: raise RuntimeError("GROQ_API_KEY fehlt in Vercel.")
  response=Groq(api_key=key,timeout=150,max_retries=1).chat.completions.create(model=os.environ.get("GROQ_MODEL","openai/gpt-oss-120b"),messages=[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],temperature=.2,max_completion_tokens=16000,response_format={"type":"json_object"})
  return response.choices[0].message.content
 from google import genai
 from google.genai import types
 key=os.environ.get("GEMINI_API_KEY","").strip()
 if not key: raise RuntimeError("GEMINI_API_KEY fehlt in Vercel.")
 return genai.Client(api_key=key).models.generate_content(model=os.environ.get("GEMINI_MODEL","gemini-3.8-flash"),contents=prompt,config=types.GenerateContentConfig(system_instruction=SYSTEM,response_mime_type="application/json",temperature=.2,max_output_tokens=16000)).text
def parse_ai(raw):
 text=(raw or "").strip()
 if text.startswith(chr(96)*3): text=re.sub("^"+chr(96)*3+"(?:json)?\\s*","",text,count=1,flags=re.I);text=re.sub("\\s*"+chr(96)*3+"$","",text,count=1)
 try: data=json.loads(text)
 except ValueError:
  a,b=text.find("{"),text.rfind("}")
  if a<0 or b<=a: raise ValueError("Die KI lieferte kein gültiges JSON.")
  data=json.loads(text[a:b+1])
 if not isinstance(data,dict) or any(not isinstance(data.get(k),str) or not data[k].strip() for k in ("roblox_code","web_simulation")): raise ValueError("KI-Antwort benötigt roblox_code und web_simulation.")
 if len(data["roblox_code"])>220000 or len(data["web_simulation"])>350000: raise ValueError("KI-Antwort zu groß.")
 return {"roblox_code":data["roblox_code"],"web_simulation":data["web_simulation"]}
def roblox_env():
 key=os.environ.get("ROBLOX_API_KEY","").strip();universe=os.environ.get("ROBLOX_UNIVERSE_ID","").strip();place=os.environ.get("ROBLOX_PLACE_ID","").strip()
 if not all((key,universe,place)): raise RuntimeError("ROBLOX_API_KEY, ROBLOX_UNIVERSE_ID und ROBLOX_PLACE_ID müssen in Vercel gesetzt sein.")
 if not re.fullmatch(r"\\d{1,24}",universe) or not re.fullmatch(r"\\d{1,24}",place): raise ValueError("Roblox-IDs müssen numerisch sein.")
 return key,universe,place
def place_xml(source,title):
 root=ET.Element("roblox",{"version":"4"})
 def add(parent,cls,name):
  obj=ET.SubElement(parent,"Item",{"class":cls,"referent":"RBX"+uuid.uuid4().hex.upper()});props=ET.SubElement(obj,"Properties");ET.SubElement(props,"string",{"name":"Name"}).text=name;return obj,props
 add(root,"Workspace","Workspace");service,_=add(root,"ServerScriptService","ServerScriptService");_,props=add(service,"Script",(title or "Game KI")[:90]);ET.SubElement(props,"ProtectedString",{"name":"Source"}).text=source;ET.SubElement(props,"bool",{"name":"Disabled"}).text="false"
 output=ET.tostring(root,encoding="utf-8",xml_declaration=True);ET.fromstring(output);return output
def publish_bytes(payload,ctype="application/xml"):
 key,universe,place=roblox_env()
 try: response=requests.post("https://apis.roblox.com/universes/v1/"+universe+"/places/"+place+"/versions",params={"versionType":"Published"},headers={"x-api-key":key,"Content-Type":ctype},data=payload,timeout=(10,120))
 except requests.Timeout: return err("Zeitüberschreitung bei Roblox. Prüfe dein Creator Dashboard.",504)
 except requests.RequestException: return err("Roblox Open Cloud ist nicht erreichbar.",502)
 if not response.ok:
  try: detail=response.json()
  except ValueError: detail=response.text[:400]
  app.logger.warning("Roblox publish rejected HTTP %s",response.status_code)
  return jsonify({"error":"Roblox hat die Veröffentlichung abgelehnt (HTTP "+str(response.status_code)+").","details":str(detail)[:600]}),502
 try: result=response.json()
 except ValueError: result={}
 return jsonify({"ok":True,"versionNumber":result.get("versionNumber"),"placeId":place})
@app.get("/")
def home(): return render_template("index.html")
@app.get("/status")
def status():
 return jsonify({"protected":bool(os.environ.get("STUDIO_ACCESS_PASSWORD","").strip()),"groqConfiguredOnServer":bool(os.environ.get("GROQ_API_KEY","").strip()),"geminiConfiguredOnServer":bool(os.environ.get("GEMINI_API_KEY","").strip()),"robloxConfiguredOnServer":all(os.environ.get(k,"").strip() for k in ("ROBLOX_API_KEY","ROBLOX_UNIVERSE_ID","ROBLOX_PLACE_ID"))})
@app.post("/generate")
def generate():
 if not authorized(): return autherr()
 data=request.get_json(silent=True)
 if not isinstance(data,dict): return err("JSON-Auftrag fehlt.",400)
 prompt=data.get("prompt");provider=data.get("provider","groq");previous=data.get("previous")
 if not isinstance(prompt,str) or not prompt.strip(): return err("Beschreibe dein Spiel.",400)
 if len(prompt)>12000: return err("Prompt maximal 12.000 Zeichen.",413)
 if provider not in ("groq","gemini"): return err("Anbieter muss Groq oder Gemini sein.",400)
 if previous is not None:
  if not isinstance(previous,dict): return err("Projektkontext ungültig.",400)
  code,html,original=previous.get("roblox_code",""),previous.get("web_simulation",""),previous.get("original_prompt","")
  if not all(isinstance(x,str) for x in (code,html,original)) or len(code)>100000 or len(html)>100000: return err("Projektkontext ungültig oder zu groß.",413)
  if code or html: prompt="Erweitere das bestehende Projekt, starte nicht neu. Ursprünglicher Auftrag: "+original[:4000]+"\\nBisher Luau:\\n"+code+"\\nBisher HTML:\\n"+html+"\\nNeue Änderung:\\n"+prompt
 try:
  raw=ai(prompt.strip(),provider)
  if not raw: return err("Die KI hat keine Antwort geliefert.",502)
  return jsonify(parse_ai(raw))
 except RuntimeError as exc: return err(str(exc),503)
 except ValueError as exc: return err(str(exc),502)
 except Exception as exc:
  app.logger.warning("AI provider %s failed: %s",provider,type(exc).__name__)
  return err("KI-Generierung fehlgeschlagen: "+str(exc)[:250],502)
@app.post("/publish-generated")
def publish_generated():
 if not authorized(): return autherr()
 data=request.get_json(silent=True)
 if not isinstance(data,dict) or not isinstance(data.get("roblox_code"),str): return err("Roblox-Code fehlt.",400)
 if data.get("confirm_replace") is not True: return err("Bestätige, dass die veröffentlichte Place-Version ersetzt werden darf.",400)
 if len(data["roblox_code"])>220000: return err("Luau-Code zu groß.",413)
 try:
  payload=place_xml(data["roblox_code"],str(data.get("game_name","Game KI"))[:90])
  if len(payload)>4*1024*1024: return err("Place-Datei größer als 4 MiB.",413)
  return publish_bytes(payload)
 except RuntimeError as exc: return err(str(exc),503)
 except ValueError as exc: return err(str(exc),400)
@app.post("/upload")
def upload():
 if not authorized(): return autherr()
 try: _key,universe,place=roblox_env()
 except RuntimeError as exc: return err(str(exc),503)
 except ValueError as exc: return err(str(exc),400)
 file=request.files.get("place_file")
 if file is None or not file.filename: return err("Wähle eine .rbxl- oder .rbxlx-Datei.",400)
 extension=Path(file.filename.rsplit("/",1)[-1].rsplit(chr(92),1)[-1]).suffix.lower()
 if extension not in (".rbxl",".rbxlx"): return err("Nur .rbxl/.rbxlx werden unterstützt.",415)
 payload=file.read(4*1024*1024+1)
 if not payload: return err("Datei leer.",400)
 if len(payload)>4*1024*1024: return err("Datei größer als 4 MiB.",413)
 if extension==".rbxlx":
  try:
   root=ET.fromstring(payload)
   if root.tag!="roblox" or root.get("version")!="4": return err("Ungültige RBXLX-Datei.",400)
  except ET.ParseError: return err("RBXLX enthält ungültiges XML.",400)
  content_type="application/xml"
 else:
  if not payload.startswith(b"<roblox!"): return err("Ungültige binäre Place-Datei.",400)
  content_type="application/octet-stream"
 return publish_bytes(payload,content_type)
@app.errorhandler(RequestEntityTooLarge)
def too_large(_exc): return err("Request überschreitet 4 MiB.",413)
@app.errorhandler(404)
def missing(_exc): return err("Route nicht gefunden.",404)
