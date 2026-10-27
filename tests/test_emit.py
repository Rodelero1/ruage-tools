"""Behaviour tests for TOML emission. Written before the implementation (D7)."""

from genconfig.emit import (toml_float, toml_str, render_units, render_effects,
                            render_civs, render_techs, render_manifest)
from genconfig.records import dname, unit_record, effect_record, tech_record, civ_record


def test_toml_float_strips_f32_noise_but_keeps_a_decimal_point():
    # The dat stores 0.8 as the f32 0.800000011920929; the config must say 0.8.
    assert toml_float(0.800000011920929) == "0.8"


def test_toml_float_renders_whole_numbers_with_a_decimal_point():
    # TOML distinguishes 1 (integer) from 1.0 (float); the config needs floats.
    assert toml_float(1.0) == "1.0"


def test_toml_float_refuses_values_below_its_precision():
    # 1e-7 would silently become 0.0 at 6dp. Silently zeroing a real value is a data bug,
    # so the formatter must refuse instead of lying.
    import pytest

    with pytest.raises(ValueError):
        toml_float(0.0000001)


def test_toml_str_escapes_quotes_and_backslashes():
    assert toml_str('Udayadityavarman\'s "Army"') == '"Udayadityavarman\'s \\"Army\\""'


def test_dname_decodes_byte_array_names_and_strips_nul():
    # The parser hands back names as sequences of char codes, NUL-terminated.
    assert dname([86, 77, 66, 65, 83, 0]) == "VMBAS"
    assert dname("ARCHR\x00") == "ARCHR"
    assert dname(["A", "R", "C", "H", "R", 0]) == "ARCHR"
    assert dname(None) == ""


def _stub_unit(**over):
    """Minimal duck-typed stand-in for a parsed dat unit."""
    from types import SimpleNamespace as NS
    base = dict(
        id=38, name=[75, 78, 71, 72, 84, 0], class_=12, hit_points=100,
        line_of_sight=4.0, resource_carry_capacity=0, garrison_capacity=0,
        radius_x=0.2, radius_y=0.2, radius_z=0.0, base_id=-1,
        animation_info=NS(speed=1.350000023841858),
        task_info=NS(work_rate=0.0),
        combat_info=NS(
            attacks=[NS(id=4, amount=10), NS(id=15, amount=0)],
            armors=[NS(id=4, amount=2), NS(id=3, amount=2)],
            max_range=0.0, displayed_reload_time=1.7999999523162842, accuracy_percent=100,
        ),
        creation_info=NS(
            costs=[NS(resource_id=-1, quantity=0), NS(resource_id=0, quantity=60),
                   NS(resource_id=3, quantity=75), NS(resource_id=4, quantity=1)],
            train_locations=[NS(train_time=30)],
        ),
    )
    base.update(over)
    return NS(**base)


def test_unit_record_extracts_and_cleans_dat_fields():
    rec = unit_record(_stub_unit())
    assert rec["id"] == 38
    assert rec["name"] == "KNGHT"
    assert rec["hp"] == 100
    # f32 noise must be gone by the time it is a record value
    assert rec["speed"] == 1.35
    assert rec["reload"] == 1.8
    assert rec["attacks"] == [[4, 10], [15, 0]]
    assert rec["armours"] == [[4, 2], [3, 2]]
    assert rec["train_time"] == 30
    # the -1 "no cost" slot is dropped; real stockpile slots survive as pairs. Resource 4 is
    # population, not a stockpile column, so it is not a cost (see the named test below).
    assert rec["costs"] == [[0, 60], [3, 75]]


def test_population_is_not_a_stockpile_cost():
    """Resource 4 is population: a knight costs 1 pop, not 1 of anything banked.

    The simulation charges a cost from a stockpile column named by the content pack, and it
    refuses an id the pack does not price rather than paying from another slot. Emitting the
    population pair as a cost therefore made every unit untrainable once the pack became the
    authority. Population is AoE2 semantics, which belong to this importer (D17); when the
    simulation grows a cap it becomes a named field, not a stockpile pair.
    """
    rec = unit_record(_stub_unit())
    assert [resource for resource, _ in rec["costs"]] == [0, 3], rec["costs"]


def test_unit_record_passes_through_a_missing_unit():
    assert unit_record(None) is None


