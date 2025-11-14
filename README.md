# Ptero-Wrapper
An asynchronous, feature-rich Python wrapper for the Pterodactyl Panel API.
`ptero-wrapper` is designed to provide a clean, modern, and fully `async` interface for both the Pterodactyl **Client API** and **Application API.** It's built on `httpx` and `asyncio`, making it highly performant for modern applications.

A key feature of this wrapper is its built-in support for **dual-panel operation**, allowing you to seamlessly manage servers across two different Pterodactyl instances (e.g., a primary panel and an OCI panel) with a single controller.

# Features
- **Fully Asynchronous:** Uses `async/await` and httpx for high-performance, non-blocking I/O.
- **Complete API Coverage:** Provides methods for all Client and Application API endpoints.
- **Dual-Panel Support:** Natively handles separate API keys and URLs for two distinct Pterodactyl instances.
- **Object-Oriented Models:** All API responses are parsed into clean, type-hinted data models (e.g., `ClientServer`, `Node`, `User`, `Backup`).
- **Relationship Handling:** Intelligently links related objects. A `ClientServer` object can have its `Node` and `Owner` (User) objects pre-attached. Models like `Nest` and `Egg` can lazy-load each other.
- **Real-time Websockets:** Includes helper methods for authenticating to the client websocket and capturing real-time console output.

# Installation
```pip install ptero-wrapper```

# Quick Start
Here's a simple example of how to instantiate the controller and manage a server.
```python
import asyncio
from ptero_wrapper import PteroControl

# API keys (only provide the ones you need)
CLIENT_KEY = "ptlc_..."
APP_KEY = "ptla_..."
CLIENT_KEY_OCI = "ptlc_..."
APP_KEY_OCI = "ptla_..."

async def main():
    # Instantiate the main controller
    # You can also customize base_url and oci_base_url
    control = PteroControl(
        client_api_key=CLIENT_KEY,
        app_api_key=APP_KEY,
        client_oci_api_key=CLIENT_KEY_OCI,
        app_oci_api_key=APP_KEY_OCI
    )

    try:
        # --- Client API Example ---
        print("Fetching servers...")
        servers = await control.get_servers()
        if not servers:
            print("No servers found.")
            return

        server = servers[0]
        print(f"Found server: {server.name} (State: {server.resources.current_state})")

        # Send a power signal
        # await server.start()
        # print("Server start signal sent.")

        # Send a command and get the output
        resp, output = await server.send_command_with_output("list")
        if not output.startswith("ws_fail"):
            print(f"Server List: {output}")

        # --- Application API Example ---
        print("\nFetching nodes...")
        nodes = await control.app.get_nodes()
        for node in nodes:
            print(f"- Node: {node.name} (Location: {node.location.short_code})")
        
        # --- Relationship Example ---
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

# License
This project is licensed under the MIT License.