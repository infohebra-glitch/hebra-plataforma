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
    estat       TEXT NOT NULL DEFAULT 'pendent' CHECK (estat IN ('pendent', 'en_cami', 'lliurada', 'no_disponible')),
    hora_peticio TEXT NOT NULL,
    hora_resolta TEXT,
    disponible  INTEGER                     -- 1/0 segons l'estoc conegut en el moment
);

-- ================================================================ v0.2: plataforma completa
-- (Taules afegides per al tauler de la marca, alertes, estoc, experiments i registre de decisions.)

-- ---------------------------------------------------------------- Usuaris del tauler i de botiga
-- Persones de l'EQUIP de la marca (no clients finals). Contrasenya amb hash (PBKDF2).
CREATE TABLE IF NOT EXISTS usuari (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    correu      TEXT UNIQUE NOT NULL,
    nom         TEXT NOT NULL,
    hash_contrasenya TEXT NOT NULL,
    rol         TEXT NOT NULL CHECK (rol IN ('admin', 'marca', 'botiga')),
    botiga_id   TEXT REFERENCES botiga(id),   -- obligatori per al rol 'botiga'
    actiu       INTEGER NOT NULL DEFAULT 1,
    creat       TEXT NOT NULL
);

-- ---------------------------------------------------------------- Estoc de botiga
CREATE TABLE IF NOT EXISTS estoc (
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    gtin        TEXT NOT NULL,
    unitats     INTEGER NOT NULL,
    actualitzat TEXT NOT NULL,
    font        TEXT NOT NULL DEFAULT 'csv',  -- 'csv' | 'shopify'
    PRIMARY KEY (botiga_id, gtin)
);

