"""Turn dat objects into plain records. Duck-typed so tests can use stubs."""


def dname(value):
    """Dat names arrive as char-code sequences (sometimes NUL-terminated) or str."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\x00", "")
    out = []
    for c in value:
        if isinstance(c, str):
            out.append(c)
        elif c:
            out.append(chr(int(c)))
    return "".join(out).replace("\x00", "")


def _f(value, nd=6):
    return round(float(value), nd)


# The dat's cost list carries a pseudo-resource that is not in the stockpile: id 4 is population
# (a spearman costs 35 food, 25 wood and 1 pop). `costs` in the pack means *stockpile* costs - the
# simulation charges each one from a stockpile column the pack names, and refuses an id the pack
# does not price rather than paying from another slot - so emitting 4 here makes every unit
# untrainable. Population is AoE2 semantics, which belong to this importer (D17); when the
# simulation grows a cap it becomes a named field of its own, not a stockpile pair.
POPULATION_RESOURCE_ID = 4


def unit_record(unit):
    if unit is None:
        return None
    ci = getattr(unit, "creation_info", None)
    cbi = getattr(unit, "combat_info", None)
    ti = getattr(unit, "task_info", None)
    ai = getattr(unit, "animation_info", None)
    costs = [[c.resource_id, c.quantity]
             for c in (getattr(ci, "costs", None) or [])
             if c.resource_id >= 0 and c.quantity
             and c.resource_id != POPULATION_RESOURCE_ID]
    trains = [t.train_time for t in (getattr(ci, "train_locations", None) or []) if getattr(t, "train_time", None)]
    return {
        "id": unit.id,
        "name": dname(getattr(unit, "name", None)),
        "class": unit.class_,
        "hp": unit.hit_points,
        "los": _f(unit.line_of_sight),
        "speed": _f(getattr(ai, "speed", 0.0)),   # dat stores movement speed here (naming wart)
        "carry": unit.resource_carry_capacity,
        "work_rate": _f(getattr(ti, "work_rate", 0.0)),
        # D11: drop-off buildings belong to the task VARIANT, not to the base villager.
        "drop_sites": [int(x) for x in (getattr(ti, "drop_site_unit_ids", None) or [])
                       if x and x > 0],
        "garrison": unit.garrison_capacity,
        "radius": [_f(unit.radius_x), _f(unit.radius_y), _f(unit.radius_z)],
        "costs": costs,
        "attacks": [[a.id, a.amount] for a in (getattr(cbi, "attacks", None) or [])],
        "armours": [[a.id, a.amount] for a in (getattr(cbi, "armors", None) or [])],
        "range": _f(getattr(cbi, "max_range", 0.0)),
        "reload": _f(getattr(cbi, "displayed_reload_time", 0.0)),
        "accuracy": getattr(cbi, "accuracy_percent", 0),
        "train_time": trains[0] if trains else 0,
        "base_id": getattr(unit, "base_id", -1),
    }


def variant_map(effect_records):
    """Unit id -> the unit it is an upgraded variant of, read out of the effects table's kind-3 commands.

    An age-up does not improve a building in place: it replaces the unit id (town centre 109 -> 71,
    barracks 12 -> 498, blacksmith 103 -> 105). The engine has to keep treating the two as the same
    building - a villager still drops wood at an upgraded town centre, and a barracks still trains
    spearmen - so the variant has to say what it came from. The dat's own `base_id` is useless here
    (it points at itself), and this relation exists only in the effects table, which makes deriving it
    the importer's job (D17).

    When two different units upgrade into the same one - the data really does this, 87 and 132 both
    upgrade into 10 - the lowest source wins, so the answer is stable between runs.
    """
    parents = {}
    for effect in effect_records:
        for command in effect.get("commands", []):
            kind, source, target = command[0], int(command[1]), int(command[2])
            if kind != 3 or source <= 0 or target <= 0 or source == target:
                continue
            if target not in parents or source < parents[target]:
                parents[target] = source
    return parents


# Attribute ids, as far as the techs that use them show. 0 is hit points (Loom adds 15, Masonry
# multiplies by 1.1), 1 range, 5 speed, 8 armour, 9 attack, 13 gather rate, 14 carry. Anything else
# is emitted as `other:<id>` rather than guessed.
ATTRIBUTE_NAMES = {
    0: "hit_points",
    1: "range",
    5: "speed",
    8: "armour",
    9: "attack",
    13: "gather_rate",
    14: "carry",
}

# Attack and armour are **packed**: the value is `class * 256 + amount`, so Forging's 1025 is class 4
# plus 1. That is a fact about the dat's encoding, so it is decoded here, in the importer (D17), and
# the engine receives `attribute = "attack", attribute_class = 4, value = 1`.
PACKED_ATTRIBUTES = {8, 9}


def _modifier(command):
    """One `[kind, a, b, c, value]` command as a decoded modifier, or None when it is not one."""
    kind, a, b, c, d = command
    if kind not in (4, 5):
        return None
    op = "add" if kind == 4 else "multiply"
    attribute = ATTRIBUTE_NAMES.get(c, f"other:{c}")
    attribute_class = -1
    value = float(d)
    if c in PACKED_ATTRIBUTES:
        # Only additions are packed in this data. A kind-5 command on attack or armour carries a
        # number that is neither a multiplier nor a clean packed pair (2936, -136 ...), so it is
        # named `unpacked:` rather than given an invented sign or packing rule (U17).
        packed = int(d)
        if kind == 4 and packed >= 0 and packed // 256 >= 0:
            attribute_class = packed // 256
            value = float(packed % 256)
        else:
            attribute = f"unpacked:{c}"
    return {
        "op": op,
        "attribute": attribute,
        "attribute_class": attribute_class,
        "unit": int(a),
        "unit_class": int(b),
        "value": value,
    }


def effect_record(index, effect):
    raw = [[c.type, c.a, c.b, c.c, round(float(c.d), 6)]
           for c in (getattr(effect, "effects", None) or [])]
    modifiers = [m for m in (_modifier(command) for command in raw) if m is not None]
    return {
        "id": index,
        "name": dname(getattr(effect, "name", None)),
        "commands": raw,
        "modifiers": modifiers,
    }


def tech_record(index, tech):
    costs = [[c.resource_id, c.quantity] for c in (getattr(tech, "costs", None) or [])
             if c.resource_id >= 0 and c.quantity]
    required = [x for x in (getattr(tech, "required_tech_ids", None) or []) if x and x > 0]
    return {
        "id": index,
        "effect_id": getattr(tech, "effect_id", -1),
        "research_time": getattr(tech, "research_time", 0),
        "costs": costs,
        "required": required,
        "location": getattr(tech, "location_unit_id", -1),
    }


def civ_record(index, civ):
    return {
        "id": index,
        "name": dname(getattr(civ, "_name_aoe2_swgb", None)),
        "tech_tree_effect": getattr(civ, "tech_tree_effect_id", -1),
        "team_bonus_effect": getattr(civ, "team_bonus_effect_id", -1),
        "resources": [_f(x) for x in (getattr(civ, "resources", None) or [])],
    }
