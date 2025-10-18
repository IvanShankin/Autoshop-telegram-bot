
def safe_int_conversion(value, default=None, positive=False):
    try:
        value_in_int = int(value)
        if positive:
            return value_in_int if value_in_int > 0 else default

        return value_in_int
    except (ValueError, TypeError):
        return default
