# --- add to perf_log.py (or a new file perf_callback.py) ---
from langchain_core.callbacks import BaseCallbackHandler

class TimingCallbackHandler(BaseCallbackHandler):
    """Times every LLM call and every tool call inside a LangGraph agent."""

    def __init__(self, req_id: str = ""):
        self.req_id = req_id
        self._starts = {}
        self.llm_calls = 0
        self.tool_calls = 0

    def _start(self, key, run_id):
        self._starts[run_id] = (key, time.perf_counter())

    def _end(self, run_id):
        if run_id in self._starts:
            key, t0 = self._starts.pop(run_id)
            logger.info(f"[{self.req_id}]     {key} — {time.perf_counter() - t0:.2f}s")

    def on_chat_model_start(self, serialized, messages, *, run_id, **kw):
        self.llm_calls += 1
        self._start(f"LLM call #{self.llm_calls}", run_id)

    on_llm_start = on_chat_model_start  # cover non-chat models too

    def on_tool_start(self, serialized, input_str, *, run_id, **kw):
        name = (serialized or {}).get("name", "tool")
        self.tool_calls += 1
        self._start(f"TOOL call: {name}", run_id)

    def on_tool_end(self, output, *, run_id, **kw):
        self._end(run_id)

    def on_tool_error(self, error, *, run_id, **kw):
        self._end(run_id)

    def on_llm_end(self, response, *, run_id, **kw):
        self._end(run_id)

    def on_llm_error(self, error, *, run_id, **kw):
        self._end(run_id)