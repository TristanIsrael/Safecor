import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

Item {
    id: root
    implicitHeight: 168

    GroupBox {
        anchors.fill: parent
        title: qsTr("Setup")

        ColumnLayout {
            anchors.fill: parent
            anchors.topMargin: 8
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 6

            RowLayout {
                Text { text: qsTr("Topology:") }
                TextField {
                    id: topologyPathField
                    Layout.fillWidth: true
                    selectByMouse: true
                    placeholderText: qsTr("path to topology.json")
                    Component.onCompleted: text = ConsoleController.topologyPath
                }
                Button {
                    text: qsTr("Load")
                    enabled: !ConsoleController.running
                    onClicked: ConsoleController.load_topology(topologyPathField.text)
                }
            }

            RowLayout {
                Text { text: qsTr("Configuration:") }
                ComboBox {
                    id: configCombo
                    Layout.fillWidth: true
                    model: ["(standard)"].concat(ConsoleController.configurationNames)
                    onActivated: ConsoleController.select_configuration(currentIndex === 0 ? "" : currentText)
                }
            }

            RowLayout {
                Button {
                    text: qsTr("Start")
                    Layout.fillWidth: true
                    enabled: !ConsoleController.running
                    onClicked: ConsoleController.start_emulator()
                }
                Button {
                    text: qsTr("Stop")
                    Layout.fillWidth: true
                    enabled: ConsoleController.running
                    onClicked: ConsoleController.stop_emulator()
                }
            }
        }
    }
}
