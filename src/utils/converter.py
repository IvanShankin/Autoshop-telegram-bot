
def safe_int_conversion(value, default=None, positive=False) -> int:
    try:
        value_in_int = int(value)
        if value_in_int > 123456789012345678901234567890: # если больше BigInt
            return default
        if positive:
            return value_in_int if value_in_int > 0 else default

        return value_in_int
    except (ValueError, TypeError):
        return default
