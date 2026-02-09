"""
Ptero-Wrapper Application
Contains the ApplicationAPI class for interacting with the Pterodactyl Application API.
"""

import httpx, logging
from typing import Optional, List, Dict, Any
from .models import User, Node, Location, Nest, Egg, NodeAllocation

logger = logging.getLogger("ptero.application")

class ApplicationAPI:
    def __init__(self, 
                 app_session: httpx.AsyncClient, 
                 base_url: str,
                 panel_id: str):
        
        self.app_session = app_session
        self.base_url = base_url
        self.panel_id = panel_id
        self.enabled = app_session is not None

    async def _paginate(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[dict]:
        """Helper to automatically paginate through 'list' endpoints."""
        if params is None:
            params = {}
        
        if not self.app_session:
            logger.warning(f"Attempted to paginate {endpoint} on panel {self.panel_id} but session is not enabled.")
            return []

        full_url = f"{self.base_url}/application/{endpoint}"
        
        all_data: List[dict] = []
        page = 1
        params['page'] = page
        
        try:
            while True:
                params['page'] = page
                resp = await self.app_session.get(full_url, params=params)
                
                if resp.status_code != 200:
                    logger.error(f"Failed to paginate {endpoint} on panel {self.panel_id} page {page}: {resp.status_code} {resp.text}")
                    break
                    
                data = resp.json()
                all_data.extend(data['data'])
                
                if data['meta']['pagination']['current_page'] >= data['meta']['pagination']['total_pages']:
                    break
                page += 1
                
        except httpx.RequestError as e:
            logger.error(f"HTTP error during pagination for {endpoint} on panel {self.panel_id}: {e}")
        
        return all_data


    # -----------------------------------------------------------------
    # Application API Helper
    # -----------------------------------------------------------------

    async def _app_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make a request to the Application API."""
        if not self.app_session:
            logger.error(f"Application API request failed for {endpoint} on panel {self.panel_id}: API is not configured.")
            return httpx.Response(status_code=500, request=httpx.Request(method, f"{self.base_url}/application/{endpoint}"), text="Application API not configured")

        full_url = f"{self.base_url}/application/{endpoint}"
        
        try:
            return await self.app_session.request(method, full_url, **kwargs)
        except httpx.RequestError as e:
            logger.error(f"Application API request failed for {endpoint} on panel {self.panel_id}: {e}")
            return httpx.Response(status_code=500, request=httpx.Request(method, full_url), text=str(e))
    
    # -----------------------------------------------------------------
    # Application API - Users
    # -----------------------------------------------------------------

    async def get_users(self, params: Optional[Dict[str, Any]] = None) -> List[User]:
        """Gets a paginated list of all users."""
        if params is None: params = {}
        params['include'] = 'servers'
        all_users_data = await self._paginate("users", params=params)
        return [User(user_data, api=self, panel_id=self.panel_id) for user_data in all_users_data]

    async def get_user(self, user_id: int, params: Optional[Dict[str, Any]] = None) -> Optional[User]:
        """Gets details for a specific user."""
        if params is None: params = {}
        params['include'] = 'servers'
        resp = await self._app_request("GET", f"users/{user_id}", params=params)
        return User(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None

    async def create_user(self, email: str, username: str, first_name: str, last_name: str, **kwargs) -> Optional[User]:
        """Creates a new user."""
        payload = {
            "email": email, "username": username,
            "first_name": first_name, "last_name": last_name,
            **kwargs # Pass extra params like 'password', 'root_admin'
        }
        resp = await self._app_request("POST", "users", json=payload)
        return User(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 201 else None

    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Updates a user's details."""
        resp = await self._app_request("PATCH", f"users/{user_id}", json=kwargs)
        return User(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None

    async def delete_user(self, user_id: int) -> bool:
        """Deletes a user."""
        resp = await self._app_request("DELETE", f"users/{user_id}")
        return resp.status_code == 204

    # -----------------------------------------------------------------
    # Application API - Servers
    # -----------------------------------------------------------------

    async def get_servers(self, params: Optional[Dict[str, Any]] = None) -> List[dict]:
        """Gets a paginated list of all servers (returns raw dicts)."""
        if params is None: params = {}
        # Ensure relationships are included
        base_includes = ['user', 'node']
        existing_includes = params.get('include', '').split(',')
        all_includes = list(set(base_includes + [inc for inc in existing_includes if inc]))
        params['include'] = ','.join(all_includes)
        
        return await self._paginate("servers", params=params)

    async def get_server_details(self, server_id: int, params: Optional[Dict[str, Any]] = None) -> Optional[dict]:
        """Gets details for a specific server (returns raw dict)."""
        if params is None: params = {}
        # Ensure relationships are included
        base_includes = ['user', 'node']
        existing_includes = params.get('include', '').split(',')
        all_includes = list(set(base_includes + [inc for inc in existing_includes if inc]))
        params['include'] = ','.join(all_includes)
        
        resp = await self._app_request("GET", f"servers/{server_id}", params=params)
        return resp.json() if resp.status_code == 200 else None

    async def create_server(self, data: Dict[str, Any]) -> Optional[dict]:
        """Creates a new server."""
        resp = await self._app_request("POST", "servers", json=data)
        return resp.json() if resp.status_code == 201 else None

    async def update_server_details(self, server_id: int, **kwargs) -> Optional[dict]:
        """Updates a server's basic details (name, user, external_id, description)."""
        resp = await self._app_request("PATCH", f"servers/{server_id}/details", json=kwargs)
        return resp.json() if resp.status_code == 200 else None

    async def update_server_build(self, server_id: int, **kwargs) -> Optional[dict]:
        """Updates a server's build configuration (limits, allocations)."""
        resp = await self._app_request("PATCH", f"servers/{server_id}/build", json=kwargs)
        return resp.json() if resp.status_code == 200 else None

    async def update_server_startup(self, server_id: int, **kwargs) -> Optional[dict]:
        """Updates a server's startup parameters."""
        resp = await self._app_request("PATCH", f"servers/{server_id}/startup", json=kwargs)
        return resp.json() if resp.status_code == 200 else None

    async def suspend_server(self, server_id: int) -> bool:
        resp = await self._app_request("POST", f"servers/{server_id}/suspend")
        return resp.status_code == 204

    async def unsuspend_server(self, server_id: int) -> bool:
        resp = await self._app_request("POST", f"servers/{server_id}/unsuspend")
        return resp.status_code == 204

    async def rebuild_server(self, server_id: int) -> bool:
        resp = await self._app_request("POST", f"servers/{server_id}/rebuild")
        return resp.status_code == 204

    async def reinstall_server(self, server_id: int) -> bool:
        resp = await self._app_request("POST", f"servers/{server_id}/reinstall")
        return resp.status_code == 204

    async def delete_server(self, server_id: int, force: bool = False) -> bool:
        endpoint = f"servers/{server_id}"
        if force:
            endpoint += "/force"
        resp = await self._app_request("DELETE", endpoint)
        return resp.status_code == 204

    # -----------------------------------------------------------------
    # Application API - Nodes
    # -----------------------------------------------------------------

    async def get_nodes(self, params: Optional[Dict[str, Any]] = None) -> List[Node]:
        """Gets a paginated list of all nodes."""
        if params is None: params = {}
        # Ensure relationships are included
        base_includes = ['location', 'allocations']
        existing_includes = params.get('include', '').split(',')
        all_includes = list(set(base_includes + [inc for inc in existing_includes if inc]))
        params['include'] = ','.join(all_includes)
        
        all_nodes_data = await self._paginate("nodes", params=params)
        return [Node(node_data, api=self, panel_id=self.panel_id) for node_data in all_nodes_data]

    async def get_node(self, node_id: int, params: Optional[Dict[str, Any]] = None) -> Optional[Node]:
        """Gets details for a specific node."""
        if params is None: params = {}
        # Ensure relationships are included
        base_includes = ['location', 'allocations']
        existing_includes = params.get('include', '').split(',')
        all_includes = list(set(base_includes + [inc for inc in existing_includes if inc]))
        params['include'] = ','.join(all_includes)
        
        resp = await self._app_request("GET", f"nodes/{node_id}", params=params)
        return Node(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None
    
    async def get_node_config(self, node_id: int) -> Optional[dict]:
        """Gets the configuration for a specific node."""
        resp = await self._app_request("GET", f"nodes/{node_id}/configuration")
        return resp.json() if resp.status_code == 200 else None

    async def create_node(self, **kwargs) -> Optional[Node]:
        """Creates a new node."""
        resp = await self._app_request("POST", "nodes", json=kwargs)
        return Node(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 201 else None

    async def update_node(self, node_id: int, **kwargs) -> Optional[Node]:
        """Updates a node's details."""
        resp = await self._app_request("PATCH", f"nodes/{node_id}", json=kwargs)
        return Node(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None

    async def delete_node(self, node_id: int) -> bool:
        """Deletes a node."""
        resp = await self._app_request("DELETE", f"nodes/{node_id}")
        return resp.status_code == 204

    # -----------------------------------------------------------------
    # Application API - Node Allocations
    # -----------------------------------------------------------------

    async def get_node_allocations(self, node_id: int, params: Optional[Dict[str, Any]] = None) -> List[NodeAllocation]:
        """Gets a paginated list of all allocations for a node."""
        all_allocs_data = await self._paginate(f"nodes/{node_id}/allocations", params=params)
        return [NodeAllocation(alloc_data) for alloc_data in all_allocs_data]

    async def create_allocation(self, node_id: int, ip: str, ports: List[str], **kwargs) -> bool:
        """Creates new allocations on a node."""
        payload = {"ip": ip, "ports": ports, **kwargs}
        resp = await self._app_request("POST", f"nodes/{node_id}/allocations", json=payload)
        return resp.status_code == 204

    async def delete_allocation(self, node_id: int, allocation_id: int) -> bool:
        """Deletes an allocation from a node."""
        resp = await self._app_request("DELETE", f"nodes/{node_id}/allocations/{allocation_id}")
        return resp.status_code == 204
        
    # -----------------------------------------------------------------
    # Application API - Nests & Eggs
    # -----------------------------------------------------------------

    async def get_nests(self, params: Optional[Dict[str, Any]] = None) -> List[Nest]:
        """Gets a paginated list of all nests."""
        if params is None: params = {}
        params['include'] = 'eggs'
        all_nests_data = await self._paginate("nests", params=params)
        return [Nest(nest_data, api=self, panel_id=self.panel_id) for nest_data in all_nests_data]

    async def get_nest(self, nest_id: int, params: Optional[Dict[str, Any]] = None) -> Optional[Nest]:
        """Gets details for a specific nest."""
        if params is None: params = {}
        params['include'] = 'eggs'
        resp = await self._app_request("GET", f"nests/{nest_id}", params=params)
        return Nest(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None
        
    async def get_eggs_in_nest(self, nest_id: int, params: Optional[Dict[str, Any]] = None) -> List[Egg]:
        """Gets a paginated list of all eggs in a nest."""
        if params is None: params = {}
        params['include'] = 'nest'
        all_eggs_data = await self._paginate(f"nests/{nest_id}/eggs", params=params)
        return [Egg(egg_data, api=self, panel_id=self.panel_id) for egg_data in all_eggs_data]

    async def get_egg(self, nest_id: int, egg_id: int, params: Optional[Dict[str, Any]] = None) -> Optional[Egg]:
        """Gets details for a specific egg."""
        if params is None: params = {}
        params['include'] = 'nest'
        resp = await self._app_request("GET", f"nests/{nest_id}/eggs/{egg_id}", params=params)
        return Egg(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None

    # -----------------------------------------------------------------
    # Application API - Locations
    # -----------------------------------------------------------------
    
    async def get_locations(self, params: Optional[Dict[str, Any]] = None) -> List[Location]:
        """Gets a paginated list of all locations."""
        if params is None: params = {}
        params['include'] = 'nodes'
        all_locs_data = await self._paginate("locations", params=params)
        return [Location(loc_data, api=self, panel_id=self.panel_id) for loc_data in all_locs_data]

    async def get_location(self, location_id: int, params: Optional[Dict[str, Any]] = None) -> Optional[Location]:
        """Gets details for a specific location."""
        if params is None: params = {}
        params['include'] = 'nodes'
        resp = await self._app_request("GET", f"locations/{location_id}", params=params)
        return Location(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None
    
    async def create_location(self, short_code: str, description: str) -> Optional[Location]:
        """Creates a new location."""
        payload = {
            "short": short_code,
            "long": description
        }
        resp = await self._app_request("POST", "locations", json=payload)
        return Location(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 201 else None

    async def update_location(self, location_id: int, **kwargs) -> Optional[Location]:
        """Updates a location."""
        resp = await self._app_request("PATCH", f"locations/{location_id}", json=kwargs)
        return Location(resp.json(), api=self, panel_id=self.panel_id) if resp.status_code == 200 else None

    async def delete_location(self, location_id: int) -> bool:
        """Deletes a location."""
        resp = await self._app_request("DELETE", f"locations/{location_id}")
        return resp.status_code == 204