"""One-off script: strip/replace all non-ASCII bytes in graph_builder.py to make it valid UTF-8 Python."""
import os
import re

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ingestion", "graph_builder.py")

with open(path, "rb") as f:
    content = f.read()

# Known multi-byte sequences first (most specific)
replacements = [
    # Smart/curly quotes
    (b"\xe2\x80\x9c", b'"'),
    (b"\xe2\x80\x9d", b'"'),
    (b"\xe2\x80\x98", b"'"),
    (b"\xe2\x80\x99", b"'"),
    # Dashes
    (b"\xe2\x80\x94", b"-"),
    (b"\xe2\x80\x93", b"-"),
    # Arrow
    (b"\xe2\x86\x92", b"->"),
    # Garbled em-dash variants (double-encoded UTF-8)
    (b"\xc3\xa2\xe2\x82\xac\xe2\x80\x9c", b"-"),   # â€" (triple garbled)
    (b"\xc3\xa2\xe2\x82\xac\"", b"-"),               # â€" variant
    # Emoji / special chars that appear in logger strings
    (b"\xc3\xa2\xc5\xa1\xc2\xa0\xc3\xaf\xc2\xb8\xc2\x8f", b""),  # garbled emoji
    (b"\xc3\xa2\xc5\x93\"", b'"'),                   # garbled open-quote
]

for bad, good in replacements:
    count = content.count(bad)
    if count:
        print(f"Replacing {count}x {bad!r} -> {good!r}")
        content = content.replace(bad, good)

# Final sweep: replace any remaining non-ASCII byte sequences with '?'
# Only in comment/string regions (safe: Python identifiers are all ASCII here)
def replace_non_ascii(b):
    result = bytearray()
    i = 0
    while i < len(b):
        byte = b[i]
        if byte < 128:
            result.append(byte)
            i += 1
        else:
            # Skip the full multi-byte sequence
            if byte >= 0xF0:
                seq_len = 4
            elif byte >= 0xE0:
                seq_len = 3
            elif byte >= 0xC0:
                seq_len = 2
            else:
                seq_len = 1
            seq = b[i:i+seq_len]
            print(f"  Stripping unrecognised bytes at offset {i}: {seq!r}")
            # Replace with nothing (safest for comments)
            i += seq_len
    return bytes(result)

content = replace_non_ascii(content)

with open(path, "wb") as f:
    f.write(content)

print("\nDone. Verifying syntax...")
import py_compile, sys
try:
    py_compile.compile(path, doraise=True)
    print("SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
