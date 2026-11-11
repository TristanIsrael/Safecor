import importlib
import inspect
import pkgutil
from pathlib import Path


class TestsHelper:
    @staticmethod
    def get_tests_list():
        tests_list = []

        app_root_path = Path(__file__).parent
        packages_path = app_root_path / "TestPackages"
        # print(f"Look for test packages into {packages_path}")

        # self.addMessage.emit(self.tr("Looking into test packages"), MessageLevel.Information)

        for _, package_name, _ in pkgutil.iter_modules([packages_path]):
            # print(f"Module {package_name} discovered")

            package = importlib.import_module(f"TestPackages.{package_name}")

            if not any(d.get("name") == package_name for d in tests_list):
                # self.addMessage.emit(self.tr(f"Found package {package_name}"), MessageLevel.Information)

                tests_list.append(
                    {"name": package_name, "success": False, "is_test": False}
                )

            for _, module_name, _ in pkgutil.walk_packages(
                package.__path__, package.__name__ + "."
            ):
                module = importlib.import_module(module_name)

                for _, cls in inspect.getmembers(module, inspect.isclass):
                    if cls.__module__ == module_name:
                        # self.addMessage.emit(self.tr(f"Found test {cls.name}"), MessageLevel.Information)
                        # print(f"Test class {module_name} discovered")

                        tests_list.append(
                            {
                                "name": cls.name,
                                "class_name": cls.__qualname__,
                                "class": cls,
                                "package": package_name,
                                "progress": 0,
                                "success": False,
                                "is_test": True,
                            }
                        )

        return tests_list
