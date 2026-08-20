"""
Proyecto Petra - Dashboard
Servidor host (corre en una computadora, NO en la Raspberry).

Arrancar:
    python app.py                    # modo definido en config.py (mock por defecto)
    PETRA_MODE=ros python app.py     # fuerza modo ROS

El robot (Raspberry) nunca recibe peticiones pesadas: este servidor solo
escucha los tópicos ROS que el robot ya publica (modo ros) o simula datos
localmente (modo mock), y sirve la interfaz web a quien la abra en el navegador.
"""
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO
import os

import config
from providers import create_provider

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Estado del modo actual (puede cambiar en caliente si ALLOW_RUNTIME_SWITCH)
state = {"mode": config.MODE, "provider": None}


def _room_at(x, y):
    """Devuelve el nombre de la sala que contiene el punto (x, y), o None."""
    for room in config.MAP_CONFIG["rooms"]:
        if room["x"] <= x <= room["x"] + room["w"] and room["y"] <= y <= room["y"] + room["h"]:
            return room["name"]
    return None


def _room_center(name):
    for room in config.MAP_CONFIG["rooms"]:
        if room["name"] == name:
            return room["x"] + room["w"] / 2, room["y"] + room["h"] / 2
    return None


def _enrich_with_room(snapshot):
    pos = snapshot.get("position") or {}
    snapshot["current_room"] = _room_at(pos.get("x", -1), pos.get("y", -1))
    return snapshot


def _on_telemetry_update(snapshot):
    """Callback que llaman los providers cada vez que hay datos nuevos."""
    _enrich_with_room(snapshot)
    socketio.emit("telemetry", snapshot)
    _check_alerts(snapshot)


def _check_alerts(snapshot):
    alerts = []
    batt = snapshot.get("battery", {}).get("level")
    if batt is not None and batt <= config.THRESHOLDS["battery_low_pct"]:
        alerts.append({"type": "battery_low", "message": f"Batería baja: {batt}%"})

    temp = snapshot.get("temperature", {}).get("cpu")
    if temp is not None and temp >= config.THRESHOLDS["temperature_high_c"]:
        alerts.append({"type": "temp_high", "message": f"Temperatura alta: {temp}°C"})

    cam = snapshot.get("camera", {})
    if cam.get("enabled") and cam.get("status") == "error":
        alerts.append({"type": "camera_error", "message": "La cámara no enciende"})

    if alerts:
        socketio.emit("alerts", alerts)


def start_provider(mode):
    if state["provider"] is not None:
        state["provider"].stop()
    provider = create_provider(mode)
    provider.start(_on_telemetry_update)
    state["provider"] = provider
    state["mode"] = mode
    print(f"[petra] Proveedor de datos activo: {mode}")


# ---------------- Rutas HTTP ----------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        map_config=config.MAP_CONFIG,
        allow_switch=config.ALLOW_RUNTIME_SWITCH,
        current_mode=state["mode"],
    )


@app.route("/api/telemetry")
def api_telemetry():
    return jsonify(_enrich_with_room(state["provider"].get_telemetry()))


@app.route("/api/locations")
def api_locations():
    telemetry = state["provider"].get_telemetry()
    pos = telemetry.get("position") or {}
    current_room = _room_at(pos.get("x", -1), pos.get("y", -1))
    rooms = [
        {"name": r["name"]}
        for r in config.MAP_CONFIG["rooms"]
        if r["name"] != current_room
    ]
    return jsonify({"current_room": current_room, "destinations": rooms})


@app.route("/api/navigate", methods=["POST"])
def api_navigate():
    data = request.get_json(force=True)
    location = data.get("location")
    if not location:
        return jsonify({"ok": False, "message": "Falta indicar el destino"}), 400

    center = _room_center(location)
    if center is None:
        return jsonify({"ok": False, "message": "Destino no reconocido"}), 400

    telemetry = state["provider"].get_telemetry()
    pos = telemetry.get("position") or {}
    if _room_at(pos.get("x", -1), pos.get("y", -1)) == location:
        return jsonify({"ok": False, "message": "El robot ya está en ese lugar"}), 400

    x, y = center
    result = state["provider"].send_goal(x, y)
    result["destination_name"] = location
    return jsonify(result)


@app.route("/api/photos")
def api_photos():
    return jsonify(state["provider"].get_photos())


@app.route("/photos/<path:filename>")
def photos_static(filename):
    return send_from_directory(os.path.join("static", "photos"), filename)


@app.route("/api/mode", methods=["GET", "POST"])
def api_mode():
    if not config.ALLOW_RUNTIME_SWITCH:
        return jsonify({"ok": False, "message": "Cambio de modo deshabilitado"}), 403
    if request.method == "GET":
        return jsonify({"mode": state["mode"]})

    data = request.get_json(force=True)
    new_mode = data.get("mode")
    if new_mode not in ("mock", "ros"):
        return jsonify({"ok": False, "message": "Modo inválido"}), 400
    start_provider(new_mode)
    return jsonify({"ok": True, "mode": state["mode"]})


@socketio.on("connect")
def on_connect():
    # Al conectar, mándale al cliente el último dato conocido de una vez
    socketio.emit("telemetry", _enrich_with_room(state["provider"].get_telemetry()))


if __name__ == "__main__":
    start_provider(state["mode"])
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True,  # servidor de desarrollo: suficiente para uso local en el host
    )
