"""
Configuración central de Proyecto Petra - Dashboard.

MODE controla de dónde vienen los datos:
  - "mock": datos simulados, no requiere ROS ni la Raspberry conectada.
  - "ros":  datos reales, se conecta a ROS (roscore corriendo en la Raspberry
            o en esta misma máquina, según tu ROS_MASTER_URI).

Puedes cambiar el modo de 3 formas (en orden de prioridad):
  1. Variable de entorno:  PETRA_MODE=ros python app.py
  2. Editando MODE abajo.
  3. Desde el propio dashboard (switch en la esquina superior derecha) si
     habilitas ALLOW_RUNTIME_SWITCH.
"""
import os

# "mock" o "ros"
MODE = os.environ.get("PETRA_MODE", "mock")

# Si True, el dashboard muestra un switch para alternar entre mock/ros
# sin reiniciar el servidor (útil mientras desarrollas).
ALLOW_RUNTIME_SWITCH = True

# --- Configuración de ROS (solo se usa si MODE == "ros") ---
ROS_CONFIG = {
    # Tópicos que publica el robot (ajusta a los nombres reales que uses)
    "battery_topic": "/battery_state",       # sensor_msgs/BatteryState
    "temperature_topic": "/system_temperature",  # std_msgs/Float32 (°C)
    "camera_status_topic": "/camera/status", # std_msgs/Bool  (True = ok)
    "pose_topic": "/amcl_pose",              # geometry_msgs/PoseWithCovarianceStamped
    # Acción/tópico para enviar metas de navegación (move_base clásico)
    "goal_topic": "/move_base_simple/goal",  # geometry_msgs/PoseStamped
    "map_frame": "map",
}

# --- Mapa de referencia mientras no exista el mapa SLAM real ---
# Rectángulo de trabajo en metros (ancho x alto). El robot se mueve
# dentro de este rango. Cuando tengas el mapa SLAM real, esto se
# reemplaza por la imagen/occupancy-grid real (ver README).
#
# "rooms" son a la vez los lugares visibles en el mapa Y los destinos
# que aparecen en el menú de navegación. El robot navega al centro
# de la sala elegida.
MAP_CONFIG = {
    "width_m": 20.0,
    "height_m": 14.0,
    "rooms": [
        {"name": "Aula A", "x": 1, "y": 1, "w": 6, "h": 5},
        {"name": "Aula B", "x": 13, "y": 1, "w": 6, "h": 5},
        {"name": "Aula C", "x": 1, "y": 8, "w": 6, "h": 5},
    ],
    # radio (en metros) para considerar que el robot "está" en una sala
    "room_detection_radius_m": 2.0,
}

# Umbrales para las alertas del panel de estadísticas
THRESHOLDS = {
    "battery_low_pct": 20,
    "temperature_high_c": 70.0,
}

SECRET_KEY = "petra-dev-key"
HOST = "0.0.0.0"
PORT = 5000
