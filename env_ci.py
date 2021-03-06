from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

import envo  # noqa: F401
from envo import (  # noqa: F401
    Namespace,
    Plugin,
    Raw,
    UserEnv,
    VirtualEnv,
    boot_code,
    command,
    context,
    logger,
    oncreate,
    ondestroy,
    onload,
    onstderr,
    onstdout,
    onunload,
    postcmd,
    precmd,
    run,
)

# Declare your command namespaces here
# like this:
# my_namespace = command(namespace="my_namespace")


class EnvoCiEnv(UserEnv):  # type: ignore
    class Meta(UserEnv.Meta):  # type: ignore
        root: str = Path(__file__).parent.absolute()
        stage: str = "ci"
        emoji: str = "🧪"
        parents: List[str] = ["env_comm.py"]
        plugins: List[Plugin] = []
        name: str = "env"
        version: str = "0.1.0"
        watch_files: List[str] = []
        ignore_files: List[str] = []

    def __init__(self) -> None:
        super().__init__()
        # Define your variables here

    @command
    def bootstrap(self) -> None:
        run("mkdir -p workspace")
        super().bootstrap()

    @command
    def test(self) -> None:
        run(
            "pytest --reruns 10 -v tests --cov-report xml:workspace/cov.xml --cov=envo ./workspace"
        )

    @command
    def build(self) -> None:
        run("poetry build")

    @command
    def publish(self) -> None:
        run("poetry publish --username $PYPI_USERNAME --password $PYPI_PASSWORD")

    @command
    def rstcheck(self) -> None:
        run("rstcheck README.rst | tee ./workspace/rstcheck.txt")

    @command
    def flake(self) -> None:
        run("flake8 . | tee ./workspace/flake8.txt")

    @command
    def check_black(self) -> None:
        run("black --check . | tee ./workspace/black.txt")

    @command
    def mypy(self) -> None:
        run("mypy . | tee ./workspace/mypy.txt")

    @command
    def generate_version(self) -> None:
        import toml

        config = toml.load(str(self.root / "pyproject.toml"))
        version: str = config["tool"]["poetry"]["version"]

        version_file = self.root / "stickybeak/__version__.py"
        Path(version_file).touch()

        version_file.write_text(f'__version__ = "{version}"\n')

    @command
    def upload_codecov(self) -> None:
        run(
            """
            curl -s https://codecov.io/bash | bash -s -- \
            -t "${CODECOV_TOKEN}" \
            -n "${CIRCLE_BUILD_NUM}" \
            -f "./workspace/cov.xml" \
            -Z
            """
        )


Env = EnvoCiEnv
