pragma Singleton
import QtQuick

QtObject {
    readonly property int mainWidth: 1200
    readonly property int mainHeight: 900

    readonly property int light: 1
    readonly property int dark: 2
    readonly property int lowVisibility: 3
    readonly property int wireframe: 4

    readonly property string iconMenu: "\ue5d2"
    readonly property string iconSystemState: "\ue9e4"
    readonly property string iconLog: "\ue896"
    readonly property string iconRestart: "\uf053"
    readonly property string iconShutdown: "\ue8ac"
    readonly property string iconHelp: "\ue887"
    readonly property string iconStart: "\ue037"
    readonly property string iconPause: "\ue034"
    readonly property string iconThemeLight: "\ue518"
    readonly property string iconThemeDark: "\uf036"
    readonly property string iconThemeLowVisibility: "\ue8f5"
    readonly property string iconFile: "\ue24d"
    readonly property string iconFolder: "\ue2c7"
    readonly property string iconFolderUp: "\ue9a3"
    readonly property string iconChecked: "\uf1fe"
    readonly property string iconUnchecked: "\ue835"
    readonly property string iconCore: "\ue726"
    readonly property string iconAntivirus: "\ue9e0"

    readonly property string battery_0: "\uf306"
    readonly property string battery_15: "\uf30b"
    readonly property string battery_30: "\uf30a"
    readonly property string battery_45: "\uf309"
    readonly property string battery_60: "\uf308"
    readonly property string battery_75: "\uf307"
    readonly property string battery_100: "\uf304"

    enum Section {
        Paragraph,
        Title1,
        Title2,
        Title3
    }
}
