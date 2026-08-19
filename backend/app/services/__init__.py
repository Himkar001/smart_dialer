"""Services package — shared mutable state store."""

# Shared store for last safety decision (used by broadcaster without circular import)
_last_safety_decision_store: dict = {"last": None}
