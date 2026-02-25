import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QTouchEvent
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class TouchTestWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Multitouch")
        self.resize(800, 600)
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        
        # UI
        self.label = QLabel("Touchez l'écran avec un ou plusieurs doigts", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.label)

    def event(self, event):
        if event.type() in [QTouchEvent.TouchBegin, QTouchEvent.TouchUpdate, QTouchEvent.TouchEnd]:
            touch_points = event.points()
            log = []
            for point in touch_points:
                log.append(f"ID: {point.id()} Pos: {point.position()} State: {point.state()}")
            self.label.setText("\n".join(log))
        return super().event(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TouchTestWidget()
    window.show()
    sys.exit(app.exec())