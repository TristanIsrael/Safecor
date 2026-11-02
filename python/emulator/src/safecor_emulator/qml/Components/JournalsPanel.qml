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

                TextArea {
                    id: actionsArea
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readOnly: true
                    selectByMouse: true
                    clip: true
                    wrapMode: TextArea.WrapAtWordBoundaryOrAnywhere
                    font.pointSize: 12
                }
                Button {
                    text: qsTr("Clear")
                    Layout.alignment: Qt.AlignBottom
                    onClicked: {
                        actionsArea.clear()
                        ConsoleController.clear_actions()
                    }
                }
            }
        }

        // --- MQTT events + platform log (bottom, tabs) ------------------
        TabBar {
            id: tabs
            Layout.fillWidth: true
            TabButton { text: qsTr("MQTT events") }
            TabButton { text: qsTr("Platform log") }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            TextArea {
                id: mqttArea
                readOnly: true
                selectByMouse: true
                clip: true
                wrapMode: TextArea.WrapAtWordBoundaryOrAnywhere
                font.pointSize: 12
            }
            TextArea {
                id: logArea
                readOnly: true
                selectByMouse: true
                clip: true
                wrapMode: TextArea.WrapAtWordBoundaryOrAnywhere
                font.pointSize: 12
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
