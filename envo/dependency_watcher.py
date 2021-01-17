from pathlib import Path
from types import ModuleType

from dataclasses import dataclass

from envo import misc

try:
    import builtins
except ImportError:
    import __builtin__ as builtins

from collections import defaultdict
from typing import List, Optional, Any, Dict, Set

import sys


__all__ = ('enable', 'disable', 'get_dependencies')

_baseimport = builtins.__import__
_blacklist = None
_dependencies = defaultdict(list)
_parent = None

# PEP 328 changed the default level to 0 in Python 3.3.
_default_level = -1 if sys.version_info < (3, 3) else 0


@dataclass
class Dependency:
    name: str
    used_objs: Set[str]

    @property
    def actual_name(self):
        return misc.get_module_from_full_name(self.name)

    @property
    def module_obj(self) -> ModuleType:
        return sys.modules[self.actual_name]

    def is_used(self, dependency: "Dependency") -> bool:
        if dependency.used_objs:
            if "*" in dependency.used_objs:
                return True
            return bool(self.used_objs & dependency.used_objs)
        else:
            source = Path(dependency.module_obj.__file__).read_text()
            return any(f"{self.actual_name}.{o}" in source for o in list(self.used_objs))


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


def flatten(dependency: Dependency, visited: Optional[List[Dependency]] = None) -> List[Dependency]:
    if not visited:
        visited = []

    deps = _dependencies.get(dependency.actual_name, [])
    for v in visited:
        while v in deps: deps.remove(v)

    for mr in deps:
        visited.append(mr)
        flat = flatten(mr, visited.copy())
        deps.extend(flat)

    # remove duplicates
    ret = []
    for d in deps:
        if d in ret:
            continue
        ret.append(d)

    return ret

def get_dependencies(dependency: Dependency) -> List[ModuleType]:
    """Get the dependency list for the given imported module."""
    flat = flatten(dependency, visited=[dependency])

    flat_used = []

    for d in flat:
        if dependency.is_used(d):
            flat_used.append(d)

    modules = [d.module_obj for d in flat_used]
    return modules

def _import(name, globals=None, locals=None, fromlist=None, level=_default_level):
    """__import__() replacement function that tracks module dependencies."""
    # Track our current parent module.  This is used to find our current place
    # in the dependency graph.
    global _parent
    parent = _parent
    if globals and "__package__" in globals and globals["__package__"]:
        _parent = (globals["__package__"] + "." + name)
    else:
        _parent = name

    # Perform the actual import work using the base import function.
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
                    m = sys.modules[m.__name__ + '.' + component]

        # If this is a nested import for a reloadable (source-based) module,
        # we append ourself to our parent's dependency list.
        if hasattr(m, '__file__'):
            from_set = set(fromlist) if fromlist else set()
            dep = Dependency(parent, from_set)
            if dep not in  _dependencies[m.__name__]:
                _dependencies[m.__name__].append(dep)

    # Lastly, we always restore our global _parent pointer.
    _parent = parent

    return base
