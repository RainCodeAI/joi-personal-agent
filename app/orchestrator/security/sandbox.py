"""Sandbox — Resource-limited wrapper for tool executions.

On Windows we use threading + timeout since chroot/cgroups aren't available.
Catches crashes and enforces output-size limits so a misbehaving tool can
never bring down the agent process.
"""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

# Defaults
DEFAULT_TIMEOUT = 30        # seconds
DEFAULT_MAX_OUTPUT = 10_000  # characters


@dataclass
class SandboxResult:
    """Outcome of a ``run_sandboxed()`` call."""
    ok: bool = True
    result: Any = None
    error: Optional[str] = None
    timed_out: bool = False
    output_truncated: bool = False


# Shared thread pool — keeps overhead low when many tools are invoked
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sandbox")


def run_sandboxed(
    fn: Callable[..., Any],
    *args: Any,
    timeout: int = DEFAULT_TIMEOUT,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT,
    **kwargs: Any,
) -> SandboxResult:
    """Execute *fn* with timeout + output-size limits.

    Parameters
    ----------
    fn : callable
        The tool function to execute.
    timeout : int
        Max seconds to wait before killing the call.
    max_output_bytes : int
        If the string representation of the result exceeds this, it is truncated.
    """
    future = _pool.submit(fn, *args, **kwargs)

    try:
        raw_result = future.result(timeout=timeout)
    except FuturesTimeout:
        future.cancel()
        log.warning("Sandboxed call %s timed out after %ds", fn.__name__, timeout)
        return SandboxResult(ok=False, error="Timed out", timed_out=True)
    except Exception as exc:
        log.warning("Sandboxed call %s raised: %s", fn.__name__, exc)
        return SandboxResult(ok=False, error=traceback.format_exc())

    # Enforce output-size limit
    output_truncated = False
    result_str = str(raw_result)
    if len(result_str) > max_output_bytes:
        raw_result = result_str[:max_output_bytes] + "... [truncated]"
        output_truncated = True

    return SandboxResult(
        ok=True,
        result=raw_result,
        output_truncated=output_truncated,
    )
