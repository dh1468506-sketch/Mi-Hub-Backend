from fastapi import FastAPI, Request
import requests, os, base64, json
from urllib.parse import quote

app = FastAPI()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO", "dh1468506-sketch/Mi-hub-Scripts")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

pendientes = {}

@app.post("/submit")
async def submit(request: Request):
    data = await request.json()
    script_id = str(len(pendientes) + 1)
    pendientes[script_id] = data
    
    if DISCORD_WEBHOOK:
        embed = {
            "title": f"Nuevo script: {data['nombre']}",
            "description": f"Autor: {data['autor']}\nJuego: {data['juego']}",
            "color": 0x00ff00,
            "fields": [
                {"name": "ID", "value": script_id, "inline": True},
                {"name": "Estado", "value": "Pendiente de aprobación", "inline": True}
            ]
        }
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
    
    return {"status": "ok", "id": script_id}

@app.post("/approve/{script_id}")
async def approve(script_id: str):
    if script_id not in pendientes:
        return {"error": "No existe"}
    data = pendientes[script_id]
    exito = subir_a_github(data['nombre'], data['codigo'], data['juego'])
    if exito:
        del pendientes[script_id]
        return {"status": "aprobado"}
    return {"error": "Fallo al subir a GitHub"}

def subir_a_github(nombre, codigo, juego):
    nombre_archivo = nombre.replace(" ", "_") + ".lua"
    path = f"scripts/{juego}/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    content = base64.b64encode(codigo.encode()).decode()
    data = {"message": f"Add {nombre}", "content": content}
    r = requests.put(url, json=data, headers=HEADERS)
    if r.status_code in [200, 201]:
        actualizar_index(nombre, juego, path)
        return True
    return False

def actualizar_index(nombre, juego, path):
    url = f"https://api.github.com/repos/{REPO}/contents/index.json"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        content = base64.b64decode(r.json()['content']).decode()
        index = json.loads(content)
        sha = r.json()['sha']
    else:
        index = []
        sha = None
    
    # Codificar el path para que los espacios se conviertan en %20
    path_seguro = quote(path)
    
    encontrado = False
    for item in index:
        if item['nombre'] == nombre:
            item['juego'] = juego
            item['url'] = f"https://raw.githubusercontent.com/{REPO}/main/{path_seguro}"
            encontrado = True
            break
    if not encontrado:
        index.append({
            "nombre": nombre,
            "juego": juego,
            "url": f"https://raw.githubusercontent.com/{REPO}/main/{path_seguro}"
        })
    
    nuevo_content = base64.b64encode(json.dumps(index, indent=2).encode()).decode()
    data = {"message": "Update index", "content": nuevo_content}
    if sha:
        data["sha"] = sha
    requests.put(url, json=data, headers=HEADERS)
