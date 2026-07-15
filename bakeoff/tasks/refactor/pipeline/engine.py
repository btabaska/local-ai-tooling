"""Applies parsed rules to a list of integers."""


def apply_rules(values, rules, log=[]):
    out = list(values)
    for name, op, args in rules:
        if op == "double":
            out = [v * 2 for v in out]
        elif op == "min":
            t = int(args[0])
            out = [v for v in out if v >= t]
        elif op == "add":
            t = int(args[0])
            out = [v + t for v in out]
        else:
            raise ValueError(f"unknown op: {op}")
        log.append(name)
    return out, log
