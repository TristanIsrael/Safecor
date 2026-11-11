""" MQTT helper utilities

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

class MqttHelper():
    """ This class contains helper functions for the MQTT facility """

    @staticmethod
    def check_payload(payload:dict, expected_keys:list):
        """ Verifies that the payload contains some necessary keys """
        
        for key in expected_keys:
            if payload.get(key) is None:
                return False
        
        return True