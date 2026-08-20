"""
Proveedor ROS: se conecta a los tópicos reales del robot.
Requisitos en la máquina (el host):
  - ROS instalado (o al menos rospy) y variables de entorno apuntando al
    roscore correcto:
        export ROS_MASTER_URI=http://<IP_RASPBERRY>:11311
        export ROS_IP=<IP_DE_ESTA_COMPUTADORA>
  - Que el roscore esté corriendo en la Raspberry (o donde sse levante)

Este provider NO hace overhead en la Raspberry: solo se suscribe a los
tópicos que el robot ya publica, y le manda la meta de navegación cuando
el usuario la pide desde el dashboard. Todo el cómputo del dashboard
(HTTP, WebSocket, HTML) corre en esta computadora o el host

por ultimo se justa los nombres de tópicos en config.py en: ROS_CONFIG según lo que
tenga el robot
"""
import threading
from datetime import datetime

from providers.base_provider import BaseProvider
from config import ROS_CONFIG


class RosProvider(BaseProvider):
    def __init__(self):
        self._lock = threading.Lock()
        self._on_update = None
        self._running = False

        self._latest = {
            "timestamp": None,
            "battery": {"level": None, "charging": None},
            "camera": {"enabled": True, "status": "unknown"},
            "temperature": {"cpu": None},
            "autonomy": {"remaining_minutes": None, "distance_traveled_m": None},
            "position": {"x": 0.0, "y": 0.0, "theta": 0.0},
            "goal": None,
            "mode": "ros",
        }
        self._last_pos = None
        self._distance_traveled_m = 0.0

    def start(self, on_update):
        self._on_update = on_update
        self._running = True

        # Import perezoso: si rospy no está instalado, el resto de la app
        # (modo mock) sigue funcionando sin romperse.
        import rospy
        from sensor_msgs.msg import BatteryState
        from std_msgs.msg import Float32, Bool
        from geometry_msgs.msg import PoseWithCovarianceStamped

        self._rospy = rospy
        rospy.init_node("petra_dashboard_bridge", anonymous=True, disable_signals=True)

        rospy.Subscriber(ROS_CONFIG["battery_topic"], BatteryState, self._on_battery)
        rospy.Subscriber(ROS_CONFIG["temperature_topic"], Float32, self._on_temperature)
        rospy.Subscriber(ROS_CONFIG["camera_status_topic"], Bool, self._on_camera)
        rospy.Subscriber(ROS_CONFIG["pose_topic"], PoseWithCovarianceStamped, self._on_pose)

        from geometry_msgs.msg import PoseStamped
        self._PoseStamped = PoseStamped
        self._goal_pub = rospy.Publisher(ROS_CONFIG["goal_topic"], PoseStamped, queue_size=1)

        # rospy corre su propio loop; lo he hecho en un hilo para no bloquear Flask
        self._spin_thread = threading.Thread(target=rospy.spin, daemon=True)
        self._spin_thread.start()

    def stop(self):
        self._running = False
        try:
            self._rospy.signal_shutdown("petra_dashboard cerrado")
        except Exception:
            pass

    def get_telemetry(self):
        with self._lock:
            return dict(self._latest)

    def send_goal(self, x, y):
        from geometry_msgs.msg import PoseStamped
        msg = PoseStamped()
        msg.header.frame_id = ROS_CONFIG["map_frame"]
        msg.header.stamp = self._rospy.Time.now()
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.orientation.w = 1.0
        self._goal_pub.publish(msg)
        with self._lock:
            self._latest["goal"] = {"x": x, "y": y}
        return {"ok": True, "message": f"Meta publicada en {ROS_CONFIG['goal_topic']}"}

    def get_photos(self):
        # Si finalmente hacemos un tópico/servicio de imágenes, aquí es donde se
        # conectaría para listar fotos capturadas. placeholder por ahora
        return []

   -
    def _touch(self):
        with self._lock:
            self._latest["timestamp"] = datetime.now().isoformat(timespec="seconds")
            snapshot = dict(self._latest)
        if self._on_update:
            self._on_update(snapshot)

    def _on_battery(self, msg):
        with self._lock:
            level = msg.percentage
            # BatteryState.percentage puede venir 0-1 o 0-100 según el driver
            if level is not None and level <= 1.0:
                level = level * 100.0
            self._latest["battery"] = {
                "level": round(level, 1) if level is not None else None,
                "charging": bool(getattr(msg, "power_supply_status", 0) == 1),
            }
        self._touch()

    def _on_temperature(self, msg):
        with self._lock:
            self._latest["temperature"] = {"cpu": round(msg.data, 1)}
        self._touch()

    def _on_camera(self, msg):
        with self._lock:
            self._latest["camera"] = {
                "enabled": True,
                "status": "ok" if msg.data else "error",
            }
        self._touch()

    def _on_pose(self, msg):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        with self._lock:
            if self._last_pos is not None:
                dx = x - self._last_pos[0]
                dy = y - self._last_pos[1]
                self._distance_traveled_m += (dx ** 2 + dy ** 2) ** 0.5
            self._last_pos = (x, y)
            self._latest["position"] = {"x": round(x, 2), "y": round(y, 2), "theta": 0.0}
            self._latest["autonomy"]["distance_traveled_m"] = round(
                self._distance_traveled_m, 1
            )
        self._touch()
