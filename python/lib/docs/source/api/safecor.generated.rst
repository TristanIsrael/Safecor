Safecor API - Classes et Fonctions Complètes
============================================

API Auto-Générée depuis le module ``safecor``. La documentation est générée automatiquement à partir des docstrings Python et des hints de type.

**Utilisation**: Pour utiliser l'API Safecor, instanciez la :class:`Api` classe et ouvrez la socket en appelant :func:`start()`. Les autres fonctions permettent de gérer les communications MQTT avec le domaine Dom0.

.. autoclass:: Api
   :members:
   :undoc-members:
   :show-inheritance:


---

**DomainController & Domain Class**: Interface gérant les commandes MQTT depuis DomU et contrôlant la gestion des domaines.

.. autoclass:: Dom0Controller
   :members:
   :undoc-members:
   
.. autoclass:: System
   :members:
   :undoc-members:


---

**Mqtt & Serial MQTT Clients**: Gestionnaires de connexion MQTT pour communications sans fil/serail.

.. autoclass:: MqttClient
   :members:
   
.. autoclass:: SerialMQTTClient
   :members:


---

**XenStore & Xen Integration**: Support natif Xen pour écran, rotation et paramètres.

.. autoclass:: XenStore
   :members:


---

**Hardware Controllers**: Gestion des périphériques (USB, X11, Serial).

.. autoclass:: SysUsbController
   :members:

.. autoclass:: FileHelper
   :members:

.. autoclass:: DiskMonitor
   :members:


---

**API Helpers & Outils**: Aides et utilitaires génériques.

.. autoclass:: ApiHelper
   :members:
