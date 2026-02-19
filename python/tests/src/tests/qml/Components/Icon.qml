import QtQuick
import Components

Item {
    id: root

    property alias text: txt.text

    signal clicked()

    width: implicitWidth
    height: implicitHeight
    implicitHeight: 24
    implicitWidth: 24

    Text {
        id: txt
        anchors.fill: parent
        font.family: "Material Symbols Outlined"
        font.pixelSize: height * 0.9
        verticalAlignment: Text.AlignVCenter
        color: Environment.colorText
        text: Constants.iconFile
    }

    MouseArea {
        anchors.fill: parent

        onClicked: function() {
            root.clicked()
        }
    }
}
