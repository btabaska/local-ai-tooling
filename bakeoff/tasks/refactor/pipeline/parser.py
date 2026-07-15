"""Rule parser for the mini pipeline.

Rule syntax (one rule per line):
    <name>: <op>[<args>]
e.g.
    strip_ws: map[strip]
    keep_big: filter[min=10]
Args inside [] are comma-separated; commas inside nested brackets belong
to the nested group, e.g. compose[a[1,2],b] has args 'a[1,2]' and 'b'.
"""


def split_args(s):
    return [p.strip() for p in s.split(",") if p.strip()]


def parse_rules(text):
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, spec = line.partition(":")
        spec = spec.strip()
        op, _, rest = spec.partition("[")
        args = split_args(rest[:-1]) if rest.endswith("]") else []
        rules.append((name.strip(), op.strip(), args))
    return rules
