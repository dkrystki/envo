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
from typing import List, Optional, Any, Dict, Set

import sys
import inspect


__all__ = ('enable', 'disable', 'get_dependencies')

_baseimport = builtins.__import__
_blacklist = None
_dependencies = defaultdict(list)

# PEP 328 changed the default level to 0 in Python 3.3.
_default_level = -1 if sys.version_info < (3, 3) else 0


@dataclass
class Dependency:
    name: str
    used_obj: List[str]

    @property
    def actual_name(self):
        return misc.get_module_from_full_name(self.name)

    @property
    def module_obj(self) -> ModuleType:
        return sys.modules[self.actual_name]

    def is_used(self, obj_name: str) -> bool:
        obj_parts = obj_name.split(".")

        if self.used_obj:
            if "*" in self.used_obj:
                return True

            if not set(self.used_obj) & set(obj_parts):
                return False

        return obj_parts[-1] in Path(self.module_obj.__file__).read_text()


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
    _dependencies = defaultdict(list)


def flatten(module_full_name: str, used_obj: str, visited: Optional[List[str]] = None) -> List[Dependency]:
    if not visited:
        visited = []

    deps = _dependencies.get(module_full_name, [])

    for v in visited:
        deps = [d for d in deps if d.name != v]

    deps = [d for d in deps if d.is_used(used_obj)]

    for d in deps:
        visited.append(d.name)
        flat = flatten(d.name, used_obj, visited.copy())
        deps.extend(flat)

    # remove duplicates
    ret = []
    for d in deps:
        if d in ret:
            continue
        ret.append(d)

    return ret

def get_dependencies(module_full_name: str, used_obj: str) -> List[ModuleType]:
    """Get the dependency list for the given imported module."""
    flat = flatten(module_full_name, used_obj, visited=[module_full_name])

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

# import sys
# from os.path import isdir
# from importlib import invalidate_caches
# from importlib.abc import SourceLoader
# from importlib.machinery import FileFinder
#
# from importlib.machinery import SourceFileLoader
#
# class MyLoader(SourceLoader):
#     def __init__(self, fullname, path):
#         self.fullname = fullname
#         self.path = path
#
#     def get_filename(self, fullname):
#         return self.path
#
#     def get_data(self, filename):
#         """exec_module is already defined for us, we just have to provide a way
#         of getting the source code of the module"""
#
#         with open(filename, "rb") as f:
#             data = f.read()
#
#
#         parsed = ast.parse(data)
#         classes = [o for o in ast.walk(parsed) if isinstance(o, ast.ClassDef)]
#         methods_body_line_numbers = []
#         for c in classes:
#             methods = [o for o in c.body if isinstance(o, ast.FunctionDef)]
#             for m in methods:
#                 first_a = next((a for a in m.body if type(a) in [ast.Expr, ast.Assign, ast.Return, ast.Pass, ast.Call,
#                                                                  ast.AnnAssign]), None)
#                 if not first_a:
#                     continue
#                 methods_body_line_numbers.append(first_a.lineno)
#
#         lines = data.splitlines(keepends=True)
#         for l in methods_body_line_numbers:
#             index = l-1
#             line = lines[index]
#             content = line.lstrip()
#             spaces = line[0:len(line) - len(content)]
#             lines[index] = spaces+b"__class__;"+content
#
#         data = b"".join(lines)
#
#         return data


# once = False
#
# def install():
#     global once
#     if once:
#         return
#     # insert the path hook ahead of other path hooks
#     hook_index, hook = next((i, h) for i, h in enumerate(sys.path_hooks) if "FileFinder" in h.__name__)
#
#     def new_hook(path: str):
#         finder = hook(path)
#         if "site-packages" in path or "python3" in path:
#             return finder
#         py_loader_index = next(i for i, l in enumerate(finder._loaders) if ".py" in l[0])
#         finder._loaders.insert(0, (".py", MyLoader))
#         return finder
#
#     sys.path_hooks[hook_index] = new_hook
#
#     once = True


def _import(name, globals=None, locals=None, fromlist=None, level=_default_level):
    """__import__() replacement function that tracks module dependencies."""
    # Track our current parent module.  This is used to find our current place
    # in the dependency graph.

    # Perform the actual import work using the base import function.
    this_frame_n = get_this_frame_n()
    parent = sys._getframe(this_frame_n+1).f_globals
    base = _baseimport(name, globals, locals, fromlist, level)

    if base is not None and parent is not None:
        m = base

        # We manually walk through the imported hierarchy because the import
        # function only returns the top-level package reference for a nested
        # import statement (e.g. 'package' for `import package.module`) when
        # no fromlist has been specified.  It's possible that the package
        # might not have all of its descendents as attributes, in which case
        # we fall back to using the immediate ancestor of the module instead.
        if fromlist is None:
            for component in name.split('.')[1:]:
                try:
                    m = getattr(m, component)
                except AttributeError:
                    if not hasattr(m, "__name__"):
                        continue
                    m = sys.modules[m.__name__ + '.' + component]

        # If this is a nested import for a reloadable (source-based) module,
        # we append ourself to our parent's dependency list.
        if hasattr(m, '__file__') and "__name__" in parent:
            dep = Dependency(parent["__name__"], fromlist)
            _dependencies[m.__name__].append(dep)

    return base

# install()
