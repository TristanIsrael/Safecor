import QtQuick
import Components

Text {
    id: root

    property int section: Constants.Section.Paragraph

    font.family: "Inter"
    text: "Text"
    color: Environment.colorText
    font.pixelSize: {
        switch(root.section) {
        case Constants.Section.Title1: return 24
        case Constants.Section.Title2: return 22
        case Constants.Section.Title3: return 20
        case Constants.Section.Paragraph: return 18
        }

        return 18
    }
}
