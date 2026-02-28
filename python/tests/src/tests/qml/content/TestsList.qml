import QtQuick
import QtQuick.Layouts
import Components
import Safecor

Item {
    width: implicitWidth
    height: implicitHeight
    implicitWidth: 600
    implicitHeight: 800

    ColumnLayout {
        anchors.fill: parent
        spacing: 20

        ListView {
            id: root

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            model: bindings.testsListModel

            delegate: ProgressListEntry {
                implicitWidth: 600

                label: model.label
                progress: model.progress
                success: model.success
                isPackage: model.isPackage
            }
        }
    }

    Bindings {
        id: bindings
    }

    Component.onCompleted: {
        console.debug(bindings, bindings.testsListModel)
    }
}
