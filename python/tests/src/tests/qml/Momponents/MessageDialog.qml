import QtQuick
import QtQuick.Layouts
import Components

Rectangle {
    id: itemRoot

    property bool handheld: true
    property alias label: txt.text
    property var buttonsLabels: [ labelOk, labelCancel ]

    readonly property string labelOk: qsTr("Ok")
    readonly property string labelAccept: qsTr("Yes")
    readonly property string labelReject: qsTr("No")
    readonly property string labelCancel: qsTr("Cancel")

    signal accepted()
    signal rejected()
    signal buttonClicked(string label)

    implicitWidth: handheld ? Environment.mainWidth : root.implicitWidth
    implicitHeight: handheld ? Environment.mainHeight : root.implicitHeight
    color: handheld ? Environment.colorOverlay : "transparent"
    z: 100

    PanelBase {
        id: root

        anchors.centerIn: parent

        width: implicitWidth
        height: implicitHeight
        implicitWidth: Environment.mainWidth/3
        implicitHeight: Environment.mainHeight/3
        radius: 10

        Text {
            id: txt
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                bottom: itemRoot.handheld ? parent.bottom : lyt.top
                margins: height/10
            }

            text: "Message dialog"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: Environment.colorText
            font.pixelSize: height
            fontSizeMode: Text.HorizontalFit
        }

        RowLayout {
            id: lyt
            visible: buttonsLabels.length > 0 && !itemRoot.handheld

            anchors {
                bottom: parent.bottom
                bottomMargin: 20
                left: parent.left
                right: parent.right
            }

            Item {
                Layout.fillWidth: true
            }

            Repeater {
                id: rpt
                model: buttonsLabels

                Rectangle {
                    width: 100
                    height: 50

                    color: "transparent"
                    border {
                        width: 2
                        color: "#fafafa"
                    }

                    StyledText {
                        id: btnText
                        anchors.fill: parent
                        text: modelData
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: parent.height * 0.4
                        font.capitalization: Font.SmallCaps
                    }

                    MouseArea {
                        anchors.fill: parent

                        onClicked: function() {
                            if(btnText.text === labelAccept || btnText.text === labelOk) {
                                itemRoot.accepted()
                            }

                            if(btnText.text === labelCancel || btnText.text === labelReject) {
                                itemRoot.rejected()
                            }

                            itemRoot.buttonClicked(btnText.text)
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }
    }

    // Buttons for handheld mode
    Repeater {
        id: rptButtonsHandheld
        model: buttonsLabels        

        Panel {
            width: 100
            height: 100
            visible: itemRoot.handheld
            anchors {
                verticalCenter: parent.verticalCenter
            }
            x: index === 1 ? width * 0.25 : (parent.width - width - width*0.25)
            radius: height

            RoundButton {
                flat: true
                borderWidth: 2
                anchors.fill: parent

                icon: ""

                StyledText {
                    id: btnText2
                    anchors.fill: parent
                    text: modelData
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    font.bold: true
                    font.pixelSize: parent.height * 0.4
                    font.capitalization: Font.SmallCaps
                }


                onClicked: function() {
                    if(btnText2.text === labelAccept || btnText2.text === labelOk) {
                        itemRoot.accepted()
                    }

                    if(btnText2.text === labelCancel || btnText2.text === labelReject) {
                        itemRoot.rejected()
                    }

                    itemRoot.buttonClicked(btnText2.text)
                }

            }
        }
    }
}
