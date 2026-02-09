"""
Ptero-Wrapper Client
Contains the ClientServer class for interacting with the Pterodactyl Client API.
"""

import httpx, json, re, websockets, asyncio, logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from .models import (
    EggVariable, Allocation, SftpDetails, Limits, FeatureLimits, Resource,
    Backup, Database, FileStat, Schedule, Task, Subuser, Node, User
)

if TYPE_CHECKING:
    from .application import ApplicationAPI

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
logger = logging.getLogger("ptero.client")

class ClientServer:
    def __init__(self, 
                 srv_data: dict, 
                 panel_id: str,
                 client_session: httpx.AsyncClient, 
                 base_url: str,
                 games_domain: Optional[str],
                 app_api: Optional['ApplicationAPI'] = None,
                 node_obj: Optional[Node] = None,
                 server_app_data: Optional[dict] = None,
                 user_obj: Optional[User] = None):
        
        self.data: dict = srv_data["attributes"]
        
        # Panel-specific attributes
        self.panel_id = panel_id
        self.session = client_session
        self.base_url = base_url
        self.games_domain = games_domain
        self.app: Optional['ApplicationAPI'] = app_api
        
        # Handle cases where session might be None (if key is missing)
        self.client_headers = self.session.headers if self.session else {}

        # Basic attributes
        self.name: str = self.data["name"]
        self.identifier: str = self.data["identifier"]
        
        # Detailed attributes
        self.uuid: str = self.data["uuid"]
        self.id: str = self.identifier # Alias for identifier
        self.node_id: int = self.data["node"] # Renamed from self.node
        self.sftp_details = SftpDetails(self.data["sftp_details"])
        self.description: str = self.data.get("description", "")
        self.limits = Limits(self.data["limits"])
        self.invocation: str = self.data.get("invocation", "")
        self.docker_image: str = self.data.get("docker_image", "")
        self.egg_features: list = self.data.get("egg_features", [])
        self.feature_limits = FeatureLimits(self.data["feature_limits"])
        self.is_suspended: bool = bool(self.data["is_suspended"])
        self.is_installing: bool = bool(self.data["is_installing"])
        self.is_transferring: bool = bool(self.data["is_transferring"])
        
        # --- Integrated Application API Data ---
        self.node: Optional[Node] = node_obj
        self.app_details: Optional[dict] = server_app_data # Raw app attributes
        self.owner: Optional[User] = user_obj
        
        # Handle relationships
        self.allocations = [Allocation(alloc["attributes"]) for alloc in self.data.get("relationships", {}).get("allocations", {}).get("data", [])]
        self.egg_variables = [EggVariable(var["attributes"]) for var in self.data.get("relationships", {}).get("variables", {}).get("data", [])]
        
        # Websocket attributes
        self.ws_resp: Optional[httpx.Response] = None
        self.ws_token: str = ""
        self.ws_url: str = ""
        
        # Runtime attributes
        self.resources: Optional[Resource] = None
        
    async def _async_setup(self):
        """Asynchronous setup tasks."""
        if not self.session: # If client API is disabled, we can't do any of this
            logger.warning(f"Client API disabled for panel {self.panel_id}, skipping async setup for server {self.identifier}")
            return
            
        if not self.is_installing:
            try:
                self.resources = await self.get_resources()
            except Exception as e:
                logger.warning(f"Failed to get resources for {self.identifier} during setup: {e}")
        
        try:
            ws_data = await self.get_websocket()
            if ws_data:
                self.ws_token = ws_data.get("token", "")
                self.ws_url = ws_data.get("socket", "")
            else:
                self.ws_token = ""
                self.ws_url = ""
        except Exception as e:
            logger.warning(f"Failed to get websocket for {self.identifier} during setup: {e}")
            self.ws_token = ""
            self.ws_url = ""

    @classmethod
    async def with_data(cls, 
                        srv_data: dict, 
                        panel_id: str,
                        client_session: httpx.AsyncClient, 
                        base_url: str,
                        games_domain: Optional[str] = None,
                        app_api: Optional['ApplicationAPI'] = None,
                        node_obj: Optional[Node] = None,
                        server_app_data: Optional[dict] = None,
                        user_obj: Optional[User] = None):
        """Class method to create and asynchronously initialize an instance."""
        client = cls(srv_data, panel_id, client_session, base_url, games_domain,
                     app_api, node_obj, server_app_data, 
                     user_obj)
        await client._async_setup()
        return client

    # -----------------------------------------------------------------
    # Internal API Request Helper
    # -----------------------------------------------------------------

    async def _client_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make a request to the correct panel."""
        if not self.session:
            logger.error(f"Client API request failed for {self.identifier} on panel {self.panel_id}: Client is not enabled (missing API key).")
            return httpx.Response(status_code=500, request=httpx.Request(method, f"{self.base_url}/client/servers/{self.identifier}/{endpoint}"), text="Client API not configured")

        full_url = f"{self.base_url}/client/servers/{self.identifier}/{endpoint}"
        
        try:
            return await self.session.request(method, full_url, **kwargs)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed for server {self.identifier} on panel {self.panel_id}: {e}")
            return httpx.Response(status_code=500, request=httpx.Request(method, full_url), text=str(e))

    # -----------------------------------------------------------------
    # App API Lazy Loaders
    # -----------------------------------------------------------------

    async def get_owner(self) -> Optional[User]:
        """Fetches the Application API User object for this server's owner."""
        if self.owner: # Return cached if available
            return self.owner
        if not self.app:
            logger.warning(f"Cannot get owner for {self.id} on panel {self.panel_id}: Application API not configured.")
            return None
        if not self.app_details:
            # Try to fetch app details if they weren't provided during init
            self.app_details = await self.app.get_server_details(self.id) # Assumes client ID == app ID
        
        if not self.app_details:
            logger.warning(f"Cannot get owner for {self.id} on panel {self.panel_id}: App details not found.")
            return None
            
        user_id = self.app_details.get('user')
        if not user_id:
            logger.warning(f"Cannot get owner for {self.id} on panel {self.panel_id}: Server app data has no user ID.")
            return None
        
        self.owner = await self.app.get_user(user_id)
        return self.owner

    async def get_node(self) -> Optional[Node]:
        """Fetches the Application API Node object for this server."""
        if self.node: # Return cached if available
            return self.node
        if not self.app:
            logger.warning(f"Cannot get node for {self.id} on panel {self.panel_id}: Application API not configured.")
            return None
        
        self.node = await self.app.get_node(self.node_id)
        return self.node

    # -----------------------------------------------------------------
    # Resources / Websocket
    # -----------------------------------------------------------------

    async def get_resources(self) -> Optional[Resource]:
        """Gets the current resource usage for the server."""
        response = await self._client_request("GET", "resources")
        if response.status_code == 200:
            self.resources = Resource(response.json())
            return self.resources
        elif response.status_code == 404:
            logger.warning(f"Server {self.identifier} not found on panel {self.panel_id} while getting resources.")
        else:
            logger.error(f"Error getting resources for {self.identifier} on panel {self.panel_id}: {response.status_code} {response.text}")
        return None

    async def get_websocket(self) -> Optional[Dict[str, str]]:
        """Gets websocket connection details."""
        response = await self._client_request("GET", "websocket")
        if response.status_code == 200:
            self.ws_resp = response
            return response.json()["data"]
        self.ws_resp = response
        logger.error(f"Failed to get websocket for {self.identifier} on panel {self.panel_id}: {response.status_code} {response.text}")
        return None

    async def refresh_websocket(self):
        """Refreshes websocket token and URL."""
        logger.debug(f"Refreshing websocket for {self.identifier} on panel {self.panel_id}")
        ws_data = await self.get_websocket()
        if ws_data:
            self.ws_token = ws_data.get("token", "")
            self.ws_url = ws_data.get("socket", "")
        else:
            self.ws_token = ""
            self.ws_url = ""

    # -----------------------------------------------------------------
    # Power Control
    # -----------------------------------------------------------------

    async def _send_power_signal(self, signal: str) -> httpx.Response:
        """Internal helper to send a power signal."""
        return await self._client_request("POST", "power", json={"signal": signal})

    async def start(self) -> httpx.Response: 
        return await self._send_power_signal("start")

    async def stop(self) -> httpx.Response: 
        return await self._send_power_signal("stop")

    async def restart(self) -> httpx.Response: 
        return await self._send_power_signal("restart")

    async def kill(self) -> httpx.Response: 
        return await self._send_power_signal("kill")

    # -----------------------------------------------------------------
    # Command Sending
    # -----------------------------------------------------------------
        
    async def send_command(self, command: str) -> httpx.Response: 
        """Sends a command to the server console."""
        return await self._client_request("POST", "command", json={"command": command})

    async def send_command_with_output(self, command: str, timeout: int = 5) -> tuple[httpx.Response, str]: 
        """Sends a command and attempts to capture the immediate output via websocket."""
        headers = self.client_headers.copy()
        headers.pop("Accept", None)
        headers.pop("Content-Type", None)
        origin = self.base_url.removesuffix("/api")
        headers["Origin"] = origin

        if not self.ws_url or not self.ws_token:
            logger.warning(f"No websocket details for {self.identifier}, refreshing...")
            await self.refresh_websocket()
            if not self.ws_url or not self.ws_token:
                logger.error(f"Failed to refresh websocket for {self.identifier}. Cannot send command with output.")
                return (httpx.Response(500, request=httpx.Request("POST", "command"), text="WebSocket details unavailable"), "ws_fail")

        try:
            async with websockets.connect(self.ws_url, additional_headers=headers, open_timeout=timeout) as ws:
                await ws.send(json.dumps({
                    "event": "auth",
                    "args": [self.ws_token]
                }))

                auth_success = False
                try:
                    async for message_raw in ws:
                        message = json.loads(message_raw)
                        if message["event"] == "auth success":
                            auth_success = True
                            break
                        if message["event"] == "jwt error":
                            logger.warning(f"JWT error for {self.identifier} on panel {self.panel_id}, refreshing token and retrying.")
                            await self.refresh_websocket()
                            return (httpx.Response(401, request=httpx.Request("POST", "command"), text="JWT Error"), "ws_fail:jwt")
                except websockets.exceptions.ConnectionClosed:
                    logger.error(f"Websocket closed prematurely during auth for {self.identifier} on panel {self.panel_id}")
                    return (httpx.Response(500, request=httpx.Request("POST", "command"), text="WebSocket closed during auth"), "ws_fail:auth_closed")

                if not auth_success:
                    logger.error(f"Websocket auth failed for {self.identifier} on panel {self.panel_id}")
                    return (httpx.Response(401, request=httpx.Request("POST", "command"), text="WebSocket auth failed"), "ws_fail:auth")

                while True:
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=0.1)
                    except asyncio.TimeoutError:
                        break
                
                resp = await self.send_command(command)

                if resp.status_code != 204:
                    return resp, "http_fail"

                output_lines = []
                try:
                    while True:
                        message_raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        data = json.loads(message_raw)
                        if data["event"] == "console output":
                            raw = data["args"][0]
                            stripped = ANSI_ESCAPE.sub('', raw).strip()
                            lines = stripped.splitlines()
                            for line in lines:
                                if line and line != command:
                                    return resp, line
                        elif data["event"] == "status":
                            pass
                except asyncio.TimeoutError:
                    logger.debug(f"Websocket output timed out for command '{command}' on {self.identifier}")
                    return resp, "ws_timeout"

        except websockets.exceptions.InvalidStatus as e:
            logger.error(f"Failed to establish websocket (InvalidStatus) for {self.identifier} (origin: {origin}): {e}")
            if e.status_code == 401 or e.status_code == 403:
                logger.info(f"Refreshing websocket due to {e.status_code}...")
                await self.refresh_websocket()
            return (httpx.Response(e.status_code, request=httpx.Request("POST", "command"), text=str(e)), "ws_fail:connect")
        except Exception as e:
            logger.error(f"Generic websocket failure for {self.identifier} on panel {self.panel_id}: {e}")
            return (httpx.Response(500, request=httpx.Request("POST", "command"), text=str(e)), "ws_fail:generic")

        return (httpx.Response(500, request=httpx.Request("POST", "command"), text="No output captured"), "ws_no_output")

    # -----------------------------------------------------------------
    # Backups API
    # -----------------------------------------------------------------

    async def list_backups(self) -> List[Backup]:
        resp = await self._client_request("GET", "backups")
        if resp.status_code == 200:
            return [Backup(b) for b in resp.json()["data"]]
        return []

    async def create_backup(self, name: Optional[str] = None, ignored_files: Optional[List[str]] = None, is_locked: bool = False) -> Optional[Backup]:
        payload = {"name": name, "ignored_files": ignored_files, "is_locked": is_locked}
        payload = {k: v for k, v in payload.items() if v is not None}
        
        resp = await self._client_request("POST", "backups", json=payload)
        if resp.status_code == 200:
            return Backup(resp.json())
        logger.error(f"Failed to create backup for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def get_backup_details(self, backup_uuid: str) -> Optional[Backup]:
        resp = await self._client_request("GET", f"backups/{backup_uuid}")
        if resp.status_code == 200:
            return Backup(resp.json())
        return None

    async def get_backup_download(self, backup_uuid: str) -> Optional[str]:
        resp = await self._client_request("POST", f"backups/{backup_uuid}/download")
        if resp.status_code == 200:
            return resp.json()["attributes"]["url"]
        logger.error(f"Failed to get backup download for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def restore_backup(self, backup_uuid: str, truncate_files: bool = False) -> httpx.Response:
        return await self._client_request("POST", f"backups/{backup_uuid}/restore", json={"truncate": truncate_files})

    async def toggle_backup_lock(self, backup_uuid: str) -> httpx.Response:
        return await self._client_request("POST", f"backups/{backup_uuid}/lock")

    async def delete_backup(self, backup_uuid: str) -> httpx.Response:
        return await self._client_request("DELETE", f"backups/{backup_uuid}")

    # -----------------------------------------------------------------
    # Databases API
    # -----------------------------------------------------------------

    async def list_databases(self) -> List[Database]:
        resp = await self._client_request("GET", "databases")
        if resp.status_code == 200:
            return [Database(db) for db in resp.json()["data"]]
        return []

    async def create_database(self, database_name: str, remote: str = "%") -> Optional[Database]:
        payload = {"database": database_name, "remote": remote}
        resp = await self._client_request("POST", "databases", json=payload)
        if resp.status_code == 200:
            return Database(resp.json())
        logger.error(f"Failed to create database for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def rotate_database_password(self, database_id: str) -> httpx.Response:
        return await self._client_request("POST", f"databases/{database_id}/rotate-password")

    async def delete_database(self, database_id: str) -> httpx.Response:
        return await self._client_request("DELETE", f"databases/{database_id}")

    # -----------------------------------------------------------------
    # Files API
    # -----------------------------------------------------------------

    async def list_files(self, directory: str = "/") -> List[FileStat]:
        resp = await self._client_request("GET", "files/list", params={"directory": directory})
        if resp.status_code == 200:
            return [FileStat(f) for f in resp.json()["data"]]
        return []

    async def get_file_contents(self, file_path: str) -> Optional[str]:
        resp = await self._client_request("GET", "files/contents", params={"file": file_path})
        if resp.status_code == 200:
            return resp.text
        return None

    async def get_file_download(self, file_path: str) -> Optional[str]:
        resp = await self._client_request("POST", "files/download", json={"file": file_path})
        if resp.status_code == 200:
            return resp.json()["attributes"]["url"]
        return None

    async def rename_file(self, root: str, from_name: str, to_name: str) -> httpx.Response:
        payload = {"root": root, "files": [{"from": from_name, "to": to_name}]}
        return await self._client_request("PUT", "files/rename", json=payload)

    async def copy_file(self, location: str) -> httpx.Response:
        return await self._client_request("POST", "files/copy", json={"location": location})

    async def write_file(self, file_path: str, content: str) -> httpx.Response:
        headers = self.client_headers.copy()
        headers["Content-Type"] = "text/plain"
        
        if not self.session:
            return httpx.Response(status_code=500, request=httpx.Request("POST", f"{self.base_url}/client/servers/{self.identifier}/files/write"), text="Client API not configured")

        full_url = f"{self.base_url}/client/servers/{self.identifier}/files/write"
        
        return await self.session.post(full_url, params={"file": file_path}, content=content, headers=headers)

    async def compress_files(self, root: str, files: List[str]) -> Optional[FileStat]:
        payload = {"root": root, "files": files}
        resp = await self._client_request("POST", "files/compress", json=payload)
        if resp.status_code == 200:
            return FileStat(resp.json())
        return None

    async def decompress_file(self, root: str, file: str) -> httpx.Response:
        payload = {"root": root, "file": file}
        return await self._client_request("POST", "files/decompress", json=payload)

    async def delete_files(self, root: str, files: List[str]) -> httpx.Response:
        payload = {"root": root, "files": files}
        return await self._client_request("POST", "files/delete", json=payload)

    async def create_folder(self, root: str, name: str) -> httpx.Response:
        payload = {"root": root, "name": name}
        return await self._client_request("POST", "files/create-folder", json=payload)

    async def get_upload_url(self) -> Optional[str]:
        resp = await self._client_request("GET", "files/upload")
        if resp.status_code == 200:
            return resp.json()["attributes"]["url"]
        return None

    # -----------------------------------------------------------------
    # Network API
    # -----------------------------------------------------------------

    async def list_allocations(self) -> List[Allocation]:
        resp = await self._client_request("GET", "network/allocations")
        if resp.status_code == 200:
            self.allocations = [Allocation(alloc["attributes"]) for alloc in resp.json()["data"]]
            return self.allocations
        return []

    async def set_primary_allocation(self, allocation_id: int) -> Optional[Allocation]:
        resp = await self._client_request("POST", f"network/allocations/{allocation_id}/primary")
        if resp.status_code == 200:
            return Allocation(resp.json()["attributes"])
        return None

    async def unassign_allocation(self, allocation_id: int) -> httpx.Response:
        return await self._client_request("DELETE", f"network/allocations/{allocation_id}")
        
    # -----------------------------------------------------------------
    # Schedules API
    # -----------------------------------------------------------------

    async def list_schedules(self) -> List[Schedule]:
        resp = await self._client_request("GET", "schedules")
        if resp.status_code == 200:
            return [Schedule(s) for s in resp.json()["data"]]
        return []

    async def create_schedule(self, name: str, cron_minute: str, cron_hour: str, cron_day_of_month: str, cron_month: str, cron_day_of_week: str, is_active: bool = True, only_when_online: bool = False) -> Optional[Schedule]:
        payload = {
            "name": name, "is_active": is_active, "only_when_online": only_when_online,
            "minute": cron_minute, "hour": cron_hour, "day_of_month": cron_day_of_month,
            "month": cron_month, "day_of_week": cron_day_of_week
        }
        resp = await self._client_request("POST", "schedules", json=payload)
        if resp.status_code == 200:
            return Schedule(resp.json())
        logger.error(f"Failed to create schedule for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def get_schedule(self, schedule_id: int) -> Optional[Schedule]:
        resp = await self._client_request("GET", f"schedules/{schedule_id}")
        if resp.status_code == 200:
            return Schedule(resp.json())
        return None

    async def update_schedule(self, schedule_id: int, **kwargs) -> Optional[Schedule]:
        payload = {
            "name": kwargs.get("name"), "is_active": kwargs.get("is_active"),
            "only_when_online": kwargs.get("only_when_online"),
            "minute": kwargs.get("cron_minute"), "hour": kwargs.get("cron_hour"),
            "day_of_month": kwargs.get("cron_day_of_month"), "month": kwargs.get("cron_month"),
            "day_of_week": kwargs.get("cron_day_of_week")
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        
        resp = await self._client_request("POST", f"schedules/{schedule_id}", json=payload)
        if resp.status_code == 200:
            return Schedule(resp.json())
        logger.error(f"Failed to update schedule {schedule_id} for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def delete_schedule(self, schedule_id: int) -> httpx.Response:
        return await self._client_request("DELETE", f"schedules/{schedule_id}")

    async def create_task(self, schedule_id: int, action: str, payload: str, time_offset: int = 0) -> Optional[Task]:
        payload_json = {"action": action, "payload": payload, "time_offset": time_offset}
        resp = await self._client_request("POST", f"schedules/{schedule_id}/tasks", json=payload_json)
        if resp.status_code == 200:
            return Task(resp.json()["attributes"])
        logger.error(f"Failed to create task for schedule {schedule_id} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def update_task(self, schedule_id: int, task_id: int, action: str, payload: str, time_offset: int) -> Optional[Task]:
        payload_json = {"action": action, "payload": payload, "time_offset": time_offset}
        resp = await self._client_request("POST", f"schedules/{schedule_id}/tasks/{task_id}", json=payload_json)
        if resp.status_code == 200:
            return Task(resp.json()["attributes"])
        logger.error(f"Failed to update task {task_id} for schedule {schedule_id} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None
        
    async def delete_task(self, schedule_id: int, task_id: int) -> httpx.Response:
        return await self._client_request("DELETE", f"schedules/{schedule_id}/tasks/{task_id}")

    # -----------------------------------------------------------------
    # Settings API
    # -----------------------------------------------------------------

    async def rename_server(self, name: str) -> httpx.Response:
        resp = await self._client_request("POST", "settings/rename", json={"name": name})
        if resp.status_code == 204:
            self.name = name
        return resp

    async def reinstall_server(self) -> httpx.Response:
        return await self._client_request("POST", "settings/reinstall")

    async def update_docker_image(self, docker_image: str) -> httpx.Response:
        return await self._client_request("PUT", "settings/docker-image", json={"docker_image": docker_image})

    # -----------------------------------------------------------------
    # Startup API
    # -----------------------------------------------------------------

    async def get_startup_vars(self) -> List[EggVariable]:
        resp = await self._client_request("GET", "startup")
        if resp.status_code == 200:
            self.egg_variables = [EggVariable(var["attributes"]) for var in resp.json()["data"]]
            return self.egg_variables
        return []

    async def update_startup_var(self, key: str, value: str) -> Optional[EggVariable]:
        payload = {"key": key, "value": str(value)}
        resp = await self._client_request("PUT", "startup/variable", json=payload)
        if resp.status_code == 200:
            return EggVariable(resp.json()["attributes"])
        logger.error(f"Failed to update startup var {key} for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    # -----------------------------------------------------------------
    # Users (Subusers) API
    # -----------------------------------------------------------------

    async def list_subusers(self) -> List[Subuser]:
        resp = await self._client_request("GET", "users")
        if resp.status_code == 200:
            return [Subuser(u) for u in resp.json()["data"]]
        return []

    async def create_subuser(self, email: str, permissions: List[str]) -> Optional[Subuser]:
        payload = {"email": email, "permissions": permissions}
        resp = await self._client_request("POST", "users", json=payload)
        if resp.status_code == 200:
            return Subuser(resp.json())
        logger.error(f"Failed to create subuser for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def get_subuser(self, user_uuid: str) -> Optional[Subuser]:
        resp = await self._client_request("GET", f"users/{user_uuid}")
        if resp.status_code == 200:
            return Subuser(resp.json())
        return None

    async def update_subuser(self, user_uuid: str, permissions: List[str]) -> Optional[Subuser]:
        payload = {"permissions": permissions}
        resp = await self._client_request("POST", f"users/{user_uuid}", json=payload)
        if resp.status_code == 200:
            return Subuser(resp.json())
        logger.error(f"Failed to update subuser {user_uuid} for {self.identifier} on panel {self.panel_id}: {resp.status_code} {resp.text}")
        return None

    async def delete_subuser(self, user_uuid: str) -> httpx.Response:
        return await self._client_request("DELETE", f"users/{user_uuid}")