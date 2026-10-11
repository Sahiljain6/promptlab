from __future__ import annotations

import ast
import base64
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RUNNER = r'''
import importlib.util, json, sys
cfg = json.load(open("/work/config.json", encoding="utf-8"))
try:
    spec = importlib.util.spec_from_file_location("candidate", "/work/solution.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    fn = getattr(mod, cfg["function_name"])
    results = []
    for i, case in enumerate(cfg["tests"], 1):
        try:
            actual = fn(*case.get("args", []))
            passed = actual == case.get("expected")
            results.append({"case": i, "passed": bool(passed), "expected": case.get("expected"),
                            "actual": repr(actual)[:500], "error": None if passed else "Returned value did not match expected value."})
        except BaseException as e:
            results.append({"case": i, "passed": False, "expected": case.get("expected"),
                            "actual": None, "error": type(e).__name__ + ": " + str(e)[:300]})
    print(json.dumps({"results": results, "load_error": None}, ensure_ascii=False))
except BaseException as e:
    print(json.dumps({"results": [], "load_error": type(e).__name__ + ": " + str(e)[:400]}))
'''


def evaluate_python_code(
    code: str,
    function_name: str,
    tests: list[dict[str, Any]],
    timeout_seconds: int = 18,
    judge0_api_key: str = "",
) -> dict[str, Any]:
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return {
            "status": "SYNTAX ERROR",
            "passed_tests": 0,
            "total_tests": len(tests),
            "task_passed": False,
            "results": [],
            "error": f"SyntaxError on line {exc.lineno}: {exc.msg}",
        }

    key = judge0_api_key.strip() or os.getenv("JUDGE0_API_KEY", "").strip()
    if key:
        return _evaluate_with_judge0(code, function_name, tests, key, timeout_seconds)

    if not shutil.which("docker"):
        return _not_tested(
            len(tests),
            "No Judge0 API key or Docker CLI was found. Enter a Judge0 RapidAPI key for cloud testing, or run Docker locally.",
        )

    name = "promptlab-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="promptlab_") as tmp:
        work = Path(tmp).resolve()
        (work / "solution.py").write_text(code, encoding="utf-8")
        (work / "runner.py").write_text(RUNNER, encoding="utf-8")
        (work / "config.json").write_text(
            json.dumps({"function_name": function_name, "tests": tests}), encoding="utf-8"
        )
        try:
            info = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
            if info.returncode:
                return _not_tested(
                    len(tests), "Docker daemon is unavailable: " + (info.stderr or info.stdout)[-500:]
                )
            cmd = [
                "docker", "run", "--rm", "--name", name, "--network=none", "--memory=128m",
                "--cpus=0.5", "--pids-limit=32", "--read-only",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=16m", "--security-opt=no-new-privileges",
                "--cap-drop=ALL", "--user=65534:65534", "--mount",
                f"type=bind,source={work},target=/work,readonly", "--workdir=/work",
                "python:3.12-slim", "python", "-I", "-S", "/work/runner.py",
            ]
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=5)
            return {
                "status": "TIMEOUT", "passed_tests": 0, "total_tests": len(tests),
                "task_passed": False, "results": [],
                "error": f"Test execution exceeded {timeout_seconds} seconds.",
            }
        except OSError as exc:
            return _not_tested(len(tests), f"Could not start Docker: {exc}")
        finally:
            try:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass

        if completed.returncode:
            return {
                "status": "RUNNER ERROR", "passed_tests": 0, "total_tests": len(tests),
                "task_passed": False, "results": [],
                "error": (completed.stderr or completed.stdout)[-800:],
            }
        payload = _last_json_payload(completed.stdout)
        return _format_runner_payload(payload, len(tests))


