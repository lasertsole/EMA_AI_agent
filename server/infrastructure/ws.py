from robyn import WebSocketAdapter

class WebsocketManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.websocket_id_to_session_id: dict[str, str] = {}
        self.session_id_to_websocket_id: dict[str, str] = {}
        self.websocket_id_to_ws: dict[str, WebSocketAdapter] = {}
        self._initialized = True

    def register_websocket(self, session_id: str, websocket: WebSocketAdapter):
        self.websocket_id_to_session_id[websocket.id] = session_id
        self.session_id_to_websocket_id[session_id] = websocket.id
        self.websocket_id_to_ws[websocket.id] = websocket


    def unregister_websocket_by_websocket(self, websocket: WebSocketAdapter):
        session_id: str = self.websocket_id_to_session_id.pop(websocket.id, None)
        if session_id:
            self.session_id_to_websocket_id.pop(session_id, None)
            self.websocket_id_to_ws.pop(websocket.id, None)

    def unregister_websocket_by_websocket_id(self, websocket_id: str):
        self.websocket_id_to_ws.pop(websocket_id, None)
        session_id: str  = self.websocket_id_to_session_id.pop(websocket_id, None)
        if session_id:
            self.session_id_to_websocket_id.pop(session_id, None)

    def unregister_websocket_by_session_id(self, session_id: str):
        websocket_id: str  = self.session_id_to_websocket_id.pop(session_id, None)
        self.websocket_id_to_session_id.pop(websocket_id, None)
        if websocket_id:
            self.websocket_id_to_ws.pop(websocket_id, None)

    def get_websocket_by_session_id(self, session_id: str)->WebSocketAdapter | None:
        websocket_id: str = self.session_id_to_websocket_id.get(session_id, None)
        if websocket_id:
            return self.websocket_id_to_ws.get(websocket_id, None)
        return None

    def get_websocket_by_websocket_id(self, websocket_id: str) -> WebSocketAdapter | None:
        return self.websocket_id_to_ws.get(websocket_id, None)

    def get_session_id_by_websocket_id(self, websocket_id: str)->str | None:
        return self.websocket_id_to_session_id.get(websocket_id, None)

    def get_session_id_by_websocket(self, websocket: WebSocketAdapter)->str | None:
        return self.get_session_id_by_websocket_id(websocket.id)

    def get_websocket_id_by_session_id(self, session_id: str)->str | None:
        return self.session_id_to_websocket_id.get(session_id, None)

websocket_manager = WebsocketManager()