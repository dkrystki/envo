from env_comm import EnvoEnvComm
from envo import Raw, command, run, logger, onload, dataclass  # noqa: F401


@dataclass
class EnvoEnv(EnvoEnvComm):  # type: ignore
    class Meta(EnvoEnvComm.Meta):  # type: ignore
        stage = "local"
        emoji = "🐣"
        parent = ".."

    # Declare your variables here

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        stickybeak_root = self.get_parent().root / "stickybeak"
        self.pythonpath = f"{str(stickybeak_root)}:{self.pythonpath}"

        # Define your variables here

    @onload
    def _dump_env(self) -> None:
        self.dump_dot_env()

    @command(glob=True)
    def test(self) -> None:
        logger.info("Running tests")
        run("pytest tests -v")

    @command
    def flake(self) -> None:
        self.black()
        run("flake8")

    @command(glob=True)
    def mypy(self) -> None:
        logger.info("Running mypy")
        run("mypy envo")

    @command(glob=True)
    def black(self) -> None:
        run("isort .")
        run("black .")

    @command(glob=True)
    def ci(self) -> None:
        self.flake()
        self.mypy()
        self.test()


Env = EnvoEnv