def _evaluate_with_judge0(
    code: str, function_name: str, tests: list[dict[str, Any]], api_key: str, timeout_seconds: int
) -> dict[str, Any]:
    host = os.getenv("JUDGE0_RAPIDAPI_HOST", "judge0-ce.p.rapidapi.com").strip()
    endpoint = f"https://{host}/submissions?base64_encoded=true&wait=true"
    cfg_b64 = base64.b64encode(
        json.dumps({"function_name": function_name, "tests": tests}, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    runner = (
        "import base64,json,sys\n"
        f"source=base64.b64decode({code_b64!r}).decode('utf-8')\n"
        f"cfg=json.loads(base64.b64decode({cfg_b64!r}).decode('utf-8'))\n"
        "try:\n"
        " ns={'__name__':'candidate'}\n"
        " exec(compile(source,'<generated>','exec'),ns)\n"
        " fn=ns[cfg['function_name']]\n"
        " results=[]\n"
        " for i,case in enumerate(cfg['tests'],1):\n"
        "  try:\n"
        "   actual=fn(*case.get('args',[]))\n"
        "   passed=(actual==case.get('expected'))\n"
        "   results.append({'case':i,'passed':bool(passed),'expected':case.get('expected'),'actual':repr(actual)[:500],'error':None if passed else 'Returned value did not match expected value.'})\n"
        "  except BaseException as e:\n"
        "   results.append({'case':i,'passed':False,'expected':case.get('expected'),'actual':None,'error':type(e).__name__+': '+str(e)[:300]})\n"
        " print(json.dumps({'results':results,'load_error':None},ensure_ascii=False,default=repr))\n"
        "except BaseException as e:\n"
        " print(json.dumps({'results':[],'load_error':type(e).__name__+': '+str(e)[:400]}))\n"
    )
    source_b64 = base64.b64encode(runner.encode("utf-8")).decode("ascii")
    payload = {
        "source_code": source_b64,
        "language_id": 71,
        "cpu_time_limit": min(max(timeout_seconds - 3, 1), 5),
        "wall_time_limit": min(max(timeout_seconds, 5), 10),
        "memory_limit": 128000,
        "enable_network": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": host,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds + 8) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:600]
        return _not_tested(len(tests), f"Judge0 API returned HTTP {exc.code}: {details}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _not_tested(len(tests), f"Could not reach Judge0 or parse its response: {exc}")

    status = (result.get("status") or {}).get("description", "Unknown")
    if status != "Accepted":
        detail = _decode_judge0_field(result.get("stderr")) or _decode_judge0_field(result.get("compile_output"))
        if not detail:
            detail = status
        return {
            "status": "TIMEOUT" if "time" in status.lower() else "EXECUTION ERROR",
            "passed_tests": 0, "total_tests": len(tests), "task_passed": False,
            "results": [], "error": detail[:800],
        }
    stdout = _decode_judge0_field(result.get("stdout")) or ""
    payload = _last_json_payload(stdout)
    if payload is None:
        return {
            "status": "RUNNER ERROR", "passed_tests": 0, "total_tests": len(tests),
            "task_passed": False, "results": [],
            "error": "Judge0 completed, but the test runner did not return valid JSON.",
        }
    return _format_runner_payload(payload, len(tests))


def _decode_judge0_field(value: str | None) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return value


def _last_json_payload(output: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        try:
            item = json.loads(line)
            if "results" in item and "load_error" in item:
                return item
        except json.JSONDecodeError:
            continue
    return None


def _format_runner_payload(payload: dict[str, Any] | None, total: int) -> dict[str, Any]:
    if payload is None:
        return {
            "status": "RUNNER ERROR", "passed_tests": 0, "total_tests": total,
            "task_passed": False, "results": [], "error": "Runner did not return valid JSON.",
        }
    if payload.get("load_error"):
        return {
            "status": "EXECUTION ERROR", "passed_tests": 0, "total_tests": total,
            "task_passed": False, "results": [], "error": payload["load_error"],
        }
    results = payload.get("results", [])
    passed = sum(bool(item.get("passed")) for item in results)
    return {
        "status": "PASSED" if passed == total else "FAILED",
        "passed_tests": passed, "total_tests": total, "task_passed": passed == total,
        "results": results, "error": None,
    }


def _not_tested(total: int, message: str) -> dict[str, Any]:
    return {
        "status": "NOT TESTED", "passed_tests": 0, "total_tests": total,
        "task_passed": False, "results": [], "error": message,
    }
