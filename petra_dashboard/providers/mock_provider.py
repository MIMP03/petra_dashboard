"""
Hola nikoool, te explico esta parte. el proveedor MOCK: simula un robot moviéndose dentro del mapa de referencia,
con batería bajando lentamente, temperatura, cámara que a veces
"falla" (eso esta simulado) para poder ver cómo se comportan las alertas del dashboard.

No requiere ROS ni la Raspberry conectada, sirve para desarrollar y probar
la interfaz ya mismo.
"""
import math
import random
import threading
import time
from datetime import datetime

from providers.base_provider import BaseProvider
from config import MAP_CONFIG


class MockProvider(BaseProvider):
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._on_update = None

        w, h = MAP_CONFIG["width_m"], MAP_CONFIG["height_m"]
        first_room = MAP_CONFIG["rooms"][0]
        start_x = first_room["x"] + first_room["w"] / 2
        start_y = first_room["y"] + first_room["h"] / 2
        self._pos = {"x": start_x, "y": start_y, "theta": 0.0}
        self._goal = None  
        self._speed_mps = 0.6  # velocidad simulada del robot

        self._battery_pct = 87.0
        self._charging = False
        self._camera_ok = True
        self._temperature_c = 42.0
        self._distance_traveled_m = 0.0
        self._t0 = time.time()

    # ---------- ciclo de vida ----------
    def start(self, on_update):
        self._on_update = on_update
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    # ---------- API pública ----------
    def get_telemetry(self):
        with self._lock:
            return self._snapshot()

    def send_goal(self, x, y):
        with self._lock:
            self._goal = {"x": x, "y": y}
        return {"ok": True, "message": f"Meta enviada: ({x:.2f}, {y:.2f})"}

    def get_photos(self):
        # En modo mock no hay fotos reales; se deja vacío a propósito.
        # Cuando se conectee la camara real, el ROS provider llenará esto.
        return []

    # ---------- simulación interna ----------
    def _loop(self):
        tick = 0.5  
        while self._running:
            with self._lock:
                self._simulate_step(tick)
                snapshot = self._snapshot()
            if self._on_update:
                self._on_update(snapshot)
            time.sleep(tick)

    def _simulate_step(self, dt):
        if self._goal:
            dx = self._goal["x"] - self._pos["x"]
            dy = self._goal["y"] - self._pos["y"]
            dist = math.hypot(dx, dy)
            if dist < 0.05:
                self._goal = None
            else:
                step = min(self._speed_mps * dt, dist)
                self._pos["x"] += dx / dist * step
                self._pos["y"] += dy / dist * step
                self._pos["theta"] = math.atan2(dy, dx)
                self._distance_traveled_m += step
                # moverse consume bateria un poco más rápido
                self._battery_pct -= 0.03

        # Batería baja lentamente con el tiempo (standby)
        self._battery_pct -= 0.01
        if self._battery_pct <= 15 and not self._charging:
            self._charging = True
        if self._charging:
            self._battery_pct += 0.4
            if self._battery_pct >= 95:
                self._charging = False
        self._battery_pct = max(0.0, min(100.0, self._battery_pct))

        # Temperatura fluctúa alrededor de una media(tambien simulado)
        base = 44 if self._goal else 40
        self._temperature_c += (base - self._temperature_c) * 0.05
        self._temperature_c += random.uniform(-0.4, 0.4)

        # Cámara: falla ocasionalmente (2% de probabilidad por tick) para
        # poder probar la alerta "cámara no enciende"
        if self._camera_ok and random.random() < 0.01:
            self._camera_ok = False
        elif not self._camera_ok and random.random() < 0.1:
            self._camera_ok = True

    def _snapshot(self):
        # Autonomía estimada: minutos restantes según consumo simple
        consumo_pct_por_min = 0.6 if self._goal else 0.15
        minutos_restantes = (
            self._battery_pct / consumo_pct_por_min if consumo_pct_por_min > 0 else 0
        )

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "battery": {
                "level": round(self._battery_pct, 1),
                "charging": self._charging,
            },
            "camera": {
                "enabled": True,  # es opcional pero está instalada
                "status": "ok" if self._camera_ok else "error",
            },
            "temperature": {
                "cpu": round(self._temperature_c, 1),
            },
            "autonomy": {
                "remaining_minutes": round(minutos_restantes, 1),
                "distance_traveled_m": round(self._distance_traveled_m, 1),
            },
            "position": {
                "x": round(self._pos["x"], 2),
                "y": round(self._pos["y"], 2),
                "theta": round(self._pos["theta"], 2),
            },
            "goal": self._goal,
            "mode": "mock",
        }
