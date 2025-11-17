# Ptero-Wrapper
An asynchronous, feature-rich Python wrapper for the Pterodactyl Panel API.

`ptero` is designed to provide a clean, modern, and fully `async` interface for both the Pterodactyl **Client API** and **Application API.** It's built on `httpx` and `asyncio`, making it highly performant for modern applications.

A key feature of this wrapper is its built-in support for **multi-panel operation**, allowing you to seamlessly manage servers across multiple different Pterodactyl instances with a single controller.

## Features
- **Fully Asynchronous:** Uses `async/await` and `httpx` for high-performance, non-blocking I/O.
- **Complete API Coverage:** Provides methods for all Client and Application API endpoints.
- **Multi-Panel Support:** Natively handles API keys and URLs for multiple distinct Pterodactyl instances.
- **Object-Oriented Models:** All API responses are parsed into clean, type-hinted data models (e.g., `ClientServer`, `Node`, `User`, `Backup`).
- **Relationship Handling:** Intelligently links related objects. A `ClientServer` object can have its `Node` and `Owner` (User) objects pre-attached. Models like `Nest` and `Egg` can lazy-load each other.
- **Real-time Websockets:** Includes helper methods for authenticating to the client websocket and capturing real-time console output.

## Installation
```
pip install ptero
```

## Quick Start
Here's a simple example of how to instantiate the controller and manage a server.
```python
import asyncio
from ptero import PteroControl, Panel

# Define your panel configurations
panels_config = [
    Panel(
        id='main_panel',
        base_url='[https://panel.example.com/api](https://panel.example.com/api)',
        client_key='ptlc_MainKey...',
        app_key='ptla_MainKey...'
    ),
    Panel(
        id='oci_panel',
        base_url='[http://panel2.example.com/api](http://panel2.example.com/api)',
        client_key='ptlc_OciKey...',
        app_key='ptla_OciKey...'
    ),
    Panel(
        id='test_panel',
        base_url='[http://testpanel.example.com/api](http://testpanel.example.com/api)',
        client_key='ptlc_TestKey...'
        # This panel has no app key
    )
]

async def main():
    # Instantiate the main controller
    control = PteroControl(panels=panels_config)

    try:
        # --- Client API Example ---
        print("Fetching servers from ALL panels...")
        servers = await control.get_servers()
        if not servers:
            print("No servers found.")
            return

        server = servers[0]
        print(f"Found server: {server.name} (Panel: {server.panel_id}, State: {server.resources.current_state})")

        # Send a power signal
        # await server.start()
        # print("Server start signal sent.")

        # Send a command and get the output
        resp, output = await server.send_command_with_output("list")
        if not output.startswith("ws_fail"):
            print(f"Server List: {output}")

        # --- Application API Example ---
        print("\nFetching nodes from 'main_panel'...")
        # Access a specific panel's API
        if 'main_panel' in control.app_apis:
            nodes = await control.app_apis['main_panel'].get_nodes()
            for node in nodes:
                print(f"- Node: {node.name} (Location: {node.location.short_code})")
        
        # --- Relationship Example ---
        if server.node and server.owner:
            print(f"\nServer {server.name} is on Node: {server.node.name}")
            print(f"Server {server.name} is owned by: {server.owner.username}")


    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Always close the session when done
        await control.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## License
This project is licensed under the MIT License.