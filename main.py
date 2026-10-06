from fastapi import FastAPI, Request
import requests, os, base64, json
from urllib.parse import quote

app = FastAPI()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO", "dh1468506-sketch/Mi-hub-Scripts")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

pendientes = {}

def obtener_userid_roblox(username):
    """Busca el ID y nombre de Roblox a partir del nombre de usuario."""
    try:
        url = "https://users.roblox.com/v1/usernames/users"
        body = {"usernames": [username], "excludeBannedUsers": True}
        r = requests.post(url, json=body, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0]["id"], data["data"][0].get("displayName", username)
    except Exception as e:
        print(f"Error buscando Roblox ID: {e}")
    return None, None

@app.post("/submit")
async def submit(request: Request):
    data = await request.json()
    script_id = str(len(pendientes) + 1)
    pendientes[script_id] = data
    
    if DISCORD_WEBHOOK:
        embed = {
            "title": f"Nuevo script: {data['nombre']}",
            "description": f"Discord: {data['autor']}\nRoblox: {data.get('autor_roblox', 'Desconocido')}\nJuego: {data['juego']}",
            "color": 0x00ff00,
            "fields": [
                {"name": "ID", "value": script_id, "inline": True},
                {"name": "Estado", "value": "Pendiente", "inline": True}
            ]
        }
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
    
    return {"status": "ok", "id": script_id}

@app.post("/approve/{script_id}")
async def approve(script_id: str):
    if script_id not in pendientes:
        return {"error": "No existe"}
    data = pendientes[script_id]
    
    # Buscar el ID de Roblox
    userid_roblox, display_roblox = obtener_userid_roblox(data.get("autor_roblox", ""))
    data["autor_userid"] = userid_roblox
    data["autor_display"] = display_roblox or data.get("autor_roblox", "Anónimo")
    
    exito = subir_a_github(data['nombre'], data['codigo'], data['juego'], data)
    if exito:
        del pendientes[script_id]
        return {"status": "aprobado"}
    return {"error": "Fallo al subir a GitHub"}

def subir_a_github(nombre, codigo, juego, data):
    nombre_archivo = nombre.replace(" ", "_") + ".lua"
    path = f"scripts/{juego}/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    content = base64.b64encode(codigo.encode()).decode()
    
    # Verificar si ya existe
    r = requests.get(url, headers=HEADERS)
    put_data = {"message": f"Add {nombre}", "content": content}
    if r.status_code == 200:
        put_data["sha"] = r.json()["sha"]
    
    r = requests.put(url, json=put_data, headers=HEADERS)
    if r.status_code in [200, 201]:
        actualizar_index(data, juego, path)
        return True
    return False

def actualizar_index(data, juego, path):
    url = f"https://api.github.com/repos/{REPO}/contents/index.json"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        content = base64.b64decode(r.json()['content']).decode()
        index = json.loads(content)
        sha = r.json()['sha']
    else:
        index = []
        sha = None
    
    path_seguro = quote(path)
    nombre = data['nombre']
    
    encontrado = False
    for item in index:
        if item['nombre'] == nombre:
            item['juego'] = juego
            item['url'] = f"https://raw.githubusercontent.com/{REPO}/main/{path_seguro}"
            item['autor_display'] = data.get("autor_display", "Anónimo")
            item['autor_userid'] = data.get("autor_userid")
            encontrado = True
            break
    if not encontrado:
        index.append({
            "nombre": nombre,
            "juego": juego,
            "url": f"https://raw.githubusercontent.com/{REPO}/main/{path_seguro}",
            "autor_display": data.get("autor_display", "Anónimo"),
            "autor_userid": data.get("autor_userid")
        })
    
    nuevo_content = base64.b64encode(json.dumps(index, indent=2).encode()).decode()
    put_data = {"message": "Update index", "content": nuevo_content}
    if sha:
        put_data["sha"] = sha
    requests.put(url, json=put_data, headers=HEADERS)
