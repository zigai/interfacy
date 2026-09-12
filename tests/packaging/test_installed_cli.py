import hashlib
import json
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DIST_DIRECTORY = REPOSITORY_ROOT / "dist"
PROJECT = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PROJECT_VERSION = PROJECT["project"]["version"]


def _environment_executable(root: Path, name: str) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return root / directory / f"{name}{suffix}"


@dataclass(frozen=True)
class InstalledDistribution:
    name: str
    root: Path
    artifact: Path
    backends: tuple[str, ...]

    @property
    def python(self) -> Path:
        return _environment_executable(self.root, "python")

    @property
    def interfacy(self) -> Path:
        return _environment_executable(self.root, "interfacy")


def _run(
    install: InstalledDistribution,
    workspace: Path,
    args: list[str],
    *,
    executable: Path | None = None,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    config = workspace / "config.toml"
    env = {
        "INTERFACY_CONFIG": str(config),
        "NO_COLOR": "1",
        "PATH": str(install.python.parent) + os.pathsep + os.defpath,
        "PYTHONIOENCODING": "utf-8",
        "XDG_CONFIG_HOME": str(workspace / "xdg"),
    }
    return subprocess.run(
        [str(executable or install.interfacy), *args],
        cwd=workspace,
        env=env,
        input=stdin,
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )


def _install_artifact(
    root: Path,
    artifact: Path,
    *,
    python: str,
    extras: str = "",
    additional: tuple[str, ...] = (),
) -> InstalledDistribution:
    uv = shutil.which("uv")
    assert uv is not None, "uv is required for artifact verification"
    subprocess.run(
        [uv, "venv", "--python", python, str(root)],
        check=True,
        cwd=REPOSITORY_ROOT,
        timeout=120,
    )
    requirement = f"{artifact}{extras}"
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(_environment_executable(root, "python")),
            requirement,
            *additional,
        ],
        check=True,
        cwd=REPOSITORY_ROOT,
        timeout=120,
    )

    return InstalledDistribution(
        name=root.name,
        root=root,
        artifact=artifact,
        backends=("argparse", "click") if extras else ("argparse",),
    )


@pytest.fixture(scope="session")
def installed_distributions(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[InstalledDistribution, ...]:
    if os.environ.get("INTERFACY_TEST_ARTIFACTS") != "1":
        pytest.skip("artifact verification runs through `just build`")

    wheel = DIST_DIRECTORY / f"interfacy-{PROJECT_VERSION}-py3-none-any.whl"
    sdist = DIST_DIRECTORY / f"interfacy-{PROJECT_VERSION}.tar.gz"
    assert wheel.is_file(), "wheel missing; run uv build first"
    assert sdist.is_file(), "sdist missing; run uv build first"
    root = tmp_path_factory.mktemp("installed-distributions")

    return (
        _install_artifact(root / "wheel-base", wheel, python="3.14"),
        _install_artifact(root / "wheel-click", wheel, python="3.14", extras="[click]"),
        _install_artifact(
            root / "wheel-full",
            wheel,
            python="3.14",
            extras="[full]",
            additional=("pydantic>=2,<3",),
        ),
        _install_artifact(root / "sdist-base", sdist, python="3.10"),
    )


@pytest.fixture(params=["wheel-base", "wheel-click", "wheel-full", "sdist-base"])
def install(
    request: pytest.FixtureRequest,
    installed_distributions: tuple[InstalledDistribution, ...],
) -> InstalledDistribution:
    return next(item for item in installed_distributions if item.name == request.param)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "config.toml").write_text("[behavior]\nprint_result = true\n", encoding="utf-8")
    return tmp_path


