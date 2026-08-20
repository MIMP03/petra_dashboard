"""
contrato común que debe cumplir cualquier proveedor de datos del robot,
sea simulado (mock) o real (ROS). Gracias a esto, app.py y el frontend
no necesitan saber de dónde vienen los datos.
"""
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Todo proveedor debe poder:
    1) arrancar/detenerse
    2) entregar el último estado de telemetría conocido
    3) recibir una orden de navegación (origen -> destino)
    """

    @abstractmethod
    def start(self, on_update):
        """Arranca el proveedor. `on_update(telemetry_dict)` se debe llamar
        cada vez que haya datos nuevos (el server los reenvía por WebSocket)."""
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

    @abstractmethod
    def get_telemetry(self):
        """Devuelve el último snapshot de telemetría conocido."""
        raise NotImplementedError

    @abstractmethod
    def send_goal(self, x, y):
        """Envía al robot la orden de moverse a la posición (x, y) en metros,
        dentro del frame del mapa. El origen es la posición actual del robot,
        no hace falta especificarlo."""
        raise NotImplementedError

    @abstractmethod
    def get_photos(self):
        """Devuelve una lista de fotos disponibles (opcional, cámara)."""
        raise NotImplementedError
        #esta es la parte que no se como conectar con el slam
