_is_raspberry_pi = None


def is_raspberry_pi() -> bool:
    """
        True when running on real Pi hardware (RPi.GPIO importable), False on a
        desktop OS where the tkinter emulator backend is used instead.
    """
    global _is_raspberry_pi
    if _is_raspberry_pi is None:
        try:
            import RPi.GPIO  # noqa: F401
            _is_raspberry_pi = True
        except Exception:
            _is_raspberry_pi = False
    return _is_raspberry_pi