def test_installed_identity_exports_and_typing_assets(
    install: InstalledDistribution,
    workspace: Path,
) -> None:
    process = _run(
        install,
        workspace,
        [
            "-I",
            "-c",
            textwrap.dedent(
                """
                import ast
                import importlib.metadata as metadata
                import importlib.util
                import json
                from pathlib import Path
                import interfacy

                root = Path(interfacy.__file__).parent
                stub = ast.parse((root / "__init__.pyi").read_text(encoding="utf-8"))
                stub_all = next(
                    ast.literal_eval(node.value)
                    for node in stub.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
                )
                assert (root / "py.typed").is_file()
                assert set(stub_all) == set(interfacy.__all__)
                for name in interfacy.__all__:
                    getattr(interfacy, name)
                print(json.dumps({
                    "click": importlib.util.find_spec("click") is not None,
                    "exports": len(interfacy.__all__),
                    "path": str(root),
                    "version": metadata.version("interfacy"),
                }))
                """
            ),
        ],
        executable=install.python,
    )

    assert process.returncode == 0, process.stderr
    evidence = json.loads(process.stdout)
    assert evidence["version"] == PROJECT_VERSION
    assert evidence["exports"] == 19
    assert evidence["click"] == ("click" in install.backends)
    assert Path(evidence["path"]).is_relative_to(install.root)
    assert process.stderr == ""


@pytest.mark.parametrize("flag", ["--help", "--version", "--config-paths"])
def test_installed_root_flags_succeed(
    install: InstalledDistribution,
    workspace: Path,
    flag: str,
) -> None:
    process = _run(install, workspace, [flag])

    assert process.returncode == 0, process.stderr
    assert process.stdout
    assert process.stderr == ""

    if flag == "--help":
        assert "TARGET" in process.stdout
    elif flag == "--version":
        assert process.stdout.startswith("interfacy ")
    else:
        assert str(workspace / "config.toml") in process.stdout


@pytest.mark.parametrize(
    ("case", "body", "args", "expected_code", "expected_stdout", "error_text"),
    [
        ("integer", "def command() -> int:\n    return 7\n", [], 0, "7\n", None),
        (
            "greeting",
            (
                "def command(name: str, times: int = 1) -> str:\n"
                "    return ' '.join([f'Hello {name}!'] * times)\n"
            ),
            ["Ada", "--times", "2"],
            0,
            "Hello Ada! Hello Ada!\n",
            None,
        ),
        (
            "missing",
            (
                "from pathlib import Path\n"
                "def command(name: str) -> str:\n"
                "    Path('executed').write_text(name, encoding='utf-8')\n"
                "    return name\n"
            ),
            [],
            2,
            "",
            "usage:",
        ),
        (
            "failure",
            "def command() -> None:\n    raise ValueError('deliberate failure')\n",
            [],
            1,
            "",
            "ValueError: deliberate failure",
        ),
        ("explicit-exit", "def command() -> None:\n    raise SystemExit(7)\n", [], 7, "", None),
    ],
)
def test_installed_command_contract(
    install: InstalledDistribution,
    workspace: Path,
    case: str,
    body: str,
    args: list[str],
    expected_code: int,
    expected_stdout: str,
    error_text: str | None,
) -> None:
    del case
    target = workspace / "target.py"
    target.write_text(body, encoding="utf-8")

    for backend in install.backends:
        (workspace / "config.toml").write_text(
            f'[behavior]\nbackend = "{backend}"\nprint_result = true\n',
            encoding="utf-8",
        )
        process = _run(install, workspace, ["target.py:command", *args])

        assert process.returncode == expected_code, (process.stdout, process.stderr)
        assert process.stdout == expected_stdout

        if error_text is None:
            assert process.stderr == ""
        else:
            assert error_text.lower() in process.stderr.lower()

        assert not (workspace / "executed").exists()


