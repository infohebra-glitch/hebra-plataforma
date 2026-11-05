# Què falta i què cal decidir

## Per revisar amb el Xavier

1. **Interfície del R700**: la passarel·la (`hebra_passarella/lector.py`) fa servir l'API REST d'Impinj (IoT Device Interface) i el flux HTTP de línies JSON. **Està provada contra un lector fals, no contra un R700 real.** Cal comprovar al Swagger del lector: camins (v0 o v1), mètodes, si el flux és `GET /api/v1/data/stream`, i el format exacte de l'esdeveniment. Tot és configurable a `passarella.toml`.
2. **Passarel·la (Raspberry Pi)**: feta (`hebra_passarella/`): lector, sensors GPIO, agregació cada 10 s, cua de 7 dies i enviament. Falta provar-la amb maquinari: cablejat dels sensors, comportament del radar LD2410C, rebots del contacte de porta. El filtre per prefix d'EPC es fa a la Raspberry; es podria passar al lector (filtres del preset).
3. **Calibratge** amb la prova de laboratori de 20 peces: llindar RSSI per antena, temps mínim (60 s?), lectures mínimes, marges de confiança. Tot és configurable per variables d'entorn; el llindar és per antena a la taula `antena`.
4. **Les etiquetes són SGTIN-96?** Si no, cal omplir la taula `etiqueta` (EPC → GTIN) des del dossier de la marca.
5. **Tecnologia**: SQLite val per al pilot d'una botiga. Per a més botigues, PostgreSQL. Revisar si FastAPI + plantilles al servidor li sembla bé.

## Funcionalitat pendent (dins l'abast del MVP)

- **Nivell Bàsic** (sense sensors per cabina): comptar entrades a zona en lloc de sessions.
- **Peces abandonades** (EPC que queda a la cabina buida): la taula és a la proposta però no s'ha implementat.
- **Shopify per API** (només si la marca ja el fa servir a botiga). Ara només hi ha CSV.
- **Prova estadística** de l'efecte de l'origen sobre les 6 setmanes (p. ex. test de proporcions o regressió amb dia de la setmana), i càlcul de la mostra mínima amb les setmanes 2-3.
- **Altres informes**: alertes, resum diari, mensual d'accions, fi de temporada, final de pilot, pilot de Mango.
- **Estoc real** a la fitxa: ara surt del fitxer d'origen (fix). Hauria de venir del TPV o de Shopify.
- **Avisos al mòbil del dependent** quan arriba una petició (ara cal actualitzar la pàgina).
- **Gestió de botigues, cabines i antenes** des de la web (ara: `python -m hebra.admin`).
- **Recàlcul incremental de proves**: ara es recalcula tot l'historial de cada cabina cada 5 minuts. Per a 8 setmanes i una botiga va bé; per a moltes botigues caldrà fer-ho només dels darrers dies.

## Abans de posar-ho davant d'una botiga real

- **Canviar totes les claus i contrasenyes** i servir-ho només amb HTTPS.
- Usuaris per botiga (ara hi ha un sol usuari de botiga per a tot).
- Límit de peticions a la fitxa i a l'API.
- **Retenció de dades**: esborrar `lectura_agregada` i `sensor_event` passats N dies.
- Revisió de l'advocat: avaluació d'impacte, textos de privacitat de la fitxa.

## Notes sobre les dades de prova

- `dades/origen-prova.json` és una còpia del fitxer del prototip del provador. **Els GTIN del fitxer tenen el dígit de control malament**: la importació fa servir el GTIN que surt de l'EPC i ho avisa al registre.
- Els GTIN de les talles que no són la de la peça es generen sumant 1000 a la referència del model. És una convenció només per a les dades de prova.
- El simulador inventa una conversió per categoria (el vestit «es prova i no es ven») i un efecte de l'origen de +6 punts, per veure com ho detecta l'informe. **No són resultats.**
