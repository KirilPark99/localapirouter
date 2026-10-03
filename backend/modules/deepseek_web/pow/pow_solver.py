import asyncio
import base64
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("app.modules.deepseek_web.pow")

POW_DIR = Path(__file__).resolve().parent
SOLVE_SCRIPT = POW_DIR / "solve.cjs"


def find_node_binary() -> Optional[str]:
    """Find a usable node binary on the host system."""
    # 1. Check PATH
    node_path = shutil.which("node")
    if node_path and os.path.exists(node_path):
        return node_path

    # 2. Check common NVM / system paths
    candidate_paths = [
        "/home/kiril/.nvm/versions/node/v24.18.0/bin/node",
        "/usr/bin/node",
        "/usr/local/bin/node",
        "/bin/node",
    ]
    for p in candidate_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    # 3. Check ~/.nvm directory dynamically
    nvm_dir = Path(os.path.expanduser("~/.nvm/versions/node"))
    if nvm_dir.exists():
        for ver_dir in sorted(nvm_dir.iterdir(), reverse=True):
            candidate = ver_dir / "bin" / "node"
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)

    return None


async def solve_deepseek_pow(challenge_dict: Dict[str, Any], timeout: float = 15.0) -> Tuple[int, str]:
    """
    Solve DeepSeekHashV1 Proof-of-Work challenge using the high-performance WASM/JS solver.
    Returns:
        (answer_nonce: int, base64_header_response: str)
    Raises:
        RuntimeError if solving fails or node binary is missing.
    """
    algorithm = challenge_dict.get("algorithm", "DeepSeekHashV1")
    if algorithm != "DeepSeekHashV1":
        raise ValueError(f"Unsupported PoW algorithm: {algorithm}")

    node_bin = find_node_binary()
    if not node_bin:
        raise RuntimeError("Node.js binary not found on host. Required for high-speed DeepSeek PoW calculation.")

    input_payload = json.dumps(challenge_dict)

    proc = await asyncio.create_subprocess_exec(
        node_bin,
        str(SOLVE_SCRIPT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=input_payload.encode("utf-8")), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        raise RuntimeError(f"PoW solver timed out after {timeout} seconds")

    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"PoW solver process failed with code {proc.returncode}: {err_msg}")

    try:
        res = json.loads(stdout.decode("utf-8", errors="ignore"))
    except Exception as e:
        raise RuntimeError(f"Failed to parse PoW solver output: {stdout.decode('utf-8', errors='ignore')} ({e})")

    answer = res.get("answer")
    if answer is None or answer < 0:
        err_detail = res.get("error", "No solution found")
        raise RuntimeError(f"PoW challenge could not be solved: {err_detail}")

    response_payload = {
        "algorithm": algorithm,
        "challenge": challenge_dict.get("challenge"),
        "salt": challenge_dict.get("salt"),
        "answer": answer,
        "signature": challenge_dict.get("signature"),
        "target_path": challenge_dict.get("target_path", "/api/v0/chat/completion"),
    }

    b64_response = base64.b64encode(json.dumps(response_payload).encode("utf-8")).decode("utf-8")
    return answer, b64_response
