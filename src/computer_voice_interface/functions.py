"""Local functions that Claude can call via JSON blocks."""


FUNCTION_REGISTRY = {}


def register(name, description, parameters):
    """Decorator to register a function Claude can call."""
    def decorator(fn):
        FUNCTION_REGISTRY[name] = {
            "function": fn,
            "description": description,
            "parameters": parameters,
        }
        return fn
    return decorator


def call(name, args):
    """Call a registered function by name with the given args dict."""
    if name not in FUNCTION_REGISTRY:
        return {"error": f"Unknown function: {name}"}
    try:
        return FUNCTION_REGISTRY[name]["function"](**args)
    except Exception as e:
        return {"error": str(e)}


def get_prompt_description():
    """Generate a description of available functions for the system prompt."""
    lines = []
    for name, info in FUNCTION_REGISTRY.items():
        params = ", ".join(
            f'{p["name"]} ({p["type"]}): {p["description"]}'
            for p in info["parameters"]
        )
        lines.append(f'- {name}({params}): {info["description"]}')
    return "\n".join(lines)


# --- Registered functions ---


@register(
    name="get_weather",
    description="Get the current weather for a location",
    parameters=[
        {"name": "location", "type": "string", "description": "City or location name"},
    ],
)
def get_weather(location):
    return {"location": location, "temperature": 24, "condition": "sunny"}
