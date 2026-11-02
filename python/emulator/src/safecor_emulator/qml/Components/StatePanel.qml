import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

ColumnLayout {
    id: root
    //implicitHeight: 220

    SystemPalette {
        id: appPalette
    }

    GroupBox {
        Layout.fillWidth: true
        title: qsTr("State")

        GridLayout {
            anchors.fill: parent
            anchors.topMargin: 8
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            columns: 2
            columnSpacing: 12
            rowSpacing: 4

            Label { text: qsTr("Product"); font.bold: true }
            Label {
                objectName: "stateProduct"
                text: ConsoleController.productName || qsTr("(none)")
                color: appPalette.text
            }

            Label { text: qsTr("Languages"); font.bold: true }
            Label {
                text: (ConsoleController.languages.length ? ConsoleController.languages.join(", ") : qsTr("(none)"))
                     + qsTr("  (default: ") + ConsoleController.defaultLanguage + ")"
            }

            Label { text: qsTr("Screen"); font.bold: true }
            Label {
                text: ConsoleController.screenWidth + "×" + ConsoleController.screenHeight
                     + qsTr("   rotation: ") + ConsoleController.screenRotation
                     + qsTr("   focus: ") + (ConsoleController.screenDefaultFocus || "-")
            }

            Label { text: qsTr("USB"); font.bold: true }
            Label { text: ConsoleController.useUsb ? qsTr("enabled") : qsTr("disabled") }

            Label { text: qsTr("Business domains"); font.bold: true }
            Label {
                text: ConsoleController.businessDomains.length
                     ? ConsoleController.businessDomains.join(", ")
                     : qsTr("(none)")
            }

            Label { text: qsTr("Energy"); font.bold: true }
            Label {
                text: Math.round(ConsoleController.energyLevel) + "%   "
                     + (ConsoleController.plugged ? qsTr("AC plugged") : qsTr("on battery"))
            }

            Label { text: qsTr("Broker"); font.bold: true }
            Label {
                text: qsTr("port ") + ConsoleController.brokerPort
                     + (ConsoleController.running
                        ? (ConsoleController.brokerOwned ? qsTr(" (embedded)") : qsTr(" (external)"))
                        : qsTr(" (stopped)"))
            }

            Label { text: qsTr("Peers"); font.bold: true }
            Label {
                text: ConsoleController.peersConnected.length
                     ? ConsoleController.peersConnected.join(", ")
                     : qsTr("(none)")
            }

            Label { text: qsTr("Restarted domains"); font.bold: true }
            Label {
                text: ConsoleController.restartedDomains.length
                     ? ConsoleController.restartedDomains.join(", ")
                     : qsTr("(none)")
            }
        }
    }
}
