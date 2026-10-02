"""
MCP Client / Tool provider for agents.

Two modes (env MEDICAL_TOOL_MODE):
- "direct" (default): tools are plain in-process Python functions taken from
  the mcp_servers modules. No subprocesses, no stdio, no event-loop hazards.
  If a server's functions cannot be imported, that server transparently
  falls back to the MCP stdio path.
- "mcp": every server runs as a stdio subprocess with persistent connections
  on a dedicated background event loop (kept for demonstration/compat).

NOTE: We do NOT use nest_asyncio — patching the global event loop breaks
Streamlit's ASGI/anyio internals.
"""
import os
import sys
import time
import asyncio
import threading

from langchain_mcp_adapters.client import MultiServerMCPClient

from perf_log import timer, logger as perf_logger

TOOL_MODE = os.getenv("MEDICAL_TOOL_MODE", "direct").strip().lower()

# ---------------- MCP server configs (used in "mcp" mode or as fallback) ----------------

def _get_server_configs() -> dict:
    """Builds MCP server configurations with absolute paths."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable

    return {
        "medical_records": {
            "command": python_exe,
            "args": [os.path.join(base_dir, "mcp_servers", "medical_records_server.py")],
            "transport": "stdio",
        },
        "scheduling": {
            "command": python_exe,
            "args": [os.path.join(base_dir, "mcp_servers", "scheduling_server.py")],
            "transport": "stdio",
        },
        "clinical": {
            "command": python_exe,
            "args": [os.path.join(base_dir, "mcp_servers", "clinical_server.py")],
            "transport": "stdio",
        },
        "drug": {
            "command": python_exe,
            "args": [os.path.join(base_dir, "mcp_servers", "drug_server.py")],
            "transport": "stdio",
        },
    }


# Map each agent intent to the MCP servers it needs
INTENT_SERVERS = {
    "receptionist": ["scheduling"],
    "reasoning": ["clinical", "medical_records"],
    "memory": ["medical_records"],
    "prescriber": ["clinical", "medical_records", "drug"],
    "doctor_summary": ["medical_records"],
}

# ---------------- persistent loop + caches (MCP mode) ----------------

_loop = None
_loop_lock = threading.Lock()

_server_clients = {}   # server name -> MultiServerMCPClient
_server_tools = {}     # server name -> list of tools

_warmup_started = False
_warmup_done = threading.Event()


def _get_loop() -> asyncio.AbstractEventLoop:
    """One background event loop for the whole process."""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            t = threading.Thread(
                target=_loop.run_forever, daemon=True, name="mcp-event-loop"
            )
            t.start()
        return _loop


async def _get_server_tools(server: str, connect_timeout: float = 30) -> list:
    """Load tools for one MCP server, once. Subprocess stays alive."""
    if server in _server_tools:
        return _server_tools[server]
    async with asyncio.Lock():
        if server in _server_tools:  # double-checked
            return _server_tools[server]
        with timer(f"MCP connect + get_tools: '{server}'", "boot"):
            configs = _get_server_configs()
            client = MultiServerMCPClient({server: configs[server]})
            tools = await asyncio.wait_for(client.get_tools(), timeout=connect_timeout)
        _server_clients[server] = client
        _server_tools[server] = tools
    return _server_tools[server]


def _get_tools_for_server(server: str) -> list:
    """
    Returns tools for one server. In direct mode, prefers in-process tools
    and falls back to MCP for that server if its functions can't be loaded.
    In mcp mode, always uses the stdio subprocess.
    """
    if TOOL_MODE == "direct":
        from direct_tools import get_direct_tools_for_server
        direct = get_direct_tools_for_server(server)
        if direct is not None:
            return direct
        print(f"[mcp_client] direct mode unavailable for '{server}' — using MCP",
              file=sys.stderr, flush=True)
    return _get_server_tools_sync(server)


def _get_server_tools_sync(server: str) -> list:
    """Synchronous bridge to the async MCP tool loader on the shared loop."""
    loop = _get_loop()
    fut = asyncio.run_coroutine_threadsafe(
        _get_server_tools(server), loop
    )
    return fut.result(timeout=60)


async def _get_intent_tools(intent: str) -> list:
    tools = []
    for server in INTENT_SERVERS.get(intent, []):
        tools.extend(_get_tools_for_server(server))
    return tools


def _drop_cached_server(server: str):
    _server_tools.pop(server, None)
    _server_clients.pop(server, None)


async def _run_with_mcp_async(intent: str, agent_factory_fn, messages: list) -> dict:
    with timer(f"Tool-loading for '{intent}'", ""):
        try:
            tools = await _get_intent_tools(intent)
        except Exception:
            for server in INTENT_SERVERS.get(intent, []):
                _drop_cached_server(server)
            tools = await _get_intent_tools(intent)
    perf_logger.info(f"      -> {len(tools)} tools loaded")

    agent = agent_factory_fn(tools)
    from perf_log import TimingCallbackHandler
    handler = TimingCallbackHandler()
    with timer("Agent invoke loop (LLM + tool calls)", ""):
        result = await agent.ainvoke({"messages": messages}, config={"callbacks": [handler]})
    perf_logger.info(
        f"      -> agent made {handler.llm_calls} LLM calls, {handler.tool_calls} tool calls"
    )
    return result


def run_agent_with_mcp(intent: str, agent_factory_fn, messages: list) -> dict:
    """Synchronous wrapper. Runs the agent on the persistent background loop."""
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(
        _run_with_mcp_async(intent, agent_factory_fn, messages), loop
    )
    try:
        return future.result(timeout=120)
    except TimeoutError:
        # Do not leave the coroutine hanging forever on the shared loop
        future.cancel()
        raise


def warm_mcp_connections(intents: list = None):
    """
    Pre-loads tools for the given intents. In direct mode this is nearly
    instant (module imports); in mcp mode it spawns subprocesses.
    """
    loop = _get_loop()

    async def _warm():
        for intent in (intents or list(INTENT_SERVERS)):
            try:
                await asyncio.wait_for(_get_intent_tools(intent), timeout=45)
            except Exception as e:
                print(f"[mcp] warm-up failed for '{intent}': {e}", file=sys.stderr)

    fut = asyncio.run_coroutine_threadsafe(_warm(), loop)
    try:
        fut.result(timeout=120)
    except Exception as e:
        print(f"[mcp] warm-up incomplete: {e}", file=sys.stderr)
    finally:
        _warmup_done.set()


def start_background_warmup(intents: list = None):
    """Non-blocking, idempotent warm-up in a daemon thread."""
    global _warmup_started
    if _warmup_started:
        return
    _warmup_started = True

    def _runner():
        t0 = time.perf_counter()
        try:
            warm_mcp_connections(intents)
            print(f"[warmup] tool warm-up finished in {time.perf_counter() - t0:.1f}s",
                  file=sys.stderr)
        except Exception as e:
            print(f"[warmup] warm-up crashed: {e}", file=sys.stderr)
            _warmup_done.set()

    threading.Thread(target=_runner, daemon=True, name="mcp-warmup").start()


def is_warmed_up() -> bool:
    return _warmup_done.is_set()