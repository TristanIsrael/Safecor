import QtQuick
import Safecor
import Components

QtObject {
    id: root

    /* Bindings */
    property bool handheld: true
    property bool ready: AppController.ready
    property bool running: AppController.running
    property int batteryLevel: 100
    property bool plugged: true
    property bool ambientLightSensorReady: false
    property int ambientLight: 0 // 0 (dark) - 100 (sunny)
    property int systemState: 0
    property int nbTestsTotal: AppController.nbTestsTotal
    property int nbTestsFailed: AppController.nbTestsFailed
    property int nbTestsSucceeded: AppController.nbTestsSucceeded
    property int nbCapacitiesTotal: AppController.nbCapacitiesTotal
    property int nbCapacitiesFailed: 0
    property int nbCapacitiesSucceeded: 0    

    /* Models */
    property var testsListModel: AppController.testsListModel
    property var messagesModel: AppController.messagesModel

    /* System states */
    readonly property color systemStateColor: {
        if(!bindings.ready) {
            return Environment.colorFilterNotReady
        } else {
            if(bindings.infected) {
                return Environment.colorFilterInfected
            } else if(bindings.used) {
                return Environment.colorFilterUsed
            }
        }

        return Environment.colorFilterReady
    }

    /* Functions */


    /**
        For development only
    */
    property var debugMessages: ListModel { }

    property var modelTest: ListModel {
            ListElement {
                display: "Capacité 1"
                RoleProgress: 20
                RoleSuccess: false
            }

            ListElement {
                display: "Un premier test pour voir"
                RoleProgress: 100
                RoleSuccess: true
            }

            ListElement {
                display: "Test bidule pour le machin"
                RoleProgress: 96
            }
        }

}
