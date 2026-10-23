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


def unit_record(unit):
    if unit is None:
        return None
    ci = getattr(unit, "creation_info", None)
    cbi = getattr(unit, "combat_info", None)
    ti = getattr(unit, "task_info", None)
    ai = getattr(unit, "animation_info", None)
    costs = [[c.resource_id, c.quantity]
             for c in (getattr(ci, "costs", None) or [])
             if c.resource_id >= 0 and c.quantity]
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


def effect_record(index, effect):
    commands = [[c.type, c.a, c.b, c.c, round(float(c.d), 6)]
                for c in (getattr(effect, "effects", None) or [])]
    return {"id": index, "name": dname(getattr(effect, "name", None)), "commands": commands}


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
