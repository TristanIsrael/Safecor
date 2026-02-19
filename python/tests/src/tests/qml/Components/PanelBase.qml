import QtQuick
import QtQuick.Effects

Item {
    id: root

    property alias radius: wrapper.radius
    property color taint: enabled ? Environment.colorPanelEnabled : Environment.colorPanelDisabled
    property int borderWidth: 1
    property bool highlight: true
    property bool flat: false

    width: implicitWidth
    height: implicitHeight
    implicitWidth: 300
    implicitHeight: 300

    Rectangle { // Wrapper
        id: wrapper

        width: root.width + 2*shadow.shadowBlur
        height: root.height + 2*shadow.shadowBlur
        visible: !flat

        border {
            width: root.borderWidth
            color: root.enabled ? Qt.alpha(Qt.lighter(root.taint, 2.5), 0.7) : root.taint
        }

        MultiEffect {
            anchors.fill: parent
            visible: !flat

            source: ShaderEffectSource {
                width: root.width
                height: root.height

                sourceItem: back
                sourceRect: Qt.rect(root.x, root.y, root.width, root.height)
                hideSource: true
                live: true                
            }

            anchors {
                fill: parent
                margins: root.borderWidth
            }

            brightness: root.enabled ? 0.3 : 0.0
            saturation: root.enabled ? 0.1 : 0.0
            blurEnabled: true
            blurMax: 45
            blur: 0.8
            autoPaddingEnabled: false
            maskEnabled: true
            maskSource: ShaderEffectSource {
                sourceItem: Rectangle {
                    color: "white"
                    width: root.width
                    height: root.height
                    radius: wrapper.radius
                    layer.enabled: true
                }
            }
        }

        Rectangle {
            id: highlightGradient
            anchors.fill: parent
            visible: root.highlight && !flat

            radius: wrapper.radius

            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(root.taint.r, root.taint.g, root.taint.b, 0.0) } // ~7 %
                GradientStop { position: 0.7; color: Qt.rgba(root.taint.r, root.taint.g, root.taint.b, 0.13) }
                GradientStop { position: 1.0; color: Qt.rgba(root.taint.r, root.taint.g, root.taint.b, 0.27) }
            }
        }
    }

    MultiEffect {
        id: shadow
        visible: !flat
        source: wrapper
        anchors.fill: wrapper
        shadowEnabled: true
        shadowColor: root.enabled ? Environment.colorShadowEnabled : Environment.colorShadowDisabled
        shadowBlur: root.enabled ? 1.0 : 0.2
    }
}
