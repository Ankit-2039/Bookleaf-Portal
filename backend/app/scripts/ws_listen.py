"""Print realtime events for a user: python -m app.scripts.ws_listen <email>  (run from backend/)."""
import asyncio
import getpass
import json
import sys

import httpx
import websockets

HTTP = "http://localhost:8000"
WS = "ws://localhost:8000/api/v1/ws"


async def main(email: str) -> None:
    password = getpass.getpass("Password: ")
    r = httpx.post(f"{HTTP}/api/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    async with websockets.connect(WS) as ws:
        await ws.send(json.dumps({"type": "auth", "token": r.json()["access_token"]}))
        print("connected:", await ws.recv())
        async for message in ws:
            print(message)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))