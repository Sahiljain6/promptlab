from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
import uuid
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


def evaluate_python_code(code: str, function_name: str, tests: list[dict[str, Any]], timeout_seconds: int = 18) -> dict[str, Any]:
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return {"status": "SYNTAX ERROR", "passed_tests": 0, "total_tests": len(tests),
                "task_passed": False, "results": [], "error": f"SyntaxError on line {exc.lineno}: {exc.msg}"}
    if not shutil.which("docker"):
        return _not_tested(len(tests), "Docker CLI was not found. Install and start Docker Desktop; code was not executed.")
    name = "promptlab-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="promptlab_") as tmp:
        work = Path(tmp).resolve()
        (work / "solution.py").write_text(code, encoding="utf-8")
        (work / "runner.py").write_text(RUNNER, encoding="utf-8")
        (work / "config.json").write_text(json.dumps({"function_name": function_name, "tests": tests}), encoding="utf-8")
        try:
            info = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
            if info.returncode:
                return _not_tested(len(tests), "Docker daemon is unavailable: " + (info.stderr or info.stdout)[-500:])
            cmd = ["docker", "run", "--rm", "--name", name, "--network=none", "--memory=128m", "--cpus=0.5",
                   "--pids-limit=32", "--read-only", "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
                   "--security-opt=no-new-privileges", "--cap-drop=ALL", "--user=65534:65534",
                   "--mount", f"type=bind,source={work},target=/work,readonly", "--workdir=/work",
                   "python:3.12-slim", "python", "-I", "-S", "/work/runner.py"]
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=5)
            return {"status": "TIMEOUT", "passed_tests": 0, "total_tests": len(tests), "task_passed": False,
                    "results": [], "error": f"Test execution exceeded {timeout_seconds} seconds."}
        except OSError as exc:
            return _not_tested(len(tests), f"Could not start Docker: {exc}")
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=5)
        if completed.returncode:
            return {"status": "RUNNER ERROR", "passed_tests": 0, "total_tests": len(tests), "task_passed": False,
                    "results": [], "error": (completed.stderr or completed.stdout)[-800:]}
        payload = None
        for line in reversed(completed.stdout.splitlines()):
            try:
                item = json.loads(line)
                if "results" in item:
                    payload = item
                    break
            except json.JSONDecodeError:
                pass
        if payload is None:
            return {"status": "RUNNER ERROR", "passed_tests": 0, "total_tests": len(tests), "task_passed": False,
                    "results": [], "error": "Runner did not return valid JSON."}
        if payload["load_error"]:
            return {"status": "EXECUTION ERROR", "passed_tests": 0, "total_tests": len(tests), "task_passed": False,
                    "results": [], "error": payload["load_error"]}
        results = payload["results"]
        passed = sum(bool(x["passed"]) for x in results)
        return {"status": "PASSED" if passed == len(tests) else "FAILED", "passed_tests": passed,
                "total_tests": len(tests), "task_passed": passed == len(tests), "results": results, "error": None}


def _not_tested(total: int, message: str) -> dict[str, Any]:
    return {"status": "NOT TESTED", "passed_tests": 0, "total_tests": total, "task_passed": False,
            "results": [], "error": message}
