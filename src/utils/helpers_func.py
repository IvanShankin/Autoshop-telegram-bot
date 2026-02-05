import inspect as inspect_python

async def maybe_await(v):
    try:
        if inspect_python.isawaitable(v):
            return await v
        return v
    except AttributeError: # если получили синхронную функцию
        return v