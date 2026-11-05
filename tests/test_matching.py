from app.services import sdg, vectors


def test_synonyms_bridge_vocabulary():
    a = vectors.embed("We need funding for water sensors")
    b = vectors.embed("CSR money available for sensors")
    c = vectors.embed("Volunteer doctors for health camps")
    assert vectors.cosine(a, b) > vectors.cosine(a, c)


def test_sdg_classifier_and_clean():
    assert 7 in sdg.classify("solar energy for villages")
    assert sdg.clean([0, 3, "5", 99, "x"]) == [3, 5]
