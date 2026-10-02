"""
In-process LangChain tools built directly on the MCP server functions.

The FastMCP @tool decorator returns the original function unchanged, so we
can import the server functions and wrap them as StructuredTools with the
SAME names and docstrings the agents would see over MCP. Prompts need no
changes.

Mode is selected in mcp_client.py via env MEDICAL_TOOL_MODE:
- "direct" (default): in-process tools — fast, no subprocesses, no stdio
- "mcp": the original stdio subprocess behavior (kept for demonstration)
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.tools import StructuredTool


def _import_fn(module_name: str, fn_name: str):
    """Imports a function; returns None (with a logged reason) on failure."""
    try:
        module = __import__(module_name, fromlist=[fn_name])
        fn = getattr(module, fn_name, None)
        if callable(fn):
            return fn
        print(f"[direct-tools] {module_name}.{fn_name} not found",
              file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[direct-tools] import failed for {module_name}.{fn_name}: {e}",
              file=sys.stderr, flush=True)
    return None


# server name -> list of (module_name, function_name)
DIRECT_SERVER_FUNCTIONS = {
    "clinical": [
        ("mcp_servers.clinical_server", "clinical_triage"),
    ],
    "drug": [
        ("mcp_servers.drug_server", "search_drug_library"),
        ("mcp_servers.drug_server", "log_prescription"),
    ],
    "medical_records": [
        ("mcp_servers.medical_records_server", "record_medical_record"),
        ("mcp_servers.medical_records_server", "fetch_medical_history"),
        ("mcp_servers.medical_records_server", "fetch_patient_documents"),
        ("mcp_servers.medical_records_server", "search_medical_records"),
        ("mcp_servers.medical_records_server", "get_document_full_text"),
        ("mcp_servers.medical_records_server", "save_document_summary"),
    ],
    "scheduling": [
        ("mcp_servers.scheduling_server", "fetch_doctor_schedule"),
        ("mcp_servers.scheduling_server", "book_appointment"),
    ],
}

_cache = {}


def get_direct_tools_for_server(server: str):
    """
    Returns a list of LangChain tools for the given server, or None if any
    of the server's functions could not be loaded (caller falls back to MCP
    for that server).
    """
    if server in _cache:
        return _cache[server]

    spec = DIRECT_SERVER_FUNCTIONS.get(server)
    if spec is None:
        _cache[server] = None
        return None

    tools = []
    for module_name, fn_name in spec:
        fn = _import_fn(module_name, fn_name)
        if fn is None:
            print(f"[direct-tools] server '{server}' not fully available "
                  f"in direct mode — falling back to MCP",
                  file=sys.stderr, flush=True)
            _cache[server] = None
            return None

        # FastMCP's @tool returns the original function, but unwrap defensively
        raw = getattr(fn, "fn", None) or getattr(fn, "__wrapped__", None) or fn
        if not callable(raw):
            raw = fn

        description = (inspect.getdoc(raw) or fn_name).strip()
        tools.append(StructuredTool.from_function(
            func=raw,
            name=fn_name,
            description=description,
        ))

    print(f"[direct-tools] server '{server}': {len(tools)} in-process tools ready",
          file=sys.stderr, flush=True)
    _cache[server] = tools
    return tools