"""
blocks random nicknames
"""

from handle.core import IRCD, Hook

# A lower score means more matches, and also more innocent kills.
# A higher score will result in fewer matches, but also fewer innocent kills.

max_score = 4

stringdict = {
    "aj": "fqtvxz",
    "aq": "deghjkmnprtxyz",
    "av": "bfhjqwxz",
    "az": "jwx",
    "bd": "bghjkmpqvxz",
    "bf": "bcfgjknpqvwxyz",
    "bg": "bdfghjkmnqstvxz",
    "bh": "bfhjkmnqvwxz",
    "bj": "bcdfghjklmpqtvwxyz",
    "bk": "dfjkmqrvwxyz",
    "bl": "bgpqwxz",
    "bm": "bcdflmnqz",
    "bn": "bghjlmnpqtvwx",
    "bp": "bfgjknqvxz",
    "bq": "bcdefghijklmnopqrstvwxyz",
    "bt": "dgjkpqtxz",
    "bv": "bfghjklnpqsuvwxz",
    "bw": "bdfjklmnpqsuwxyz",
    "bx": "abcdfghijklmnopqtuvwxyz",
    "bz": "bcdfgjklmnpqrstvwxz",
    "cb": "bfghjkpqyz",
    "cc": "bcdfgjklmnqrstxz",
    "cd": "hjkqvwxz",
    "cf": "gjknqvwyz",
    "cg": "bdfgjkpqvz",
    "cl": "fghjmpqxz",
    "cm": "bcdjkqv",
    "cn": "bghjkpqwxz",
    "cp": "gjkvxyz",
    "cq": "abcdefghijklmnopqsvwxyz",
    "cr": "bcdfgjqx",
    "cs": "bcdfgjxz",
    "cv": "bdfghjklmnquvwxyz",
    "cx": "abdefghjklmnpqrstuvwxyz",
    "cy": "jqy",
    "cz": "bcdfghjlpqrtvwxz",
    "db": "bdgjnpqstxz",
    "dc": "bcdfgjqxz",
    "dd": "fgklmnpqrstvwxz",
    "df": "bghjknpqvxyz",
    "dg": "bdfghjqstvxz",
    "dh": "bfkmnqwxz",
    "dk": "cdhjkpqrtuvwxz",
    "dl": "bcdfhjklmnqwxz",
    "dm": "bcdfjnqw",
    "dn": "fghjkmnpqvwz",
    "dp": "bgjkqsvwxz",
    "dq": "abcefghijkmnopqtvwxyz",
    "dr": "bfkqtvx",
    "dt": "bcdfghqtxz",
    "dv": "bfghjknqruvwyz",
    "dw": "cdfjkmnpqsvwxz",
    "dx": "abcdeghjklmnopqrsuvwxyz",
    "dy": "jyz",
    "dz": "bcdfgjlnpqrstvxz",
    "eb": "jqx",
    "eg": "cjvxz",
    "eh": "hxz",
    "ej": "fghjpqtwxyz",
    "ek": "jqxz",
    "ep": "jvx",
    "eq": "bcghijkmotvxyz",
    "ev": "bfpq",
    "fc": "bdjkmnqvxz",
    "fd": "bgjklqsvyz",
    "fg": "fgjkmpqtvwxyz",
    "fh": "bcfghjkpqvwxz",
    "fj": "bcdfghijklmnpqrstvwxyz",
    "fk": "bcdfghjkmpqrstvwxz",
    "fl": "fjkpqxz",
    "fm": "bdfhjlmnpvwxyz",
    "fn": "bdfghjklnqrstvwxz",
    "fp": "bfjknqtvwxz",
    "fq": "abcefghijklmnopqrstvwxyz",
    "fr": "nqxz",
    "fs": "gjxz",
    "ft": "jqx",
    "fv": "bcdfhjklmnpqtuvwxyz",
    "fw": "bcfgjklmpqstuvwxyz",
    "fx": "bcdfghjklmnpqrstvwxyz",
    "fy": "ghjpquvxy",
    "fz": "abcdfghjklmnpqrtuvwxyz",
    "gb": "bcdknpqvwx",
    "gc": "gjknpqwxz",
    "gd": "cdfghjklmqtvwxz",
    "gf": "bfghjkmnpqsvwxyz",
    "gg": "jkqvxz",
    "gj": "bcdfghjklmnpqrstvwxyz",
    "gk": "bcdfgjkmpqtvwxyz",
    "gl": "fgjklnpqswxz",
    "gm": "dfjkmnqvxz",
    "gn": "jkqvxz",
    "gp": "bjknpqtwxyz",
    "gq": "abcdefghjklmnopqrsvwxyz",
    "gr": "jkqt",
    "gs": "df",
    "gt": "fjknqvx",
    "gu": "qwx",
    "gv": "bcdfghjklmpqstvwxyz",
    "gw": "bcdfgjknpqtvwxz",
    "gx": "abcdefghjklmnopqrstvwxyz",
    "gy": "jkqxy",
    "gz": "bcdfgjklmnopqrstvxyz",
    "hb": "bcdfghjkqstvwxz",
    "hc": "cjknqvwxz",
    "hd": "fgjnpvz",
    "hf": "bfghjkmnpqtvwxyz",
    "hg": "bcdfgjknpqsxyz",
    "hh": "bcgklmpqrtvwxz",
    "hj": "bcdfgjkmpqtvwxyz",
    "hk": "bcdgkmpqrstvwxz",
    "hl": "jklmnpqvxz",
    "hm": "dhjqrvwxz",
    "hn": "jrxz",
    "hp": "bjkmqvwxyz",
    "hq": "abcdefghijklmnopqrstvwyz",
    "hr": "cjqx",
    "hs": "jqxz",
    "ht": "bdfghjklmnpqstuvwxz",
    "hv": "bcdfghjklmnpqstuvwxz",
    "hw": "bcfghjklnpqsvwxz",
    "hx": "abcdefghijklmnopqrstuvwxyz",
    "hz": "bcdfghjklmnpqrstuvwxz",
    "ib": "jqx",
    "if": "jqvwz",
    "ih": "bgjqx",
    "ii": "bjqxy",
    "ij": "cfgqxy",
    "ik": "bcfqx",
    "iq": "cdefgjkmnopqtvxyz",
    "iu": "hiwxy",
    "iv": "cfgmqx",
    "iw": "dgjkmnpqtvxz",
    "ix": "jkqrxz",
    "iy": "bcdfghjklpqtvwx",
    "jb": "bcdghjklmnopqrtuvwxyz",
    "jc": "cfgjkmnopqvwxy",
    "jd": "cdfghjklmnpqrtvwx",
    "jf": "abcdfghjlnopqrtuvwxyz",
    "jg": "bcdfghijklmnopqstuvwxyz",
    "jh": "bcdfghjklmnpqrxyz",
    "jj": "bcdfghjklmnopqrstuvwxyz",
    "jk": "abcdfghjknqrstwxyz",
    "jl": "bcfghjmnpqrstuvwxyz",
    "jm": "bcdfghiklmnqrtuvwyz",
    "jn": "bcfjlmnpqsuvwxz",
    "jp": "bcdfhijkmpqstvwxyz",
    "jq": "abcdefghijklmnopqrstuvwxyz",
    "jr": "bdfhjklpqrstuvwxyz",
    "js": "bfgjmoqvxyz",
    "jt": "bcdfghjlnpqrtvwxz",
    "jv": "abcdfghijklpqrstvwxyz",
    "jw": "bcdefghijklmpqrstuwxyz",
    "jx": "abcdefghijklmnopqrstuvwxyz",
    "jy": "bcdefghjkpqtuvwxyz",
    "jz": "bcdfghijklmnopqrstuvwxyz",
    "kb": "bcdfghjkmqvwxz",
    "kc": "cdfgjknpqtwxz",
    "kd": "bfghjklmnpqsvwxyz",
    "kf": "bdfghjkmnpqsvwxyz",
    "kg": "cghjkmnqtvwxyz",
    "kh": "cfghjkqx",
    "kj": "bcdfghjkmnpqrstwxyz",
    "kk": "bcdfgjmpqswxz",
    "kl": "cdfghjlmqstwxz",
    "km": "bdfghjknqrstwxyz",
    "kn": "bcdfhjklmnqsvwxz",
    "kp": "bdfgjkmpqvxyz",
    "kq": "abdefghijklmnopqrstvwxyz",
    "kr": "bcdfghjmqrvwx",
    "ks": "djlqx",
    "kt": "cdfjklqvx",
    "ku": "qux",
    "kv": "bcfghjklnpqrstvxyz",
    "kw": "bcdfgjklmnpqsvwxz",
    "kx": "abcdefghjklmnopqrstuvwxyz",
    "ky": "vxy",
    "kz": "bcdefghjklmnpqrstuvwxyz",
    "lb": "cdgkqtvxz",
    "lc": "bqx",
    "lf": "bcdklmnpqrstxvwxz",
    "lg": "cdfgpqvxz",
    "lh": "cfghkmnpqrtvx",
    "lj": "cfjklpqxz",
    "lk": "qxz",
    "ln": "cfjqxz",
    "lp": "jkqxz",
    "lq": "bcdefhijklmopqrstvwxyz",
    "lr": "dfgjklmpqrtvwx",
    "lv": "bcfhjklmnpqrstwxz",
    "lw": "bcdfgjknqxz",
    "lx": "bcdfghjklmnpqrtuwz",
    "lz": "cdjptvxz",
    "mb": "qxz",
    "md": "hjkpvz",
    "mf": "fkpqvwxz",
    "mg": "cfgjnpqsvwxz",
    "mh": "bchjkmnqvx",
    "mj": "bcdfghjknpqrstvwxyz",
    "mk": "bcfgklmnpqrvwxz",
    "ml": "jkqz",
    "mm": "qvz",
    "mn": "fhjkqxz",
    "mq": "bdefhjklmnopqtwxyz",
    "mr": "jklqvwz",
    "mt": "bjmnpkqx",
    "mv": "bcfghjklmnqtvwxz",
    "mw": "bcdfgjklnpqsuvwxyz",
    "mx": "abcefghijklmnopqrstvwxyz",
    "mz": "bcdfghjkmnpqrstvwxz",
    "nb": "hkmnqxz",
    "nf": "bghksqvxz",
    "nh": "fhjkmqtvxz",
    "nk": "qxz",
    "nl": "bghjknqvwxz",
    "nm": "dfghjkqtvwxz",
    "np": "bdjmqwxz",
    "nq": "abcdfghjklmnopqrtvwxyz",
    "nr": "bfjkqstvx",
    "nv": "bcdfgjkmnqswxz",
    "nw": "dgjpqvxz",
    "nx": "abfghjknopuyz",
    "nz": "cfqrxz",
    "oc": "fjvw",
    "og": "qxz",
    "oh": "fqxz",
    "oj": "bfhjmqrswxyz",
    "ok": "qxz",
    "oq": "bcdefghijklmnopqrstvwxyz",
    "ov": "bfhjqwx",
    "oy": "qxy",
    "oz": "fjpqtvx",
    "pb": "fghjknpqvwz",
    "pc": "gjq",
    "pd": "bgjkvwxz",
    "pf": "hjkmqtvwyz",
    "pg": "bdfghjkmqsvwxyz",
    "ph": "kqvx",
    "pk": "bcdfhjklmpqrvx",
    "pl": "ghkqvwx",
    "pm": "bfhjlmnqvwyz",
    "pn": "fjklmnqrtvwz",
    "pp": "gqwxz",
    "pq": "abcdefghijklmnopqstvwxyz",
    "pr": "hjkqrwx",
    "ps": "mw",
    "pt": "jqxz",
    "pv": "bdfghjklquvwxyz",
    "pw": "fjkmnpqsuvwxz",
    "px": "abcdefghijklmnopqrstuvwxyz",
    "pz": "bdefghjklmnpqrstuvwxyz",
    "qa": "ceghkopqxy",
    "qb": "bcdfghjklmnqrstuvwxyz",
    "qc": "abcdfghijklmnopqrstuvwxyz",
    "qd": "defghijklmpqrstuvwxyz",
    "qe": "abceghjkmopquwxyz",
    "qf": "abdfghijklmnopqrstuvwxyz",
    "qg": "abcdefghijklmnopqrtuvwxz",
    "qh": "abcdefghijklmnopqrstuvwxyz",
    "qi": "efgijkmpwx",
    "qj": "abcdefghijklmnopqrstuvwxyz",
    "qk": "abcdfghijklmnopqrsuvwxyz",
    "ql": "abcefghjklmnopqrtuvwxyz",
    "qm": "bdehijklmnoqrstuvxyz",
    "qn": "bcdefghijklmnoqrtuvwxyz",
    "qo": "abcdefgijkloqstuvwxyz",
    "qp": "abcdefghijkmnopqrsuvwxyz",
    "qq": "bcdefghijklmnopstwxyz",
    "qr": "bdefghijklmnoqruvwxyz",
    "qs": "bcdefgijknqruvwxz",
    "qt": "befghjklmnpqtuvwxz",
    "qu": "cfgjkpwz",
    "qv": "abdefghjklmnopqrtuvwxyz",
    "qw": "bcdfghijkmnopqrstuvwxyz",
    "qx": "abcdefghijklmnopqrstuvwxyz",
    "qy": "abcdefghjklmnopqrstuvwxyz",
    "qz": "abcdefghijklmnopqrstuvwxyz",
    "rb": "fxz",
    "rg": "jvxz",
    "rh": "hjkqrxz",
    "rj": "bdfghjklmpqrstvwxz",
    "rk": "qxz",
    "rl": "jnq",
    "rp": "jxz",
    "rq": "bcdefghijklmnopqrtvwxy",
    "rr": "jpqxz",
    "rv": "bcdfghjmpqrvwxz",
    "rw": "bfgjklqsvxz",
    "rx": "bcdfgjkmnopqrtuvwxz",
    "rz": "djpqvxz",
    "sb": "kpqtvwxz",
    "sd": "bjpqxz",
    "sf": "bghjkpqw",
    "sg": "cgjkqvwxz",
    "sj": "bfghjkmnpqrstvwxz",
    "sk": "qxz",
    "sl": "gjkqwxz",
    "sm": "fkqwxz",
    "sn": "dhjknqvwxz",
    "sq": "bfghjkmopstvwxz",
    "sr": "jklqrwxz",
    "ss": "bdfghjklmnquvwxyz",
    "sv": "bfhjklmnqtwxyz",
    "sw": "jkmpqvwxz",
    "sx": "bcdefghjklmnopqrtuvwxyz",
    "sy": "qxy",
    "sz": "bdfgjpqsvxz",
    "tb": "cghjkmnpqtvwx",
    "tc": "jnqvx",
    "td": "bfgjkpqtvxz",
    "tf": "ghjkqvwyz",
    "tg": "bdfghjkmpqsx",
    "tj": "bdfhjklmnpqstvwxyz",
    "tk": "bcdfghjklmpqvwxz",
    "tl": "jkqwxz",
    "tm": "bknqtwxz",
    "tn": "fhjkmqrvwxz",
    "tp": "bjpqvwxz",
    "tq": "abdefhijklmnopqrstvwxyz",
    "tr": "gjqvx",
    "tv": "bcfghjknpquvwxz",
    "tw": "bcdfjknqvz",
    "tx": "bcdefghjklmnopqrsuvwxz",
    "tz": "jklmnpqxz",
    "uc": "fjmvx",
    "uf": "jpqvx",
    "ug": "qvx",
    "uh": "bcgjkpvxz",
    "uj": "wbfghklmqvwx",
    "uk": "fgqxz",
    "uq": "bcdfghijklmnopqrtwxyz",
    "uu": "fijkqvwyz",
    "uv": "bcdfghjkmpqtwxz",
    "uw": "dgjnquvxyz",
    "ux": "jqxz",
    "uy": "jqxyz",
    "uz": "fgkpqrx",
    "vb": "bcdfhijklmpqrtuvxyz",
    "vc": "bcdfgjklnpqtvwxyz",
    "vd": "bdghjklnqvwxyz",
    "vf": "bfghijklmnpqtuvxz",
    "vg": "bcdgjkmnpqtuvwxyz",
    "vh": "bcghijklmnpqrtuvwxyz",
    "vj": "abcdfghijklmnpqrstuvwxyz",
    "vk": "bcdefgjklmnpqruvwxyz",
    "vl": "hjkmpqrvwxz",
    "vm": "bfghjknpquvxyz",
    "vn": "bdhjkmnpqrtuvwxz",
    "vp": "bcdeghjkmopqtuvwyz",
    "vq": "abcdefghijklmnopqrstvwxyz",
    "vr": "fghjknqrtvwxz",
    "vs": "dfgjmqz",
    "vt": "bdfgjklmnqtxz",
    "vu": "afhjquwxy",
    "vv": "cdfghjkmnpqrtuwxz",
    "vw": "abcdefghijklmnopqrtuvwxyz",
    "vx": "abcefghjklmnopqrstuvxyz",
    "vy": "oqx",
    "vz": "abcdefgjklmpqrstvwxyz",
    "wb": "bdfghjpqtvxz",
    "wc": "bdfgjkmnqvwx",
    "wd": "bdfghjpqvxz",
    "wf": "cdghjkmqvwxyz",
    "wg": "bcdfgjknpqtvwxyz",
    "wh": "cdghjklpqvwxz",
    "wj": "bfghijklmnpqrstvwxyz",
    "wk": "cdfgjkpqtuvxz",
    "wl": "jqvxz",
    "wm": "dghjlnqtvwxz",
    "wp": "dfgjkpqtvwxz",
    "wq": "abcdefghijklmnopqrstvwxyz",
    "wr": "bcdfghjlmpnqwvx",
    "ws": "bcdfghjlmnpqwvx",
    "wt": "bcdfghjlmnpqtvx",
    "wu": "koquvwy",
    "wv": "bcdfghjklmnpqrtuvwxyz",
    "ww": "bcdgkpqstuvxyz",
    "wx": "abcdefghijklmnopqrstuvwxz",
    "wy": "jquwxy",
    "wz": "bcdfghjkmnopqrstuvwxz",
    "xa": "ajoqy",
    "xb": "bcdfghjkmnpqsvwxz",
    "xc": "bcdgjkmnqsvwxz",
    "xd": "bcdfghjklnpqstuvwxyz",
    "xf": "bcdfghjkmnpqtvwxyz",
    "xg": "bcdfghjkmnpqstvwxyz",
    "xh": "cdfghjkmnpqrstvwxz",
    "xi": "jkqy",
    "xj": "abcdefghijklmnopqrstvwxyz",
    "xk": "abcdfghjkmnopqrstuvwxyz",
    "xl": "bcdfghjklmnpqrvwxz",
    "xm": "bcdfghjknpqvwxz",
    "xn": "bcdfghjklmnpqrvwxyz",
    "xp": "bcfjknpqvxz",
    "xq": "abcdefghijklmnopqrstvwxyz",
    "xr": "bcdfghjklnpqrsvwyz",
    "xs": "bdfgjmnqrsvxz",
    "xt": "jkpqvwxz",
    "xu": "fhjkquwx",
    "xv": "bcdefghjklmnpqrsuvwxyz",
    "xw": "bcdfghjklmnpqrtuvwxyz",
    "xx": "bcdefghjkmnpqrstuwyz",
    "xy": "jxy",
    "xz": "abcdefghjklmnpqrstuvwxyz",
    "yb": "cfghjmpqtvwxz",
    "yc": "bdfgjmpqsvwx",
    "yd": "chjkpqvwx",
    "yf": "bcdghjmnpqsvwx",
    "yg": "cfjkpqtxz",
    "yh": "bcdfghjkpqx",
    "yi": "hjqwxy",
    "yj": "bcdfghjklmnpqrstvwxyz",
    "yk": "bcdfgpqvwxz",
    "ym": "dfgjqvxz",
    "yp": "bcdfgjkmqxz",
    "yq": "abcdefghijklmnopqrstvwxyz",
    "yr": "jqx",
    "yt": "bcfgjnpqx",
    "yv": "bcdfghjlmnpqstvwxz",
    "yw": "bfgjklmnpqstuvwxz",
    "yx": "bcdfghjknpqrstuvwxz",
    "yy": "bcdfghjklpqrstvwxz",
    "yz": "bcdfjklmnpqtvwx",
    "zb": "dfgjklmnpqstvwxz",
    "zc": "bcdfgjmnpqstvwxy",
    "zd": "bcdfghjklmnpqstvwxy",
    "zf": "bcdfghijkmnopqrstvwxyz",
    "zg": "bcdfgjkmnpqtvwxyz",
    "zh": "bcfghjlpqstvwxz",
    "zj": "abcdfghjklmnpqrstuvwxyz",
    "zk": "bcdfghjklmpqstvwxz",
    "zl": "bcdfghjlnpqrstvwxz",
    "zm": "bdfghjklmpqstvwxyz",
    "zn": "bcdfghjlmnpqrstuvwxz",
    "zp": "bcdfhjklmnpqstvwxz",
    "zq": "abcdefghijklmnopqrstvwxyz",
    "zr": "bcfghjklmnpqrstvwxyz",
    "zs": "bdfgjmnqrsuwxyz",
    "zt": "bcdfgjkmnpqtuvwxz",
    "zu": "ajqx",
    "zv": "bcdfghjklmnpqrstuvwxyz",
    "zw": "bcdfghjklmnpqrstuvwxyz",
    "zx": "abcdefghijklmnopqrstuvwxyz",
    "zy": "fxy",
    "zz": "cdfhjnpqrvx"
}


