import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    objectName: "operatorWindow"

    width: 1100
    height: 650
    minimumWidth: 900
    minimumHeight: 500
    visible: true
    title: qsTr("Safecor Emulator — Operator Console")

    font.family: "Roboto"
    font.pointSize: 13

    OperatorWindow {
        id: operatorWindow
        anchors.fill: parent
    }
    
}
