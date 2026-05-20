""" \author Tristan Israël """

import copy
from . import ComponentState

class ComponentsHelper():
    """ This class helps extracting information about components

    It handles a list of system components that can be updated on demand (:func:`update`). The information stored can the be
    extracted using the other functions.

    .. seealso::
        - :func:`Api.discover_components` - Discover components with the API
        - :class:`ComponentState` - Component state
    """

    __components = []

    def clear(self):
        """ Resets all components in the list """
        self.__components.clear()

    def update(self, updates:list) -> None:
        """ Updates the components list with a new list

        .. seealso::
            - Protocol documentation <|URL_DOC_PROTOCOL|> chapter Discover the components of the system            
        """

        components_dict = {comp["id"]: comp for comp in self.__components}
    
        for update in copy.deepcopy(updates):
            if update["id"] in components_dict:
                # Si l'id existe, mettre à jour uniquement le champ 'state'
                state = update.get("state", ComponentState.UNKNOWN)
                components_dict[update["id"]]["state"] = ComponentState(state)
            else:
                # Si l'id n'existe pas, ajouter l'entrée
                state = update.get("state", ComponentState.UNKNOWN)
                update["state"] = ComponentState(state) # On traduit le str en énumération
                self.__components.append(update)

    def get_by_id(self, component_id:str) -> dict:
        """ Returns a component by its ID """

        for comp in self.__components:
            if comp.get("id") is not None and comp.get("id") == component_id:
                return comp
            
        return {}

    def get_ids(self) -> list[str]:
        """ Returns a list of all components IDs """

        return [d["id"] for d in self.__components if "id" in d]
    
    def get_states(self) -> dict:
        """ Returns a dict of components states 

            Example:
            ::
            
                {
                    "sys-usb": "ready",
                    "sys-gui": "ready"
                }

            .. seealso::
                - :class:`ComponentState`
        """

        return {comp["id"]: comp["state"] for comp in self.__components if "id" in comp and "state" in comp}
    
    def get_state(self, component_id:str) -> ComponentState:
        """ Returns the state of a component 
        
            .. seealso::
                - :class:`ComponentState`
        """

        for comp in self.__components:
            if comp.get("id") == component_id:
                return comp.get("state", ComponentState.UNKNOWN)
            
        return ComponentState.UNKNOWN
    
    def get_type(self, component_id:str) -> str:
        """ Returns the type of a component 
        
            The types of components are free for the products based on Safecor, but for the components
            of the Safecor core the value is ``core``.
        """

        for comp in self.__components:
            if comp.get("id") == component_id:
                return comp.get("type", "")
            
        return ""
    
    def get_ids_by_type(self, component_type:str) -> list[str]:
        """ Returns all components IDs that match a specific type
        
            For exemple, to query all the core components:
            ::
                def query(self):
                    Api().add_message_callback(self.on_message)
                    Api().discover_components()
                
                def on_message(self, topic:str, payload:dict):
                    if topic == Topics.DISCOVER_COMPONENTS:
                        hlp = ComponentsHelper()
                        hlp.update(payload)
                        core_components = hlp.get_ids_by_type("core")
        """
        
        ids = []

        for comp in self.__components:
            if comp.get("type") is not None and comp.get("type") == component_type:
                ids.append(comp.get("id", ""))
            
        return ids
    
    def get_components(self):
        """ Returns all the components stored by this instance """

        return self.__components

    def is_ready(self, component_id:str):
        """ Returns True if the component is in the list and is ready """

        state = self.get_state(component_id)

        if state == ComponentState.UNKNOWN:
            return False
        
        return state == ComponentState.READY
