from typing import *

__all__ = [
    "NotSpecified",
    "NotSpecifiedType",
]


@final
class NotSpecified:
    """
    Sentinel value meant to be assigned as default values for function
    arguments.
    
    Example
    ```
    def my_function[T](argument: T|NotSpecifiedType = NotSpecified):
        if argument is NotSpecified:
            argument = 42
        print(argument)
    
        
    my_function(10)
    # > 10
    my_function()
    # > 42
    ```
    """
    pass

type NotSpecifiedType = type[NotSpecified]
"""Type of `NotSpecified`"""
