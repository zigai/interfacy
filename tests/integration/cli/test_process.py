import os
import select
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(REPOSITORY_ROOT)

    return env


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal transport")
@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_sigint_runs_cleanup_and_interrupt_callback(tmp_path: Path, backend: str) -> None:
    script = tmp_path / "interrupted.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import signal
            from pathlib import Path
            from interfacy import Interfacy

            def command():
                print("READY", flush=True)
                try:
                    signal.pause()
                finally:
                    Path("cleaned").write_text("yes", encoding="utf-8")

            def callback(exc):
                Path("callback").write_text(type(exc).__name__, encoding="utf-8")

            Interfacy(backend={backend!r}, on_interrupt=callback).run(command)
            """
        ),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=_child_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        readable, _, _ = select.select([process.stdout], [], [], 20)
        assert readable, "Child did not reach the signal-ready boundary"
        assert process.stdout.readline() == "READY\n"

        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=20)

        assert process.returncode == 130, (stdout, stderr)
        assert stdout == ""
        assert stderr == ""
        assert (tmp_path / "cleaned").read_text(encoding="utf-8") == "yes"
        assert (tmp_path / "callback").read_text(encoding="utf-8") == "KeyboardInterrupt"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=20)


def test_argcomplete_protocol_returns_candidates_without_running_command(tmp_path: Path) -> None:
    script = tmp_path / "complete.py"
    script.write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            from typing import Literal
            from interfacy import Interfacy

            def deploy(environment: Literal["dev", "staging", "prod"]) -> str:
                Path("executed").write_text(environment, encoding="utf-8")
                return environment

            Interfacy(tab_completion=True).run(deploy)
            """
        ),
        encoding="utf-8",
    )
    completion_output = tmp_path / "completions"
    command_line = f"{script} sta"
    env = _child_environment()
    env.update(
        {
            "_ARGCOMPLETE": "1",
            "_ARGCOMPLETE_IFS": "\v",
            "_ARGCOMPLETE_SHELL": "bash",
            "_ARGCOMPLETE_STDOUT_FILENAME": str(completion_output),
            "_ARGCOMPLETE_SUPPRESS_SPACE": "1",
            "COMP_LINE": command_line,
            "COMP_POINT": str(len(command_line)),
        }
    )

    process = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout == ""
    assert process.stderr == ""
    assert completion_output.read_text(encoding="utf-8").split("\v") == ["staging"]
    assert not (tmp_path / "executed").exists()
