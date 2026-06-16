"""Scope the comment-line (libcleri) grammar cost in the C read path.

Builds derived files (pure text, no parsing) that hold the per-frame count
fixed at the real value but vary the work, then times extxyz.read_dicts
(dict level — no ASE conversion) on each:

  E0 real          : grammar(6 keys) + marshal + tokenize(~27 atoms)   [baseline]
  E1 real, 1 atom  : grammar(6 keys) + marshal + tokenize(1 atom)      [comment path only]
  E2 min,  1 atom  : grammar(2 keys) + marshal + tokenize(1 atom)      [minimal comment]
  E3 rebundled x8  : 1/8 the frames, same atom lines                   [per-frame overhead]

Deltas:
  E0 - E1  ~= per-atom tokenizer cost for ~26 atoms (the part use_regex toggles)
  E1 - E2  ~= marginal grammar+marshal cost of the 4 extra info keys
  E0 - E3  ~= total per-frame overhead removed by 8x bigger frames
"""
import sys, time
import extxyz

SRC = sys.argv[1] if len(sys.argv) > 1 else "mad-train.xyz"
NIT = int(sys.argv[2]) if len(sys.argv) > 2 else 3

REAL_COMMENT = None
PROPS_LATT = None  # minimal: Properties + Lattice only


def split_frames(path):
    """Yield (natoms:int, comment:str, atom_lines:list[str]) streaming."""
    with open(path) as f:
        while True:
            head = f.readline()
            if not head:
                return
            nat = int(head)
            comment = f.readline()
            atoms = [f.readline() for _ in range(nat)]
            yield nat, comment, atoms


def build_derived():
    global REAL_COMMENT, PROPS_LATT
    f_e1 = open("scope_e1_0atom_real.xyz", "w")
    f_e2 = open("scope_e2_0atom_min.xyz", "w")
    f_e3 = open("scope_e3_rebundle8.xyz", "w")
    buf_nat, buf_lines, buf_comment, group = 0, [], None, 0
    K = 8
    for nat, comment, atoms in split_frames(SRC):
        if REAL_COMMENT is None:
            REAL_COMMENT = comment
            toks = comment.split()
            # keep Properties=... and Lattice="..." (Lattice spans quotes)
            props = next(t for t in toks if t.startswith("Properties="))
            li = comment.index('Lattice="')
            latt = comment[li:comment.index('"', li + 9) + 1]
            PROPS_LATT = f"{props} {latt}\n"
        # E1: 1-atom frames with the real comment (1 atom = minimal tokenizer work)
        f_e1.write("1\n")
        f_e1.write(REAL_COMMENT)
        f_e1.write(atoms[0])
        # E2: 1-atom frames with minimal comment
        f_e2.write("1\n")
        f_e2.write(PROPS_LATT)
        f_e2.write(atoms[0])
        # E3: rebundle K frames into one (reuse this group's first comment)
        if group == 0:
            buf_comment = comment
        buf_lines.extend(atoms)
        buf_nat += nat
        group += 1
        if group == K:
            f_e3.write(f"{buf_nat}\n")
            f_e3.write(buf_comment)
            f_e3.writelines(buf_lines)
            buf_nat, buf_lines, buf_comment, group = 0, [], None, 0
    if group:
        f_e3.write(f"{buf_nat}\n")
        f_e3.write(buf_comment)
        f_e3.writelines(buf_lines)
    f_e1.close(); f_e2.close(); f_e3.close()


def timeit(path, n=NIT):
    best = float("inf"); nframes = 0
    for _ in range(n):
        t0 = time.perf_counter()
        out = extxyz.read_dicts(path, use_regex=False)
        best = min(best, time.perf_counter() - t0)
        nframes = len(out)
    return best, nframes


build_derived()
cases = [
    ("E0 real (baseline)",        SRC),
    ("E1 real comment, 1 atom",   "scope_e1_0atom_real.xyz"),
    ("E2 min comment,  1 atom",   "scope_e2_0atom_min.xyz"),
    ("E3 rebundled x8",           "scope_e3_rebundle8.xyz"),
]
res = {}
for name, path in cases:
    dt, nf = timeit(path)
    res[name] = (dt, nf)
    print(f"{name:28s} {dt:6.2f}s  ({nf} frames)")

e0 = res["E0 real (baseline)"][0]
e1 = res["E1 real comment, 1 atom"][0]
e2 = res["E2 min comment,  1 atom"][0]
e3 = res["E3 rebundled x8"][0]
print()
print(f"per-atom tokenizer cost  (E0-E1): {e0-e1:5.2f}s  ({100*(e0-e1)/e0:4.0f}% of read)")
print(f"comment path total       (E1)   : {e1:5.2f}s  ({100*e1/e0:4.0f}% of read)")
print(f"  of which 4 extra keys (E1-E2) : {e1-e2:5.2f}s")
print(f"  minimal comment+marshal (E2)  : {e2:5.2f}s")
print(f"per-frame overhead via rebundle (E0-E3): {e0-e3:5.2f}s  (E3={e3:.2f}s)")
