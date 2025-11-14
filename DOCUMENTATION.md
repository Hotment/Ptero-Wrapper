# Ptero-Wrapper Documentation
This guide provides a detailed overview of the `ptero` package, its main classes, and how to use them effectively.

# Table of Contents
1. Introduction & Architecture
2. The PteroControl Class
3. The ClientServer Class (Client API)
4. The ApplicationAPI Class (Application API)
5. Working with Relationships

**1. Introduction & Architecture**
This wrapper is built around one central controller (`PteroControl`) that manages API sessions and acts as the entry point.
- `PteroControl`: You instantiate this class once with your API keys. It handles all `httpx` sessions.
- `ClientServer`: `PteroControl` returns a list of `ClientServer` objects. Each object represents one server and contains all the methods to manage it (start, stop, files, etc.).
- `ApplicationAPI`: This class is attached to your `PteroControl` instance as `control.app`. It contains all methods for the Application-side API (managing users, nodes, etc.).
- **Models**: All other files in `ptero/models.py` are data classes (like `Node`, `User`, `Backup`) that parse the JSON responses into easy-to-use Python objects.

# Dual-Panel Logic
The wrapper is designed to work with two separate Pterodactyl panels (e.g., "Main" and "OCI").
- You provide API keys for both (e.g., `client_api_key` and `client_oci_api_key`).
- When you call `control.get_servers()`, it fetches servers from both panels and combines them into one list.
- When you call `control.get_server(id)`, it checks both panels to find the correct one.
- Each `ClientServer` object internally knows if it belongs to the "Main" or "OCI" panel (as `server.oci: bool`) and automatically uses the correct API session for all its methods (e.g., `server.start()` will work correctly regardless of which panel it's on).

2. The `PteroControl` Class
This is the main entry point for the entire wrapper.

**Initialization**
```python
from ptero_wrapper import PteroControl

control = PteroControl(
    client_api_key="ptlc_...",
    app_api_key="ptla_...",
    client_oci_api_key="ptlc_...",
    app_oci_api_key="ptla_...",
    base_url="https.../api",       # Optional: URL for main panel
    oci_base_url="http.../api"  # Optional: URL for OCI panel
)
```

All parameters are optional. If you don't provide client_api_key, all Client API calls for the main panel will be disabled.

# Primary Methods
`await control.get_servers(fast: bool = False) -> List[ClientServer]` Fetches all servers from all configured Client APIs.
- `fast=False` (Default): Fully initializes each `ClientServer` object, including fetching its resource usage and websocket data. This is slower but provides complete objects.
- `fast=True`: Quickly fetches the server list without getting resources/websocket data for each one. `server.resources` will be `None`. Useful for autocompletion or just listing names.

`await control.get_server(id: str) -> Optional[ClientServer]` Fetches a single, fully-initialized `ClientServer` object by its identifier (e.g., `5a01ps2e`). It automatically checks both Main and OCI panels.

`await control.close()` **CRITICAL:** You must call this before your program exits to properly close all `httpx` network sessions. A good place is in a `finally` block.

`control.app -> ApplicationAPI` This attribute is your gateway to the Application API. See section 4 for details.

**3. The `ClientServer` Class (Client API)**
This object represents a single server and contains all methods for managing it. You get this object from `control.get_servers()` or `control.get_server(id)`.

**Key Attributes**
- `server.name` (str): The server name.
- `server.id` (str): The short identifier.
- `server.uuid` (str): The full unique ID.
- `server.resources` (Resource): An object with `.current_state`, `.memory_bytes`, `.cpu_absolute`, etc.
- `server.allocations` (List[Allocation]): A list of all allocations for the server.
- `server.node` (Node): (App API) The `Node` object this server runs on.
- `server.owner` (User): (App API) The `User` object that owns this server.
- `server.oci` (bool): `True` if this server is on the OCI panel, `False` otherwise.

# Power Control
- `await server.start() -> httpx.Response`
- `await server.stop() -> httpx.Response`
- `await server.restart() -> httpx.Response`
- `await server.kill() -> httpx.Response`

# Sending Commands
- `await server.send_command(command: str) -> httpx.Response`Sends a simple command. Does not return output.
- `await server.send_command_with_output(command: str, timeout: int = 5) -> tuple[httpx.Response, str]` Sends a command and connects to the websocket to listen for the first line of output.
    - Success: Returns `(response, "Server output line")`
    - Failure: Returns `(response, "ws_fail:jwt")`, `(response, "ws_timeout")`, etc.

# File Management
`await server.list_files(directory: str = "/") -> List[FileStat]`
`await server.get_file_contents(file_path: str) -> Optional[str]`
`await server.write_file(file_path: str, content: str) -> httpx.Response`
`await server.rename_file(root: str, from_name: str, to_name: str) -> httpx.Response`
`await server.delete_files(root: str, files: List[str]) -> httpx.Response`
...and many more (`compress`, `decompress`, `copy`, `create_folder`, etc.)

# Other Methods
`ClientServer` also includes full management for:
- Backups: `list_backups`, `create_backup`, `get_backup_download`, `restore_backup`, `delete_backup`
- Databases: `list_databases`, `create_database`, `rotate_database_password`, `delete_database`
- Schedules & Tasks: `list_schedules`, `create_schedule`, `create_task`, `delete_task`
- Subusers: `list_subusers`, `create_subuser`, `update_subuser`, `delete_subuser`
- Network: `list_allocations`, `set_primary_allocation`
- Settings: `rename_server`, `reinstall_server`
- Startup: `get_startup_vars`, `update_startup_var`

4. The `ApplicationAPI` Class (Application API)
This class handles all "admin-level" API calls. You access it via your `PteroControl` instance: `control.app`.

All methods in `ApplicationAPI` accept an `oci: bool = False` parameter to specify which panel to query.

**User Management**
`await control.app.get_users(oci: bool = False) -> List[User]`
`await control.app.get_user(user_id: int, oci: bool = False) -> Optional[User]`
`await control.app.create_user(email=..., username=...) -> Optional[User]`
`await control.app.delete_user(user_id: int, oci: bool = False) -> bool`
**Node Management**
`await control.app.get_nodes(oci: bool = False) -> List[Node]`
`await control.app.get_node(node_id: int, oci: bool = False) -> Optional[Node]`
`await control.app.get_node_config(node_id: int, oci: bool = False) -> Optional[dict]`
`await control.app.create_allocation(node_id=1, ip="...", ports=["25565"]) -> bool`
**Server Management**
`await control.app.get_servers(oci: bool = False) -> List[dict]` (Returns raw server dicts, as `ClientServer` is a Client API object)
`await control.app.get_server_details(server_id: int, oci: bool = False) -> Optional[dict]`
`await control.app.create_server(data: dict, oci: bool = False) -> Optional[dict]`
`await control.app.suspend_server(server_id: int, oci: bool = False) -> bool`
`await control.app.delete_server(server_id: int, force: bool = False, oci: bool = False) -> bool`
**Nest & Egg Management**
`await control.app.get_nests(oci: bool = False) -> List[Nest]`
`await control.app.get_nest(nest_id: int, oci: bool = False) -> Optional[Nest]`
`await control.app.get_eggs_in_nest(nest_id: int, oci: bool = False) -> List[Egg]`
`await control.app.get_egg(nest_id: int, egg_id: int, oci: bool = False) -> Optional[Egg]`

5. Working with Relationships
The wrapper automatically links objects together.

**Eager-Loading (Automatic)**
When you call `control.get_servers()` or `control.get_server(id)`, the wrapper:
1. Fetches the `ClientServer` object.
2. Fetches the Application API `Node` and `User` objects from its internal cache.
3. Attaches them directly to the `ClientServer` object.
This means you can immediately access relational data:
```py
server = await control.get_server("5a01ps2e")

# These attributes are pre-loaded
print(f"Server Owner: {server.owner.username}")
print(f"Server Node: {server.node.name}")
print(f"Node Location: {server.node.location.short_code}")
```

**Lazy-Loading (On-Demand)**
Some models have methods to fetch their relatives on demand.
**Example 1: Get an Egg's Nest**
```py
# Get an egg directly
egg = await control.app.get_egg(nest_id=1, egg_id=5)

# The egg.nest attribute might be partial, so we fetch the full object
nest = await egg.get_nest()
print(f"Egg '{egg.name}' belongs to Nest '{nest.name}'")
```

**Example 2: Get a Nest's Eggs**
```py
nest = await control.app.get_nest(1)

# Eager-loading already includes eggs
for egg in nest.eggs:
    print(f"- {egg.name}")

# To refresh the list, you can call the method:
await nest.get_eggs()
```

**Example 3: Re-fetch a Server's Owner**
```py
server = await control.get_server("5a01ps2e")

# This is usually pre-loaded, but this method forces a fresh API call
owner = await server.get_owner()
print(f"Refetched owner: {owner.username}")
```