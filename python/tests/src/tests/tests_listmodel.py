from PySide6.QtCore import QObject, QAbstractListModel, QModelIndex, Signal, Slot
from enums import Roles, MessageLevel
from tests_helper import TestsHelper

class TestsListModel(QAbstractListModel):

    #__cache = [] # List of dicts

    addMessage = Signal(str, MessageLevel)

    def __init__(self, tests_list:list, parent:QObject):
        super().__init__(parent)
        self.__tests_list = tests_list

    #def update_cache(self):
    #    """ The cache contains all tests automatically discovered """
    #    self.__cache = TestsHelper.get_tests_list()
        

    def rowCount(self, parent=QModelIndex()):
        #return len(self.__cache.keys()) + len(self.__cache.values())        
        return len(self.__tests_list)
    
    def data(self, index, role):
        if not index.isValid():
            return None
        
        if len(self.__tests_list) <= index.row():
            return

        item = self.__tests_list[index.row()]

        #if item.get("name") == "Get storages list":
        #    print(item)

        if role == Roles.RoleLabel:
            return item.get("name")
        elif role == Roles.RoleSection:
            return not item.get("is_test")
        elif role == Roles.RoleProgress:
            if item.get("is_test"):
                return item.get("progress")
            else:
                return self.__calculate_package_progress(item.get("name"))
        elif role == Roles.RoleSuccess:
            if item.get("is_test"):
                return item.get("success")
            else:
                return self.__calculate_package_success(item.get("name"))
        elif role == Roles.RoleIsPackage:
            return not item.get("is_test")
        
    def __calculate_package_progress(self, package_name) -> int:
        """ Calculates the progress for a package by calculating the mean of 
            the values for the package's tests 
        """

        tests = [d for d in self.__tests_list if d.get("package") == package_name]
        sum_ = sum(d.get("progress") for d in tests)
        cnt_ = len(tests)

        progress = float(sum_) / float(cnt_)if cnt_ > 0 else 0

        return progress
    
    def __calculate_package_success(self, package_name) -> int:
        """ Calculates the success for a package by veryfying all tests are 
        successful
        """

        tests = [d for d in self.__tests_list if d.get("package") == package_name]
        for test in tests:
            if not test.get("success", False):
                return False

        return True
        

    def get_nb_capacities_total(self) -> int:
        return sum(1 for d in self.__tests_list if d.get("is_test") is False)
    
    def get_nb_tests_total(self) -> int:
        return sum(1 for d in self.__tests_list if d.get("is_test"))

    def roleNames(self) -> dict:
        roles = {
            Roles.RoleProgress: b'progress',
            Roles.RoleIsPackage: b'isPackage', 
            Roles.RoleLabel: b'label',
            Roles.RoleSuccess: b'success'
        }

        return roles

    @Slot()
    def on_data_changed(self):
        # TODO: improve the algorithm
        self.beginResetModel()
        self.endResetModel()