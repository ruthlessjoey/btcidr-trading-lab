"""markets/risk/numbers.py - strict number parsing and exact arithmetic for the risk engine (M6).

Boundary rules:
  - Inputs must be an int (not bool), a Decimal, or a decimal string such as "100", "0.25" or "-3". Floats are refused,
    because a binary float cannot carry a monetary value exactly. Booleans are refused. NaN, infinities and signalling
    NaN are refused. Nothing is coerced, defaulted or guessed.
  - Internal arithmetic is exact: Fraction values. Division never rounds mid-calculation.
  - Output rounding is explicit, and it is conservative:
      quantities    round DOWN to the configured quantity step (never more than the caps allow);
      money outputs round UP to the configured money quantum (a reported loss or exposure is never understated).
  - Rounded outputs are built from integer multiples of a Decimal step, so they are exact decimals, with no float.
"""
import math
import re
from decimal import Decimal
from fractions import Fraction

_DECIMAL_TEXT = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)")


class NumberError(ValueError):
    """An input is not an acceptable finite decimal number. The message names the field."""


def parse_decimal(name, value):
    """Returns a finite Decimal, or raises NumberError. Never coerces a float."""
    if isinstance(value, bool):
        raise NumberError(f"{name} must not be a boolean")
    if isinstance(value, float):
        raise NumberError(f"{name} must be a decimal string or integer, not a float")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, str):
        if not _DECIMAL_TEXT.fullmatch(value):
            raise NumberError(f"{name} is not a decimal number: {value!r}")
        number = Decimal(value)
    else:
        raise NumberError(f"{name} has unsupported type {type(value).__name__}")
    if not number.is_finite():
        raise NumberError(f"{name} must be finite")
    return number


def parse_positive(name, value):
    number = parse_decimal(name, value)
    if number <= 0:
        raise NumberError(f"{name} must be greater than zero")
    return number


def parse_non_negative(name, value):
    number = parse_decimal(name, value)
    if number < 0:
        raise NumberError(f"{name} must not be negative")
    return number


def parse_fraction_of_one(name, value):
    """A value in the half-open interval (0, 1]."""
    number = parse_positive(name, value)
    if number > 1:
        raise NumberError(f"{name} must not exceed 1")
    return number


def parse_int(name, value, minimum):
    if isinstance(value, bool) or not isinstance(value, int):
        raise NumberError(f"{name} must be an integer")
    if value < minimum:
        raise NumberError(f"{name} must be at least {minimum}")
    return value


def floor_to_step(amount, step):
    """Largest integer multiple of step that does not exceed amount. Exact. Amount may be negative (-> the caller
    checks sign). Returns a Fraction."""
    multiples = math.floor(Fraction(amount) / Fraction(step))
    return multiples * Fraction(step)


def ceil_to_quantum(amount, quantum):
    """Smallest integer multiple of quantum that is not below amount. Exact. Returns a Fraction."""
    multiples = math.ceil(Fraction(amount) / Fraction(quantum))
    return multiples * Fraction(quantum)


def to_text(decimal_value):
    """Plain positional text with no exponent, so the same value always gives the same string."""
    return format(decimal_value.normalize(), "f")


def fraction_to_decimal_text(amount, step):
    """Exact text of an amount that is an integer multiple of a Decimal step. Used only after ceil or floor."""
    if amount == 0:
        return "0"
    multiples = Fraction(amount) / Fraction(step)
    if multiples.denominator != 1:
        raise NumberError("amount is not an integer multiple of its step")
    return to_text(Decimal(int(multiples)) * step)
