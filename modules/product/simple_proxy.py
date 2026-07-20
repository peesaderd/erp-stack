"""Simple forward HTTP/HTTPS proxy (Python, no root)."""
import asyncio, logging, os, sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxy_simple")

async def handle_client(reader, writer):
    try:
        data = await reader.readuntil(b"\r\n\r\n")
        first_line = data.split(b"\r\n")[0].decode()
        method, target = first_line.split(" ")[0], first_line.split(" ")[1]
        logger.info(f"{method} {target}")

        if method == "CONNECT":
            # HTTPS CONNECT tunnel
            host, port = target.split(":")
            port = int(port)
            try:
                remote = await asyncio.open_connection(host, port)
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                await asyncio.gather(
                    _pipe(reader, remote[1]),
                    _pipe(remote[0], writer),
                )
            except Exception as e:
                writer.write(f"HTTP/1.1 502 Bad Gateway\r\n\r\n".encode())
                await writer.drain()
        else:
            # HTTP forward
            from urllib.parse import urlparse
            parsed = urlparse(target)
            if not parsed.hostname:
                raise ValueError(f"Bad target: {target}")

            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            path = parsed.path or "/"
            if parsed.query: path += "?" + parsed.query

            try:
                remote_r, remote_w = await asyncio.open_connection(host, port)
                request = f"{method} {path} HTTP/1.1\r\n"
                for line in data.split(b"\r\n"):
                    decoded = line.decode(errors="replace")
                    if decoded.startswith("Proxy-"):
                        continue
                    if decoded.upper().startswith("HOST"):
                        request += f"{decoded}\r\n"
                    elif decoded == method + " " + target + " HTTP/1.1":
                        continue
                    elif decoded:
                        request += f"{decoded}\r\n"
                request += "\r\n"
                remote_w.write(request.encode())
                await remote_w.drain()
                await asyncio.gather(
                    _pipe(reader, remote_w, extra_data=data),
                    _pipe(remote_r, writer),
                )
            except Exception as e:
                writer.write(f"HTTP/1.1 502 Bad Gateway: {e}\r\n\r\n".encode())
                await writer.drain()
    except Exception as e:
        logger.error(f"Proxy error: {e}")
    finally:
        try: writer.close()
        except: pass

async def _pipe(reader, writer, extra_data=None):
    try:
        if extra_data:
            writer.write(extra_data)
            await writer.drain()
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except:
        pass

async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    server = await asyncio.start_server(handle_client, "127.0.0.1", port)
    logger.info(f"Proxy running on 127.0.0.1:{port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
