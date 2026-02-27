"""Tests for the 3-layer ontology loader with V3 version support."""

from app.core.ontology_loader import OntologyLoader


class TestOntologyVersion:
    def test_core_has_version(self):
        loader = OntologyLoader.from_layers()
        assert loader.version is not None
        assert loader.version.startswith("3.")

    def test_combined_version_string(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        assert "3.0.0" in loader.version

    def test_layer_names(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        assert loader.active_layer_names == ["core", "genre", "series"]

    def test_layer_names_without_series(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        assert loader.active_layer_names == ["core", "genre"]


class TestOntologySchemaExport:
    def test_get_types_for_core_layer(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        core_types = loader.get_node_types_for_layer("core")
        assert "Character" in core_types
        assert "Event" in core_types
        assert "Location" in core_types
        # Genre types should NOT be in core
        assert "Skill" not in core_types

    def test_get_types_for_genre_layer(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        genre_types = loader.get_node_types_for_layer("genre")
        assert "Skill" in genre_types
        assert "Class" in genre_types
        # Core types should NOT be in genre
        assert "Character" not in genre_types

    def test_get_types_for_series_layer(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        series_types = loader.get_node_types_for_layer("series")
        assert "Bloodline" in series_types
        assert "PrimordialChurch" in series_types

    def test_to_json_schema(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        schema = loader.to_json_schema(["Character", "Event"])
        assert "Character" in schema
        assert "properties" in schema["Character"]
        assert "name" in schema["Character"]["properties"]
        assert "Event" in schema
        assert "event_type" in schema["Event"]["properties"]

    def test_to_json_schema_includes_enum_values(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        schema = loader.to_json_schema(["Character"])
        role_prop = schema["Character"]["properties"]["role"]
        assert "values" in role_prop
        assert "protagonist" in role_prop["values"]

    def test_to_json_schema_all_types(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        schema = loader.to_json_schema()  # None = all
        assert len(schema) == len(loader.node_types)

    def test_new_entity_types_loaded(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        all_types = loader.get_all_node_types()
        assert "StatBlock" in all_types
        assert "QuestObjective" in all_types
        assert "Achievement" in all_types
        assert "Realm" in all_types


class TestRegexPatternsFromYaml:
    def test_loads_genre_regex(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        patterns = loader.get_regex_patterns_list()
        names = {p["name"] for p in patterns}
        assert "skill_acquired" in names
        assert "skill_evolved" in names
        assert "xp_gain" in names
        assert "quest_received" in names

    def test_loads_series_regex(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        patterns = loader.get_regex_patterns_list()
        names = {p["name"] for p in patterns}
        assert "bloodline_notification" in names
        assert "profession_obtained" in names

    def test_regex_pattern_count(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        patterns = loader.get_regex_patterns_list()
        assert len(patterns) >= 25  # 20 genre + 5 series

    def test_regex_patterns_have_layer_info(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        patterns = loader.get_regex_patterns_list()
        genre_patterns = [p for p in patterns if p["layer"] == "litrpg"]
        series_patterns = [p for p in patterns if p["layer"] == "primal_hunter"]
        assert len(genre_patterns) >= 20
        assert len(series_patterns) >= 5

    def test_regex_pattern_structure(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        patterns = loader.get_regex_patterns_list()
        for p in patterns:
            assert "name" in p
            assert "pattern" in p
            assert "entity_type" in p
            assert "captures" in p
            assert "layer" in p


class TestBackwardCompatibility:
    def test_existing_regex_patterns_dict_still_works(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        # The old dict-based access still works
        assert "skill_acquired" in loader.regex_patterns
        assert "pattern" in loader.regex_patterns["skill_acquired"]

    def test_get_node_type_names_still_works(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        names = loader.get_node_type_names()
        assert "Character" in names
        assert "Skill" in names

    def test_validate_entity_still_works(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        errors = loader.validate_entity(
            "Character",
            {"name": "Jake", "canonical_name": "jake thayne", "role": "protagonist"},
        )
        assert len(errors) == 0

    def test_enum_constraints_still_populated(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        assert "Character" in loader.enum_constraints
        assert "role" in loader.enum_constraints["Character"]
