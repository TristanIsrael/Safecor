import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Components
import net.alefbet

Rectangle {
    implicitWidth: 800
    implicitHeight: 600

    color: Colors.background

    anchors {
        fill: parent
    }

    Rectangle {
        id: frame
        anchors {
            fill: parent
            margins: 10
        }

        color: "transparent"
        border {
            color: Colors.cyan
            width: 1
        }
    }

    Rectangle {
        anchors {
            horizontalCenter: title.horizontalCenter
        }
        width: title.width + 20
        height: title.height
        color: parent.color
    }

    PText {
        id: title
        anchors {
            horizontalCenter: parent.horizontalCenter
        }
        text: qsTr("Safecor Diagnostics")
        font.pixelSize: 18
    }

    Item {
        anchors {
            left: frame.left
            right: frame.right
            top: title.bottom
            bottom: frame.bottom
            margins: 10
        }

        Rectangle {
            id: rctDescription
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
            }
            color: Colors.black
            height: lblDescription.height

            PText {
                id: lblDescription
                anchors {
                    left: parent.left
                    right: parent.right
                    top: parent.top
                }

                font.pixelSize: 20
                wrapMode: Text.WordWrap
                padding: 10
                text: qsTr("This tool diagnoses the hardware and verifies whether it allows a product based on Safecor to run with different levels of capabilities and security.")
            }
        }

        RowLayout {
            anchors {
                top: rctDescription.bottom
                topMargin: 20
                left: parent.left
                right: parent.right
                bottom: buttons.top
            }

            HardwareCapabilities {}

            SecurityCapabilities {}
        }

        RowLayout {
            id: buttons

            anchors {
                bottom: parent.bottom
                left: parent.left
                right: parent.right
            }
            spacing: 20

            Item {
                Layout.fillWidth: true
            }

            /*PButton {
                text: qsTr("Quit app (Ctrl-C)")

                onClicked: function() {
                    Qt.quit()
                }
            }*/

            PButton {
                text: qsTr("Shutdown (Ctrl-C)")

                onClicked: function() {
                    AppController.shutdown()
                }
            }

            Item {
                Layout.fillWidth: true
            }
        }
    }
}
