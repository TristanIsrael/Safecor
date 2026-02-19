import QtQuick
import QtQuick.Shapes
import Components

Shape {
    id: root

    property alias color: shape.fillColor
    property alias borderColor: shape.strokeColor
    property alias borderWidth: shape.strokeWidth

    width: 100
    height: 100

    layer.enabled: true
    layer.smooth: true    

    ShapePath {
        id: shape
        fillColor: Environment.colorControl
        strokeWidth: 10
        strokeColor: Environment.colorBorder

        readonly property real r: (Math.min(root.width, root.height) - strokeWidth) / 2

        startX: root.width / 2
        startY: (root.height / 2) - shape.r

        PathArc {
            x: root.width / 2
            y: (root.height / 2) + shape.r
            radiusX: shape.r
            radiusY: shape.r
            direction: PathArc.Clockwise
        }

        PathArc {
            x: root.width / 2
            y: (root.height / 2) - shape.r
            radiusX: shape.r
            radiusY: shape.r
            direction: PathArc.Clockwise
        }
    }
}
