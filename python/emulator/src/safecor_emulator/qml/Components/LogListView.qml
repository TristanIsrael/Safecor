import QtQuick
import QtQuick.Controls

Item {
    id: root

    // Add a line to the list (journal / event / log streams). The view
    // auto-scrolls to the newest line.
    function append(line) {
        model.append({ "line": line })
        list.positionViewAtEnd()
    }

    // Remove all the lines.
    function clear() {
        model.clear()
    }

    // Copy all the lines to the clipboard.
    function copySelected() {
        var lines = []
        for (var j = 0; j < model.count; j++) {
            lines.push(model.get(j).line)
        }
        if (lines.length > 0 && Qt.clipboard) {
            Qt.clipboard.setText(lines.join("\n"))
        }
    }

    ListModel { id: model }

    ListView {
        id: list
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: model
        delegate: Label {
            width: list.width
            text: line
            font.pointSize: 12
            elide: Text.ElideRight
            padding: 2
        }

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
        }
    }
}
