import QtQuick
import Components

PanelBase {
    id: btn

    property string label: lbl.text

    width: implicitWidth
    height: implicitHeight
    implicitWidth: lbl.width *1.2
    implicitHeight: 70

    radius: height / 5
    borderWidth: 2

    Text {
        id: lbl
        anchors.centerIn: parent
        text: "Button"
        color: btn.enabled ? Environment.colorButtonTextEnabled : Environment.colorButtonTextDisabled
        font.pixelSize: parent.height * 0.6
        fontSizeMode: Text.HorizontalFit
    }
}
