import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

Item {
    id: root
    implicitHeight: 220

    ColumnLayout {
        anchors.fill: parent
        spacing: 6

        // --- Actions timeline (top) -------------------------------------
        GroupBox {
            title: qsTr("Actions")
            Layout.fillWidth: true
            Layout.preferredHeight: 150

            RowLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                LogListView {
                    id: actionsArea
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
                ColumnLayout {
                    spacing: 4
                    Button {
                        text: qsTr("Clear")
                        onClicked: {
                            actionsArea.clear()
                            ConsoleController.clear_actions()
                        }
                    }
                    Button {
                        text: qsTr("Copy")
                        onClicked: actionsArea.copySelected()
                    }
                }
            }
        }

        // --- MQTT events + platform log (bottom, tabs) ------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            TabBar {
                id: tabs
                Layout.fillWidth: true
                TabButton { text: qsTr("MQTT events") }
                TabButton { text: qsTr("Platform log") }
            }
            Button {
                text: qsTr("Copy")
                onClicked: (tabs.currentIndex === 0 ? mqttArea : logArea).copySelected()
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            LogListView {
                id: mqttArea
            }
            LogListView {
                id: logArea
            }
        }
    }

    Connections {
        target: ConsoleController

        function onActionLogged(line) {
            actionsArea.append(line)
        }
        function onMqttEventLogged(line) {
            mqttArea.append(line)
        }
        function onLogLine(line) {
            logArea.append(line)
        }
    }
}
