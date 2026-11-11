from datetime import datetime

from enums import MessageLevel, Roles
from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Slot


class MessagesListModel(QAbstractListModel):
    __messages = []  # List of dicts

    def __init__(self, parent: QObject):
        super().__init__(parent)

    def rowCount(self, parent=QModelIndex()):
        return len(self.__messages)

    def data(self, index, role):
        if not index.isValid():
            return None

        if len(self.__messages) <= index.row():
            return None

        item = self.__messages[index.row()]

        if role == Roles.RoleLabel:
            return item.get("message")
        elif role == Roles.RoleCriticity:
            return item.get("criticity")
        elif role == Roles.RoleDateTime:
            return item.get("datetime")

    @Slot(str, MessageLevel)
    def add_message(
        self, message: str, criticity: MessageLevel = MessageLevel.Information
    ):
        self.beginInsertRows(QModelIndex(), len(self.__messages), len(self.__messages))
        self.__messages.append(
            {
                "datetime": datetime.now().strftime(self.tr("%Y-%m-%d %H:%M:%S")),
                "message": message,
                "criticity": criticity.value,
            }
        )
        self.endInsertRows()

    def roleNames(self) -> dict:
        roles = {
            Roles.RoleProgress: b"progress",
            Roles.RoleIsPackage: b"isPackage",
            Roles.RoleLabel: b"label",
            Roles.RoleSuccess: b"success",
            Roles.RoleCriticity: b"criticity",
            Roles.RoleDateTime: b"datetime",
        }

        return roles
