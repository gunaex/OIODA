import os, socket
import uvicorn

APP = os.environ.get("APP_MODULE", "app.main:app")
PORT = int(os.environ.get("PORT", "8000"))

sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)  # dual-stack
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("::", PORT))
sock.listen(2048)

server = uvicorn.Server(uvicorn.Config(APP, log_level="info"))
server.run(sockets=[sock])
