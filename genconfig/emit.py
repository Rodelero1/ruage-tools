"""TOML emission for generated game data. Pure functions: no dat access, no file I/O."""

PRECISION = 6


def toml_float(value):
    v = float(value)
    rounded = round(v, PRECISION)
    if v != 0.0 and rounded == 0.0:
        raise ValueError(
            f"{v!r} is smaller than the {PRECISION}-decimal precision of the config format; "
            "refusing to silently round a real value to zero"
        )
    text = f"{rounded:.{PRECISION}f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def toml_str(value):
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{text}"'


def _pairs(pairs):
    return "[" + ", ".join(f"[{int(a)}, {int(b)}]" for a, b in pairs) + "]"


def _ints(values):
    return "[" + ", ".join(str(int(v)) for v in values) + "]"


def _floats(values):
    return "[" + ", ".join(toml_float(v) for v in values) + "]"


def _header(meta):
    return [
        "# GENERATED FILE — do not edit.",
        f"# source: {meta['source']}",
        f"# source_sha256: {meta['source_sha256']}",
        f"# generated: {meta.get('generated', '')}",
        "# regenerate: tools/genconfig (test-first, see SPEC §11)",
        "# Edit config/overrides.toml instead; these files are overwritten.",
        "",
    ]


def render_units(records, meta):
    lines = _header(meta)
    lines += ["schema = 1", 'kind = "units"',
              f"civ = {meta['civ']}", f"civ_name = {toml_str(meta['civ_name'])}", ""]
    for r in records:
        lines += [
            "[[unit]]",
            f"id = {r['id']}",
            f"name = {toml_str(r['name'])}",
            f"class = {r['class']}",
            f"hp = {r['hp']}",
            f"los = {toml_float(r['los'])}",
            f"speed = {toml_float(r['speed'])}",
            f"carry = {r['carry']}",
            f"work_rate = {toml_float(r['work_rate'])}",
            f"drop_sites = {_ints(r['drop_sites'])}",
            f"garrison = {r['garrison']}",
            f"radius = {_floats(r['radius'])}",
            f"costs = {_pairs(r['costs'])}",
            f"attacks = {_pairs(r['attacks'])}",
            f"armours = {_pairs(r['armours'])}",
            f"range = {toml_float(r['range'])}",
            f"reload = {toml_float(r['reload'])}",
            f"accuracy = {r['accuracy']}",
            f"train_time = {r['train_time']}",
            f"base_id = {r['base_id']}",
            *([f"variant_of = {r['variant_of']}"] if r.get("variant_of") else []),
            "",
        ]
    return "\n".join(lines)


def _commands(cmds):
    def fmt(cmd):
        parts = [toml_float(v) if isinstance(v, float) else str(int(v)) for v in cmd]
        return "[" + ", ".join(parts) + "]"
    return "[" + ", ".join(fmt(c) for c in cmds) + "]"


def _modifiers(modifiers):
    if not modifiers:
        return "[]"
    parts = [
        "{ op = %s, attribute = %s, attribute_class = %d, unit = %d, unit_class = %d, value = %s }"
        % (toml_str(m["op"]), toml_str(m["attribute"]), int(m["attribute_class"]),
           int(m["unit"]), int(m["unit_class"]), toml_float(m["value"]))
        for m in modifiers
    ]
    return "[" + ", ".join(parts) + "]"


def _resource_modifiers(modifiers):
    if not modifiers:
        return "[]"
    parts = [
        "{ resource = %d, mode = %d, value = %s }"
        % (int(m["resource"]), int(m["mode"]), toml_float(m["value"]))
        for m in modifiers
    ]
    return "[" + ", ".join(parts) + "]"


def render_effects(records, meta):
    lines = _header(meta) + ["schema = 1", 'kind = "effects"', ""]
    for r in records:
        lines += ["[[effect]]", f"id = {r['id']}", f"name = {toml_str(r['name'])}",
                  f"commands = {_commands(r['commands'])}",
                  f"modifiers = {_modifiers(r.get('modifiers', []))}",
                  f"resource_modifiers = {_resource_modifiers(r.get('resource_modifiers', []))}",
                  ""]
    return "\n".join(lines)


def render_techs(records, meta):
    lines = _header(meta) + ["schema = 1", 'kind = "techs"', ""]
    for r in records:
        lines += ["[[tech]]", f"id = {r['id']}", f"effect_id = {r['effect_id']}",
                  f"research_time = {r['research_time']}",
                  f"costs = {_pairs(r['costs'])}",
                  f"required = [" + ", ".join(str(int(x)) for x in r["required"]) + "]",
                  f"min_required = {r['min_required']}",
                  f"location = {r['location']}", ""]
    return "\n".join(lines)


def render_civs(records, meta):
    lines = _header(meta) + ["schema = 1", 'kind = "civs"', ""]
    for r in records:
        lines += ["[[civ]]", f"id = {r['id']}", f"name = {toml_str(r['name'])}",
                  f"tech_tree_effect = {r['tech_tree_effect']}",
                  f"team_bonus_effect = {r['team_bonus_effect']}",
                  f"resources = {_floats(r['resources'])}", ""]
    return "\n".join(lines)


def render_manifest(meta, counts, files):
    lines = [
        "# GENERATED — provenance and counts for config/gamedata/.",
        f"generated = {toml_str(meta.get('generated', ''))}",
        f"source_file = {toml_str(meta['source'])}",
        f"source_sha256 = {toml_str(meta['source_sha256'])}",
        "",
        "[counts]",
    ]
    for key, value in counts.items():
        lines.append(f"{key} = {value}")
    lines += ["", "[files]"]
    for key, info in files.items():
        lines.append(
            f'{key} = {{ path = {toml_str(info["path"])}, bytes = {info["bytes"]}, '
            f'sha256 = {toml_str(info["sha256"])} }}'
        )
    return "\n".join(lines) + "\n"
