
from covis_db import covis_db

good_basenames = ["APLUWCOVISMBSONAR001_20100930T153416.845Z-DIFFUSE"]

bad_basenames = ["APLUWCOVISMBSONAR001_20141215T030021.657Z-IMAGING"]

def test_find_basenames():
    db = covis_db.CovisDB()

    for bn in good_basenames:
        results = db.find(basename=bn)
        assert results
        assert len(results) == 1

    for bn in bad_basenames:
        results = db.find(basename=bn)
        assert results == []


def test_covis_run():

    db = covis_db.CovisDB()

    results = db.find( basename=good_basenames[0])

    assert len(results) == 1

    run = results[0]

    assert run.mode() == "DIFFUSE"