def test_effect_record_keeps_multipliers_numeric():
    # Regression: an earlier generator emitted d=1.2 as the STRING "1.2", which TOML accepts
    # as a string and the engine then silently ignored.
    from types import SimpleNamespace as NS
    eff = NS(id=195, name="Double-Bit Axe", effects=[
        NS(type=5, a=218, b=-1, c=13, d=1.2000000476837158),
        NS(type=5, a=123, b=-1, c=13, d=1.2000000476837158),
    ])
    rec = effect_record(195, eff)
    assert rec["id"] == 195
    assert rec["commands"] == [[5, 218, -1, 13, 1.2], [5, 123, -1, 13, 1.2]]
    assert all(isinstance(cmd[4], float) for cmd in rec["commands"])


def test_unit_record_carries_drop_sites_per_variant():
    # D11: gathering needs the drop-off list of the *variant* (lumberjack -> lumber camp 562,
    # miner -> mining camp 584). The base villager lists only town centre + mill, which is why
    # looking them up on VMBAS gives the wrong answer.
    from types import SimpleNamespace as NS

    rec = unit_record(_stub_unit(task_info=NS(work_rate=0.39, drop_site_unit_ids=[562, 0, -1])))
    assert rec is not None
    assert rec["drop_sites"] == [562], "zero and -1 slots are not drop sites"

    rec = unit_record(_stub_unit(task_info=NS(work_rate=0.53)))
    assert rec is not None
    assert rec["drop_sites"] == [], "a variant with no drop sites must emit an empty list"


def test_render_units_emits_drop_sites():
    meta = {"source": "d.dat", "source_sha256": "x", "civ": 1, "civ_name": "British"}
    rec = {"id": 123, "name": "VMLUM", "class": 4, "hp": 25, "los": 4.0, "speed": 0.8,
           "carry": 10, "work_rate": 0.39, "garrison": 0, "radius": [0.2, 0.2, 0.0],
           "costs": [], "attacks": [], "armours": [], "range": 0.0, "reload": 0.0,
           "accuracy": 0, "train_time": 0, "base_id": -1, "drop_sites": [562]}
    text = render_units([rec], meta)
    assert "drop_sites = [562]" in text, text


def test_render_units_emits_generated_header_and_one_table_per_unit():
    meta = {"source": "empires2_x2_p1.dat", "source_sha256": "abc123", "civ": 1, "civ_name": "British"}
    rec = {"id": 38, "name": "KNGHT", "class": 12, "hp": 100, "los": 4.0, "speed": 1.35,
           "carry": 0, "work_rate": 0.0, "garrison": 0, "radius": [0.2, 0.2, 0.0],
           "costs": [[0, 60], [3, 75]], "attacks": [[4, 10]], "armours": [[4, 2]],
           "range": 0.0, "reload": 1.8, "accuracy": 100, "train_time": 30, "base_id": -1,
           "drop_sites": []}
    text = render_units([rec], meta)
    assert "GENERATED FILE" in text and "do not edit" in text
    assert "source_sha256: abc123" in text
    assert text.count("[[unit]]") == 1
    for expected in ('id = 38', 'name = "KNGHT"', 'hp = 100', 'speed = 1.35',
                     'costs = [[0, 60], [3, 75]]', 'attacks = [[4, 10]]', 'train_time = 30'):
        assert expected in text, expected


def test_render_effects_keeps_command_values_typed():
    meta = {"source": "d.dat", "source_sha256": "x"}
    rec = {"id": 195, "name": "Double-Bit Axe", "commands": [[5, 218, -1, 13, 1.2]]}
    text = render_effects([rec], meta)
    assert "commands = [[5, 218, -1, 13, 1.2]]" in text
    # no quoted numbers anywhere in a command list
    assert '"1.2"' not in text


def test_render_civs_writes_float_arrays_and_ids():
    meta = {"source": "d.dat", "source_sha256": "x"}
    rec = {"id": 1, "name": "British", "tech_tree_effect": 102, "team_bonus_effect": 0,
           "resources": [0.0, 1.600000023841858, 32000.0]}
    text = render_civs([rec], meta)
    assert "[[civ]]" in text
    assert 'name = "British"' in text
    assert "resources = [0.0, 1.6, 32000.0]" in text


