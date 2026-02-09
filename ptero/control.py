"""
Ptero-Wrapper Control
Contains the main PteroControl class, the entry point for the wrapper.
"""

import httpx, asyncio, logging
from typing import Optional, List, Dict, Any, Tuple, Union
from .client import ClientServer
from .application import ApplicationAPI
from .models import Node, User, Panel

logger = logging.getLogger("ptero.control")

class PteroControl:
    def __init__(self, panels: List[Union[Dict[str, str], Panel]]):
        """
        Initializes the PteroControl with multiple panel configurations.

        Args:
            panels: A list of models.Panel objects or a list of panel config 
                dictionaries. Each dict must have 'id' and 'base_url'. 
                'client_key' and 'app_key' are optional.

        Example:
            [
                {
                    'id': 'panel1',
                    'base_url': 'https://panel.example.com/api',
                    'client_key': 'ptlc_...',
                    'app_key': 'ptla_...'
                },
                {
                    'id': 'panel2',
                    'base_url': 'https://panel2.example.com/api',
                    'client_key': 'ptlc_...'
                }
            ]
        """
        if not panels:
            logger.critical("No panels configured for PteroControl. Wrapper will be non-functional.")
        for i, panel in enumerate(panels.copy()):
            if isinstance(panel, Dict):
                panels[i] = Panel.from_dict(panel)
            
        self.panels_config: Dict[str, Panel] = {p.id: p for p in panels}
        
        self.client_sessions: Dict[str, httpx.AsyncClient] = {}
        self.app_apis: Dict[str, ApplicationAPI] = {}

        for panel_id, config in self.panels_config.items():
            base_url = config.base_url.rstrip('/')
            
            # Setup Client
            client_key = config.client_key
            if client_key:
                headers = {'Accept': 'application/json','Content-Type':'application/json','Authorization': f'Bearer {client_key}'}
                self.client_sessions[panel_id] = httpx.AsyncClient(headers=headers, event_hooks={'response': [self._check_rate_limit]})
            
            # Setup App
            app_key = config.app_key
            if app_key:
                app_headers = {'Accept': 'application/json','Content-Type':'application/json','Authorization': f'Bearer {app_key}'}
                app_session = httpx.AsyncClient(headers=app_headers, event_hooks={'response': [self._check_rate_limit]})
                self.app_apis[panel_id] = ApplicationAPI(app_session, base_url, panel_id)
    
        # Internal cache for API integration
        self._node_cache: Dict[Tuple[str, int], Node] = {} # Key: (panel_id, node_id)
        self._app_server_cache: Dict[str, Tuple[str, dict]] = {} # Key: uuid, Value: (panel_id, server_dict)
        self._last_app_cache_refresh = 0.0

    async def _check_rate_limit(self, response: httpx.Response):
        """Logs a warning if a rate limit is hit."""
        if response.status_code == 429:
            logger.warning(f"Rate limit hit for {response.request.url}! Limit: {response.headers.get('X-RateLimit-Limit')}, Remaining: {response.headers.get('X-RateLimit-Remaining')}")


    async def _refresh_app_caches(self, force: bool = False):
        """Refreshes the internal node and app-server caches from all panels."""
        if not self.app_apis:
            return # App API is not configured on any panel

        now = asyncio.get_event_loop().time()
        # Cache for 5 minutes (300 seconds)
        if not force and (now - self._last_app_cache_refresh < 300):
            return

        logger.debug("Refreshing Application API caches (Nodes and Servers) from all panels...")
        tasks = []
        node_params = {'include': 'location,allocations'}
        server_params = {'include': 'user,node'}
        
        for panel_id, app in self.app_apis.items():
            tasks.append(app.get_nodes(params=node_params))
            tasks.append(app.get_servers(params=server_params))

        results = await asyncio.gather(*tasks)
        
        new_node_cache = {}
        new_server_cache = {}
        
        app_api_list = list(self.app_apis.values())
        
        for i, app in enumerate(app_api_list):
            panel_id = app.panel_id
            all_nodes: List[Node] = results[i*2]
            all_app_servers: List[dict] = results[i*2 + 1]
            
            for node in all_nodes:
                new_node_cache[(panel_id, node.id)] = node
            for srv in all_app_servers:
                new_server_cache[srv['attributes']['uuid']] = (panel_id, srv)

        self._node_cache = new_node_cache
        self._app_server_cache = new_server_cache
        self._last_app_cache_refresh = now
        logger.debug(f"Refreshed caches: {len(self._node_cache)} nodes, {len(self._app_server_cache)} app servers across {len(self.app_apis)} panels.")


    # -----------------------------------------------------------------
    # Client API Methods
    # -----------------------------------------------------------------

    async def get_servers(self, fast: bool = False) -> List[ClientServer]:
        """Gets all servers accessible by all configured CLIENT API keys."""
        if not self.client_sessions:
            logger.warning("get_servers called but no Client API keys are configured.")
            return []
            
        async def fetch_panel(panel_id: str, session: httpx.AsyncClient, url: str) -> Tuple[str, httpx.Response]:
            try:
                resp = await session.get(url)
                return panel_id, resp
            except httpx.RequestError as e:
                logger.error(f"Failed to get servers from panel {panel_id} ({url}): {e}")
                return panel_id, httpx.Response(500, request=httpx.Request("GET", url), text=str(e))

        tasks = []
        for panel_id, session in self.client_sessions.items():
            url = f"{self.panels_config[panel_id].base_url}/client"
            tasks.append(fetch_panel(panel_id, session, url))
        
        responses = await asyncio.gather(*tasks)

        server_data_list: List[Tuple[str, dict]] = []
        for panel_id, resp in responses:
            if resp.status_code == 200:
                for srv_data in resp.json().get("data", []):
                    server_data_list.append((panel_id, srv_data))
            else:
                logger.error(f"An error occurred while getting servers from panel {panel_id} ({resp.url}):\n{resp.text}")

        if not server_data_list:
            return []

        # Refresh App API cache if needed for integration
        if self.app_apis and not fast:
            await self._refresh_app_caches()

        servers = []
        tasks = []
        for panel_id, server_data in server_data_list:
            node_id = server_data['attributes']['node']
            uuid = server_data['attributes']['uuid']
            
            # Find matching app data
            node_obj = self._node_cache.get((panel_id, node_id))
            cached_panel_id, server_app_full_obj = self._app_server_cache.get(uuid, (None, None))
            
            server_app_data = None
            user_obj = None
            if server_app_full_obj and cached_panel_id == panel_id: # Ensure app data is from the same panel
                server_app_data = server_app_full_obj['attributes']
                user_data = server_app_full_obj.get("relationships", {}).get("user", {}).get("data")
                if user_data:
                    user_obj = User(user_data, api=self.app_apis.get(panel_id), panel_id=panel_id)
            
            app_api = self.app_apis.get(panel_id)
            client_session = self.client_sessions[panel_id]
            base_url = self.panels_config[panel_id].base_url
            games_domain = self.panels_config[panel_id].games_domain

            if fast:
                server_obj = ClientServer(server_data, panel_id, client_session, base_url, games_domain,
                                          app_api, node_obj, server_app_data, user_obj)
                servers.append(server_obj)
            else:
                tasks.append(ClientServer.with_data(server_data, panel_id, client_session, base_url, games_domain,
                                                   app_api, node_obj, server_app_data, user_obj))
        
        if not fast:
            results = await asyncio.gather(*tasks)
            servers = [s for s in results if s]

        return servers
        
    async def get_server(self, id: str) -> Optional[ClientServer]:
        """Gets a single server by ID from any configured CLIENT API panel."""
        if not self.client_sessions:
            logger.warning("get_server called but no Client API keys are configured.")
            return None
            
        async def fetch_panel(panel_id: str, session: httpx.AsyncClient, url: str) -> Tuple[str, httpx.Response]:
            try:
                resp = await session.get(url, timeout=3)
                return panel_id, resp
            except httpx.RequestError as e:
                return panel_id, httpx.Response(500, request=httpx.Request("GET", url), text=str(e))
        
        tasks = []
        for panel_id, session in self.client_sessions.items():
            url = f"{self.panels_config[panel_id].base_url}/client/servers/{id}"
            tasks.append(fetch_panel(panel_id, session, url))
            
        results = await asyncio.gather(*tasks)
        
        found_panel_id = None
        response = None
        
        for panel_id, resp in results:
            if resp.status_code == 200:
                found_panel_id = panel_id
                response = resp
                break
        
        if not response or not found_panel_id:
            logger.error(f"An error occurred while getting server {id}. It was not found on any panel.")
            return None
        
        server_data = response.json()

        # --- API Integration ---
        node_obj = None
        server_app_data = None
        user_obj = None
        app_api = self.app_apis.get(found_panel_id)
        
        if app_api:
            await self._refresh_app_caches() # Ensure caches are warm
            node_id = server_data['attributes']['node']
            uuid = server_data['attributes']['uuid']
            node_obj = self._node_cache.get((found_panel_id, node_id))
            
            cached_panel_id, server_app_full_obj = self._app_server_cache.get(uuid, (None, None))
            if server_app_full_obj and cached_panel_id == found_panel_id:
                server_app_data = server_app_full_obj['attributes']
                user_data = server_app_full_obj.get("relationships", {}).get("user", {}).get("data")
                if user_data:
                    user_obj = User(user_data, api=app_api, panel_id=found_panel_id)
        # --- End Integration ---

        client_session = self.client_sessions[found_panel_id]
        base_url = self.panels_config[found_panel_id].base_url
        games_domain = self.panels_config[found_panel_id].games_domain
        
        server = await ClientServer.with_data(server_data, found_panel_id, client_session, base_url, games_domain,
                                            app_api, node_obj, server_app_data, user_obj)
        
        if not server.resources: 
            logger.error(f"An error occurred while getting server object {id} (missing resources) {response.json()}")
            return None
        return server
    
    async def validate_server_id(self, srv_id: str) -> bool:
        """Validates a server ID exists on any configured CLIENT API panel."""
        if not self.client_sessions:
            logger.warning("validate_server_id called but no Client API keys are configured.")
            return False

        async def fetch_panel(panel_id: str, session: httpx.AsyncClient, url: str) -> bool:
            try:
                resp = await session.get(url, timeout=3)
                if resp.status_code == 200:
                    logger.debug(f"the server_id {srv_id} is valid on panel {panel_id}")
                    return True
            except httpx.RequestError as e:
                logger.error(f"Error validating server ID {srv_id} on panel {panel_id}: {e}")
            return False

        tasks = []
        for panel_id, session in self.client_sessions.items():
            url = f"{self.panels_config[panel_id].base_url}/client/servers/{srv_id}"
            tasks.append(fetch_panel(panel_id, session, url))
        
        results = await asyncio.gather(*tasks)
        
        if any(results):
            return True

        logger.debug(f"the server_id {srv_id} is invalid on all panels")
        return False
    
    async def get_servers_from_list(self, srv_ids: list[str]) -> List[ClientServer]:
        """Gets multiple servers by ID from any configured CLIENT API panel."""
        if not self.client_sessions:
            logger.warning("get_servers_from_list called but no Client API keys are configured.")
            return []
            
        tasks = [self.get_server(srv_id) for srv_id in srv_ids]
        results = await asyncio.gather(*tasks)
        return [srv for srv in results if srv]

    async def close(self):
        """Closes all httpx sessions."""
        tasks = []
        for session in self.client_sessions.values():
            tasks.append(session.aclose())
        for app in self.app_apis.values():
            tasks.append(app.app_session.aclose())
        
        await asyncio.gather(*tasks)