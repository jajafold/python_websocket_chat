import json
from aiohttp import web
from aiohttp.web import FileResponse, Request, WebSocketResponse


class WebSocketChat:
    def __init__(self, host='0.0.0.0', port=80):
        self._host = host
        self._port = port
        self._connections: dict[str, WebSocketResponse] = {}

    @staticmethod
    async def __obtain_main_page() -> FileResponse:
        return FileResponse('./index.html')

    # region Connection
    async def __check_connection(self) -> None:
        for _id, _ws in list(self._connections.items()):
            if _ws.closed:
                await self.__leave(_id)

    async def __pong(self, socket: WebSocketResponse):
        await socket.send_str("pong")
        await self.__check_connection()

    async def __join(self, data: dict, socket: WebSocketResponse) -> None:
        self._connections[data['id']] = socket
        await self._send({'mtype': 'USER_ENTER', 'id': data['id']}, {data['id']})

    async def __leave(self, user_id: str) -> None:
        self._connections.pop(user_id)
        await self._send({'mtype': 'USER_LEAVE', 'id': user_id})
    # endregion

    async def _handle_message(self, request: Request) -> None:
        _socket = web.WebSocketResponse(autoping=False)

        if not _socket.can_prepare(request):
            return

        await _socket.prepare(request)

        async for _message in _socket:
            _data = _message.data

            if _data == "ping":
                await self.__pong(_socket)

            elif json_data := json.loads(_data):
                if json_data['mtype'] == "INIT":
                    await self.__join(json_data, _socket)
                elif json_data['mtype'] == "TEXT":
                    await self._reply(json_data)

    async def _send(self, message: dict, ignored_ids: set[str] = None) -> None:
        if ignored_ids is None:
            ignored_ids = set()

        await self.__check_connection()

        for _id, _socket in self._connections.items():
            if _id in ignored_ids:
                continue
            try:
                await _socket.send_json(message)
            except ConnectionResetError:
                await self.__leave(_id)

    async def _reply(self, data: dict) -> None:
        if data['to'] is None:
            await self._send(
                {
                    'mtype': 'MSG',
                    'id': data['id'],
                    'text': data['text']
                },
                {
                    data['id']
                })
        else:
            await self._connections[data['to']].send_json({'mtype': 'DM', 'id': data['id'], 'text': data['text']})

    def run(self):
        _app = web.Application()

        _app.router.add_get('/', self.__obtain_main_page)
        _app.router.add_get('/chat', self._handle_message)

        web.run_app(_app, host=self._host, port=self._port)


if __name__ == '__main__':
    WebSocketChat('127.0.0.1', 80).run()
