import QtQuick
import QtQuick.Effects

Item {
    id: root

    property bool outlined: true
    property alias icon: txt.text
    property color taint: enabled ? Environment.colorButtonEnabled : Environment.colorButtonDisabled
    property int borderWidth: enabled ? 7 : 1
    property bool highlight: true
    property bool flat: false

    signal clicked()

    width: implicitWidth
    height: implicitHeight
    implicitWidth: 80
    implicitHeight: 80
    clip: false

    Circle { // Wrapper
        id: wrapper

        anchors.centerIn: parent
        width: root.width
        height: root.height
        visible: !root.flat

        borderWidth: root.borderWidth
        borderColor: root.enabled ? Qt.alpha(Qt.lighter(root.taint, 2.5), 0.9) : root.taint

        MultiEffect {
            anchors.fill: parent
            visible: !root.flat

            source: ShaderEffectSource {
                width: wrapper.width
                height: wrapper.height

                sourceItem: back
                sourceRect: Qt.rect(wrapper.x, wrapper.y, wrapper.width, wrapper.height)
                hideSource: true
                live: true
            }

            anchors {
                fill: wrapper
            }

            brightness: root.enabled ? 0.7 : 0.2
            saturation: root.enabled ? 0.1 : 0.0
            blurEnabled: true
            blurMax: 45
            blur: 0.7
            colorization: 0.3
            colorizationColor: root.taint
            autoPaddingEnabled: false
            maskEnabled: true
            maskSource: ShaderEffectSource {
                sourceItem: Circle {
                    color: "white"
                    width: wrapper.width
                    height: wrapper.height
                    layer.enabled: true
                    borderWidth: 10
                }
            }
        }        
    }

    MultiEffect {
        id: shadow
        visible: !root.flat
        source: wrapper
        anchors.fill: wrapper
        shadowEnabled: true
        shadowColor: root.enabled ? Environment.colorShadowEnabled : Environment.colorShadowDisabled
        shadowBlur: root.enabled ? 1.0 : 0.2
    }

    Item {
        anchors {
            centerIn: wrapper
        }

        width: wrapper.width *0.8
        height: wrapper.width *0.8

        Text {
            id: txt
            anchors.fill: parent
            font.family: outlined ? "Material Icons Outlined" : "Material Icons"
            text: Constants.iconHelp
            font.pixelSize: parent.height
            color: root.enabled ? Environment.colorButtonTextEnabled : Environment.colorButtonTextDisabled
        }
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
