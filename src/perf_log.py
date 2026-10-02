"""
Central performance logging: writes timestamped stage timings to console
AND to logs/perf.log so a full request can be traced end-to-end.

Also provides TimingCallbackHandler, which times every individual LLM call
and tool call inside a LangGraph agent run.
"""
import os
import time
import logging
from contextlib import contextmanager
from datetime import datetime

from langchain_core.callbacks import BaseCallbackHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "perf.log")

logger = logging.getLogger("perf")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d | %(message)s", datefmt="%H:%M:%S")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    filehandler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    filehandler.setFormatter(fmt)
    logger.addHandler(console)
    logger.addHandler(filehandler)


@contextmanager
def timer(stage: str, request_id: str = ""):
    """Usage:
        with timer("guardrails", req_id):
            do_stuff()
    """
    start = time.perf_counter()
    logger.info(f"[{request_id}] START {stage}")
    try:
        yield
    except Exception as e:
        logger.error(f"[{request_id}] FAIL {stage} after {time.perf_counter() - start:.2f}s: {e}")
        raise
    elapsed = time.perf_counter() - start
    logger.info(f"[{request_id}] DONE  {stage} — {elapsed:.2f}s")


def new_request_id() -> str:
    return datetime.now().strftime("%H%M%S%f")[:8]


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
            logger.info(f"[{self.req_id}]       {key} — {time.perf_counter() - t0:.2f}s")

    def on_chat_model_start(self, serialized, messages, *, run_id=None, **kwargs):
        self.llm_calls += 1
        self._start(f"LLM call #{self.llm_calls}", run_id)

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs):
        self.llm_calls += 1
        self._start(f"LLM call #{self.llm_calls}", run_id)

    def on_llm_end(self, response, *, run_id=None, **kwargs):
        self._end(run_id)

    def on_llm_error(self, error, *, run_id=None, **kwargs):
        self._end(run_id)

    def on_tool_start(self, serialized, input_str, *, run_id=None, **kwargs):
        name = "tool"
        if isinstance(serialized, dict):
            name = serialized.get("name", "tool")
        self.tool_calls += 1
        self._start(f"TOOL call: {name}", run_id)

    def on_tool_end(self, output, *, run_id=None, **kwargs):
        self._end(run_id)

    def on_tool_error(self, error, *, run_id=None, **kwargs):
        self._end(run_id)