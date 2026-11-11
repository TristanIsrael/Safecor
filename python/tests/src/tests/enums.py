from enum import Enum

from PySide6.QtCore import QEnum, QObject, Qt
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "Safecor"
QML_IMPORT_MAJOR_VERSION = 1


class MessageLevel(Enum):
    User, Information, Warning, Error = range(4)


class Roles:
    RoleProgress = Qt.UserRole + 1
    RoleIsPackage = Qt.UserRole + 2
    RoleSection = Qt.UserRole + 3
    RoleLabel = Qt.UserRole + 4
    RoleSuccess = Qt.UserRole + 5
    RoleCriticity = Qt.UserRole + 6
    RoleDateTime = Qt.UserRole + 7


@QmlElement
class Enums(QObject):
    QEnum(MessageLevel)
