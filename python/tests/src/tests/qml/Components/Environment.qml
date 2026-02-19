pragma Singleton
import QtQuick
import Components

QtObject {
    id: root

    property bool handheld: false
    property bool portrait: false

    property int theme: Constants.dark

    property int mainWidth: 1200
    property int mainHeight: 800    

    /** Colors */
    readonly property color colorOverlay: "#bb010101"
    readonly property color colorDark: "#010101"
    readonly property color colorClear: "#eaeaea"
    readonly property color colorBg: "#333333"
    readonly property color colorControl: "#333333"
    readonly property color colorText: "#aafafafa"
    readonly property color colorBorder: "#aafafafa"
    readonly property color colorButtonEnabled: "#d8d8d8"
    readonly property color colorButtonDisabled: "#444480"
    readonly property color colorPanelEnabled: "#444480"
    readonly property color colorPanelDisabled: "#666666"
    readonly property color colorShadowEnabled: "#aaeaeaea"
    readonly property color colorShadowDisabled: "#aaeaeaea"
    readonly property color colorButtonTextEnabled: "#aafafafa"
    readonly property color colorButtonTextDisabled: "#030303"

    readonly property color colorFilterNotReady: "#b0c4de"
    readonly property color colorFilterReady: "#656dfd"
    readonly property color colorFilterUsed: "#ffa500"
    readonly property color colorFilterInfected: "#ff0000"

    readonly property color colorSuccess: "#4CAF50"
    readonly property color colorFailure: "#F44330"    
    readonly property color colorRunning: "#66656dfd"

    readonly property color colorUserMessage: "#4CAF50"
    readonly property color colorWarning: "#ffa500"
    readonly property color colorError: "#F44330"

    readonly property color colorSelected: "#66656dfd"

}
