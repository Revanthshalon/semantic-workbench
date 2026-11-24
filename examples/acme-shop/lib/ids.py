"""Pure-Python BLAKE3 (reference algorithm) and the id encoding of the step 1 plan.

node_id(scope_type, scope_name, path, kind, qualified_name, ordinal) -> 16 hex chars
reference_id(from_id_hex, name, edge_kind, site_path, line, column) -> 16 hex chars
content_hash(bytes) -> 64 hex chars
"""
import struct

IV = [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19]
PERM = [2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8]
CHUNK_START, CHUNK_END, PARENT, ROOT = 1, 2, 4, 8
M32 = 0xFFFFFFFF


def _rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & M32


def _g(s, a, b, c, d, x, y):
    s[a] = (s[a] + s[b] + x) & M32; s[d] = _rotr(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & M32;     s[b] = _rotr(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b] + y) & M32; s[d] = _rotr(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & M32;     s[b] = _rotr(s[b] ^ s[c], 7)


def _compress(cv, block_words, counter, block_len, flags):
    s = list(cv) + IV[:4] + [counter & M32, (counter >> 32) & M32, block_len, flags]
    m = list(block_words)
    for r in range(7):
        _g(s, 0, 4, 8, 12, m[0], m[1]); _g(s, 1, 5, 9, 13, m[2], m[3])
        _g(s, 2, 6, 10, 14, m[4], m[5]); _g(s, 3, 7, 11, 15, m[6], m[7])
        _g(s, 0, 5, 10, 15, m[8], m[9]); _g(s, 1, 6, 11, 12, m[10], m[11])
        _g(s, 2, 7, 8, 13, m[12], m[13]); _g(s, 3, 4, 9, 14, m[14], m[15])
        if r < 6:
            m = [m[i] for i in PERM]
    for i in range(8):
        s[i] ^= s[i + 8]
        s[i + 8] ^= cv[i]
    return s


def _words(block):
    block = block.ljust(64, b"\0")
    return list(struct.unpack("<16I", block))


class _Output:
    def __init__(self, cv, words, counter, block_len, flags):
        self.cv, self.words, self.counter, self.block_len, self.flags = cv, words, counter, block_len, flags

    def chaining_value(self):
        return _compress(self.cv, self.words, self.counter, self.block_len, self.flags)[:8]

    def root_bytes(self, n=32):
        out = _compress(self.cv, self.words, 0, self.block_len, self.flags | ROOT)
        return struct.pack("<16I", *out)[:n]


def _chunk_output(chunk, counter):
    cv = IV
    blocks = [chunk[i:i + 64] for i in range(0, len(chunk), 64)] or [b""]
    for i, blk in enumerate(blocks):
        flags = (CHUNK_START if i == 0 else 0) | (CHUNK_END if i == len(blocks) - 1 else 0)
        if i == len(blocks) - 1:
            return _Output(cv, _words(blk), counter, len(blk), flags)
        cv = _compress(cv, _words(blk), counter, 64, flags)[:8]


def blake3(data: bytes, n: int = 32) -> bytes:
    chunks = [data[i:i + 1024] for i in range(0, len(data), 1024)] or [b""]
    stack = []
    for idx, chunk in enumerate(chunks):
        out = _chunk_output(chunk, idx)
        if idx == len(chunks) - 1:
            break
        cv = out.chaining_value()
        total = idx + 1
        while total & 1 == 0:
            cv = _compress(IV, stack.pop() + cv, 0, 64, PARENT)[:8]
            total >>= 1
        stack.append(cv)
    while stack:
        out = _Output(IV, stack.pop() + out.chaining_value(), 0, 64, PARENT)
    return out.root_bytes(n)


def _field(buf: bytearray, b: bytes):
    buf += struct.pack("<I", len(b)) + b


def node_id(scope_type, scope_name, path, kind, qualified_name, ordinal=0) -> str:
    """scope_type: workspace|project|stack. scope_name: '' for workspace.
    path: '' for a declared node. kind: snake-case NodeKindName, e.g. 'external_service'."""
    buf = bytearray()
    for f in (scope_type, scope_name or "", path or "", kind, qualified_name):
        _field(buf, f.encode())
    _field(buf, struct.pack("<I", ordinal))
    return blake3(bytes(buf))[:8].hex()


def reference_id(from_id_hex, name, edge_kind, site_path, line, column) -> str:
    buf = bytearray()
    _field(buf, bytes.fromhex(from_id_hex))
    for f in (name, edge_kind, site_path):
        _field(buf, f.encode())
    _field(buf, struct.pack("<I", line))
    _field(buf, struct.pack("<I", column))
    return blake3(bytes(buf))[:8].hex()


def content_hash(data: bytes) -> str:
    return blake3(data).hex()


if __name__ == "__main__":
    assert blake3(b"").hex() == "af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262", blake3(b"").hex()
    assert blake3(b"abc").hex() == "6437b3ac38465133ffb63b75273a8db548c558465d79db03fd359c6cd5bd9d85", blake3(b"abc").hex()
    # official test vectors: input byte i = i % 251
    vec = lambda n: bytes(i % 251 for i in range(n))
    exp = {
        1024: "42214739f095a406f3fc83deb889744ac00df831c10daa55189b5d121c855af7",
        1025: "d00278ae47eb27b34faecf67b4fe263f82d5412916c1ffd97c8cb7fb814b8444",
        2048: "e776b6028c7cd22a4d0ba182a8bf62205d2ef576467e838ed6f2529b85fba24a",
        3072: "b98cb0ff3623be03326b373de6b9095218513e64f1ee2edd2525c7ad1e5cffd2",
        8192: "aae792484c8efe4f19e2ca7d371d8c467ffb10748d8a5a1ae579948f718a2a63",
    }
    for n, h in exp.items():
        got = blake3(vec(n)).hex()
        assert got == h, (n, got)
    print("blake3 ok;", node_id("workspace", "", "", "workspace", "workspace"))
