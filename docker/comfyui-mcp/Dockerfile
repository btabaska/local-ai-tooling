# comfyui-mcp — joenorton/comfyui-mcp-server, pinned at tag v1.1.1 (lai-11, 2026-08-06).
# No upstream image exists, so we build from a pinned git SHA (immutable, same spirit
# as the fleet's digest pins — bump COMFYUI_MCP_REF to update). Apache-2.0.
# Streamable-HTTP MCP on :9000/mcp (stateless_http); stdio mode unused here.
FROM python:3.12-slim
ARG COMFYUI_MCP_REF=e0101b2312f30501664dabe4a74c1283c4268eb8
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
 && git clone https://github.com/joenorton/comfyui-mcp-server.git /app \
 && cd /app && git checkout ${COMFYUI_MCP_REF} && rm -rf /app/.git \
 && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# mcp pinned <2 on purpose: the server is written against SDK 1.x, and the 2026-08-03
# mcp SDK 2.0 rename (McpError -> MCPError) broke mcpo's time/fetch exactly this way.
RUN pip install --no-cache-dir "requests>=2.31.0" "mcp>=1.9,<2" "Pillow>=10.0.0"
# Upstream hardcodes FastMCP(host=127.0.0.1) (unreachable from outside the container)
# and current mcp 1.x ignores FASTMCP_* env (host became an explicit ctor kwarg).
# Patch the ctor call to honor FASTMCP_HOST; the build fails loudly if the anchor
# ever moves on a REF bump.
RUN python - <<'PY'
import pathlib
p = pathlib.Path("server.py")
src = p.read_text()
anchor = '    lifespan=app_lifespan,\n    port=9000,'
assert anchor in src, "server.py FastMCP ctor anchor moved - fix the Dockerfile patch"
src = src.replace(anchor, '    lifespan=app_lifespan,\n    host=os.getenv("FASTMCP_HOST", "127.0.0.1"),\n    port=9000,')
p.write_text(src)
print("patched server.py host kwarg")
PY
ENV FASTMCP_HOST=0.0.0.0
EXPOSE 9000
CMD ["python", "server.py"]
