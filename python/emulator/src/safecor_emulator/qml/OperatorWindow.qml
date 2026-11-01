import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Components

Item {
    id: root

    RowLayout {
        anchors.fill: parent
        spacing: 8

        // Left column: setup + controls
        ColumnLayout {
            Layout.fillHeight: true
            Layout.preferredWidth: 380
            Layout.minimumWidth: 320
            Layout.maximumWidth: 460
            spacing: 8

            SetupPanel {
                Layout.fillWidth: true
            }

            ControlPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        // Right column: state + journals
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            StatePanel {
                Layout.fillWidth: true
                Layout.preferredHeight: 220
            }

            JournalsPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }
    }
}
