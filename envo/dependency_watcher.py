import re
from pathlib import Path
from types import ModuleType
from copy import copy

from dataclasses import dataclass

from envo import misc
import ast

try:
    import builtins
except ImportError:
    import __builtin__ as builtins

from collections import defaultdict
from typing import List, Optional, Any, Dict, Set, DefaultDict

import sys
import inspect


__all__ = ('enable', 'disable', 'get_dependencies')

_baseimport = builtins.__import__
_blacklist = None
_dependencies: DefaultDict[str, List["Dependency"]] = defaultdict(list)
path_to_modules = defaultdict(set)

# PEP 328 changed the default level to 0 in Python 3.3.
_default_level = -1 if sys.version_info < (3, 3) else 0


@dataclass
class Dependency:
    module_file: Path
    used_obj: List[str]

    @property
    def module_obj(self) -> ModuleType:
        return list(path_to_modules[str(self.module_file)])[0]

    def is_used(self, obj_name: str) -> bool:
        obj_parts = obj_name.split(".")

        if self.used_obj:
            if "*" in self.used_obj:
                return True

            if not set(self.used_obj) & set(obj_parts):
                return False

        return obj_parts[-1] in self.module_file.read_text()


def enable(blacklist=None) -> None:
    """Enable global module dependency tracking.

    A blacklist can be specified to exclude specific modules (and their import
    hierachies) from the reloading process.  The blacklist can be any iterable
    listing the fully-qualified names of modules that should be ignored.  Note
    that blacklisted modules will still appear in the dependency graph; they
    will just not be reloaded.
    """
    global _blacklist
    builtins.__import__ = _import
    if blacklist is not None:
        _blacklist = frozenset(blacklist)

def disable():
    """Disable global module dependency tracking."""
    global _blacklist, _parent
    builtins.__import__ = _baseimport

def _reset():
    global _dependencies
    global path_to_modules
    _dependencies = defaultdict(list)
    path_to_modules = defaultdict(set)


def flatten(module_file: str, used_obj: str, visited: Optional[List[str]] = None) -> List[Dependency]:
    if not visited:
        visited = []

    deps = _dependencies.get(module_file, [])

    for v in visited:
        deps = [d for d in deps if d.module_file != v]

    deps = [d for d in deps if d.is_used(used_obj)]

    for d in deps:
        visited.append(d.module_file)
        flat = flatten(d.module_file, used_obj, visited.copy())
        deps.extend(flat)

    # remove duplicates
    ret = []
    for d in deps:
        if d in ret:
            continue
        ret.append(d)

    return ret

def get_dependencies(module_file: str, used_obj: str) -> List[ModuleType]:
    """Get the dependency list for the given imported module."""
    flat = flatten(module_file, used_obj, visited=[module_file])

    modules = []
    for d in flat:
        if d.module_obj in modules:
            continue
        modules.append(d.module_obj)
    return modules

def get_this_frame_n() -> int:
    ret = 0

    while True:
        if sys._getframe(ret).f_globals["__name__"] == "envo.dependency_watcher":
            return ret
        ret += 1


def _import(name, globals=None, locals=None, fromlist=None, level=_default_level):
    """__import__() replacement function that tracks module dependencies."""
    # Track our current parent module.  This is used to find our current place
    # in the dependency graph.

    # Perform the actual import work using the base import function.
    this_frame_n = get_this_frame_n()
    parent = sys._getframe(this_frame_n+1).f_globals
    base = _baseimport(name, globals, locals, fromlist, level)

    if hasattr(base, "__file__"):
        path_to_modules[base.__file__].add(base)

    child_modules = [o for o in base.__dict__.values() if isinstance(o, ModuleType)]
    for m in child_modules:
        if not hasattr(m, "__file__"):
            continue
        path_to_modules[m.__file__].add(m)

    if fromlist:
        if hasattr(base, '__file__') and "__file__" in parent:
            dep = Dependency(Path(parent["__file__"]), fromlist)
            if dep not in _dependencies[base.__file__]:
                _dependencies[base.__file__].append(dep)
    else:
        if hasattr(base, '__file__') and "__file__" in parent:
            dep = Dependency(Path(parent["__file__"]), tuple())
            if dep not in _dependencies[base.__file__]:
                _dependencies[base.__file__].append(dep)

    return base

# install()
