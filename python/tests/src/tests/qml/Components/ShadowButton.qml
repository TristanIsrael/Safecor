import QtQuick
import QtQuick.Effects

Item {
    id: root

    property alias icon: txt.text
    property bool outlined: true
    property color taint: enabled ? Environment.colorButtonEnabled : Environment.colorButtonDisabled

    signal clicked()

    width: implicitWidth
    height: implicitHeight
    implicitWidth: 80
    implicitHeight: 80
    clip: false        

    Text {
        id: txt     
        anchors.fill: parent       
        font.family: outlined ? "Material Icons Outlined" : "Material Icons"
        text: Constants.iconHelp
        font.pixelSize: parent.height*0.8
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        color: root.enabled ? Environment.colorButtonTextEnabled : Environment.colorButtonTextDisabled
    }

    MultiEffect {
        id: shadow
        source: txt
        anchors.fill: root
        shadowEnabled: true
        shadowColor: '#cccccc' //root.enabled ? Environment.colorShadowEnabled : Environment.colorShadowDisabled
        shadowBlur: 1.0 // root.enabled ? 1.0 : 0.2
        shadowScale: 1.5
    }
    

    MouseArea {
        anchors.fill: parent

        onClicked: {
            if(!root.enabled)
                return
            root.clicked()
        }
    }
}
