import copy
import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import List, Any

import pytest

from envo.misc import import_from_file
from envo.partial_reloader import PartialReloader, Action
from tests.unit import utils


def assert_actions(reloader: PartialReloader, actions_names: List[str]) -> None:
    actions_str = [repr(a) for a in reloader.old_module.get_actions(reloader.new_module)]
    assert actions_str == actions_names


def load_module(path: Path) -> Any:
    module = import_from_file(path)
    module.__name__ = "module"
    return module


class TestBase:
    @pytest.fixture(autouse=True)
    def setup(self, sandbox):
        pass


class TestFunctions(TestBase):
    def test_added_function(self, sandbox):
        module_file = sandbox / "module.py"
        module_file.touch()
        source = """
        import math
        
        global_var = 2
        
        def fun(arg1: str, arg2: str) -> str:
            return f"{arg1}_{arg2}_{id(global_var)}"
        """
        module_file.write_text(dedent(source))

        module = load_module(module_file)

        utils.add_function(
            """
            def fun2(arg1: str, arg2: str) -> str:
                return f"{arg1}_{arg2}_{id(global_var)}"
            """,
            module_file
        )

        reloader = PartialReloader(module)
        assert_actions(reloader, ['Add: Function: module.fun2', 'Update: GlobalVariable: module.global_var'])

        reloader.run()

        assert "fun" in  module.__dict__
        assert "fun2" in module.__dict__

        assert module.fun("str1", "str2") == module.fun2("str1", "str2")

    def test_modified_function(self, sandbox):
        module_file = sandbox / "module.py"
        module_file.touch()
        source = """
        import math

        global_var = 2

        def fun(arg1: str, arg2: str) -> str:
            return f"{arg1}_{arg2}_{id(global_var)}"
        """
        module_file.write_text(dedent(source))
        module = load_module(module_file)

        fun_id_before = id(module.fun)

        new_source = """
        import math

        global_var = 2

        def fun(arg1: str) -> str:
            return f"{arg1}_{id(global_var)}"
        """
        module_file.write_text(dedent(new_source))

        reloader = PartialReloader(module)
        assert_actions(reloader, ['Update: GlobalVariable: module.global_var', 'Update: Function: module.fun'])
        reloader.run()

        assert "fun" in module.__dict__

        global_var_id = id(module.global_var)

        assert module.fun("str1").endswith(str(global_var_id))
        assert id(module.fun) == fun_id_before

    def test_added_global_var(self, sandbox):
        module_file = sandbox / "module.py"
        module_file.touch()
        source = """
        global_var1 = 1 
        """
        module_file.write_text(dedent(source))

        module = load_module(module_file)
        new_source = """
        global_var1 = 1
        global_var2 = 2
        """
        module_file.write_text(dedent(new_source))

        reloader = PartialReloader(module)
        assert_actions(reloader,
                       ['Add: GlobalVariable: module.global_var2',
                        'Update: GlobalVariable: module.global_var1']
                       )
        reloader.run()

        assert "global_var1" in module.__dict__
        assert "global_var2" in module.__dict__

        assert module.global_var1 == 1
        assert module.global_var2 == 2

    def test_modified_global_var(self, sandbox):
        Path("__init__.py").touch()
        module_file = sandbox / "module.py"
        module_file.touch()
        module_file.write_text(dedent("""
        sprinkler_n = 1

        def some_fun():
            return "Some Fun"

        sample_dict = {
            "sprinkler_n_plus_1": sprinkler_n + 1,
            "sprinkler_n_plus_2": sprinkler_n + 2,
            "lambda_fun": lambda x: sprinkler_n + x,
            "fun": some_fun 
        }

        def print_sprinkler():
            return f"There is {sprinkler_n} sprinkler. ({sample_dict['sprinkler_n_plus_1']}, {sample_dict['sprinkler_n_plus_2']})"
            
        class Car:
            car_sprinkler_n = sprinkler_n 
        
        """))

        module = load_module(module_file)

        print_sprinkler_id = id(module.print_sprinkler)
        lambda_fun_id = id(module.sample_dict["lambda_fun"])
        some_fun_id = id(module.some_fun)
        assert module.sprinkler_n == 1

        utils.replace_in_code("sprinkler_n = 1", "sprinkler_n = 2", module_file)

        reloader = PartialReloader(module)
        assert_actions(reloader,
                       ['Update: GlobalVariable: module.sprinkler_n',
                        'Update: DictionaryItem: module.sample_dict.sprinkler_n_plus_1',
                        'Update: DictionaryItem: module.sample_dict.sprinkler_n_plus_2',
                        'Update: GlobalVariable: module.Car.car_sprinkler_n']
                       )

        reloader.run()

        assert print_sprinkler_id == id(module.print_sprinkler)
        assert module.Car.car_sprinkler_n == 2
        assert lambda_fun_id == id(module.sample_dict["lambda_fun"])
        assert some_fun_id == id(module.some_fun)
        assert module.sample_dict == {'sprinkler_n_plus_1': 3, 'sprinkler_n_plus_2': 4,
                                      "lambda_fun": module.sample_dict["lambda_fun"], "fun": module.some_fun}

    def test_modified_class_attr(self, sandbox):
        module_file = sandbox / "module.py"
        module_file.touch()
        module_file.write_text(dedent(
        """
        import math
        
        class CarwashBase:
            sprinklers_n: int = 12
            
            def print_sprinklers(self) -> str:
                return f"There are {self.sprinklers_n} sprinklers (Base)."
        
        class Carwash(CarwashBase):
            sprinklers_n: int = 22
            
            def print_sprinklers(self) -> str:
                return f"There are {self.sprinklers_n} sprinklers (Inherited)."
        """

        ))

        module = load_module(module_file)
        print_sprinklers_id = id(module.CarwashBase.print_sprinklers)

        # First edit
        module_file.write_text(dedent(
            """
            import math

            class CarwashBase:
                sprinklers_n: int = 55

                def print_sprinklers(self) -> str:
                    return f"There are {self.sprinklers_n} sprinklers (Base)."

            class Carwash(CarwashBase):
                sprinklers_n: int = 77

                def print_sprinklers(self) -> str:
                    return f"There are {self.sprinklers_n} sprinklers (Inherited)." 
            """
        ))

        reloader = PartialReloader(module)
        assert_actions(reloader, ['Update: GlobalVariable: module.CarwashBase.sprinklers_n',
 'Update: GlobalVariable: module.Carwash.sprinklers_n'])
        reloader.run()

        assert module.CarwashBase.sprinklers_n == 55
        assert module.Carwash.sprinklers_n == 77
        assert print_sprinklers_id == id(module.CarwashBase.print_sprinklers)

    def test_modified_method(self, sandbox):
        module_file = sandbox / "module.py"
        module_file.touch()
        module_file.write_text(dedent(
            """
            class Carwash:
                @classmethod
                def print_sprinklers_cls(cls) -> str:
                    return f"There is one sprinkler (Cls)."
                    
                def print_sprinklers(self) -> str:
                    return f"There is one sprinkler."
            """

        ))

        module = load_module(module_file)
        reffered_print_sprinklers_cls = module.Carwash.print_sprinklers_cls
        assert module.Carwash.print_sprinklers_cls() == "There is one sprinkler (Cls)."
        assert reffered_print_sprinklers_cls() == "There is one sprinkler (Cls)."
        assert module.Carwash().print_sprinklers() == "There is one sprinkler."

        print_sprinklers_id = id(module.Carwash.print_sprinklers)

        # First edit
        module_file.write_text(dedent(
            """
            class Carwash:
                @classmethod
                def print_sprinklers_cls(cls) -> str:
                    return f"There are 5 sprinklers (Cls)."
                    
                def print_sprinklers(self) -> str:
                    return f"There are 5 sprinklers." 
            """
        ))

        reloader = PartialReloader(module)
        assert_actions(reloader, ['Update: Method: module.Carwash.print_sprinklers_cls',
                                  'Update: Function: module.Carwash.print_sprinklers'])
        reloader.run()

        assert module.Carwash.print_sprinklers_cls() == "There are 5 sprinklers (Cls)."
        assert reffered_print_sprinklers_cls() == "There are 5 sprinklers (Cls)."
        assert module.Carwash().print_sprinklers() == "There are 5 sprinklers."
        assert print_sprinklers_id == id(module.Carwash.print_sprinklers)

    def test_added_method(self, sandbox):
        module_file = sandbox / "module.py"
        module_file.touch()
        module_file.write_text(dedent(
            """
            class Carwash:
                pass
            """

        ))

        module = load_module(module_file)

        module_file.write_text(dedent(
            """
            class Carwash:
                def print_sprinklers(self) -> str:
                    return f"There are 5 sprinklers." 
            """
        ))

        reloader = PartialReloader(module)
        assert_actions(reloader, ['Add: Function: module.Carwash.print_sprinklers'])
        reloader.run()

        assert module.Carwash().print_sprinklers() == "There are 5 sprinklers."
