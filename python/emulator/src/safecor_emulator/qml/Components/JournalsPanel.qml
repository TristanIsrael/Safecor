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

                ListView {
                    id: actionsList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: []
                    delegate: Text {
                        text: modelData
                        elide: Text.ElideRight
                        width: actionsList.width
                        font.pointSize: 12
                    }
                }
                Button {
                    text: qsTr("Clear")
                    Layout.alignment: Qt.AlignBottom
                    onClicked: {
                        actionsList.model = []
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

            ListView {
                id: mqttList
                clip: true
                model: []
                delegate: Text {
                    text: modelData
                    elide: Text.ElideRight
                    width: mqttList.width
                    font.pointSize: 12
                }
            }
            ListView {
                id: logList
                clip: true
                model: []
                delegate: Text {
                    text: modelData
                    elide: Text.ElideRight
                    width: logList.width
                    font.pointSize: 12
                }
            }
        }
    }

    Connections {
        target: ConsoleController

        function onActionLogged(event) {
            actionsList.model.push(event.source + ": " + event.text)
        }
        function onMqttEventLogged(event) {
            mqttList.model.push(event.source + ": " + event.text)
        }
        function onLogLine(line) {
            logList.model.push(line)
        }
    }
}
