from dettato.postprocess import clean_transcript


def test_removes_simple_filler_word():
    result = clean_transcript("Allora ehm andiamo avanti", ["ehm"])
    assert result == "Allora andiamo avanti"


def test_removes_multiple_filler_occurrences():
    result = clean_transcript("ehm quindi ehm il punto è questo", ["ehm"])
    assert result == "quindi il punto è questo"


def test_case_insensitive_removal():
    result = clean_transcript("Ehm certo", ["ehm"])
    assert result == "certo"


def test_removes_repeated_phrase_filler():
    result = clean_transcript("Cioè cioè il punto è che funziona", ["cioè cioè"])
    assert result == "il punto è che funziona"


def test_normalizes_multiple_spaces():
    result = clean_transcript("ciao    come   va", [])
    assert result == "ciao come va"


def test_empty_string_returns_empty():
    assert clean_transcript("", ["ehm"]) == ""


def test_fixes_space_before_punctuation():
    result = clean_transcript("ciao , come va ?", [])
    assert result == "ciao, come va?"


def test_replacements_fix_recurring_mistakes_case_insensitively():
    result = clean_transcript("Ho lanciato la campagna su Meta ed oggi", [], {"meta ed": "Meta Ads"})
    assert result == "Ho lanciato la campagna su Meta Ads oggi"


def test_replacements_match_whole_words_only():
    assert clean_transcript("metadati", [], {"meta": "Meta"}) == "metadati"


def test_longer_replacement_wins_over_its_prefix():
    result = clean_transcript("meta ed e meta", [], {"meta": "Meta", "meta ed": "Meta Ads"})
    assert result == "Meta Ads e Meta"
