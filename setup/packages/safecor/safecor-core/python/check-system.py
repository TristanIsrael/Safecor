#!/usr/bin/python3

import subprocess
from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich.align import Align
from rich.panel import Panel
from rich.columns import Columns
from safecor import Api, MqttFactory, Topics, System, topology, Constants
from threading import Event

console = Console()
mqtt_client = MqttFactory.create_mqtt_client_dom0("check-system")
api_ready = False
components = []
api_lock = Event()

def on_api_ready():
    global api_ready

    Api().subscribe(f"{Topics.DISCOVER_COMPONENTS}/response")

    api_ready = True
    api_lock.set()

def on_message(topic:str, payload:dict):
    global components

    if topic == f"{Topics.DISCOVER_COMPONENTS}/response":
        comps = payload.get("components", [])

        for c in comps:
            components.append(c)

    # We expect 3 components
    if len(components) == 3:
        api_lock.set()

def cls():
    """ Clears the screen """

    print("\033[2J\033[H", end="")

def check_service(service_name:str) -> tuple[bool, str]: 
    """ Check a service status """

    cmd = ["rc-service", service_name, "status"]

    result = subprocess.run(cmd, capture_output=True, text=True)

    status = "Unknown"
    if result.returncode == 0:
        status = "Running"
    elif result.returncode == 1:
        status = "Unknown service"
    elif result.returncode == 3:
        status = "Stopped"
    elif result.returncode == 32:
        status = "Crashed"

    return result.returncode == 0, status

def check_kernel_parameter(param_name:str) -> bool:
    """ Verifies whether a kernel parameter is present """

    f = open("/proc/cmdline", "r")
    params = f.read()

    return param_name in params.strip().split(" ")

def make_report_services() -> Table:
    """ Create a report for all services status """

    services = [ "orchestrator", "sysfs", "devfs", "dmesg", "mdev", "modules", "hwdrivers", "fsck", "root", "swap", "localmount", "hostname", "sysctl", "bootmisc", "syslog-ng", "xenstored", "mosquitto", "safecor-core-controller", "chronyd", "virtlogd", "xenconsoled", "libvirtd", "create-mqtt-tunnels", "splash", "xserver", "apparmor", "seedrng", "crond", "acpid", "hardening" ]

    table = Table(show_lines=True, box=None)
    table.add_column("Service")
    table.add_column("State")

    for service in services:
        running, status = check_service(service)
        table.add_row(service, Text(status), style="bold green" if running else "bold red")

    return table

def make_report_kernel_params() -> Table:
    """ Create a report for the kernel parameters """

    params_mandatory = [ "apparmor=1", "security=apparmor" ]
    params_optional = [ "debug=on", "nosplash", "no_autostart", "apparmor=1", "security=apparmor" ]

    table = Table(box=None)
    table.add_column("Parameter")
    table.add_column(" ")

    for param in params_mandatory:
        present = check_kernel_parameter(param)
        table.add_row(param, Text("Present" if present else "Absent"), style="bold green" if present else "bold red")

    for param in params_optional:
        present = check_kernel_parameter(param)
        table.add_row(param, Text("Present" if present else "Absent"), style="bold green" if present else "bold yellow")

    return table

def get_xen_domains():
    """ Returns a list of tuples (Domain, state) with the result of xl list """

    try:
        output = subprocess.check_output(["xl", "list"], text=True)
    except FileNotFoundError:
        raise RuntimeError("An error occured while executing xl")
    
    lines = output.strip().splitlines()
    domains = []

    if len(lines) < 2:
        return domains  # pas de domaines

    headers = lines[0].split()
    # trouver l'index de State pour être sûr
    try:
        state_idx = headers.index("State")
        name_idx = headers.index("Name")
    except ValueError:
        raise RuntimeError("Parsing error")

    # traiter toutes les lignes sauf l'en-tête
    for line in lines[1:]:
        cols = line.split()
        if len(cols) <= max(name_idx, state_idx):
            continue
        name = cols[name_idx]
        state = cols[state_idx]
        domains.append((name, state))

    return domains

def make_report_safecor_components() -> Table:
    """ Create a report for Safecor components """    

    # Verify Domains
    domains_states = get_xen_domains()

    table = Table(box=None)
    table.add_column("Component")
    table.add_column("State")

    for domain in topology.domain_names():
        state = next((v for k,v in domains_states if k == domain), None)
        running = state is not None and (state.startswith("r") or state.startswith("-b"))
        table.add_row(domain, Text("Running" if running else "Not running"), style="bold green" if running else "bold red" )

    # Verify components
    components_ids = [ Constants.SAFECOR_DISK_CONTROLLER, Constants.SAFECOR_INPUT_CONTROLLER, Constants.SAFECOR_SYSTEM_CONTROLLER ]

    for comp_id in components_ids:
        comp = next((d for d in components if d.get("id", "") == comp_id), None)
        table.add_row(comp_id, Text(comp.get("state", "Unknown") if comp is not None else "Not ready"), style="bold green" if comp is not None and comp.get("state") == "ready" else "bold red")

    return table

def make_report_safecor_features() -> Table:
    """ Create a report for Safecor features """

    global components
    table = Table(box=None)
    table.add_column("Feature")
    table.add_column("State")

    # API connection
    Api().add_ready_callback(on_api_ready)
    Api().add_message_callback(on_message)
    Api().start(mqtt_client, "Dom0", False)
    api_lock.wait(1)
    api_lock.clear()

    table.add_row("API connection", Text("OK" if api_ready else "KO"), style="bold green" if api_ready else "bold red")

    # Get components
    components.clear()
    Api().discover_components()
    resp_ok = api_lock.wait(2)
    api_lock.clear()

    table.add_row("Components discovery", Text("OK" if resp_ok else "KO"), style="bold green" if resp_ok else "bold red")

    return table

def check_system():
    """ Check the system state """

    cls()

    services = make_report_services()
    kernel_params = make_report_kernel_params()
    safecor_features = make_report_safecor_features()
    safecor_components = make_report_safecor_components()    

    panels = [
        Panel(services, title="Services"),
        Panel(kernel_params, title="Kernel parameters"),
        Panel(safecor_components, title="Safecor components"),
        Panel(safecor_features, title="Safecor features")
    ]

    console.print(Align.center(Columns(panels)))


if __name__ == "__main__":
    print("Gathering information... Please wait...")

    System.get_topology()
    check_system()
