import inspect
import os
from collections import OrderedDict
from collections import defaultdict
from copy import copy
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import Any, Dict, List, Optional, Type, Set, Callable

import sys
from dataclasses import dataclass, field
from envo import dependency_watcher
from envo import misc
from envo.dependency_watcher import Dependency

dataclass = dataclass(repr=False)


def equal(a: Any, b: Any) -> bool:
    ret = bool(a == b)

    if not ret:
        try:
            ret = a.__dict__ == b.__dict__
        except AttributeError:
            pass

    return ret


equals: Dict[str, Callable] = defaultdict(lambda: equal)
equals["pandas.core.series.Series"] = lambda a, b: a.equals(b)
equals["pandas.core.series.Series"] = lambda a, b: a.equals(b)
equals["pandas.DataFrame"] = lambda a, b: a.equals(b)


@dataclass
class Action:
    reloader: "PartialReloader"

    def pre_execute(self) -> None:
        self.reloader.applied_actions.append(self)

    def __eq__(self, other: "Action") -> bool:
        raise NotImplementedError()


@dataclass
class Object:
    @dataclass
    class Add(Action):
        parent: "ContainerObj"
        object: "Object"

        def __repr__(self) -> str:
            return f"Add: {repr(self.object)}"

        def execute(self) -> None:
            self.pre_execute()
            setattr(self.parent.python_obj, self.object.name, self.object.python_obj)

    @dataclass
    class Update(Action):
        parent: Optional["ContainerObj"]
        old_object: "Object"
        new_object: Optional["Object"]

        def __repr__(self) -> str:
            return f"Update: {repr(self.old_object)}"

        def execute(self) -> None:
            self.pre_execute()
            setattr(
                self.old_object.parent.python_obj,
                self.old_object.name,
                self.new_object.python_obj,
            )

    @dataclass
    class Delete(Action):
        parent: Optional["ContainerObj"]
        object: "Object"

        def __repr__(self) -> str:
            return f"Delete: {repr(self.object)}"

        def execute(self) -> None:
            self.pre_execute()
            delattr(self.parent.python_obj, self.object.name)

    python_obj: Any
    reloader: "PartialReloader"
    name: str = ""
    module: Optional["Module"] = None
    parent: Optional["ContainerObj"] = None

    def get_actions_for_update(
        self, new_object: "Object"
    ) -> List["Action"]:
        raise NotImplementedError()

    def get_actions_for_add(
            self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        return [self.Add(reloader=reloader, parent=parent, object=obj)]

    def get_actions_for_delete(
        self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        ret = [self.Delete(reloader=reloader, parent=parent, object=obj)]
        ret.extend(self.get_actions_for_dependent_modules())
        return ret

    @property
    def full_name(self) -> str:
        return (
            f"{self.parent.full_name}.{self.name}"
            if self.parent and self.parent.name
            else self.name
        )

    @property
    def type(self) -> str:
        try:
            return f"{self.python_obj.__module__}.{self.python_obj.__class__.__name__}"
        except AttributeError:
            return self.python_obj.__class__.__name__


    @property
    def flat(self) -> Dict[str, Any]:
        return {self.full_name: self}

    @classmethod
    def _is_ignored(cls, name: str) -> bool:
        name = str(name)
        if name.startswith("__") and name.endswith("__"):
            return True

        return name in [
            "None"
        ]

    def safe_compare(self, other: "Object"):
        try:
            return equals[self.type](self.python_obj, other.python_obj)
        except BaseException as e:
            return False

    @property
    def source(self) -> str:
        try:
            ret = inspect.getsource(self.python_obj)
            ret = dedent(ret)
            return ret
        except (TypeError, OSError):
            return ""

    def get_parents_flat(self) -> List["Object"]:
        ret = []

        obj = self
        while obj.parent:
            ret.append(obj.parent)
            obj = obj.parent

        return ret

    def get_parents_obj_flat(self) -> List["Object"]:
        ret = [o.python_obj for o in self.get_parents_flat()]
        return ret

    def get_actions_for_dependent_modules(self) -> List[Action]:
        ret = []

        full_name_without_module = self.full_name[len(self.module.full_name)+1:]
        for m in dependency_watcher.get_dependencies(module_full_name=self.module.full_name,
                                                     used_obj=full_name_without_module):
            module = Module(m, reloader=self.reloader)
            ret.extend(module.get_actions_for_update())

        return ret

    def __eq__(self, other: "Object") -> bool:
        return self.python_obj == other.python_obj

    def __ne__(self, other: "Object") -> bool:
        return self.python_obj != other.python_obj

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.full_name}"


@dataclass
class FinalObj(Object):
    pass


@dataclass
class Function(FinalObj):
    class Update(FinalObj.Update):
        old_object: "Function"
        new_object: Optional["Function"]

        def execute(self) -> None:
            self.pre_execute()
            self.old_object.get_func(
                self.old_object.python_obj
            ).__code__ = self.new_object.get_func(self.new_object.python_obj).__code__

    def get_actions_for_update(
        self, new_object: "Function", ignore_objects: Optional[List[Object]] = None
    ) -> List["Action"]:
        if self != new_object:
            return [
                self.Update(
                    reloader=self.reloader,
                    parent=self.parent,
                    old_object=self,
                    new_object=new_object,
                )
            ]
        else:
            return []

    def get_actions_for_add(
        self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        return [self.Add(reloader=reloader, parent=parent, object=obj)]

    def __eq__(self, other: "Function") -> bool:
        compare_fields = [
            "co_argcount",
            "co_cellvars",
            "co_code",
            "co_consts",
            "co_flags",
            "co_freevars",
            "co_lnotab",
            "co_name",
            "co_names",
            "co_nlocals",
            "co_stacksize",
            "co_varnames",
        ]

        for f in compare_fields:
            if getattr(self.get_func(self.python_obj).__code__, f) != getattr(
                self.get_func(other.python_obj).__code__, f
            ):
                return False

        return True

    def __ne__(self, other: "Function") -> bool:
        return not (Function.__eq__(self, other))

    @property
    def source(self) -> str:
        try:
            ret = inspect.getsource(self.get_func(self.python_obj))
            ret = dedent(ret)
        except (TypeError, OSError):
            return ""

        if (
            isinstance(self.parent, Dictionary)
            and self.python_obj.__name__ == "<lambda>"
        ):
            ret = ret[ret.find(":") + 1 :]
            ret = dedent(ret)

        return ret

    def is_global(self) -> bool:
        ret = self.parent == self.module
        return ret

    @classmethod
    def get_func(cls, obj: Any) -> Any:
        return obj

    @classmethod
    def _is_ignored(cls, name: str) -> bool:
        return False


@dataclass
class Method(Function):
    @classmethod
    def get_func(cls, obj: Any) -> Any:
        return obj.__func__


@dataclass
class PropertyGetter(Function):
    @classmethod
    def get_func(cls, obj: Any) -> Any:
        return obj.fget


class PropertySetter(Function):
    @classmethod
    def get_func(cls, obj: Any) -> Any:
        return obj.fset


@dataclass
class ContainerObj(Object):
    children: Dict[str, "Object"] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._collect_objs()

    def get_dict(self) -> Dict[str, Any]:
        raise NotImplementedError()

    def is_foreign_obj(self, obj: Any) -> bool:
        if hasattr(obj, "__module__") and obj.__module__:
            module_name = obj.__module__.replace(".py", "").replace("/", ".").replace("\\", ".")
            if not module_name.endswith(self.module.name):
                return True

        return False

    def _python_obj_to_obj_classes(self, name: str, obj: Any) -> Dict[str, Type[Object]]:
        if self.is_foreign_obj(obj):
            return {name: Variable}

        if obj in [o.python_obj for o in self.module.flat.values()]:
            return {name: Variable}

        if inspect.isclass(obj):
            # Check if it's definition
            return {name: Class}

        if inspect.isfunction(obj):
            return {name: Function}

        if isinstance(obj, dict):
            return {name: Dictionary}

        return {}

    def _collect_objs(self) -> None:
        for n, o in self.get_dict().items():
            # break recursions
            if any(o is p for p in self.get_parents_obj_flat() + [self.python_obj]):
                continue

            obj_classes = self._python_obj_to_obj_classes(n, o)

            for n, obj_class in obj_classes.items():
                if obj_class._is_ignored(n):
                    continue

                self.children[n] = obj_class(
                    o, parent=self, name=n, reloader=self.reloader, module=self.module
                )

    @property
    def flat(self) -> Dict[str, Object]:
        ret = {}
        for o in self.children.values():
            ret.update(o.flat)

        ret.update({self.full_name: self})

        return ret

    def get_functions(self) -> List[Function]:
        ret = [o for o in self.children if isinstance(o, Function)]
        return ret

    def get_functions_recursive(self) -> List[Function]:
        ret = [o for o in self.flat.values() if isinstance(o, Function)]
        return ret

    @property
    def source(self) -> str:
        ret = inspect.getsource(self.python_obj)
        for c in self.children.values():
            ret = ret.replace(c.source, "")

        return ret


@dataclass
class Class(ContainerObj):
    def get_actions_for_update(
        self, new_object: "Class"
    ) -> List["Action"]:
        return []

    def get_dict(self) -> Dict[str, Any]:
        ret = self.python_obj.__dict__
        return ret

    def _python_obj_to_obj_classes(self, name: str, obj: Any) -> Dict[str, Type[Object]]:
        # If already process means it's just a reference
        if obj in [o.python_obj for o in self.module.flat.values()]:
            return {name: ClassAttribute}

        ret = super()._python_obj_to_obj_classes(name, obj)
        if ret:
            return ret

        if inspect.ismethod(obj) or inspect.ismethoddescriptor(obj):
            return {name: Method}

        if isinstance(obj, property):
            ret = {name: PropertyGetter}

            if obj.fset:
                setter_name = name + "__setter__"
                ret[setter_name] = PropertySetter
            return ret

        return {name: ClassAttribute}

    def get_actions_for_add(
        self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        ret = [self.Add(reloader=reloader, parent=parent, object=obj)]
        ret.extend(self.get_actions_for_dependent_modules())
        return ret


@dataclass
class Dictionary(ContainerObj):
    def get_actions_for_update(
        self, new_object: "Class"
    ) -> List["Action"]:
        return []

    def get_dict(self) -> Dict[str, Any]:
        return self.python_obj

    def _python_obj_to_obj_classes(self, name: str, obj: Any) -> Dict[str, Type[Object]]:
        if isinstance(obj, dict):
            return {name: Dictionary}

        return {name: DictionaryItem}


@dataclass
class Variable(FinalObj):
    @dataclass
    class Update(FinalObj.Update):
        def execute(self) -> None:
            self.pre_execute()
            if hasattr(self.new_object.python_obj, "__module__") and self.new_object.python_obj.__module__ == f"{self.reloader.module_obj.__package__}.{self.reloader.module_obj.__name__}":
                if inspect.isclass(self.new_object.python_obj):
                    python_obj_name_to_obj = {str(o.python_obj): o for o in self.reloader.old_module.flat.values()}
                    self.new_object.python_obj = python_obj_name_to_obj[str(self.new_object.python_obj)].python_obj
                elif inspect.isfunction(self.new_object.python_obj):
                    python_obj_name_to_obj = {str(o.python_obj): o for o in self.reloader.old_module.flat.values()}
                    self.new_object.python_obj = python_obj_name_to_obj[str(self.new_object.python_obj)].python_obj
                else:
                    self.new_object.python_obj.__class__ = self.old_object.python_obj.__class__

            setattr(
                self.old_object.parent.python_obj,
                self.old_object.name,
                self.new_object.python_obj,
            )

    def get_actions_for_update(
        self, new_object: "Variable"
    ) -> List["Action"]:
        if self.safe_compare(new_object):
            return []

        ret = [
            self.Update(
                reloader=self.reloader,
                parent=self.parent,
                old_object=self,
                new_object=new_object,
            )
        ]

        ret.extend(self.get_actions_for_dependent_modules())
        return ret

    def get_actions_for_add(
        self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        ret = [self.Add(reloader=reloader, parent=parent, object=obj)]
        ret.extend(self.get_actions_for_dependent_modules())
        return ret


@dataclass
class ClassAttribute(Variable):
    def get_actions_for_update(
        self, new_object: "Variable"
    ) -> List["Action"]:
        if self.safe_compare(new_object):
            return []

        ret = [
            self.Update(
                reloader=self.reloader,
                parent=self.parent,
                old_object=self,
                new_object=new_object,
            )
        ]

        ret.extend(self.get_actions_for_dependent_modules())

        return ret


@dataclass
class DictionaryItem(FinalObj):
    class Add(FinalObj.Add):
        def execute(self) -> None:
            self.pre_execute()
            self.parent.python_obj[self.object.name] = copy(self.object.python_obj)

    class Update(FinalObj.Update):
        def execute(self) -> None:
            self.pre_execute()
            self.old_object.parent.python_obj[
                self.new_object.name
            ] = self.new_object.python_obj

    class Delete(FinalObj.Delete):
        parent: Optional["ContainerObj"]
        object: "Object"

        def execute(self) -> None:
            self.pre_execute()
            del self.parent.python_obj[self.object.name]

    def get_actions_for_update(
        self, new_object: "Variable"
    ) -> List["Action"]:

        if self.safe_compare(new_object):
            return []

        ret = [
            self.Update(
                reloader=self.reloader,
                parent=self.parent,
                old_object=self,
                new_object=new_object,
            )
        ]

        ret.extend(self.get_actions_for_dependent_modules())
        return ret


@dataclass
class Import(FinalObj):
    class Add(FinalObj.Add):
        def execute(self) -> None:
            self.pre_execute()
            module = sys.modules.get(self.object.name, self.object.python_obj)
            setattr(self.parent.python_obj, self.object.name, module)

    def get_actions_for_update(
        self, new_object: "Variable"
    ) -> List["Action"]:
        return []

    def get_actions_for_add(
        self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        ret = [self.Add(reloader=reloader, parent=parent, object=obj)]
        ret.extend(self.get_actions_for_dependent_modules())
        return ret

    def get_actions_for_delete(
        self, reloader: "PartialReloader", parent: "ContainerObj", obj: "Object"
    ) -> List["Action"]:
        return []


@dataclass
class Module(ContainerObj):
    @dataclass
    class Update(Action):
        module: "Module"

        def execute(self) -> None:
            self.pre_execute()
            reloader = PartialReloader(self.module.python_obj, self.reloader.root, self.reloader.logger)
            reloader.run()
            self.reloader.applied_actions.extend(reloader.applied_actions)

        def __repr__(self) -> str:
            return f"Update: {repr(self.module)}"

    def __post_init__(self) -> None:
        self.module = self
        super().__post_init__()

    def _python_obj_to_obj_classes(self, name: str, obj: Any) -> Dict[str, Type[Object]]:
        ret = super()._python_obj_to_obj_classes(name, obj)
        if ret:
            return ret

        if inspect.ismodule(obj):
            return {name: Import}

        return {name: Variable}

    def get_dict(self) -> Dict[str, Any]:
        return self.python_obj.__dict__

    def get_actions_for_update(self) -> List["Action"]:
        ret = [self.Update(self.reloader, self)]
        return ret

    @classmethod
    def _is_ignored(cls, name: str) -> bool:
        return False

    @property
    def final_objs(self) -> List[FinalObj]:
        """
        Return non container objects
        """
        ret = []
        for o in self.children:
            if not isinstance(o, FinalObj):
                continue
            ret.append(o)
        return ret

    @property
    def flat(self) -> Dict[str, Object]:
        ret = {self.name: self}
        for o in self.children.values():
            ret.update(o.flat)

        return ret

    def get_actions(self, obj: Object) -> List[Action]:
        ret = []

        a = self.flat
        b = obj.flat
        new_objects_names = b.keys() - a.keys()
        new_objects = {n: b[n] for n in new_objects_names}
        for o in new_objects.values():
            parent = a.get(o.parent.full_name, b[o.parent.full_name])
            ret.extend(
                o.get_actions_for_add(reloader=self.reloader, parent=parent, obj=o)
            )

        deleted_objects_names = a.keys() - b.keys()
        deleted_objects = {n: a[n] for n in deleted_objects_names}
        for o in deleted_objects.values():
            parent = a[o.parent.full_name]
            ret.extend(
                o.get_actions_for_delete(reloader=self.reloader, parent=parent, obj=o)
            )

        for n, o in a.items():
            # if deleted
            if n not in b:
                continue

            if o is self:
                continue

            ret.extend(o.get_actions_for_update(new_object=b[n]))

        return ret

    def __repr__(self) -> str:
        return f"Module: {self.python_obj.__name__}"


class PartialReloader:
    module_obj: Any
    applied_actions: List[Action]
    logger: Any

    def __init__(self, module_obj: Any, root: Path, logger: Any) -> None:
        self.root = root.resolve()
        self.module_obj = module_obj
        self.logger = logger
        self.applied_actions = []

    def _is_user_module(self, module: Any):
        if not hasattr(module, "__file__"):
            return False

        ret = self.module_dir in Path(module.__file__).parents
        return ret

    @property
    def module_dir(self) -> Path:
        ret = Path(self.module_obj.__file__).parent
        return ret

    @property
    def source_files(self) -> List[str]:
        ret = [str(p) for p in self.module_dir.glob("**/*.py")]
        return ret

    @property
    def old_module(self) -> Module:
        return Module(self.module_obj, reloader=self, name=f"{self.module_obj.__name__}")

    @property
    def new_module(self) -> Module:
        dependency_watcher.disable()
        module_obj = misc.import_from_file(Path(self.module_obj.__file__), self.root)
        dependency_watcher.enable()

        return Module(
            module_obj,
            reloader=self,
            name=f"{self.module_obj.__name__}",
        )

    def run(self) -> List[Action]:
        """
        :return: True if succeded False i unable to reload
        """
        self.applied_actions = []

        old_module = self.old_module
        new_module = self.new_module

        actions = old_module.get_actions(new_module)

        for a in actions:
            a.execute()

        return self.applied_actions
