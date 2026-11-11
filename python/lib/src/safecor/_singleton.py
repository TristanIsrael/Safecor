"""Singleton metaclass.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""


class SingletonMeta(type):
    """
    This class is a metaclass for developing Singleton classes.

    Use use this way:
    ::

        class MyClass(metaclass=SingletonMeta):

            # There won't be any __init__() method.

            def function(self):
                pass

        # Use the Singleton
        MyClass().function()
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """

        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
