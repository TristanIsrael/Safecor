import QtQuick
import Components
import Safecor

MainScreenUi {
    id: window

    //anchors.fill: parent
    focus: true

    property point mouse_last_position

    //anchors.fill: parent
    backFilter.colorizationColor: bindings.systemStateColor

    /* Slots */
    Connections {
        target: window.btnStartStop
        
        function onClicked() {
            AppController.start_stop()
        }
    }

    Connections {
        target: window.btnSkipTest

        function onClicked() {
            AppController.skip_test()
        }
    }

    Connections {
        target: window.btnShutdown

        function onClicked() {
            AppController.shutdown()
        }
    }

    HoverHandler {
        id: mouseHandler
        acceptedDevices: PointerDevice.Mouse

        onPointChanged: function() {            

            if(mouseHandler.point.position !== window.mouse_last_position)
                window.mouse_last_position = mouseHandler.point.position
                AppController.mouse_moved()
        }
    } 

    HoverHandler {
        id: touchHandler
        acceptedDevices: PointerDevice.TouchScreen

        onPointChanged: function() {            

            if(mouseHandler.point.position !== window.mouse_last_position)
                window.mouse_last_position = mouseHandler.point.position
                AppController.screen_touched()
        }
    }   

    Keys.onPressed: (event) => {
        AppController.userText += event.text
    }

    Bindings {
        id: bindings
    }

}

