import os
from pathlib import Path

import pytest

from envo.plugins import VenvPath
from tests.e2e import utils


class TestVenv(utils.TestBase):
    def assert_activated(
        self,
        shell,
        venv_dir: Path,
        activated_from="sandbox",
        venv_name=".venv",
    ) -> None:
        e = shell.expecter
        shell.sendline("import url_regex")

        e.prompt(name=activated_from)
        shell.sendline("print(url_regex.UrlRegex)")
        e.output(r"<class 'url_regex\.url_regex\.UrlRegex'>\n")
        e.prompt(name=activated_from).eval()

        path = shell.envo.get_env_field("path")

        venv_path = VenvPath(root_path=venv_dir, venv_name=venv_name)

        assert path.count(str(venv_path.bin_path)) == 1

        site_packages_path = venv_path.site_packages_path

        sys_path = shell.envo.get_sys_path()
        assert sys_path.count(str(site_packages_path)) == 1

    def assert_predicted(self, shell, venv_dir: Path, venv_name=".venv") -> None:
        venv_path = VenvPath(root_path=venv_dir, venv_name=venv_name)
        path = shell.envo.get_env_field("path")
        assert path.count(str(venv_path.bin_path)) == 1

        sys_path = shell.envo.get_sys_path()
        assert set(str(p) for p in venv_path.possible_site_packages).issubset(
            set(sys_path)
        )

    @pytest.mark.parametrize(
        "file",
        ["env_comm.py", "env_test.py"],
    )
    def test_venv_addon(self, file, shell, sandbox):
        venv_path = VenvPath(root_path=sandbox, venv_name=".venv")
        utils.run("python -m venv .venv")
        utils.run(f"{str(venv_path.bin_path / 'pip')} install url-regex")
        utils.add_plugins("VirtualEnv", file=Path(file))

        e = shell.start()
        e.prompt().eval()

        self.assert_activated(shell, venv_dir=sandbox)

        shell.exit()
        e.exit().eval()

    def test_venv_addon_no_venv(self, sandbox, shell):
        venv_path = VenvPath(root_path=sandbox, venv_name=".venv")

        utils.add_plugins("VirtualEnv")
        utils.replace_in_code(
            "# Define your variables here", "VirtualEnv.init(self, venv_path=self.root)"
        )

        e = shell.start()
        e.prompt().eval()

        self.assert_predicted(shell, venv_dir=sandbox)

        utils.run("python -m venv .venv")
        utils.run(f"{str(venv_path.bin_path / 'pip')} install url-regex")

        self.assert_activated(shell, venv_dir=sandbox)

        shell.exit()
        e.exit().eval()

    def test_autodiscovery(self, shell, init_child_env, sandbox):
        venv_path = VenvPath(root_path=sandbox, venv_name=".venv")

        utils.run("python -m venv .venv")
        utils.run(f"{str(venv_path.bin_path / 'pip')} install url-regex")

        os.chdir("child")

        utils.add_plugins("VirtualEnv")

        e = shell.start()
        e.prompt(name="child", state=utils.PromptState.MAYBE_LOADING).eval()

        self.assert_activated(shell, venv_dir=sandbox, activated_from="child")

        shell.exit()
        e.exit().eval()

    def test_autodiscovery_cant_find(self, sandbox, shell):
        utils.add_plugins("VirtualEnv")
        utils.replace_in_code(
            "# Define your variables here",
            "VirtualEnv.init(self, venv_name='.some_venv')",
        )

        e = shell.start()
        e.prompt().eval()

        self.assert_predicted(shell, venv_dir=sandbox, venv_name=".some_venv")

        shell.exit()
        e.exit().eval()

    def test_custom_venv_name(self, shell, sandbox, init_child_env):
        venv_path = VenvPath(root_path=sandbox, venv_name=".custom_venv")

        utils.run("python -m venv .custom_venv")
        utils.run(f"{str(venv_path.bin_path / 'pip')} install url-regex")

        os.chdir("child")

        utils.add_plugins("VirtualEnv")
        utils.replace_in_code(
            "# Define your variables here",
            "VirtualEnv.init(self, venv_name='.custom_venv')",
        )

        e = shell.start()
        e.prompt(name="child").eval()

        self.assert_activated(
            shell, venv_dir=sandbox, venv_name=".custom_venv", activated_from="child"
        )

        shell.exit()
        e.exit().eval()
