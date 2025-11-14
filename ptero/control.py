"""
Ptero-Wrapper Control
Contains the main PteroControl class, the entry point for the wrapper.
"""

import httpx, asyncio, logging
from typing import Optional, List, Dict, Any
from .client import ClientServer
from .application import ApplicationAPI
from .models import Node, User

logger = logging.getLogger("ptero_wrapper.control")

class PteroControl:
    def __init__(self, 
                 client_api_key: Optional[str] = None, 
                 app_api_key: Optional[str] = None, 
                 client_oci_api_key: Optional[str] = None, 
                 app_oci_api_key: Optional[str] = None, 
                 base_url: str = 'https://panel.hotment.online/api', 
                 oci_base_url: str = 'http://panel.mc.hotment.online/api'):
        
        self.base_url = base_url
        self.oci_base_url = oci_base_url

        # --- Check which APIs are enabled ---
        self.client_enabled = client_api_key is not None
        self.client_oci_enabled = client_oci_api_key is not None
        self.app_enabled = app_api_key is not None
        self.app_oci_enabled = app_oci_api_key is not None
        
        # --- Client API Headers & Sessions ---
        self.client_headers = {'Accept': 'application/json','Content-Type':'application/json','Authorization': f'Bearer {client_api_key}'}
        self.client_headers_oci = {'Accept': 'application/json','Content-Type':'application/json','Authorization': f'Bearer {client_oci_api_key}'}
        self.session = httpx.AsyncClient(headers=self.client_headers) if self.client_enabled else None
        self.oci_session = httpx.AsyncClient(headers=self.client_headers_oci) if self.client_oci_enabled else None
        
        # --- Application API Headers & Sessions ---
        self.app_headers = {'Accept': 'application/json','Content-Type':'application/json','Authorization': f'Bearer {app_api_key}'}
        self.app_headers_oci = {'Accept': 'application/json','Content-Type':'application/json','Authorization': f'Bearer {app_oci_api_key}'}
        self.app_session = httpx.AsyncClient(headers=self.app_headers) if self.app_enabled else None
        self.app_oci_session = httpx.AsyncClient(headers=self.app_headers_oci) if self.app_oci_enabled else None

        # Instantiate Application API handler
        self.app = ApplicationAPI(self.app_session, self.app_oci_session, self.base_url, self.oci_base_url) if (self.app_enabled or self.app_oci_enabled) else None
    
        # Internal cache for API integration
        self._node_cache: Dict[int, Node] = {}
        self._app_server_cache: Dict[str, dict] = {} # Keyed by UUID
        self._last_app_cache_refresh = 0.0

    async def _refresh_app_caches(self, force: bool = False):
        """Refreshes the internal node and app-server caches."""
        if not self.app:
            return # App API is not configured

        now = asyncio.get_event_loop().time()
        # Cache for 5 minutes
        if not force and (now - self._last_app_cache_refresh < 300):
            return

        logger.debug("Refreshing Application API caches (Nodes and Servers)...")
        tasks = []
        # We now include relationships in these calls
        node_params = {'include': 'location,allocations'}
        server_params = {'include': 'user,node'}
        
        if self.app.main_enabled:
            tasks.append(self.app.get_nodes(oci=False, params=node_params))
            tasks.append(self.app.get_servers(oci=False, params=server_params))
        if self.app.oci_enabled:
            tasks.append(self.app.get_nodes(oci=True, params=node_params))
            tasks.append(self.app.get_servers(oci=True, params=server_params))

        results = await asyncio.gather(*tasks)
        
        all_nodes: List[Node] = []
        all_app_servers: List[dict] = []
        
        idx = 0
        if self.app.main_enabled:
            all_nodes.extend(results[idx])
            all_app_servers.extend(results[idx+1])
            idx += 2
        if self.app.oci_enabled:
            all_nodes.extend(results[idx])
            all_app_servers.extend(results[idx+1])

        self._node_cache = {node.id: node for node in all_nodes}
        # Store the full server object (dict), not just attributes
        self._app_server_cache = {srv['attributes']['uuid']: srv for srv in all_app_servers}
        self._last_app_cache_refresh = now
        logger.debug(f"Refreshed caches: {len(self._node_cache)} nodes, {len(self._app_server_cache)} app servers.")


    # -----------------------------------------------------------------
    # Client API Methods
    # -----------------------------------------------------------------

    async def get_servers(self, fast: bool = False) -> List[ClientServer]:
        """Gets all servers accessible by the CLIENT API key."""
        if not self.client_enabled and not self.client_oci_enabled:
            logger.warning("get_servers called but no Client API keys are configured.")
            return []
            
        tasks = []
        if self.session:
            tasks.append(self.session.get(f"{self.base_url}/client"))
        if self.oci_session:
            tasks.append(self.oci_session.get(f"{self.oci_base_url}/client"))
        
        try:
            responses = await asyncio.gather(*tasks)
        except httpx.RequestError as e:
            logger.error(f"Failed to get servers: {e}")
            return []

        server_data_list = []
        for resp in responses:
            if resp.status_code == 200:
                server_data_list.extend(resp.json().get("data", []))
            else:
                logger.error(f"An error occurred while getting servers from {resp.url}:\n{resp.text}")

        if not server_data_list:
            return []

        # Refresh App API cache if needed for integration
        if self.app and not fast:
            await self._refresh_app_caches()

        servers = []
        tasks = []
        for server_data in server_data_list:
            node_id = server_data['attributes']['node']
            uuid = server_data['attributes']['uuid']
            
            # Find matching app data
            node_obj = self._node_cache.get(node_id)
            server_app_full_obj = self._app_server_cache.get(uuid)
            
            # Extract attributes and user relationship
            server_app_data = None
            user_obj = None
            if server_app_full_obj:
                server_app_data = server_app_full_obj['attributes']
                user_data = server_app_full_obj.get("relationships", {}).get("user", {}).get("data")
                if user_data:
                    user_obj = User(user_data, api=self.app)
            
            if fast:
                server_obj = ClientServer(server_data, self.session, self.oci_session, 
                                          self.base_url, self.oci_base_url, 
                                          node_obj, server_app_data, user_obj, self.app)
                if str(server_obj.base_url).startswith(self.oci_base_url):
                    server_obj.oci = True
                servers.append(server_obj)
            else:
                tasks.append(ClientServer.with_data(server_data, self.session, self.oci_session, 
                                                   self.base_url, self.oci_base_url, 
                                                   node_obj, server_app_data, user_obj, self.app))
        
        if not fast:
            results = await asyncio.gather(*tasks)
            servers = [s for s in results if s]

        return servers
        
    async def get_server(self, id: str) -> Optional[ClientServer]:
        """Gets a single server by ID using the CLIENT API."""
        if not self.client_enabled and not self.client_oci_enabled:
            logger.warning("get_server called but no Client API keys are configured.")
            return None
            
        response = None
        is_oci = False

        if self.session:
            try:
                response = await self.session.get(f"{self.base_url}/client/servers/{id}", timeout=3)
                if response.status_code == 200:
                    is_oci = False
            except httpx.RequestError as e:
                logger.error(f"Failed to connect to main panel for get_server: {e}")

        if not response or response.status_code != 200:
            if self.oci_session:
                try:
                    response = await self.oci_session.get(f"{self.oci_base_url}/client/servers/{id}", timeout=3)
                    if response.status_code == 200:
                        is_oci = True
                except httpx.RequestError as e:
                    logger.error(f"Failed to connect to OCI panel for get_server: {e}")

        if not response or response.status_code != 200:
            logger.error(f"An error occurred while getting server {id}. Last response: {response.text if response else 'No response'}")
            return None
        
        server_data = response.json()

        # --- API Integration ---
        node_obj = None
        server_app_data = None
        user_obj = None
        if self.app:
            await self._refresh_app_caches() # Ensure caches are warm
            node_id = server_data['attributes']['node']
            uuid = server_data['attributes']['uuid']
            node_obj = self._node_cache.get(node_id)
            
            server_app_full_obj = self._app_server_cache.get(uuid)
            if server_app_full_obj:
                server_app_data = server_app_full_obj['attributes']
                user_data = server_app_full_obj.get("relationships", {}).get("user", {}).get("data")
                if user_data:
                    user_obj = User(user_data, api=self.app)
        # --- End Integration ---

        server = await ClientServer.with_data(server_data, self.session, self.oci_session, 
                                            self.base_url, self.oci_base_url, 
                                            node_obj, server_app_data, user_obj, self.app)
        server.oci = is_oci # Manually set OCI status based on successful request
        
        if not server.resources: 
            logger.error(f"An error occurred while getting server object {id} (missing resources) {response.json()}")
            return None
        return server
    
    async def validate_server_id(self, srv_id: str) -> bool:
        """Validates a server ID exists using the CLIENT API."""
        if not self.client_enabled and not self.client_oci_enabled:
            logger.warning("validate_server_id called but no Client API keys are configured.")
            return False

        try:
            if self.session:
                response = await self.session.get(f"{self.base_url}/client/servers/{srv_id}", timeout=3)
                if response.status_code == 200:
                    logger.debug(f"the server_id {srv_id} is valid on main panel")
                    return True
            
            if self.oci_session:
                response_oci = await self.oci_session.get(f"{self.oci_base_url}/client/servers/{srv_id}", timeout=3)
                if response_oci.status_code == 200:
                    logger.debug(f"the server_id {srv_id} is valid on OCI panel")
                    return True

        except httpx.RequestError as e:
            logger.error(f"Error validating server ID {srv_id}: {e}")

        logger.debug(f"the server_id {srv_id} is invalid")
        return False
    
    async def get_servers_from_list(self, srv_ids: list[str]) -> List[ClientServer]:
        """Gets multiple servers by ID using the CLIENT API."""
        if not self.client_enabled and not self.client_oci_enabled:
            logger.warning("get_servers_from_list called but no Client API keys are configured.")
            return []
            
        tasks = [self.get_server(srv_id) for srv_id in srv_ids]
        results = await asyncio.gather(*tasks)
        return [srv for srv in results if srv]

    async def close(self):
        """Closes all httpx sessions."""
        tasks = []
        if self.session:
            tasks.append(self.session.aclose())
        if self.oci_session:
            tasks.append(self.oci_session.aclose())
        if self.app_session:
            tasks.append(self.app_session.aclose())
        if self.app_oci_session:
            tasks.append(self.app_oci_session.aclose())
        
        await asyncio.gather(*tasks)