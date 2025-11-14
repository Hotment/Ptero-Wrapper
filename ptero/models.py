"""
Ptero-Wrapper Models
Contains all the data classes used to parse responses from the Pterodactyl API.
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .application import ApplicationAPI

# --- Client API Models ---

class EggVariable:
    def __init__(self, egg_var_data: dict):
        self.data: dict = egg_var_data
        self.name: str = self.data["name"]
        self.description: str = self.data["description"]
        self.env_variable: str = self.data["env_variable"]
        self.default_value: str = self.data["default_value"]
        self.server_value: str = self.data["server_value"]
        self.is_editable: bool = self.data["is_editable"]
        self.rules: str = self.data["rules"]

class Allocation:
    def __init__(self, allocation_data: dict):
        self.data: dict = allocation_data
        self.id: int = self.data["id"]
        self.ip: str = self.data["ip"]
        self.ip_alias: Optional[str] = self.data.get("ip_alias")
        self.port: int = self.data["port"]
        self.notes: Optional[str] = self.data.get("notes")
        self.is_default: bool = self.data["is_default"]

class SftpDetails:
    def __init__(self, sftp_data: dict):
        self.data: dict = sftp_data
        self.ip: str = self.data["ip"]
        self.port: int = self.data["port"]

class Limits:
    def __init__(self, limits_data: dict):
        self.data: dict = limits_data
        self.memory: int = self.data["memory"]
        self.swap: int = self.data["swap"]
        self.disk: int = self.data["disk"]
        self.io: int = self.data["io"]
        self.cpu: int = self.data["cpu"]

class FeatureLimits:
    def __init__(self, feature_limits_data: dict):
        self.data: dict = feature_limits_data
        self.databases: int = self.data["databases"]
        self.allocations: int = self.data["allocations"]
        self.backups: int = self.data["backups"]

class Resource:
    def __init__(self, resources_data: dict):
        self.data: dict = resources_data["attributes"]
        self.current_state: str = self.data["current_state"]
        self.is_suspended: bool = self.data["is_suspended"]
        self.resources_data: dict = self.data["resources"]
        self.memory_bytes: int = self.resources_data.get("memory_bytes", 0)
        self.cpu_absolute: int = self.resources_data.get("cpu_absolute", 0)
        self.disk_bytes: int = self.resources_data.get("disk_bytes", 0)
        self.network_rx_bytes: int = self.resources_data.get("network_rx_bytes", 0)
        self.network_tx_bytes: int = self.resources_data.get("network_tx_bytes", 0) 
        self.uptime: int = self.resources_data.get("uptime", 0)

class Backup:
    def __init__(self, backup_data: dict):
        self.data: dict = backup_data["attributes"]
        self.uuid: str = self.data["uuid"]
        self.is_successful: bool = self.data["is_successful"]
        self.is_locked: bool = self.data["is_locked"]
        self.name: str = self.data["name"]
        self.ignored_files: List[str] = self.data["ignored_files"]
        self.checksum: Optional[str] = self.data.get("checksum")
        self.bytes: int = self.data.get("bytes", 0)
        self.created_at: str = self.data["created_at"]
        self.completed_at: Optional[str] = self.data.get("completed_at")

class Database:
    def __init__(self, db_data: dict):
        self.data: dict = db_data["attributes"]
        self.id: str = self.data["id"]
        self.name: str = self.data["name"]
        self.username: str = self.data["username"]
        self.host_address: str = self.data["host"]["address"]
        self.host_port: int = self.data["host"]["port"]
        self.allow_connections_from: str = self.data["connections_from"]
        self.max_connections: int = self.data.get("max_connections", 0)

class FileStat:
    def __init__(self, file_data: dict):
        self.data: dict = file_data["attributes"]
        self.name: str = self.data["name"]
        self.mode: str = self.data["mode"]
        self.size: int = self.data["size"]
        self.is_file: bool = self.data["is_file"]
        self.is_symlink: bool = self.data["is_symlink"]
        self.is_editable: bool = self.data.get("is_editable", False)
        self.mimetype: str = self.data["mimetype"]
        self.created_at: str = self.data["created_at"]
        self.modified_at: str = self.data["modified_at"]

class Schedule:
    def __init__(self, schedule_data: dict):
        self.data: dict = schedule_data["attributes"]
        self.id: int = self.data["id"]
        self.name: str = self.data["name"]
        self.cron_day_of_week: str = self.data["cron"]["day_of_week"]
        self.cron_day_of_month: str = self.data["cron"]["day_of_month"]
        self.cron_month: str = self.data["cron"]["month"]
        self.cron_hour: str = self.data["cron"]["hour"]
        self.cron_minute: str = self.data["cron"]["minute"]
        self.is_active: bool = self.data["is_active"]
        self.is_processing: bool = self.data.get("is_processing", False)
        self.only_when_online: bool = self.data["only_when_online"]
        self.last_run_at: Optional[str] = self.data.get("last_run_at")
        self.next_run_at: Optional[str] = self.data.get("next_run_at")
        self.created_at: str = self.data["created_at"]
        self.updated_at: str = self.data.get("updated_at")
        
        tasks_data = schedule_data.get("relationships", {}).get("tasks", {}).get("data", [])
        # We can't pass the API object here easily, so tasks remain flat
        self.tasks: List[Task] = [Task(task["attributes"]) for task in tasks_data]

class Task:
     def __init__(self, task_data: dict):
        self.data: dict = task_data
        self.id: int = self.data["id"]
        self.sequence_id: int = self.data["sequence_id"]
        self.action: str = self.data["action"]
        self.payload: str = self.data["payload"]
        self.time_offset: int = self.data["time_offset"]
        self.is_queued: bool = self.data.get("is_queued", False)
        self.created_at: str = self.data["created_at"]
        self.updated_at: str = self.data.get("updated_at")

class Subuser:
    def __init__(self, subuser_data: dict):
        self.data: dict = subuser_data["attributes"]
        self.uuid: str = self.data["uuid"]
        self.username: str = self.data["username"]
        self.email: str = self.data["email"]
        self.image: str = self.data["image"]
        self.two_factor_enabled: bool = self.data["2fa_enabled"]
        self.created_at: str = self.data["created_at"]
        self.permissions: List[str] = self.data.get("permissions", [])


# --- Application API Models ---

class NodeAllocation:
    """Represents an Allocation from the Application API (Node endpoint)."""
    def __init__(self, alloc_data: dict):
        self.data: dict = alloc_data["attributes"]
        self.id: int = self.data["id"]
        self.ip: str = self.data["ip"]
        self.ip_alias: Optional[str] = self.data.get("ip_alias")
        self.port: int = self.data["port"]
        self.server_id: Optional[int] = self.data.get("server_id")


class Location:
    """Represents a Location from the Application API."""
    def __init__(self, loc_data: dict, api: Optional['ApplicationAPI'] = None):
        self.api = api
        self.data: dict = loc_data["attributes"]
        self.id: int = self.data["id"]
        self.short_code: str = self.data["short"]
        self.description: str = self.data["long"]
        self.created_at: str = self.data["created_at"]
        self.updated_at: Optional[str] = self.data.get("updated_at")
        
        # Eager-loaded relationships
        nodes_data = loc_data.get("relationships", {}).get("nodes", {}).get("data", [])
        self.nodes: List['Node'] = [Node(n_data, api=api) for n_data in nodes_data]

    async def get_nodes(self) -> List['Node']:
        """(Re-)fetches the list of nodes for this location."""
        if not self.api:
            return self.nodes # Return cached list if no API
        self.nodes = await self.api.get_nodes(params={'filter[location_id]': self.id})
        return self.nodes

class Node:
    """Represents a Node from the Application API."""
    def __init__(self, node_data: dict, api: Optional['ApplicationAPI'] = None):
        self.api = api
        self.data: dict = node_data["attributes"]
        self.id: int = self.data["id"]
        self.uuid: str = self.data["uuid"]
        self.public: bool = self.data["public"]
        self.name: str = self.data["name"]
        self.description: Optional[str] = self.data.get("description")
        self.location_id: int = self.data["location_id"]
        self.fqdn: str = self.data["fqdn"]
        self.scheme: str = self.data["scheme"]
        self.behind_proxy: bool = self.data["behind_proxy"]
        self.maintenance_mode: bool = self.data["maintenance_mode"]
        self.memory: int = self.data["memory"]
        self.memory_overallocate: int = self.data["memory_overallocate"]
        self.disk: int = self.data["disk"]
        self.disk_overallocate: int = self.data["disk_overallocate"]
        self.upload_size: int = self.data["upload_size"]
        self.daemon_listen: int = self.data["daemon_listen"]
        self.daemon_sftp: int = self.data["daemon_sftp"]
        self.daemon_base: str = self.data["daemon_base"]
        
        # Eager-loaded relationships
        alloc_data = node_data.get("relationships", {}).get("allocations", {}).get("data", [])
        self.allocations: List[NodeAllocation] = [NodeAllocation(alloc) for alloc in alloc_data]
        
        loc_data = node_data.get("relationships", {}).get("location", {}).get("data")
        self.location: Optional[Location] = Location(loc_data, api=api) if loc_data else None

    async def get_location(self) -> Optional[Location]:
        """(Re-)fetches the location for this node."""
        if not self.api:
            return self.location # Return cached object if no API
        self.location = await self.api.get_location(self.location_id)
        return self.location

class User:
    """Represents a User from the Application API."""
    def __init__(self, user_data: dict, api: Optional['ApplicationAPI'] = None):
        self.api = api
        self.data: dict = user_data["attributes"]
        self.id: int = self.data["id"]
        self.external_id: Optional[str] = self.data.get("external_id")
        self.uuid: str = self.data["uuid"]
        self.username: str = self.data["username"]
        self.email: str = self.data["email"]
        self.first_name: str = self.data["first_name"]
        self.last_name: str = self.data["last_name"]
        self.language: str = self.data["language"]
        self.root_admin: bool = self.data["root_admin"]
        self.two_factor: bool = self.data["2fa"]
        self.created_at: str = self.data["created_at"]
        self.updated_at: Optional[str] = self.data.get("updated_at")

        # ELink to servers requires ClientServer, handled in control.py
        # Eager-loaded relationships
        servers_data = user_data.get("relationships", {}).get("servers", {}).get("data", [])
        self.server_ids: List[str] = [s_data['attributes']['uuid'] for s_data in servers_data]


class Nest:
    """Represents a Nest from the Application API."""
    def __init__(self, nest_data: dict, api: Optional['ApplicationAPI'] = None):
        self.api = api
        self.data: dict = nest_data["attributes"]
        self.id: int = self.data["id"]
        self.uuid: str = self.data["uuid"]
        self.author: str = self.data["author"]
        self.name: str = self.data["name"]
        self.description: Optional[str] = self.data.get("description")
        self.created_at: str = self.data["created_at"]
        self.updated_at: Optional[str] = self.data.get("updated_at")

        # Eager-loaded relationships
        eggs_data = nest_data.get("relationships", {}).get("eggs", {}).get("data", [])
        self.eggs: List['Egg'] = [Egg(egg_data, api=api) for egg_data in eggs_data]

    async def get_eggs(self) -> List['Egg']:
        """(Re-)fetches the list of eggs for this nest."""
        if not self.api:
            return self.eggs # Return cached list if no API
        self.eggs = await self.api.get_eggs_in_nest(self.id)
        return self.eggs

class Egg:
    """Represents an Egg from the Application API."""
    def __init__(self, egg_data: dict, api: Optional['ApplicationAPI'] = None):
        self.api = api
        self.data: dict = egg_data["attributes"]
        self.id: int = self.data["id"]
        self.uuid: str = self.data["uuid"]
        self.nest_id: int = self.data["nest"] # Renamed from self.nest
        self.author: str = self.data["author"]
        self.name: str = self.data["name"]
        self.description: Optional[str] = self.data.get("description")
        self.docker_image: str = self.data["docker_image"]
        self.startup: str = self.data["startup"]
        self.created_at: str = self.data["created_at"]
        self.updated_at: Optional[str] = self.data.get("updated_at")
        
        # Eager-loaded relationships
        nest_data = egg_data.get("relationships", {}).get("nest", {}).get("data")
        self.nest: Optional[Nest] = Nest(nest_data, api=api) if nest_data else None

    async def get_nest(self) -> Optional[Nest]:
        """(Re-)fetches the parent nest for this egg."""
        if not self.api:
            return self.nest # Return cached object if no API
        self.nest = await self.api.get_nest(self.nest_id)
        return self.nest