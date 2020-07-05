import builtins
import os
import sys
import time
from copy import copy
from enum import Enum
from threading import Lock
from typing import Any, Dict, Callable, Optional, List, TextIO

from dataclasses import dataclass
from prompt_toolkit.data_structures import Size
from xonsh.base_shell import BaseShell
from xonsh.execer import Execer
from xonsh.prompt.base import DEFAULT_PROMPT
from xonsh.ptk_shell.shell import PromptToolkitShell
from xonsh.readline_shell import ReadlineShell

from envo.misc import Callback


class PromptState(Enum):
    LOADING = 0
    NORMAL = 1


class PromptBase:
    default: str = str(DEFAULT_PROMPT)
    loading: bool = False
    emoji: str = NotImplemented
    state_prefix_map: Dict[PromptState, Callable[[], str]] = NotImplemented

    def __init__(self) -> None:
        self.state = PromptState.NORMAL
        self.previous_state: Optional[PromptState] = None
        self.emoji = ""
        self.name = ""

    def set_state(self, state: PromptState) -> None:
        self.previous_state = self.state
        self.state = state

    def as_str(self) -> str:
        return self.state_prefix_map[self.state]()

    def __str__(self) -> str:
        return self.state_prefix_map[self.state]()


class Shell(BaseShell):  # type: ignore
    """
    Xonsh shell extension.
    """

    @dataclass
    class Callbacs:
        pre_cmd: Callback = Callback(None)
        on_stdout: Callback = Callback(None)
        on_stderr: Callback = Callback(None)
        post_cmd: Callback = Callback(None)
        on_enter: Callback = Callback(None)
        on_exit: Callback = Callback(None)

        def reset(self) -> None:
            self.pre_cmd = Callback(None)
            self.on_stdout = Callback(None)
            self.on_stderr = Callback(None)
            self.post_cmd = Callback(None)
            self.on_enter = Callback(None)
            self.on_exit = Callback(None)

    def __init__(self, execer: Execer) -> None:
        super().__init__(execer=execer, ctx={})

        self.callbacks = self.Callbacs()

        self.environ = builtins.__xonsh__.env  # type: ignore
        self.history = builtins.__xonsh__.history  # type: ignore
        self.environ_before = copy(self.environ)
        self.context: Dict[str, Any] = {}

        self.cmd_lock = Lock()

    def set_prompt(self, prompt: str) -> None:
        self.environ["PROMPT"] = prompt

    def set_variable(self, name: str, value: Any) -> None:
        """
        Send a variable to the shell.

        :param name: variable name
        :param value: variable value
        :return:
        """
        self.context[name] = value

        built_in_name = f"__envo_{name}__"
        setattr(builtins, built_in_name, value)
        exec(f"{name} = {built_in_name}", builtins.__dict__)

    def update_context(self, context: Dict[str, Any]) -> None:
        for k, v in context.items():
            self.set_variable(k, v)

        self.context.update(**context)

    def start(self) -> None:
        pass

    def reset(self) -> None:
        self.environ = copy(self.environ_before)
        for n, v in self.context.items():
            exec(f"del {n}", builtins.__dict__)

        self.context = {}

    @property
    def prompt(self) -> str:
        from xonsh.ansi_colors import ansi_partial_color_format

        return str(ansi_partial_color_format(super().prompt))

    @classmethod
    def create(cls) -> "Shell":
        import signal
        from xonsh.built_ins import load_builtins
        from xonsh.built_ins import XonshSession
        from xonsh.imphooks import install_import_hooks
        from xonsh.xontribs import xontribs_load
        import xonsh.history.main as xhm

        ctx: Dict[str, Any] = {}

        execer = Execer(xonsh_ctx=ctx)

        builtins.__xonsh__ = XonshSession(ctx=ctx, execer=execer)  # type: ignore

        load_builtins(ctx=ctx, execer=execer)
        env = builtins.__xonsh__.env  # type: ignore
        env.update({"XONSH_INTERACTIVE": True, "SHELL_TYPE": "prompt_toolkit"})

        if "ENVO_SHELL_NOHISTORY" not in os.environ:
            builtins.__xonsh__.history = xhm.construct_history(  # type: ignore
                env=env.detype(), ts=[time.time(), None], locked=True
            )
            builtins.__xonsh__.history.gc.wait_for_shell = False  # type: ignore

        install_import_hooks()
        builtins.aliases.update({"ll": "ls -alF"})  # type: ignore
        xontribs_load([""])

        def func_sig_ttin_ttou(n: Any, f: Any) -> None:
            pass

        signal.signal(signal.SIGTTIN, func_sig_ttin_ttou)
        signal.signal(signal.SIGTTOU, func_sig_ttin_ttou)

        shell = cls(execer)
        builtins.__xonsh__.shell = shell  # type: ignore
        builtins.__xonsh__.shell.shell = shell  # type: ignore

        return shell

    def default(self, line: str) -> Any:
        self.cmd_lock.acquire()

        class Stream:
            device: TextIO

            def __init__(self, command: str, on_write: Callable) -> None:
                self.command = command
                self.on_write = on_write
                self.output: List[str] = []

            def write(self, text: str) -> None:
                if isinstance(text, bytes):
                    text = text.decode("utf-8")

                text = self.on_write(command=self.command, out=text)
                self.output.append(text)
                self.device.write(text)

            def flush(self) -> None:
                self.device.flush()

        class StdOut(Stream):
            device = sys.__stdout__

        class StdErr(Stream):
            device = sys.__stderr__

        if self.callbacks.pre_cmd:
            line = self.callbacks.pre_cmd(line)

        out = None
        if self.callbacks.on_stdout:
            out = StdOut(command=line, on_write=self.callbacks.on_stdout)
            sys.stdout = out  # type: ignore

        err = None
        if self.callbacks.on_stderr:
            err = StdErr(command=line, on_write=self.callbacks.on_stderr)
            sys.stderr = err  # type: ignore

        try:
            # W want to catch all exceptions just in case the command fails so we can handle std_err and post_cmd
            ret = super().default(line)
        finally:
            if self.callbacks.on_stdout:
                sys.stdout = sys.__stdout__

            if self.callbacks.on_stderr:
                sys.stderr = sys.__stderr__

            if self.callbacks.post_cmd and out and err:
                self.callbacks.post_cmd(command=line, stdout=out.output, stderr=err.output)

            self.cmd_lock.release()

        return ret


class FancyShell(Shell, PromptToolkitShell):  # type: ignore
    @classmethod
    def create(cls) -> "Shell":
        from xonsh.main import _pprint_displayhook

        shell = super().create()

        setattr(sys, "displayhook", _pprint_displayhook)
        return shell

    def start(self) -> None:
        if "ENVO_E2E_TEST" in os.environ:
            self.prompter.output.get_size = lambda: Size(50, 200)

        self.callbacks.on_enter()
        self.cmdloop()

        self.callbacks.on_exit()

    def set_prompt(self, prompt: str) -> None:
        super(FancyShell, self).set_prompt(prompt)
        self.prompter.message = self.prompt_tokens()
        self.prompter.app.invalidate()


class SimpleShell(Shell, ReadlineShell):  # type: ignore
    def start(self) -> None:
        self.cmdloop()


shells = {"fancy": FancyShell, "simple": SimpleShell, "headless": Shell}