def randomness(string, strict=True):
    rnd = 0
    str_lower = string.lower()
    len_str = len(str_lower)

    for i in range(len_str - 2):
        if (first := str_lower[i:i + 2]) in stringdict and str_lower[i + 2] in stringdict[first]:
            # If the string is short, be more strict
            rnd += 2 if len_str <= 6 and strict else 1

    # Randomness of 2 or higher is recommended.
    return rnd


def check_aleatory(name, min_length):
    """Check if string starts with a letter followed by only digits."""
    return name[0].isalpha() and name[1:].isdigit() and len(name) > min_length


def validate_client_identifier(client, identifier, identifier_type, max_score_value, min_length) -> int:
    if (score := randomness(identifier.lower())) >= max_score_value:
        client.exit(f"Please provide a valid {identifier_type}")
        IRCD.send_snomask(client, 's', f"*** Randomness match for {client.name}[{client.ip}] with score {score} (/{identifier_type})")
        return 0

    if check_aleatory(identifier, min_length):
        client.exit(f"Please provide a valid {identifier_type}")
        IRCD.send_snomask(client, 's', f"*** Aleatory {identifier_type} match for {client.name}[{client.ip}]")
        return 0

    return 1


def antirandom_check(client) -> Hook:
    if client.name and not validate_client_identifier(client, client.name, "nick", max_score, 3):
        return Hook.DENY

    if client.user.username and not validate_client_identifier(client, client.user.username, "ident", max_score + 1, 4):
        return Hook.DENY

    return Hook.CONTINUE


def init(module):
    Hook.add(Hook.PRE_CONNECT, antirandom_check)
