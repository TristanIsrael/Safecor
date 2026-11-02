import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Components
import safecor.emulator 1.0

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        // Header: UI-language toggle (localizes the console itself)
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Text { text: qsTr("Interface:") }
            ComboBox {
                id: uiLanguageCombo
                model: ConsoleController.supportedUiLanguages
                Layout.preferredWidth: 70
                Component.onCompleted: {
                    var i = model.indexOf(ConsoleController.uiLanguage)
                    currentIndex = (i === -1) ? 0 : i
                }
                onActivated: ConsoleController.set_ui_language(currentText)
            }
        }

        // Body: two columns
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
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
}
