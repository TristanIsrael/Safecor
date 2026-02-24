import os
from PySide6.QtCore import QObject, Property, Slot, Signal, QTimer
from tests_listmodel import TestsListModel
from messages_listmodel import MessagesListModel
from lib import AbstractTest
from enums import MessageLevel
from safecor import Api, MqttFactory
from tests_helper import TestsHelper
DEVMODE = os.environ.get("DEVMODE")
if DEVMODE:
    from mocks.DevModeHelper import DevModeHelper
    DevModeHelper.set_qt_plugins_path()

class AppController(QObject):

    __ready = False
    __running = False
    __tests_list = TestsHelper.get_tests_list()
    __current_test_index = 0

    def __init__(self, parent:QObject):
        super().__init__(parent)
        
        self.__messages_model = MessagesListModel(self)        
        self.__tests_listmodel = TestsListModel(self.__tests_list, self)
        self.__tests_listmodel.addMessage.connect(self.__messages_model.add_message)
        self.__messages_model.add_message(self.tr("Safecor tests app has started"))

        Api().add_ready_callback(self.__on_api_ready)        

        if DEVMODE:
            self.__mqtt_client = DevModeHelper.create_mqtt_client("Tests")
        else:
            self.__mqtt_client = MqttFactory.create_mqtt_client_domu("Tests")

        Api().start(domain_identifier="tests", mqtt_client=self.__mqtt_client)

    def __on_api_ready(self):
        self.__messages_model.add_message(self.tr("Safecor API is ready"))
        Api().notify_gui_ready()
        self.__ready = True
        self.readyChanged.emit()
        self.__messages_model.add_message(self.tr("Waiting for user action..."), MessageLevel.User)


    @Slot()
    def start_stop(self):
        if not self.__running:
            self.__messages_model.add_message(self.tr("Start the whole test plan"))
            self.__running = True
            self.runningChanged.emit()
            
            self.__run_next_test()
        else:
            self.__messages_model.add_message(self.tr("Stop the whole test plan"))

    def __run_next_test(self):
        if self.__current_test_index >= len(self.__tests_list):
            return
                
        test = self.__tests_list[self.__current_test_index]
        self.__current_test_index = self.__current_test_index+1

        if not test["is_test"]:
            QTimer.singleShot(1, self.__run_next_test)
            return

        if test.get("finished", False):
            QTimer.singleShot(1, self.__run_next_test)
            return

        self.__messages_model.add_message(self.tr("Run next test"))
        test_name = test["name"]
        test_class_name = test["class_name"]
        test_class:AbstractTest = test["class"]
        self.__messages_model.add_message(self.tr(f"Starting test {test_name}"))
            
        obj = test_class(self)
        if obj is None:
            self.__messages_model.add_message(self.tr(f"Could not start test {test_name}: Could not instanciate"))
            QTimer.singleShot(0, self.__run_next_test)
            return

        # Connect slots
        obj.progressChanged.connect(self.__on_progress_changed)
        obj.message.connect(self.__messages_model.add_message)
        obj.finished.connect(self.__on_test_finished)

        # Start the test
        obj.start()

    def __on_progress_changed(self):
        sender = self.sender()

        if sender is None:
            self.__messages_model.add_message(self.tr("Error when receiving progress signal: no sender"))
            return
        else:
            test = self.__get_test(sender.name)
            if test is None:
                self.__messages_model.add_message(self.tr(f"Error: the finished test has no name"))
                return  
            
            test["progress"] = sender.progress

    def __on_test_finished(self):
        sender = self.sender()

        if sender is None:
            self.__messages_model.add_message(self.tr("Error when receiving finished signal: no sender"))
            return
        else:
            self.__messages_model.add_message(self.tr(f"The test {sender.name} has finished"))
            test = self.__get_test(sender.name)

            if test is None:
                self.__messages_model.add_message(self.tr(f"Error: the finished test has no name"))
                return            

            # Set the test finished            
            test["finished"] = True          
            test["success"] = sender.success
            if test.get("success", False) == True:
                self.nbTestsSucceededChanged.emit()
            else:
                self.nbTestsFailedChanged.emit()
            
            self.__tests_listmodel.on_data_changed()

        # Destroy the object
        #sender.deleteLater()

        self.__run_next_test()

    def __get_test(self, test_name:str) -> dict:
        for test in self.__tests_list:
            if test.get("name") == test_name:
                return test 
        
        return None

    ###############
    ### Signals
    ###
    nbCapacitiesTotalChanged = Signal()
    nbTestsTotalChanged = Signal()
    nbTestsFailedChanged = Signal()
    nbTestsSucceededChanged = Signal()
    readyChanged = Signal()
    runningChanged = Signal()

    ###############
    ### Properties
    ###
    @Property(QObject, constant= True)
    def testsListModel(self) -> QObject:
        return self.__tests_listmodel

    @Property(QObject, constant= True)
    def messagesModel(self) -> QObject:
        return self.__messages_model

    @Property(int, notify= nbCapacitiesTotalChanged)
    def nbCapacitiesTotal(self) -> int:
        return self.__tests_listmodel.get_nb_capacities_total()
    
    @Property(int, notify= nbTestsTotalChanged)
    def nbTestsTotal(self) -> int:
        return self.__tests_listmodel.get_nb_tests_total()

    @Property(bool, notify= readyChanged)
    def ready(self) -> bool:
        return self.__ready
    
    @Property(bool, notify= runningChanged)
    def running(self) -> bool:
        return self.__running
    
    @Property(int, notify= nbTestsFailedChanged)
    def nbTestsFailed(self) -> int:
        return sum(1 for d in self.__tests_list if d.get("finished", False) == True and d.get("success", False) == False)
    
    @Property(int, notify= nbTestsSucceededChanged)
    def nbTestsSucceeded(self) -> int:
        return sum(1 for d in self.__tests_list if d.get("finished", False) == True and d.get("success", False) == True)
