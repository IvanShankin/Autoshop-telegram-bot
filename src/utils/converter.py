
def safe_int_conversion(value, default=None, positive=False) -> int:
    try:
        value_in_int = int(value)
        if value_in_int > 2147483646: # если больше int
            return default
        if positive:
            return value_in_int if value_in_int > 0 else default

        return value_in_int
    except (ValueError, TypeError):
        return default
