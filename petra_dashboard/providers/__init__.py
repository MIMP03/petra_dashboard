from providers.mock_provider import MockProvider


def create_provider(mode):
    """Factory: crea el proveedor de datos según el modo pedido.
    Si se pide 'ros' pero rospy no está disponible, cae a mock avisando
    por consola en vez de tumbar el servidor entero.
    """
    if mode == "ros":
        try:
            from providers.ros_provider import RosProvider
            return RosProvider()
        except ImportError as e:
            print(
                f"[petra] No se pudo cargar el modo ROS ({e}). "
                "Verifica que rospy esté instalado y ROS_MASTER_URI configurado. "
                "Arrancando en modo MOCK mientras tanto."
            )
            return MockProvider()
    return MockProvider()
