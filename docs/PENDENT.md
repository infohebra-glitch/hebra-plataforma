# Què falta i què cal decidir

## Per revisar amb el Xavier

1. **Interfície del R700**: REST, MQTT o LLRP? Defineix com serà la passarel·la. El núvol ja espera lots agregats (`hebra/passarella.py`).
2. **Passarel·la (Raspberry Pi)**: no està feta. Ha de llegir el lector i els sensors per cable, filtrar per prefix d'EPC, agregar cada 5-10 s, guardar 7 dies si cau la xarxa i enviar a `POST /api/v1/lots`.
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
- **Gestió de botigues, cabines i antenes** des de la web (ara: SQL o el simulador).

## Abans de posar-ho davant d'una botiga real

- **Token NFC aleatori o signat.** Ara és `GTIN-sèrie`, fàcil d'endevinar (`cataleg.token_nfc`).
- **Canviar totes les claus i contrasenyes** i servir-ho només amb HTTPS.
- Usuaris per botiga (ara hi ha un sol usuari de botiga per a tot).
- Límit de peticions a la fitxa i a l'API.
- **Retenció de dades**: esborrar `lectura_agregada` i `sensor_event` passats N dies.
- Revisió de l'advocat: avaluació d'impacte, textos de privacitat de la fitxa.

## Notes sobre les dades de prova

- `dades/origen-prova.json` és una còpia del fitxer del prototip del provador. **Els GTIN del fitxer tenen el dígit de control malament**: la importació fa servir el GTIN que surt de l'EPC i ho avisa al registre.
- Els GTIN de les talles que no són la de la peça es generen sumant 1000 a la referència del model. És una convenció només per a les dades de prova.
- El simulador inventa una conversió per categoria (el vestit «es prova i no es ven») i un efecte de l'origen de +6 punts, per veure com ho detecta l'informe. **No són resultats.**
