import os
from pathlib import Path

from safecor import ConnectionType, MqttClient


class DevModeHelper:
    @staticmethod
    def create_mqtt_client(identifier: str) -> MqttClient:
        return MqttClient(identifier, ConnectionType.TCP_DEBUG, "localhost")

    @staticmethod
    def set_qt_plugins_path():
        python_version = "3.13"
        venv_path = os.getenv("VIRTUAL_ENV")
        plugins_path = (
            f"{venv_path}/lib/python{python_version}/site-packages/PySide6/Qt/plugins/platforms"
        )
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugins_path

    @staticmethod
    def get_mocked_source_disk_path() -> str:
        # current_script_path = Path(__file__).resolve()
        # root_path = current_script_path.parent.parent.parent.parent
        # root_path = Path("/Applications/Adobe Acrobat DC/Adobe Acrobat.app/Contents/Frameworks").resolve()
        # root_path = Path("/Applications").resolve()
        root_path = Path("/").resolve()
        return root_path.as_posix()

    @staticmethod
    def get_mocked_destination_disk_path() -> str:
        return "/tmp/safecor/OUT"

    @staticmethod
    def get_storage_path() -> str:
        return "/tmp/safecor/repository"
