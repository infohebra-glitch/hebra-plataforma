-- Model de dades del MVP de Hebra.
-- Basat en la secció 3.6 de la "Proposta MVP abans del pilot".
-- Regla de disseny: CAP taula té camps de persona (ni nom, ni correu, ni telèfon,
-- ni identificador de dispositiu). La sessió de la fitxa NFC mai s'uneix amb la compra.
-- SQL estàndard (tipus TEXT/INTEGER/REAL) perquè es pugui portar a PostgreSQL.

-- ---------------------------------------------------------------- Instal·lació
CREATE TABLE IF NOT EXISTS botiga (
    id          TEXT PRIMARY KEY,           -- p. ex. "BCN-01"
    nom         TEXT NOT NULL,
    nivell      TEXT NOT NULL DEFAULT 'cabina' CHECK (nivell IN ('basic', 'cabina', 'experiencia')),
    zona_horaria TEXT NOT NULL DEFAULT 'Europe/Madrid'
);

CREATE TABLE IF NOT EXISTS cabina (
    id          TEXT PRIMARY KEY,           -- p. ex. "BCN-01-C1"
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    nom         TEXT NOT NULL,
    veines      TEXT NOT NULL DEFAULT ''    -- ids de cabines veïnes separats per comes
);

CREATE TABLE IF NOT EXISTS antena (
    id          TEXT PRIMARY KEY,           -- p. ex. "R700-1:1" (lector:port)
    cabina_id   TEXT NOT NULL REFERENCES cabina(id),
    port        INTEGER NOT NULL,
    llindar_rssi REAL NOT NULL DEFAULT -60  -- dBm; es calibra al pilot (setmana 0)
);

-- ---------------------------------------------------------------- Catàleg
-- Una fila per variant venible (model + color + talla = un GTIN).
CREATE TABLE IF NOT EXISTS catalog_sku (
    gtin        TEXT PRIMARY KEY,           -- GTIN-14
    model       TEXT NOT NULL,
    color       TEXT NOT NULL,
    talla       TEXT NOT NULL,
    categoria   TEXT NOT NULL,
    preu_eur    REAL,
    variant_shopify TEXT,
    origen_json TEXT                        -- fitxa d'origen (format hebra-origen/0.2) del model
);

-- Peça física: l'etiqueta doble UHF + NFC. L'EPC el llegeix el lector de la cabina;
-- el token NFC és el que porta la URL que obre el mòbil del client.
CREATE TABLE IF NOT EXISTS etiqueta (
    epc         TEXT PRIMARY KEY,           -- URN SGTIN (urn:epc:id:sgtin:...) normalitzat
    nfc_token   TEXT UNIQUE NOT NULL,
    gtin        TEXT NOT NULL REFERENCES catalog_sku(gtin)
);

-- ---------------------------------------------------------------- Sensors i lectures
CREATE TABLE IF NOT EXISTS sensor_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cabina_id   TEXT NOT NULL REFERENCES cabina(id),
    ts          TEXT NOT NULL,              -- ISO 8601 amb zona
    tipus       TEXT NOT NULL CHECK (tipus IN ('porta_tancada', 'porta_oberta', 'presencia_si', 'presencia_no'))
);

-- La passarel·la (Raspberry Pi) agrega les lectures crues en finestres curtes
-- (5-10 s) abans d'enviar-les. Retenció curta.
CREATE TABLE IF NOT EXISTS lectura_agregada (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    epc         TEXT NOT NULL,
    antena_id   TEXT NOT NULL REFERENCES antena(id),
    inici       TEXT NOT NULL,
    fi          TEXT NOT NULL,
    n_lectures  INTEGER NOT NULL,
    rssi_max    REAL NOT NULL,
    rssi_mitja  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lectura_antena_temps ON lectura_agregada(antena_id, inici);

-- ---------------------------------------------------------------- Proves
CREATE TABLE IF NOT EXISTS sessio (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cabina_id   TEXT NOT NULL REFERENCES cabina(id),
    inici       TEXT NOT NULL,
    fi          TEXT NOT NULL,
    grup        TEXT                        -- grup de control del dia ('amb' / 'sense')
);

CREATE TABLE IF NOT EXISTS prova (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sessio_id   INTEGER NOT NULL REFERENCES sessio(id),
    epc         TEXT NOT NULL,
    gtin        TEXT,                       -- NULL si l'EPC no és al catàleg
    durada_s    REAL NOT NULL,
    n_lectures  INTEGER NOT NULL,
    rssi_mitja  REAL NOT NULL,
    confianca   TEXT NOT NULL CHECK (confianca IN ('alta', 'mitjana', 'ambigua'))
);

-- ---------------------------------------------------------------- Vendes
CREATE TABLE IF NOT EXISTS venda_linia (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    ts          TEXT,                       -- NULL si el CSV només porta data
    data        TEXT NOT NULL,              -- AAAA-MM-DD
    gtin        TEXT NOT NULL,
    quantitat   INTEGER NOT NULL,           -- negativa si és devolució
    import_eur  REAL,
    tiquet_hash TEXT,                       -- id de tiquet xifrat (SHA-256), mai el tiquet en clar
    devolucio   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS atribucio (
    prova_id    INTEGER PRIMARY KEY REFERENCES prova(id),
    venda_id    INTEGER UNIQUE NOT NULL REFERENCES venda_linia(id),
    regla       TEXT NOT NULL               -- 'mateix_gtin_hora' | 'mateix_gtin_dia'
);

-- ---------------------------------------------------------------- Grup de control
-- Quin grup té cada dia per a cada experiment. Al MVP l'experiment és "origen":
-- els dies 'amb' la fitxa NFC ensenya l'origen; els dies 'sense', no.
CREATE TABLE IF NOT EXISTS assignacio (
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    experiment  TEXT NOT NULL,
    data        TEXT NOT NULL,
    grup        TEXT NOT NULL CHECK (grup IN ('amb', 'sense')),
    PRIMARY KEY (botiga_id, experiment, data)
);

-- ---------------------------------------------------------------- Fitxa NFC
-- sessio_nfc és un id tècnic aleatori que viu només dins la pàgina (camp ocult),
-- sense galetes. No es pot unir amb cap compra ni persona.
CREATE TABLE IF NOT EXISTS esdeveniment_nfc (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sessio_nfc  TEXT NOT NULL,
    ts          TEXT NOT NULL,
    botiga_id   TEXT,
    gtin        TEXT NOT NULL,
    tipus       TEXT NOT NULL,              -- 'obre_fitxa' | 'veu_origen' | 'demana_talla' | 'motiu_no_compra'
    valor       TEXT,                       -- motiu, talla demanada...
    idioma      TEXT NOT NULL,
    grup        TEXT
);

CREATE TABLE IF NOT EXISTS peticio_talla (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sessio_nfc  TEXT NOT NULL,
    botiga_id   TEXT NOT NULL,
    gtin_origen TEXT NOT NULL,              -- la peça que el client té a la mà
    gtin_demanat TEXT NOT NULL,
    talla_demanada TEXT NOT NULL,
    cabina      TEXT,                       -- el client la pot indicar (opcional)
    estat       TEXT NOT NULL DEFAULT 'pendent' CHECK (estat IN ('pendent', 'lliurada', 'no_disponible')),
    hora_peticio TEXT NOT NULL,
    hora_resolta TEXT,
    disponible  INTEGER                     -- 1/0 segons l'estoc conegut en el moment
);