def test_render_techs_emits_costs_and_prerequisites():
    meta = {"source": "d.dat", "source_sha256": "x"}
    rec = {"id": 202, "effect_id": 195, "research_time": 25,
           "costs": [[0, 100], [1, 50]], "required": [101, 199], "location": 109}
    text = render_techs([rec], meta)
    assert "id = 202" in text
    assert "costs = [[0, 100], [1, 50]]" in text
    assert "required = [101, 199]" in text
    assert "location = 109" in text


def test_render_manifest_records_hash_counts_and_per_file_digests():
    meta = {"source": "empires2_x2_p1.dat", "source_sha256": "deadbeef", "generated": "2026-10-23T00:00:00Z"}
    counts = {"units": 1166, "techs": 801, "effects": 798, "civs": 32}
    files = {"units": {"path": "gamedata/units.toml", "bytes": 324023, "sha256": "aa11"}}
    text = render_manifest(meta, counts, files)
    assert 'source_sha256 = "deadbeef"' in text
    assert "units = 1166" in text
    assert 'path = "gamedata/units.toml"' in text
    assert 'sha256 = "aa11"' in text


def test_tech_record_normalises_costs_and_prerequisites():
    from types import SimpleNamespace as NS
    tech = NS(effect_id=195, research_time=25,
              costs=[NS(resource_id=0, quantity=100), NS(resource_id=1, quantity=50),
                     NS(resource_id=-1, quantity=0)],
              required_tech_ids=[101, 0, 199, -1], location_unit_id=109)
    rec = tech_record(202, tech)
    assert rec["id"] == 202 and rec["effect_id"] == 195 and rec["research_time"] == 25
    assert rec["costs"] == [[0, 100], [1, 50]]
    assert rec["required"] == [101, 199]
    assert rec["location"] == 109


def test_civ_record_carries_resources_and_effect_ids():
    from types import SimpleNamespace as NS
    civ = NS(resources=[0.0, 1.600000023841858], tech_tree_effect_id=102,
             team_bonus_effect_id=0, _name_aoe2_swgb=[66, 114, 105, 116, 105, 115, 104, 0])
    rec = civ_record(1, civ)
    assert rec["id"] == 1 and rec["name"] == "British"
    assert rec["resources"] == [0.0, 1.6]
    assert rec["tech_tree_effect"] == 102


def test_effect_record_decodes_packed_attack_and_armour():
    # The dat packs an attack/armour change as `class * 256 + amount`, so Forging's 1025 is class 4
    # plus 1. That is a fact about the *format*, so it is decoded here, in the importer (D17): the
    # engine receives `attribute = "attack", attribute_class = 4, value = 1` and never sees 1025.
    from types import SimpleNamespace as NS
    eff = NS(id=67, name="Forging", effects=[
        NS(type=4, a=-1, b=6, c=9, d=1025.0),
        NS(type=5, a=-1, b=3, c=0, d=1.1),
        NS(type=5, a=-1, b=4, c=13, d=1.2),
    ])
    rec = effect_record(67, eff)
    assert rec["commands"][0] == [4, -1, 6, 9, 1025.0], "the raw command is kept for the record"
    assert rec["modifiers"] == [
        {"op": "add", "attribute": "attack", "attribute_class": 4,
         "unit": -1, "unit_class": 6, "value": 1.0},
        {"op": "multiply", "attribute": "hit_points", "attribute_class": -1,
         "unit": -1, "unit_class": 3, "value": 1.1},
        # Attribute 13 is a gather rate: a plain number, not a packed pair.
        {"op": "multiply", "attribute": "gather_rate", "attribute_class": -1,
         "unit": -1, "unit_class": 4, "value": 1.2},
    ]


def test_effect_record_leaves_negative_packed_values_undecoded():
    # U17: six commands carry a *negative* packed attack (-136, -226 ...). `divmod` would read -136 as
    # class -1 / amount 120, which is an invented sign rule; the importer names them as undecoded
    # instead of guessing, and the engine sees an attribute it does not interpret.
    from types import SimpleNamespace as NS
    eff = NS(id=217, name="Non-Research", effects=[NS(type=4, a=1120, b=-1, c=8, d=-1025.0)])
    rec = effect_record(217, eff)
    assert rec["modifiers"] == [
        {"op": "add", "attribute": "unpacked:8", "attribute_class": -1,
         "unit": 1120, "unit_class": -1, "value": -1025.0},
    ]


