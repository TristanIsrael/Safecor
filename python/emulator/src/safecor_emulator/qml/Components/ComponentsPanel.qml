import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

GroupBox {
    id: root
    title: qsTr("Components")

    // Periodic refresh while the emulator is running (1.15: an up-to-date list).
    Timer {
        interval: 4000
        running: ConsoleController.running
        repeat: true
        onTriggered: ConsoleController.refresh_components()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 8
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        anchors.bottomMargin: 8
        spacing: 2

        // Header row
        RowLayout {
            Label { text: qsTr("Component"); Layout.preferredWidth: 240; font.bold: true }
            Label { text: qsTr("State"); Layout.fillWidth: true; font.bold: true }
        }
        // Data rows
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: ConsoleController.components
            delegate: RowLayout {
                Layout.fillWidth: true
                Label { text: modelData["name"]; Layout.preferredWidth: 240; elide: Text.ElideRight }
                Label { text: modelData["state"]; Layout.fillWidth: true }
            }
        }
    }
}
