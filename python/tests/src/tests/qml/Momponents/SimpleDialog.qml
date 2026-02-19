import QtQuick
import QtQuick.Layouts
import Components

Rectangle {
    id: itemRoot

    property bool handheld: false
    property bool overlay: false
    property var buttonsLabels: [ labelOk, labelCancel ]
    property var contentItem: Item { width: 400; height: 300}

    readonly property string labelOk: qsTr("Ok")
    readonly property string labelAccept: qsTr("Yes")
    readonly property string labelReject: qsTr("No")
    readonly property string labelCancel: qsTr("Cancel")

    signal accepted()
    signal rejected()
    signal buttonClicked(string label)

    width: implicitWidth
    height: implicitHeight
    implicitWidth: overlay || handheld ? Environment.mainWidth : root.width
    implicitHeight: overlay || handheld ? Environment.mainHeight : root.height
    color: overlay || handheld ? Environment.colorOverlay : "transparent"
    z: 100

    PanelBase {
        id: root

        anchors.centerIn: parent

        width: itemRoot.contentItem.width
        height: itemRoot.handheld ? itemRoot.contentItem.height : itemRoot.contentItem.height + lyt.height + 10
        radius: 10

        Component.onCompleted: {
            root.children.push(itemRoot.contentItem)
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
