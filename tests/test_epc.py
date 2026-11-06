from hebra import epc


def test_urn_a_gtin_amb_digit_de_control():
    s = epc.descodifica("urn:epc:id:sgtin:8400000.012345.100001")
    assert s.gtin == "08400000123457"
    assert s.serie == "100001"


def test_hex_sgtin96():
    # Exemple de l'estàndard GS1 TDS: urn:epc:id:sgtin:0614141.812345.6789
    s = epc.descodifica("3074257BF7194E4000001A85")
    assert s.urn == "urn:epc:id:sgtin:0614141.812345.6789"
    assert s.gtin == "80614141123458"


def test_epc_no_sgtin_es_retorna_tal_qual():
    assert epc.normalitza("e280 1160") == "E280 1160"