def test_installed_target_help_succeeds(
    install: InstalledDistribution,
    workspace: Path,
) -> None:
    (workspace / "target.py").write_text(
        "def command(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    process = _run(install, workspace, ["target.py:command", "--help"])

    assert process.returncode == 0, process.stderr
    assert "NAME" in process.stdout
    assert process.stderr == ""


def test_base_install_reports_missing_click(
    install: InstalledDistribution,
    workspace: Path,
) -> None:
    if "click" in install.backends:
        pytest.skip("base-only dependency partition")

    process = _run(
        install,
        workspace,
        ["-I", "-c", "from interfacy import Interfacy; Interfacy(backend='click')"],
        executable=install.python,
    )

    assert process.returncode == 1
    assert "Click is required" in process.stderr
    assert "interfacy[click]" in process.stderr


def test_installed_real_stdin_validates_literal_lists(
    install: InstalledDistribution,
    workspace: Path,
) -> None:
    (workspace / "target.py").write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            from typing import Literal

            def command(values: list[Literal["red", "blue"]]) -> list[str]:
                Path("executed").write_text(repr(values), encoding="utf-8")
                return values

            def configure_interfacy(parser):
                parser.pipe_to("values")
            """
        ),
        encoding="utf-8",
    )

    invalid = _run(install, workspace, ["target.py:command"], stdin="green")

    assert invalid.returncode == 2, invalid.stderr
    assert invalid.stdout == ""
    assert not (workspace / "executed").exists()

    valid = _run(install, workspace, ["target.py:command"], stdin="red\nblue")

    assert valid.returncode == 0, valid.stderr
    assert valid.stdout == "['red', 'blue']\n"
    assert valid.stderr == ""


def test_installed_cli_priority_ignores_invalid_unused_stdin(
    install: InstalledDistribution,
    workspace: Path,
) -> None:
    (workspace / "target.py").write_text(
        textwrap.dedent(
            """
            def command(value: int = 3) -> int:
                return value

            def configure_interfacy(parser):
                parser.pipe_to("value")
            """
        ),
        encoding="utf-8",
    )
    for backend in install.backends:
        (workspace / "config.toml").write_text(
            f'[behavior]\nbackend = "{backend}"\nprint_result = true\n',
            encoding="utf-8",
        )

        process = _run(
            install,
            workspace,
            ["target.py:command", "--value", "3"],
            stdin="not-an-integer",
        )

        assert process.returncode == 0, process.stderr
        assert process.stdout == "3\n"
        assert process.stderr == ""


def test_full_install_pydantic_validation_is_command_failure_without_side_effect(
    install: InstalledDistribution,
    workspace: Path,
) -> None:
    if install.name != "wheel-full":
        pytest.skip("full-extra provider partition")

    (workspace / "target.py").write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            from pydantic import BaseModel, Field

            class User(BaseModel):
                name: str
                age: int = Field(ge=0)

            def command(user: User) -> str:
                Path("executed").write_text(user.name, encoding="utf-8")
                return user.name
            """
        ),
        encoding="utf-8",
    )

    for backend in install.backends:
        (workspace / "config.toml").write_text(
            f'[behavior]\nbackend = "{backend}"\nprint_result = true\n',
            encoding="utf-8",
        )
        process = _run(
            install,
            workspace,
            ["target.py:command", "--user.name", "Ada", "--user.age", "-1"],
        )

        assert process.returncode == 1
        assert "ValidationError" in process.stderr
        assert not (workspace / "executed").exists()


def test_installed_wheel_typechecks_for_a_consumer(
    installed_distributions: tuple[InstalledDistribution, ...],
    tmp_path: Path,
) -> None:
    wheel = next(item.artifact for item in installed_distributions if item.name == "wheel-base")
    typed = _install_artifact(
        tmp_path / "typed-consumer",
        wheel,
        python="3.14",
        additional=("pyrefly==1.0.0",),
    )
    (tmp_path / "consumer.py").write_text(
        textwrap.dedent(
            """
            from interfacy import ExitCode, Interfacy, Param, PipeInputError

            def command(value: int) -> int:
                return value

            app = Interfacy(sys_exit_enabled=False)
            app.add_command(command, parameter_settings={"value": Param(kind="positional")})
            code: ExitCode = ExitCode.SUCCESS
            error: type[Exception] = PipeInputError
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyrefly]\nproject-includes = ['consumer.py']\npython-version = '3.14'\n",
        encoding="utf-8",
    )
    pyrefly = _environment_executable(typed.root, "pyrefly")

    process = subprocess.run(
        [str(pyrefly), "check", "consumer.py", "--summary=none", "--progress-bar", "no"],
        cwd=tmp_path,
        env={"PATH": str(typed.python.parent) + os.pathsep + os.defpath},
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert process.returncode == 0, process.stdout + process.stderr


def test_artifact_hashes_are_distinct_and_nonempty(
    installed_distributions: tuple[InstalledDistribution, ...],
) -> None:
    hashes = {
        hashlib.sha256(item.artifact.read_bytes()).hexdigest() for item in installed_distributions
    }

    assert len(hashes) == 2
    assert all(len(value) == 64 for value in hashes)
