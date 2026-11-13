"""Memory: short-term operational memory, mission memory and persistent storage.

Every record carries a timestamp, provenance and confidence. Old records are
never treated as current truth: consumers ask for records within a max age.
"""