def test_render_effects_writes_modifiers_as_inline_tables():
    meta = {"source": "d.dat", "source_sha256": "x"}
    rec = {"id": 67, "name": "Forging", "commands": [[4, -1, 6, 9, 1025.0]],
           "modifiers": [{"op": "add", "attribute": "attack", "attribute_class": 4,
                          "unit": -1, "unit_class": 6, "value": 1.0}]}
    text = render_effects([rec], meta)
    assert 'modifiers = [{ op = "add", attribute = "attack", attribute_class = 4, unit = -1, unit_class = 6, value = 1.0 }]' in text


def test_variant_map_reads_unit_upgrades_out_of_the_effect_table():
    # An age-up does not "improve" a building in place: it replaces the unit id (town centre 109 ->
    # 71, barracks 12 -> 498) with a per-age variant. The engine has to keep treating those as the
    # same building - a villager still drops wood at an upgraded town centre - so the variant has to
    # know what it was upgraded from, and the only place that relation exists is the effects table.
    from genconfig.records import variant_map

    effects = [
        {"id": 101, "commands": [[3, 109, 71, -1, 0.0], [3, 12, 498, -1, 0.0],
                                 [1, 6, 0, -1, 0.0], [4, -1, 6, 9, 1025.0]]},
        {"id": 102, "commands": [[3, 71, 141, -1, 0.0]]},
    ]
    assert variant_map(effects) == {71: 109, 498: 12, 141: 71}


def test_variant_map_keeps_a_deterministic_source_when_two_upgrades_point_at_one_unit():
    from genconfig.records import variant_map

    # Two different units are upgraded into the same one (the data really does this: 87 and 132 both
    # upgrade into 10). The engine wants one parent, so the lowest id wins - a property of the data,
    # stated once here, rather than whatever the hash map happens to yield.
    effects = [{"id": 1, "commands": [[3, 132, 10, -1, 0.0]]},
               {"id": 2, "commands": [[3, 87, 10, -1, 0.0]]}]
    assert variant_map(effects) == {10: 87}


def test_render_units_emits_variant_of_only_where_it_is_known():
    meta = {"source": "d.dat", "source_sha256": "x", "civ": 1, "civ_name": "British"}
    base = {"id": 71, "name": "RTWC2", "class": 3, "hp": 2400, "los": 8.0, "speed": 0.0,
            "carry": 0, "work_rate": 1.0, "garrison": 0, "radius": [2.5, 2.5, 0.0],
            "costs": [], "attacks": [], "armours": [], "range": 0.0, "reload": 0.0,
            "accuracy": 0, "train_time": 150, "base_id": 71, "drop_sites": []}
    text = render_units([dict(base, variant_of=109), dict(base, id=83, name="VMBAS")], meta)
    assert "variant_of = 109" in text, text
    # The unit that is nobody's variant must not carry the key at all: a -1 would be a fourth way to
    # spell "none" in a file that already has zero and -1 in the data's own fields.
    assert text.count("variant_of") == 1, text


def test_kind_1_is_decoded_as_a_resource_change_not_a_unit_one():
    """Kind 1 writes a *resource*: `a` is a resource id, `b` the mode. Reading `a` as a unit id is
    what makes Horse Collar look like it changes a bombard cannon."""
    # `effect_record` reads the dat's own attribute name: `effects`, a list of commands.
    effect = effect_record(0, type("E", (), {
        "name": "Horse Collar",
        "effects": [
            type("C", (), {"type": 1, "a": 36, "b": 1, "c": -1, "d": 75.0})(),
            type("C", (), {"type": 4, "a": 83, "b": -1, "c": 13, "d": 1.1})(),
        ],
    })())
    assert effect["resource_modifiers"] == [{"resource": 36, "mode": 1, "value": 75.0}], effect
    # And the unit-attribute decoder still ignores it: two namespaces, one command list.
    assert [m["op"] for m in effect["modifiers"]] == ["add"]
    text = render_effects([effect], {"source": "d.dat", "source_sha256": "x"})
    assert "resource_modifiers = [{ resource = 36, mode = 1, value = 75.0 }]" in text, text
