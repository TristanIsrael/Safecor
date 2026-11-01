import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

Item {
    id: root
    implicitHeight: 220

    GroupBox {
        anchors.fill: parent
        title: "State"

        GridLayout {
            anchors.fill: parent
            anchors.topMargin: 8
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            columns: 2
            columnSpacing: 12
            rowSpacing: 4

            Text { text: "Product"; font.bold: true }
            Text {
                id: productText
                objectName: "stateProduct"
                text: ConsoleController.productName || "(none)"
            }

            Text { text: "Languages"; font.bold: true }
            Text {
                text: (ConsoleController.languages.length ? ConsoleController.languages.join(", ") : "(none)")
                     + "  (default: " + ConsoleController.defaultLanguage + ")"
            }

            Text { text: "Screen"; font.bold: true }
            Text {
                text: ConsoleController.screenWidth + "×" + ConsoleController.screenHeight
                     + "   rotation: " + ConsoleController.screenRotation
                     + "   focus: " + (ConsoleController.screenDefaultFocus || "-")
            }

            Text { text: "USB"; font.bold: true }
            Text { text: ConsoleController.useUsb ? "enabled" : "disabled" }

            Text { text: "Business domains"; font.bold: true }
            Text {
                text: ConsoleController.businessDomains.length
                     ? ConsoleController.businessDomains.join(", ")
                     : "(none)"
            }

            Text { text: "Energy"; font.bold: true }
            Text {
                text: Math.round(ConsoleController.energyLevel) + "%   "
                     + (ConsoleController.plugged ? "AC plugged" : "on battery")
            }

            Text { text: "Broker"; font.bold: true }
            Text {
                text: "port " + ConsoleController.brokerPort
                     + (ConsoleController.running
                        ? (ConsoleController.brokerOwned ? " (owned)" : " (reused)")
                        : " (stopped)")
            }

            Text { text: "Peers"; font.bold: true }
            Text {
                text: ConsoleController.peersConnected.length
                     ? ConsoleController.peersConnected.join(", ")
                     : "(none)"
            }

            Text { text: "Restarted domains"; font.bold: true }
            Text {
                text: ConsoleController.restartedDomains.length
                     ? ConsoleController.restartedDomains.join(", ")
                     : "(none)"
            }
        }
    }
}
