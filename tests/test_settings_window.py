from dettato.settings_window import format_replacements, parse_replacements


def test_parse_replacements_accepts_equals_and_arrow_and_skips_junk():
    text = "meta ed = Meta Ads\ncostruisci e arreda -> Costruisci & Arreda\nriga senza separatore\n = vuoto\n"
    assert parse_replacements(text) == {
        "meta ed": "Meta Ads",
        "costruisci e arreda": "Costruisci & Arreda",
    }


def test_format_then_parse_roundtrips():
    data = {"meta ed": "Meta Ads", "a": "B"}
    assert parse_replacements(format_replacements(data)) == data
