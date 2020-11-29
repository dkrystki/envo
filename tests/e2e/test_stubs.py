import os
from pathlib import Path
from textwrap import dedent

import pytest
from pexpect import run

from envo import const
from tests.e2e import utils


class TestStubs:
    @pytest.fixture(autouse=True)
    def setup(self, sandbox):
        yield
        self.shell.on_exit()

    def init(self) -> None:
        result = run("envo test --init")
        assert b"Created test environment" in result

    def assert_stub_equal(self, stub_file: str, content: str, stage: str = "comm") -> None:
        self.shell = utils.Spawn(f"envo {stage}")
        self.shell.start()

        e = self.shell.expecter
        e.prompt(emoji=const.STAGES.get_stage_name_to_emoji()[stage]).eval()

        content = dedent(content)

        print(f"Comparing:\n{content} \n to: \n{Path(stub_file).read_text()}")

        assert content.replace(" ", "") in Path(stub_file).read_text().replace(" ", "")

        self.shell.exit()
        e.exit().eval()

    def test_comm_only(self):
        self.init()

        utils.add_flake_cmd(file=Path("env_comm.py"))
        utils.add_hook(
            r"""
            @precmd(cmd_regex=r"print\(.*\)")
            def pre_print(self, command: str) -> str:
                assert command == 'print("pancake");'
                print("pre")
                return command * 2
            """
        )

        stub = """
        class SandboxCommEnv:
            class Meta:
                emoji: str
                ignore_files: typing.List[str]
                name: str
                parents: typing.List[str]
                plugins: typing.List[envo.plugins.Plugin]
                stage: str
                version: str
                watch_files: typing.List[str]
                
                
            envo_stage: envo.env.Raw[str]
            path: envo.env.Raw[str]
            pythonpath: envo.env.Raw[str]
            root: Path
            stage: str
            
            @command
            def __flake(self, test_arg: str = "") -> str: ... 
            def _add_namespace_if_not_exists(self, name: str) -> None: ... 
            def _collect_magic_functions(self) -> None: ... 
            def _get_context(self) -> Dict[str, Any]: ... 
            def _is_python_fire_cmd(self, cmd: str) -> bool: ... 
            def _on_create(self) -> None: ... 
            def _on_env_edit(self, event: Inotify.Event) -> None: ... 
            @onload
            def _on_load(self) -> None: ... 
            def _on_postcmd(self, command: str, stdout: List[str], stderr: List[str]) -> None: ... 
            def _on_precmd(self, command: str) -> Optional[str]: ... 
            def _on_stderr(self, command: str, out: str) -> str: ... 
            def _on_stdout(self, command: str, out: str) -> str: ... 
            @postcmd
            def _post_cmd(self, command: str, stderr: str, stdout: str) -> None: ... 
            @precmd
            def _pre_cmd(self, command: str) -> Optional[str]: ... 
            def _repr(self, level: int = 0) -> str: ... 
            def _start_watchers(self) -> None: ... 
            def _stop_watchers(self): ... 
            def activate(self) -> None: ... 
            @classmethod
            def build_env(cls) -> Type["Env"]: ... 
            @classmethod
            def build_env_from_file(cls, file: Path) -> Type["Env"]: ... 
            def deactivate(self) -> None: ... 
            def dump_dot_env(self) -> Path: ... 
            def exit(self) -> None: ... 
            @command
            def genstub(self) -> None: ... 
            @classmethod
            def get_current_env(cls) -> "Env": ... 
            @classmethod
            def get_env_by_stage(cls, stage: str) -> Type["Env"]: ... 
            def get_env_vars(self, owner_name: str = "") -> Dict[str, str]: ... 
            def get_errors(self) -> List[str]: ... 
            def get_magic_functions(self) -> Dict[str, Dict[str, MagicFunction]]: ... 
            @classmethod
            def get_name(cls) -> str: ... 
            @classmethod
            def get_parent_env(cls, parent_path: str) -> Type["Env"]: ... 
            def load(self) -> None: ... 
            def unload(self) -> None: ... 
            def validate(self) -> None: ... 
        """

        self.assert_stub_equal("env_comm.pyi", stub)

    def test_in_dir(self):
        self.init()
        utils.add_flake_cmd(file=Path("env_comm.py"))

        Path("some_dir").mkdir()
        os.chdir("some_dir")

        stub = """
        class SandboxCommEnv:
            class Meta:
                emoji: str
                ignore_files: typing.List[str]
                name: str
                parents: typing.List[str]
                plugins: typing.List[envo.plugins.Plugin]
                stage: str
                version: str
                watch_files: typing.List[str]
                
                
            envo_stage: envo.env.Raw[str]
            path: envo.env.Raw[str]
            pythonpath: envo.env.Raw[str]
            root: Path
            stage: str
            
            @command
            def __flake(self, test_arg: str = "") -> str: ... 
            def _add_namespace_if_not_exists(self, name: str) -> None: ... 
            def _collect_magic_functions(self) -> None: ... 
            def _get_context(self) -> Dict[str, Any]: ... 
            def _is_python_fire_cmd(self, cmd: str) -> bool: ... 
            def _on_create(self) -> None: ... 
            def _on_env_edit(self, event: Inotify.Event) -> None: ... 
            @onload
            def _on_load(self) -> None: ... 
            def _on_postcmd(self, command: str, stdout: List[str], stderr: List[str]) -> None: ... 
            def _on_precmd(self, command: str) -> Optional[str]: ... 
            def _on_stderr(self, command: str, out: str) -> str: ... 
            def _on_stdout(self, command: str, out: str) -> str: ... 
            @postcmd
            def _post_cmd(self, command: str, stderr: str, stdout: str) -> None: ... 
            @precmd
            def _pre_cmd(self, command: str) -> Optional[str]: ... 
            def _repr(self, level: int = 0) -> str: ... 
            def _start_watchers(self) -> None: ... 
            def _stop_watchers(self): ... 
            def activate(self) -> None: ... 
            @classmethod
            def build_env(cls) -> Type["Env"]: ... 
            @classmethod
            def build_env_from_file(cls, file: Path) -> Type["Env"]: ... 
            def deactivate(self) -> None: ... 
            def dump_dot_env(self) -> Path: ... 
            def exit(self) -> None: ... 
            @command
            def genstub(self) -> None: ... 
            @classmethod
            def get_current_env(cls) -> "Env": ... 
            @classmethod
            def get_env_by_stage(cls, stage: str) -> Type["Env"]: ... 
            def get_env_vars(self, owner_name: str = "") -> Dict[str, str]: ... 
            def get_errors(self) -> List[str]: ... 
            def get_magic_functions(self) -> Dict[str, Dict[str, MagicFunction]]: ... 
            @classmethod
            def get_name(cls) -> str: ... 
            @classmethod
            def get_parent_env(cls, parent_path: str) -> Type["Env"]: ... 
            def load(self) -> None: ... 
            def unload(self) -> None: ... 
            def validate(self) -> None: ... 
        """

        self.assert_stub_equal("../env_comm.pyi", stub)

    def test_inherited(self):
        result = run("envo test --init")
        assert b"Created test environment" in result

        utils.add_flake_cmd(file=Path("env_comm.py"))
        utils.add_declaration("comm_var: str", Path("env_comm.py"))
        utils.add_definition("self.comm_var = 'test'", Path("env_comm.py"))

        utils.add_declaration("test_var: int", Path("env_test.py"))
        utils.add_definition("self.test_var = 1", Path("env_test.py"))
        utils.add_mypy_cmd(file=Path("env_test.py"))


        comm_stub = """
        class SandboxCommEnv:
            class Meta:
                emoji: str
                ignore_files: typing.List[str]
                name: str
                parents: typing.List[str]
                plugins: typing.List[envo.plugins.Plugin]
                stage: str
                version: str
                watch_files: typing.List[str]
                
                
            comm_var: str
            envo_stage: envo.env.Raw[str]
            path: envo.env.Raw[str]
            pythonpath: envo.env.Raw[str]
            root: Path
            stage: str
            
            @command
            def __flake(self, test_arg: str = "") -> str: ... 
            def _add_namespace_if_not_exists(self, name: str) -> None: ... 
            def _collect_magic_functions(self) -> None: ... 
            def _get_context(self) -> Dict[str, Any]: ... 
            def _is_python_fire_cmd(self, cmd: str) -> bool: ... 
            def _on_create(self) -> None: ... 
            def _on_env_edit(self, event: Inotify.Event) -> None: ... 
            @onload
            def _on_load(self) -> None: ... 
            def _on_postcmd(self, command: str, stdout: List[str], stderr: List[str]) -> None: ... 
            def _on_precmd(self, command: str) -> Optional[str]: ... 
            def _on_stderr(self, command: str, out: str) -> str: ... 
            def _on_stdout(self, command: str, out: str) -> str: ... 
            @postcmd
            def _post_cmd(self, command: str, stderr: str, stdout: str) -> None: ... 
            @precmd
            def _pre_cmd(self, command: str) -> Optional[str]: ... 
            def _repr(self, level: int = 0) -> str: ... 
            def _start_watchers(self) -> None: ... 
            def _stop_watchers(self): ... 
            def activate(self) -> None: ... 
            @classmethod
            def build_env(cls) -> Type["Env"]: ... 
            @classmethod
            def build_env_from_file(cls, file: Path) -> Type["Env"]: ... 
            def deactivate(self) -> None: ... 
            def dump_dot_env(self) -> Path: ... 
            def exit(self) -> None: ... 
            @command
            def genstub(self) -> None: ... 
            @classmethod
            def get_current_env(cls) -> "Env": ... 
            @classmethod
            def get_env_by_stage(cls, stage: str) -> Type["Env"]: ... 
            def get_env_vars(self, owner_name: str = "") -> Dict[str, str]: ... 
            def get_errors(self) -> List[str]: ... 
            def get_magic_functions(self) -> Dict[str, Dict[str, MagicFunction]]: ... 
            @classmethod
            def get_name(cls) -> str: ... 
            @classmethod
            def get_parent_env(cls, parent_path: str) -> Type["Env"]: ... 
            def load(self) -> None: ... 
            def unload(self) -> None: ... 
            def validate(self) -> None: ... 
        """
        self.assert_stub_equal("env_comm.pyi", comm_stub, stage="test")

        test_stub = """
        class SandboxEnv:
            class Meta:
                emoji: str
                ignore_files: typing.List[str]
                name: str
                parents: typing.List[str]
                plugins: typing.List[envo.plugins.Plugin]
                stage: str
                version: str
                watch_files: typing.List[str]
                
                
            comm_var: str
            envo_stage: envo.env.Raw[str]
            path: envo.env.Raw[str]
            pythonpath: envo.env.Raw[str]
            root: Path
            stage: str
            test_var: int
            
            def _collect_magic_functions(self) -> None: ... 
            def _get_context(self) -> Dict[str, Any]: ... 
            def _is_python_fire_cmd(self, cmd: str) -> bool: ... 
            def _on_create(self) -> None: ... 
            def _on_env_edit(self, event: Inotify.Event) -> None: ... 
            @onload
            def _on_load(self) -> None: ... 
            def _on_postcmd(self, command: str, stdout: List[str], stderr: List[str]) -> None: ... 
            def _on_precmd(self, command: str) -> Optional[str]: ... 
            def _on_stderr(self, command: str, out: str) -> str: ... 
            def _on_stdout(self, command: str, out: str) -> str: ... 
            @postcmd
            def _post_cmd(self, command: str, stderr: str, stdout: str) -> None: ... 
            @precmd
            def _pre_cmd(self, command: str) -> Optional[str]: ... 
            def _repr(self, level: int = 0) -> str: ... 
            def _start_watchers(self) -> None: ... 
            def _stop_watchers(self): ... 
            def activate(self) -> None: ... 
            @classmethod
            def build_env(cls) -> Type["Env"]: ... 
            @classmethod
            def build_env_from_file(cls, file: Path) -> Type["Env"]: ... 
            def deactivate(self) -> None: ... 
            def dump_dot_env(self) -> Path: ... 
            def exit(self) -> None: ... 
            @command
            def flake(self, test_arg: str = "") -> str: ... 
            @command
            def genstub(self) -> None: ... 
            @classmethod
            def get_current_env(cls) -> "Env": ... 
            @classmethod
            def get_env_by_stage(cls, stage: str) -> Type["Env"]: ... 
            def get_env_vars(self, owner_name: str = "") -> Dict[str, str]: ... 
            def get_errors(self) -> List[str]: ... 
            def get_magic_functions(self) -> Dict[str, Dict[str, MagicFunction]]: ... 
            @classmethod
            def get_name(cls) -> str: ... 
            @classmethod
            def get_parent_env(cls, parent_path: str) -> Type["Env"]: ... 
            def load(self) -> None: ... 
            @command
            def mypy(self, test_arg: str = "") -> None: ... 
            def unload(self) -> None: ... 
            def validate(self) -> None: ... 
        """
        self.assert_stub_equal("env_test.pyi", test_stub, stage="test")
