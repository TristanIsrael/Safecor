import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Effects
import Components
import Safecor

Item {
    id: mainWindow

    property alias back: back
    property alias backFilter: backFilter
    property alias pnlMessages: pnlMessages
    property alias btnStartStop: btnStartStop
    property alias btnSkipTest: btnSkipTest

    /* Private properties */
    /*implicitWidth: 1344
    implicitHeight: 768
    width: implicitWidth
    height: implicitHeight*/

    Item {
        id: back
        anchors.fill: parent
        layer.enabled: true

        Image {
            id: imgBack
            anchors.fill: parent
            source: "images/v627-aew-25-technologybackground.jpg"
            fillMode: Image.PreserveAspectCrop
        }

        MultiEffect {
            id: backFilter
            anchors.fill: parent
            source: imgBack
            saturation: 0
            colorization: 1.0
            colorizationColor: Environment.colorFilterNotReady
        }
    }

    TopBar {
        id: topBar
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
        }

        height: parent.height * 0.06
    }
    
    Panel {
        id: pnlStartStop

        x: (parent.width - width) / 2 - width/2 - 10
        y: parent.height - (height * 1.25)
        width: btnStartStop.width
        height: btnStartStop.height
        radius: height

        enabled: bindings.ready

        RoundButton {
            id: btnStartStop
            flat: true
            icon: bindings.running ? Constants.iconPause : Constants.iconStart
        }
    }

    Panel {
        id: pnlSkipTest    

        x: (parent.width - width) / 2 + width/2 + 10
        y: parent.height - (height * 1.25)
        width: btnSkipTest.width
        height: btnSkipTest.height
        radius: height
        visible: bindings.running

        RoundButton {
            id: btnSkipTest
            flat: true
            icon: Constants.iconSkip
        }
    }

    Item {
        id: lytMain

        property int spacing: 20

        anchors {
            top: topBar.bottom
            left: parent.left
            right: parent.right
            bottom: pnlStartStop.top
            margins: height * 0.05
        }

        Panel {
            id: pnlResults

            radius: 10
            width: (parent.width - lytMain.spacing) / 3
            height: results.implicitHeight + results.anchors.margins * 2

            PanelResults {
                id: results
                anchors {
                    fill: parent
                    margins: 10
                }
            }
        }

        Panel {
            id: pnlTests

            radius: 10
            y: pnlResults.height + lytMain.spacing
            width: (parent.width - lytMain.spacing) / 3
            height: parent.height - pnlResults.height - lytMain.spacing

            TestsList {
                anchors {
                    fill: parent
                    margins: 10
                }
            }
        }

        MessagesPanel {
            id: pnlMessages

            x: (parent.width + lytMain.spacing) / 3 + 20
            height: parent.height
            width: (parent.width - lytMain.spacing) * 2/3 - 20
            radius: 10
        }
    }

    Bindings {
        id: bindings
    }
}
