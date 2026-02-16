import QtQuick
import QtQuick.Controls
import net.alefbet

Window {
    id: window

    property bool landscape: width < height
    
    //anchors.fill: parent
    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint
    visible: true    

    MainScreen {
        anchors.fill: parent
    }

    Component.onCompleted: {
        console.log("Landscape mode: " + (landscape ? "Yes" : "No"))
        console.log("Working on: " +Qt.platform.os)
    }    

    onWidthChanged: {
        if( (window.width < window.height) && !landscape ) {            
            console.log("Automatically switch to landscape mode")
            landscape = true   
        }
    }  

    onVisibleChanged: {  
        if(visible)      
            console.log("Screen resolution: " +Qt.application.screens[0].width +"x" +Qt.application.screens[0].height)
    }
}
