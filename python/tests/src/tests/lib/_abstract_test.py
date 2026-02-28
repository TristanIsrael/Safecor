from PySide6.QtCore import QObject, Signal, Slot
from enums import MessageLevel

class Message():
    """ Encapsulates a string and a level for a message sent by a test """

    message = ""
    level = MessageLevel.Information

    def __init__(self, message:str, level:MessageLevel):
        self.message = message
        self.level = level

class AbstractTest(QObject):
    """ Abstract class for developping tests """

    #### Public properties ####
    name = "A test"
    description = "Description of the test"
    parallelizable = True
    progress = 0 # From 0 to 100
    messages = []
    success = False

    #### Private properties ####
    

    #################
    #### Methods ####
    #################
 
    def start(self):
        """ Called when the test is started """

        self._set_progress(100)
        self._send_message(self.tr("Test not implemented"), MessageLevel.Warning)
        self.finished.emit()

    def stop(self):
        """ Called when the test must be stopped, it may be resumed later """

        raise NotImplementedError
    
    def skip(self):
        """ Called to draw the test """
        
        self._set_progress(100)
        self.success = False
        self.finished.emit()

    def is_success(self) -> bool:
        """ Called to know the test result """

        return self.success

    def _send_message(self, message:str, level:MessageLevel):
        self.messages.append(Message(message, level))
        self.message.emit(message, level)

    def _set_progress(self, progress:int):
        self.progress = progress
        self.progressChanged.emit()

    def _set_finished(self, success:bool):
        self._set_progress(100)
        self.success = success
        self.finished.emit()

    def _set_waiting(self, waiting:bool):
        if waiting:
            self.waiting.emit()
        else:
            self.resumed.emit()

    #################
    ####  Slots  ####
    #################
    @Slot(str)
    def on_user_text_changed(self, text:str):
        """ Called by AppController when the user entered a text """

    @Slot()
    def on_mouse_moved(self):
        """ Called by AppController when the mouse has been moved """

    @Slot()
    def on_screen_touched(self):
        """ Called by AppController when the screen has been touched """

    #################
    #### Signals ####
    #################
    progressChanged = Signal()
    started = Signal()
    stopped = Signal()
    finished = Signal()
    waiting = Signal()
    resumed = Signal()
    message = Signal(str, MessageLevel)
    resetUserText = Signal()
