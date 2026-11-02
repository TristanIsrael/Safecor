import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import safecor.emulator 1.0

Item {
    id: root
    implicitHeight: 168

    // Native file picker for the topology (fills the path field). Declared
    // with only an ``onAccepted`` handler so it still instantiates on minimal
    // / offscreen Qt builds (which lack the advanced FileDialog properties).
    FileDialog {
        id: topologyFileDialog
        onAccepted: {
            console.debug(String(selectedFile).replace("file://", ""))
            topologyPathField.text = String(selectedFile).replace("file://", "")
        }
    }

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
                Label { text: qsTr("Topology:") }
                TextField {
                    id: topologyPathField
                    Layout.fillWidth: true
                    selectByMouse: true
                    placeholderText: qsTr("path to topology.json")
                    Component.onCompleted: text = ConsoleController.topologyPath
                }
                Button {
                    text: qsTr("Browse...")
                    onClicked: topologyFileDialog.open()
                }
                Button {
                    text: qsTr("Load")
                    enabled: !ConsoleController.running
                    onClicked: ConsoleController.load_topology(topologyPathField.text)
                }
            }

            RowLayout {
                Label { text: qsTr("Configuration:") }
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
