# Ptero-Wrapper Documentation
This guide provides a detailed overview of the `ptero` package, its main classes, and how to use them effectively.

## Table of Contents
1. Introduction & Architecture
2. The PteroControl Class
3. The ClientServer Class (Client API)
4. The ApplicationAPI Class (Application API)
5. Working with Relationships

## 1. Introduction & Architecture

This wrapper is built around one central controller (`PteroControl`) that manages API sessions and acts as the entry point.
- `PteroControl`: You instantiate this class once with your API keys. It handles all `httpx` sessions.
- `ClientServer`: `PteroControl` returns a list of `ClientServer` objects. Each object represents one server and contains all the methods to manage it (start, stop, files, etc.).
- `ApplicationAPI`: This class is attached to your `PteroControl` instance as `control.app`. It contains all methods for the Application-side API (managing users, nodes, etc.).
- **Models**: All other files in `ptero/models.py` are data classes (like `Node`, `User`, `Backup`) that parse the JSON responses into easy-to-use Python objects.

### Multi-Panel Logic
The wrapper is designed to work with multiple separate Pterodactyl panels.

- You provide a list of panel configurations (ID, URL, keys) when initializing PteroControl.
- When you call control.get_servers(), it fetches servers from all configured client panels and combines them into one list.
- When you call control.get_server(id), it checks all client panels to find the correct one.
- Each ClientServer object internally knows which panel it belongs to (server.panel_id) and automatically uses the correct API session for all its methods (e.g., server.start() will work correctly regardless of which panel it's on).

## 2. The `PteroControl` Class
This is the main entry point for the entire wrapper.

### Initialization
```python
from ptero import PteroControl, Panel

# You can use the Panel model for type safety and clarity
panels_config = [
    Panel(
        id='main',
        base_url='https://panel.example.com/api',
        client_key='ptlc_MainKey...',
        app_key='ptla_MainKey...'
    ),
    Panel(
        id='secondary',
        base_url='http://panel2.example.com/api',
        client_key='ptlc_SecondKey...',
        app_key='ptla_SecondKey...'
    )
]

# The control class also accepts a list of dictionaries
control = PteroControl(panels=panels_config)

```
You pass a list of panel configuration dictionaries.
- `id` (str): A unique name for you to identify this panel.
- `base_url` (str): The full API URL for the panel.
- `client_key` (str, Optional): The Client API key for this panel.
- `app_key` (str, Optional): The Application API key for this panel.

### Primary Methods
`await control.get_servers(fast: bool = False) -> List[ClientServer]` Fetches all servers from all configured Client APIs.
- `fast=False` (Default): Fully initializes each `ClientServer` object, including fetching its resource usage and websocket data. This is slower but provides complete objects.
- `fast=True`: Quickly fetches the server list without getting resources/websocket data for each one. `server.resources` will be `None`. Useful for autocompletion or just listing names.

`await control.get_server(id: str) -> Optional[ClientServer]` Fetches a single, fully-initialized `ClientServer` object by its identifier (e.g., `5a01ps2e`). It automatically checks both Main and OCI panels.

`await control.close()` **CRITICAL:** You must call this before your program exits to properly close all `httpx` network sessions. A good place is in a `finally` block.

`control.app_apis -> Dict[str, ApplicationAPI]` This attribute is a dictionary holding all `ApplicationAPI` instances, keyed by their `panel_id`.

Example: `await control.app_apis['main'].get_nodes()`

## 3. The `ClientServer` Class (Client API)
This object represents a single server and contains all methods for managing it. You get this object from `control.get_servers()` or `control.get_server(id)`.

### Key Attributes
- `server.name` (str): The server name.
- `server.id` (str): The short identifier.
- `server.uuid` (str): The full unique ID.
- `server.resources` (Resource): An object with `.current_state`, `.memory_bytes`, `.cpu_absolute`, etc.
- `server.allocations` (List[Allocation]): A list of all allocations for the server.
- `server.node` (Node): (App API) The `Node` object this server runs on.
- `server.owner` (User): (App API) The `User` object that owns this server.
- `server.panel_id` (str): The ID you defined for the panel this server belongs to (e.g., 'main', 'secondary').

### Power Control
- `await server.start() -> httpx.Response`
- `await server.stop() -> httpx.Response`
- `await server.restart() -> httpx.Response`
- `await server.kill() -> httpx.Response`

### Sending Commands
- `await server.send_command(command: str) -> httpx.Response` Sends a simple command. Does not return output.
- `await server.send_command_with_output(command: str, timeout: int = 5) -> tuple[httpx.Response, str]` Sends a command and connects to the websocket to listen for the first line of output.
    - Success: Returns `(response, "Server output line")`
    - Failure: Returns `(response, "ws_fail:jwt")`, `(response, "ws_timeout")`, etc.

### File Management
- `await server.list_files(directory: str = "/") -> List[FileStat]`
- `await server.get_file_contents(file_path: str) -> Optional[str]`
- `await server.write_file(file_path: str, content: str) -> httpx.Response`
- `await server.rename_file(root: str, from_name: str, to_name: str) -> httpx.Response`
- `await server.delete_files(root: str, files: List[str]) -> httpx.Response`
- ...and many more (`compress`, `decompress`, `copy`, `create_folder`, etc.)

### Other Methods
`ClientServer` also includes full management for:
- Backups: `list_backups`, `create_backup`, `get_backup_download`, `restore_backup`, `delete_backup`
- Databases: `list_databases`, `create_database`, `rotate_database_password`, `delete_database`
- Schedules & Tasks: `list_schedules`, `create_schedule`, `create_task`, `delete_task`
- Subusers: `list_subusers`, `create_subuser`, `update_subuser`, `delete_subuser`
- Network: `list_allocations`, `set_primary_allocation`
- Settings: `rename_server`, `reinstall_server`
- Startup: `get_startup_vars`, `update_startup_var`

### Other Methods

`ClientServer` also includes full management for:

- #### Backups

    - `await server.list_backups() -> List[Backup]`

    - `await server.create_backup(name: str) -> Optional[Backup]`

    - `await server.get_backup_download(backup_uuid: str) -> Optional[str]`

    - `await server.restore_backup(backup_uuid: str) -> httpx.Response`

    - `await server.delete_backup(backup_uuid: str) -> httpx.Response`

- #### Databases

    - `await server.list_databases() -> List[Database]`

    - `await server.create_database(name: str) -> Optional[Database]`

    - `await server.rotate_database_password(database_id: str) -> httpx.Response`

    - `await server.delete_database(database_id: str) -> httpx.Response`

- #### Schedules & Tasks

    - `await server.list_schedules() -> List[Schedule]`

    - `await server.create_schedule(name="My Task", cron_minute="*/5", ...) -> Optional[Schedule]`

    - `await server.create_task(schedule_id: int, action="command", payload="say Hello") -> Optional[Task]`

    - `await server.delete_task(schedule_id: int, task_id: int) -> httpx.Response`

- #### Subusers

    - `await server.list_subusers() -> List[Subuser]`

    - `await server.create_subuser(email: str, permissions: List[str]) -> Optional[Subuser]`

    - `await server.update_subuser(user_uuid: str, permissions: List[str]) -> Optional[Subuser]`

    - `await server.delete_subuser(user_uuid: str) -> httpx.Response`

- #### Network

    - `await server.list_allocations() -> List[Allocation]`

    - `await server.set_primary_allocation(allocation_id: int) -> Optional[Allocation]`

- #### Settings & Startup

    - `await server.rename_server(name: str) -> httpx.Response`

    - `await server.reinstall_server() -> httpx.Response`

    - `await server.get_startup_vars() -> List[EggVariable]`

    - `await server.update_startup_var(key: str, value: str) -> Optional[EggVariable]`

## 4. The `ApplicationAPI` Class (Application API)
This class handles all "admin-level" API calls. You access instances of it via `control.app_apis['panel_id']`

All methods in ApplicationAPI operate only on the panel they belong to.

### User Management

- `await control.app_apis['main'].get_users() -> List[User]`

- `await control.app_apis['main'].get_user(user_id: int) -> Optional[User]`

- `await control.app_apis['main'].create_user(email=..., username=...) -> Optional[User]`

- `await control.app_apis['main'].delete_user(user_id: int) -> bool`

### Node Management

- `await control.app_apis['main'].get_nodes() -> List[Node]`

- `await control.app_apis['main'].get_node(node_id: int) -> Optional[Node]`

- `await control.app_apis['main'].get_node_config(node_id: int) -> Optional[dict]`

- `await control.app_apis['main'].create_allocation(node_id=1, ip="...", ports=["25565"]) -> bool`

### Server Management

- `await control.app_apis['main'].get_servers() -> List[dict]`
(Returns raw server dicts, as ClientServer is a Client API object)

- `await control.app_apis['main'].get_server_details(server_id: int) -> Optional[dict]`

- `await control.app_apis['main'].create_server(data: dict) -> Optional[dict]`

- `await control.app_apis['main'].suspend_server(server_id: int) -> bool`

- `await control.app_apis['main'].delete_server(server_id: int, force: bool = False) -> bool`

### Nest & Egg Management

- `await control.app_apis['main'].get_nests() -> List[Nest]`

- `await control.app_apis['main'].get_nest(nest_id: int) -> Optional[Nest]`

- `await control.app_apis['main'].get_eggs_in_nest(nest_id: int) -> List[Egg]`

- `await control.app_apis['main'].get_egg(nest_id: int, egg_id: int) -> Optional[Egg]`

## 5. Working with Relationships
The wrapper automatically links objects together.

### Eager-Loading (Automatic)
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
print(f"Server Panel: {server.panel_id}, Node Panel: {server.node.panel_id}")
```

### Lazy-Loading (On-Demand)
Some models have methods to fetch their relatives on demand.
#### Example 1: Get an Egg's Nest
```py
# Get an egg directly from the 'main' panel
egg = await control.app_apis['main'].get_egg(nest_id=1, egg_id=5)

if egg:
    # The egg.nest attribute might be partial, so we fetch the full object
    # This call uses the same API instance the egg was fetched from
    nest = await egg.get_nest()
    if nest:
        print(f"Egg '{egg.name}' (Panel: {egg.panel_id}) belongs to Nest '{nest.name}' (Panel: {nest.panel_id})")
```

#### Example 2: Get a Nest's Eggs
```py
nest = await control.app_apis['main'].get_nest(1)

if nest:
    # Eager-loading (from 'include=eggs') already includes eggs
    print("--- Eager-loaded Eggs ---")
    for egg in nest.eggs:
        print(f"- {egg.name}")

    # To refresh the list, you can call the method:
    print("\n--- Refreshed Eggs ---")
    refreshed_eggs = await nest.get_eggs()
    for egg in refreshed_eggs:
        print(f"- {egg.name}")
```

#### Example 3: Re-fetch a Server's Owner
```py
server = await control.get_server("5a01ps2e")

if server:
    # This is usually pre-loaded, but this method forces a fresh API call
    owner = await server.get_owner()
    if owner:
        print(f"Refetched owner: {owner.username}")
```