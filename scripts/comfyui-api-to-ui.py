#!/usr/bin/env python3
"""Convert a ComfyUI API-format workflow ({"prompt": {node-map}} or bare node-map)
into UI/graph format so it opens cleanly from the web UI's Workflows sidebar.

Usage (on rig): python3 comfyui-api-to-ui.py in.api.json out.json ["Workflow title"]

Widget order and connection slots are derived from the live /object_info, so the
output matches this ComfyUI build exactly. Layout = topological columns.
"""
import json, sys, urllib.request

OBJECT_INFO_URL = "http://localhost:8188/object_info"
WIDGET_PRIMS = {"INT", "FLOAT", "STRING", "BOOLEAN"}


def load_object_info():
    return json.loads(urllib.request.urlopen(OBJECT_INFO_URL, timeout=30).read())


def classify_inputs(spec):
    """Return ordered [(name, kind, meta)] where kind is 'widget' or 'conn'."""
    out = []
    for section in ("required", "optional"):
        for name, s in (spec.get("input", {}).get(section) or {}).items():
            t = s[0]
            meta = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
            if isinstance(t, list) or t == "COMBO":  # enum/combo (old + new spec shapes)
                out.append((name, "widget", meta, "COMBO"))
            elif isinstance(t, str) and t in WIDGET_PRIMS:
                out.append((name, "widget", meta, t))
            else:
                out.append((name, "conn", meta, t))
    return out


def main(src, dst, title):
    oi = load_object_info()
    raw = json.load(open(src))
    graph = raw.get("prompt", raw)

    # topological depth for column layout
    depth = {}
    def calc_depth(nid, seen=()):
        if nid in depth:
            return depth[nid]
        if nid in seen:
            return 0
        d = 0
        for v in graph[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and str(v[0]) in graph:
                d = max(d, calc_depth(str(v[0]), seen + (nid,)) + 1)
        depth[nid] = d
        return d
    for nid in graph:
        calc_depth(nid)

    cols = {}
    nodes, links = [], []
    link_id = 0
    conn_slots = {}   # nid -> {input_name: slot_index}
    out_links = {}    # (from_nid, from_slot) -> [link ids]

    ordered = sorted(graph, key=lambda n: (depth[n], int(n) if n.isdigit() else 0))
    for nid in ordered:
        cls = graph[nid]["class_type"]
        spec = oi[cls]
        ins = classify_inputs(spec)
        conn_slots[nid] = {n: i for i, (n, k, _, _) in
                           enumerate([x for x in ins if x[1] == "conn"])}

    for nid in ordered:
        node = graph[nid]
        cls = node["class_type"]
        spec = oi[cls]
        ins = classify_inputs(spec)

        widgets = []
        ui_inputs = []
        for name, kind, meta, t in ins:
            if kind == "conn":
                ui_inputs.append({"name": name, "type": t, "link": None})
            else:
                v = node["inputs"].get(name, meta.get("default"))
                widgets.append(v)
                if meta.get("control_after_generate") or name in ("seed", "noise_seed"):
                    widgets.append("randomize")
        if cls == "LoadImage":
            widgets.append("image")

        out_names = spec.get("output_name") or spec.get("output") or []
        out_types = spec.get("output") or []
        ui_outputs = [{"name": str(out_names[i]), "type": str(out_types[i]),
                       "links": [], "slot_index": i} for i in range(len(out_types))]

        col = depth[nid]
        row = cols.get(col, 0)
        cols[col] = row + 1
        nodes.append({
            "id": int(nid), "type": cls,
            "pos": [80 + col * 400, 80 + row * 260],
            "size": [340, max(90, 34 + 24 * len(ui_inputs) + 28 * len(widgets))],
            "flags": {}, "order": ordered.index(nid), "mode": 0,
            "inputs": ui_inputs, "outputs": ui_outputs,
            "properties": {"Node name for S&R": cls},
            "widgets_values": widgets,
        })

    node_by_id = {n["id"]: n for n in nodes}
    for nid in ordered:
        for name, v in graph[nid]["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and str(v[0]) in graph:
                link_id += 1
                frm, fslot = int(v[0]), int(v[1])
                tslot = conn_slots[nid][name]
                ftype = node_by_id[frm]["outputs"][fslot]["type"]
                links.append([link_id, frm, fslot, int(nid), tslot, ftype])
                node_by_id[int(nid)]["inputs"][tslot]["link"] = link_id
                node_by_id[frm]["outputs"][fslot]["links"].append(link_id)

    ui = {
        "last_node_id": max(n["id"] for n in nodes),
        "last_link_id": link_id,
        "nodes": nodes, "links": links,
        "groups": [], "config": {},
        "extra": {"workflow_title": title},
        "version": 0.4,
    }
    json.dump(ui, open(dst, "w"), indent=1)
    print(f"wrote {dst}: {len(nodes)} nodes, {link_id} links")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "workflow")