-- Recompte manual contra lectura RFID (insight 23, precisió d'estoc de la zona).
CREATE TABLE IF NOT EXISTS recompte_estoc (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    data        TEXT NOT NULL,
    gtin        TEXT NOT NULL,
    manual      INTEGER NOT NULL,
    rfid        INTEGER NOT NULL
);

-- ---------------------------------------------------------------- Experiments (grup de control)
-- Generalitza l'"origen" a qualsevol canvi (insight 18). La taula `assignacio` (per dies)
-- ja existeix; `assignacio_model` permet assignar per grups de models.
CREATE TABLE IF NOT EXISTS experiment (
    id          TEXT PRIMARY KEY,               -- p. ex. "origen-2026-11"
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    variable    TEXT NOT NULL,                  -- 'origen' | 'preu' | 'exposicio' | 'peticio_talla' | 'altre'
    hipotesi    TEXT NOT NULL,
    unitat      TEXT NOT NULL DEFAULT 'dia' CHECK (unitat IN ('dia', 'model')),
    inici       TEXT NOT NULL,
    fi          TEXT NOT NULL,
    proves_minimes INTEGER NOT NULL DEFAULT 30,
    estat       TEXT NOT NULL DEFAULT 'actiu' CHECK (estat IN ('previst', 'actiu', 'tancat'))
);

CREATE TABLE IF NOT EXISTS assignacio_model (
    experiment  TEXT NOT NULL REFERENCES experiment(id),
    model       TEXT NOT NULL,
    grup        TEXT NOT NULL CHECK (grup IN ('amb', 'sense')),
    PRIMARY KEY (experiment, model)
);

-- ---------------------------------------------------------------- Registre de decisions (informe D)
CREATE TABLE IF NOT EXISTS decisio (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    botiga_id   TEXT REFERENCES botiga(id),
    creada      TEXT NOT NULL,
    titol       TEXT NOT NULL,
    descripcio  TEXT NOT NULL DEFAULT '',
    insight     TEXT,                           -- clau de l'insight que la motiva (p. ex. 'molt_provat_poc_venut')
    model       TEXT,
    responsable TEXT,                           -- rol: CEO, PROD, BOT, MKT, SOST
    data_limit  TEXT,
    estat       TEXT NOT NULL DEFAULT 'proposada' CHECK (estat IN ('proposada', 'acceptada', 'feta', 'descartada')),
    experiment_id TEXT REFERENCES experiment(id),
    resultat    TEXT                            -- què ha passat després (text), s'omple al mensual
);

-- ---------------------------------------------------------------- Peces abandonades (insight 13 i alerta)
CREATE TABLE IF NOT EXISTS peca_abandonada (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    epc         TEXT NOT NULL,
    cabina_id   TEXT NOT NULL REFERENCES cabina(id),
    detectada   TEXT NOT NULL,                  -- quan es compleix la regla (30 min sense tornar a sala ni vendre's)
    resolta     TEXT,
    UNIQUE (epc, cabina_id, detectada)
);

-- ---------------------------------------------------------------- Pilot (informe F)
CREATE TABLE IF NOT EXISTS pilot (
    botiga_id   TEXT PRIMARY KEY REFERENCES botiga(id),
    inici       TEXT NOT NULL,                  -- setmana 0 (instal·lació)
    fi          TEXT NOT NULL,
    criteris_json TEXT NOT NULL DEFAULT '[]',   -- [{"id","descripcio","metrica","objectiu","comparador"}]
    taxa_error_observacio REAL                  -- de la comparació amb l'observació manual
);

-- Observació manual per calibrar (setmana 0): què ha vist una persona a la cabina.
CREATE TABLE IF NOT EXISTS observacio_manual (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cabina_id   TEXT NOT NULL REFERENCES cabina(id),
    inici       TEXT NOT NULL,
    fi          TEXT NOT NULL,
    gtin        TEXT NOT NULL,
    nota        TEXT
);

-- ---------------------------------------------------------------- Altres
-- Configuració per botiga: marge brut per peça, quota, Shopify...  (clau-valor)
CREATE TABLE IF NOT EXISTS parametre (
    botiga_id   TEXT NOT NULL,                  -- '*' = per defecte per a totes
    clau        TEXT NOT NULL,
    valor       TEXT NOT NULL,
    PRIMARY KEY (botiga_id, clau)
);

-- ================================================================ v0.3 D-E: estoc parat, tasques, informes programats
-- (docs/ESPECIFICACIO-v3.md, seccions D i E.)

-- Tasques de botiga (D.1): el que la botiga ha de fer, sovint creat des d'un suggeriment d'estoc parat.
CREATE TABLE IF NOT EXISTS tasca (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    botiga_id   TEXT NOT NULL REFERENCES botiga(id),
    tipus       TEXT NOT NULL CHECK (tipus IN ('traspassar', 'moure_a_sala', 'promocio', 'retornar', 'revisar',
                                               'recompte', 'altre')),
    titol       TEXT NOT NULL,
    detall      TEXT NOT NULL DEFAULT '',
    gtin        TEXT,
    unitats     INTEGER,
    botiga_desti TEXT REFERENCES botiga(id),     -- només per a 'traspassar'
    estat       TEXT NOT NULL DEFAULT 'pendent' CHECK (estat IN ('pendent', 'feta', 'descartada')),
    creada      TEXT NOT NULL,
    creada_per  INTEGER REFERENCES usuari(id),
    feta        TEXT,                            -- quan s'ha tancat (feta o descartada)
    feta_per    INTEGER REFERENCES usuari(id)
);
CREATE INDEX IF NOT EXISTS ix_tasca_botiga_estat ON tasca(botiga_id, estat);

-- Programació d'informes (E.1). botiga_id NULL = informe de totes les botigues.
CREATE TABLE IF NOT EXISTS programacio_informe (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    botiga_id   TEXT REFERENCES botiga(id),
    tipus       TEXT NOT NULL CHECK (tipus IN ('diari', 'setmanal', 'mensual', 'temporada', 'pilot', 'mango')),
    actiu       INTEGER NOT NULL DEFAULT 1,
    dia_setmana INTEGER CHECK (dia_setmana BETWEEN 0 AND 6),   -- setmanal (0 = dilluns)
    dia_mes     INTEGER CHECK (dia_mes BETWEEN 1 AND 28),      -- mensual
    data        TEXT,                                          -- temporada, pilot, mango (una vegada)
    hora        TEXT NOT NULL DEFAULT '08:00',                 -- HH:MM, hora local de la botiga
    destinataris TEXT NOT NULL DEFAULT '[]',                   -- JSON: correus de l'EQUIP de la marca
    creada      TEXT NOT NULL,
    darrera_execucio TEXT                                      -- ocurrència programada generada per última vegada
);

-- Informes lliurats (E.1): instantània JSON de cada informe generat.
CREATE TABLE IF NOT EXISTS informe_lliurat (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    programacio_id INTEGER REFERENCES programacio_informe(id) ON DELETE SET NULL,
    botiga_id   TEXT REFERENCES botiga(id),
    tipus       TEXT NOT NULL,
    des         TEXT NOT NULL,
    fins        TEXT NOT NULL,
    generat     TEXT NOT NULL,
    dades_json  TEXT NOT NULL,
    enviat_a    TEXT NOT NULL DEFAULT '[]',
    estat_enviament TEXT NOT NULL DEFAULT 'no_enviat' CHECK (estat_enviament IN ('no_enviat', 'enviat', 'error')),
    error       TEXT
);
CREATE INDEX IF NOT EXISTS ix_informe_lliurat_generat ON informe_lliurat(generat);

-- ================================================================ v0.3 A-C: fitxa configurable, assistència, sessions
-- Configuració de la fitxa NFC (A.1). botiga_id = '*' és la general; la d'una botiga és parcial
-- (només els camps que canvien). Formes i validació a hebra/fitxa_config.py.
CREATE TABLE IF NOT EXISTS config_fitxa (
    botiga_id   TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    actualitzada TEXT NOT NULL
);

-- Contingut propi de la marca per model i idioma (A.2); passa per davant de catalog_sku.origen_json.
CREATE TABLE IF NOT EXISTS contingut_model (
    model       TEXT NOT NULL,
    idioma      TEXT NOT NULL,
    camps_json  TEXT NOT NULL,
    actualitzat TEXT NOT NULL,
    PRIMARY KEY (model, idioma)
);

-- Assistència des de la fitxa (A.4): peticio_talla.tipus ('talla' | 'assistencia') s'afegeix amb
-- ALTER TABLE a db.inicialitza (SQLite no canvia taules existents amb CREATE TABLE IF NOT EXISTS).
-- Una petició d'assistència té gtin_demanat = gtin_origen i talla_demanada = ''.

-- ================================================================ v0.3 F: integracions
-- Connexions amb Shopify, Square o fitxers CSV per URL (hebra/integracions/). El testimoni d'accés
-- es desa xifrat (Fernet, clau derivada de HEBRA_SECRET) i mai surt per l'API.
CREATE TABLE IF NOT EXISTS integracio (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    botiga_id   TEXT REFERENCES botiga(id),     -- NULL = tota la marca
    proveidor   TEXT NOT NULL CHECK (proveidor IN ('shopify', 'square', 'csv_url')),
    config_json TEXT NOT NULL DEFAULT '{}',     -- domini, ubicació, noms d'opció, URL... (res secret)
    secret_xifrat TEXT,
    actiu       INTEGER NOT NULL DEFAULT 1,
    abast       TEXT NOT NULL DEFAULT '["cataleg","vendes","estoc"]',  -- JSON
    interval_min INTEGER NOT NULL DEFAULT 60,   -- mínim 15
    darrera_sync TEXT,                          -- inici de la darrera sincronització bona
    estat       TEXT NOT NULL DEFAULT 'mai' CHECK (estat IN ('ok', 'error', 'mai')),
    missatge    TEXT,
    creada      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_registre (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    integracio_id INTEGER NOT NULL REFERENCES integracio(id) ON DELETE CASCADE,
    inici       TEXT NOT NULL,
    fi          TEXT,
    estat       TEXT NOT NULL CHECK (estat IN ('en_curs', 'ok', 'error')),
    resum_json  TEXT,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS ix_sync_registre ON sync_registre(integracio_id, inici);
