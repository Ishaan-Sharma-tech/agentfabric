import inspect
import logging
from typing import Dict, Any, get_type_hints
from pydantic import create_model

logger = logging.getLogger("agent_fabric.tools.schema")

__all__ = ["generate_tool_schema"]


def generate_tool_schema(func: Any) -> Dict[str, Any]:
    """
    Generate an OpenAPI-compatible JSON Schema for a Python function's arguments.
    Uses inspect and Pydantic v2 to validate and build the schema from type hints.
    """
    try:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
    except Exception as e:
        logger.warning(f"Failed to resolve type hints for '{getattr(func, '__name__', str(func))}': {e}")
        type_hints = {}
        sig = inspect.signature(func)
    
    fields: Dict[str, Any] = {}
    
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
            
        param_type = type_hints.get(name, Any)
        if param_type is Any:
            param_type = str
            
        if param.default is inspect.Parameter.empty:
            fields[name] = (param_type, ...)
        else:
            fields[name] = (param_type, param.default)

    if not fields:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    try:
        model_name = f"{getattr(func, '__name__', 'tool')}_args"
        model = create_model(model_name, **fields)
        schema = model.model_json_schema()
        
        schema.pop("title", None)
        if "properties" in schema:
            for prop in schema["properties"].values():
                if isinstance(prop, dict):
                    prop.pop("title", None)
        return schema
    except Exception as e:
        logger.error(f"Failed to generate Pydantic schema for tool arguments: {e}")
        fallback_props = {name: {"type": "string"} for name in fields}
        req_list = [name for name, (t, default) in fields.items() if default is ...]
        return {
            "type": "object",
            "properties": fallback_props,
            "required": req_list
        }

