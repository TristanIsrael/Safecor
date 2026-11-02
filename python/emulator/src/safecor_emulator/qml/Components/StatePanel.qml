import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

Item {
    id: root
    implicitHeight: 220

    GroupBox {
        anchors.fill: parent
        title: qsTr("State")

        GridLayout {
            anchors.fill: parent
            anchors.topMargin: 8
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            columns: 2
            columnSpacing: 12
            rowSpacing: 4

            Text { text: qsTr("Product"); font.bold: true }
            Text {
                id: productText
                objectName: "stateProduct"
                text: ConsoleController.productName || qsTr("(none)")
            }

            Text { text: qsTr("Languages"); font.bold: true }
            Text {
                text: (ConsoleController.languages.length ? ConsoleController.languages.join(", ") : qsTr("(none)"))
                     + qsTr("  (default: ") + ConsoleController.defaultLanguage + ")"
            }

            Text { text: qsTr("Screen"); font.bold: true }
            Text {
                text: ConsoleController.screenWidth + "×" + ConsoleController.screenHeight
                     + qsTr("   rotation: ") + ConsoleController.screenRotation
                     + qsTr("   focus: ") + (ConsoleController.screenDefaultFocus || "-")
            }

            Text { text: qsTr("USB"); font.bold: true }
            Text { text: ConsoleController.useUsb ? qsTr("enabled") : qsTr("disabled") }

            Text { text: qsTr("Business domains"); font.bold: true }
            Text {
                text: ConsoleController.businessDomains.length
                     ? ConsoleController.businessDomains.join(", ")
                     : qsTr("(none)")
            }

            Text { text: qsTr("Energy"); font.bold: true }
            Text {
                text: Math.round(ConsoleController.energyLevel) + "%   "
                     + (ConsoleController.plugged ? qsTr("AC plugged") : qsTr("on battery"))
            }

            Text { text: qsTr("Broker"); font.bold: true }
            Text {
                text: qsTr("port ") + ConsoleController.brokerPort
                     + (ConsoleController.running
                        ? (ConsoleController.brokerOwned ? qsTr(" (embedded)") : qsTr(" (external)"))
                        : qsTr(" (stopped)"))
            }

            Text { text: qsTr("Peers"); font.bold: true }
            Text {
                text: ConsoleController.peersConnected.length
                     ? ConsoleController.peersConnected.join(", ")
                     : qsTr("(none)")
            }

            Text { text: qsTr("Restarted domains"); font.bold: true }
            Text {
                text: ConsoleController.restartedDomains.length
                     ? ConsoleController.restartedDomains.join(", ")
                     : qsTr("(none)")
            }
        }
    }
}
