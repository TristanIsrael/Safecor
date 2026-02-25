""" \author Tristan Israël """

from . import ComponentState, BenchmarkId

class ResponseFactory():
    """ This class helps generating commands for API reponses.   
    
    """

    @staticmethod
    def create_response_disks_list(disks_list:list = []) -> dict:
        payload = {
            "disks": disks_list
        }        
        return payload
    
    @staticmethod
    def create_response_list_files(disk:str, files:list = []) -> dict:
        payload = {
            "disk": disk,
            "files": files
        }
        return payload

    @staticmethod
    def create_reponse_benchmark_inputs(duree:int, iterations:int) -> dict:
        payload = {
            "id": BenchmarkId.INPUTS,
            "duration": duree,
            "iterations": iterations
        }
        return payload

    @staticmethod
    def create_reponse_benchmark_fichiers_demarre() -> dict:
        payload = {
            "id": BenchmarkId.FILES,
            "state": "started"
        }
        return payload
    
    @staticmethod
    def create_reponse_benchmark_fichiers_termine(metrics:list) -> dict:
        payload = {
            "id": BenchmarkId.FILES,
            "estatetat": "finished",
            "metrics": metrics
        }
        return payload

    @staticmethod
    def create_reponse_benchmark_fichiers_erreur(erreur:str) -> dict:
        payload = {
            "id": BenchmarkId.FILES,
            "state": "error",
            "message": erreur
        }
        return payload
    
    @staticmethod
    def create_response_file_fingerprint(filepath:str, disk:str, fingerprint:str) -> dict:
        payload = {
            "filepath": filepath,
            "disk": disk,
            "fingerprint": fingerprint
        }
        return payload
    
    @staticmethod
    def create_response_create_file(filepath:str, disk:str, fingerprint:str, success:bool) -> dict:
        payload = {
            "filepath": filepath,
            "disk": disk,
            "fingerprint": fingerprint,
            "success": success
        }
        return payload

    @staticmethod
    def create_entry_component_state(component_id:str, component_label:str, domain_name:str, state:ComponentState, component_type = "core") -> dict:
        return {
            "id": component_id,
            "domain_name": domain_name,
            "label": component_label,
            "type": component_type,
            "state": state.value
        }

    @staticmethod
    def create_response_component_state(components:list[dict]) -> dict:
        payload = {
            "components": components
        }

        return payload

    @staticmethod
    def create_response_copy_file(filepath:str, disk:str, success:bool, fingerprint:str) -> dict:
        payload = {
            "filepath": filepath,
            "status": "ok" if success else "error",
            "fingerprint": fingerprint
        }
        return payload
    
    
    @staticmethod
    def create_response_shutdown(accepted:bool):
        payload = {
            "state": "accepted" if accepted else "refused",
            "reason": ""
        }

        return payload
    

    @staticmethod
    def create_response_restart_domain(domain_name:str, accepted:bool, reason:str):
        payload = {
            "domain_name": domain_name,
            "state": "accepted" if accepted else "refused",
            "reason": reason
        }

        return payload
    
    @staticmethod
    def create_response_ping(ping_id, source_name, data, sent_at):
        return {
            "id": ping_id,
            "source": source_name,
            "data": data,
            "sent_at": sent_at
        }
