from ._classes import SourceSpec, GraphSpec, filter_classes
import sys as _sys

# Re-export filters
_mod = _sys.modules[__name__]
for _type_id, _cls in filter_classes.items():
    setattr(_mod, _cls.__name__, _cls)

