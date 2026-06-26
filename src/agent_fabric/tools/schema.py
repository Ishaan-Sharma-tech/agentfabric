import inspect
from typing import Dict, Any, get_type_hints
from pydantic import create_model


def generate_tool_schema(func: Any) -> Dict[str, Any]:
    """
    Generate an OpenAPI-compatible JSON Schema for a Python function's arguments.
    Uses inspect and Pydantic v2 to validate and build the schema from type hints.
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    fields: Dict[str, Any] = {}
    required_fields = []
    
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
            
        # Extract parameter type, defaulting to str if no type hint is provided
        param_type = type_hints.get(name, Any)
        
        # Pydantic v2 create_model expects a tuple: (type, default_value)
        # If there is no default value, we use Pydantic's Ellipsis (...) to indicate required
        if param.default is inspect.Parameter.empty:
            fields[name] = (param_type, ...)
            required_fields.append(name)
        else:
            fields[name] = (param_type, param.default)

    if not fields:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    # Dynamically create a Pydantic model for function arguments
    model_name = f"{func.__name__}_args"
    model = create_model(model_name, **fields)
    
    # Generate JSON schema
    schema = model.model_json_schema()
    
    # Strip Pydantic-specific title fields to yield a clean OpenAI/MCP compliant schema
    schema.pop("title", None)
    if "properties" in schema:
        for prop_name, prop in schema["properties"].items():
            prop.pop("title", None)
            # Add descriptions from docstring if available (we can parse basic parameter docstrings later)
            
    return schema
