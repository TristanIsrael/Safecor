import QtQuick
import QtQuick.Shapes

Shape {
    id: root

    property alias strokeColor: path.strokeColor
    property alias strokeWidth: path.strokeWidth
    property bool clockwise: true

    width: implicitWidth
    height: implicitHeight
    implicitHeight: 100
    implicitWidth: 100

    ShapePath {
        id: path

        strokeWidth: 2
        strokeColor: "#442a8dc5"
        fillColor: "transparent"
        capStyle: ShapePath.SquareCap

        startX: root.clockwise ? 0 : root.width
        startY: 0

        PathArc {
            x: path.startX
            y: root.height
            radiusX: root.height /2
            radiusY: root.height /2
            useLargeArc: false
            direction: root.clockwise ? PathArc.Clockwise : PathArc.Counterclockwise
        }

    }

}
