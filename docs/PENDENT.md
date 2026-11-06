# Què falta i què cal decidir

## Per revisar amb el Xavier

1. **Interfície del R700**: la passarel·la (`hebra_passarella/lector.py`) fa servir l'API REST d'Impinj (IoT Device Interface) i el flux HTTP de línies JSON. **Està provada contra un lector fals, no contra un R700 real.** Cal comprovar al Swagger del lector: camins (v0 o v1), mètodes, si el flux és `GET /api/v1/data/stream`, i el format exacte de l'esdeveniment. Tot és configurable a `passarella.toml`.
2. **Passarel·la (Raspberry Pi)**: feta (`hebra_passarella/`): lector, sensors GPIO, agregació cada 10 s, cua de 7 dies i enviament. Falta provar-la amb maquinari: cablejat dels sensors, comportament del radar LD2410C, rebots del contacte de porta. El filtre per prefix d'EPC es fa a la Raspberry; es podria passar al lector (filtres del preset).
3. **Calibratge** amb la prova de laboratori de 20 peces: llindar RSSI per antena, temps mínim (60 s?), lectures mínimes, marges de confiança. Tot és configurable per variables d'entorn; el llindar és per antena a la taula `antena`.
4. **Les etiquetes són SGTIN-96?** Si no, cal omplir la taula `etiqueta` (EPC → GTIN) des del dossier de la marca.
5. **Tecnologia**: SQLite val per al pilot d'una botiga. Per a més botigues, PostgreSQL. Revisar si FastAPI + plantilles al servidor li sembla bé.

## Funcionalitat pendent

- **Insight 19 («Combina amb» mesurat)** i **20 (venda recuperada en línia)**: fora del MVP segons la Proposta; el 20 depèn d'«Envia'm la llista», en suspens fins que l'advocat ho validi.
- **Devolucions de Shopify**: la sincronització importa comandes i estoc, però encara no els reemborsaments.
- **Gestió de botigues, cabines i antenes** des del tauler (ara: `python -m hebra.admin`).
- **Alertes en directe amb diversos processos**: el bus d'alertes és en memòria; cal un sol procés `uvicorn`. Per escalar, Redis o PostgreSQL LISTEN/NOTIFY.
- **Recàlcul incremental de proves**: ara es recalcula la història guardada de cada cabina cada 5 minuts. Per a una botiga i 8 setmanes va bé (la simulació de 8 setmanes triga ~1 min a generar-se, però les consultes del tauler responen en < 150 ms).
- **Notificacions push** al mòbil del dependent amb la pantalla bloquejada (ara: la pàgina oberta rep les alertes en directe, amb so i vibració).

## Abans de posar-ho davant d'una botiga real

- `HEBRA_ENTORN=produccio`, `HEBRA_SECRET`, `HEBRA_COOKIE_SECURE=1`, claus i contrasenyes noves, i només HTTPS.
- Crear els usuaris reals (`python -m hebra.admin usuari ...`) i no fer servir l'usuari bàsic de `/botiga/*`.
- Revisió de l'advocat: avaluació d'impacte, textos de privacitat de la fitxa, retenció (`HEBRA_RETENCIO_DIES`).
- Còpies de seguretat diàries de la base de dades.

## Notes sobre les dades de prova

- `dades/origen-prova.json` és una còpia del fitxer del prototip del provador. **Els GTIN del fitxer tenen el dígit de control malament**: la importació fa servir el GTIN que surt de l'EPC i ho avisa al registre.
- Els GTIN de les talles que no són la de la peça es generen sumant 1000 a la referència del model. És una convenció només per a les dades de prova.
- El simulador posa el paràmetre `dades_simulades = 1` i tots els informes avisen que les dades són simulades.
- El simulador inventa una conversió per categoria (el vestit «es prova i no es ven») i un efecte de l'origen de +6 punts, per veure com ho detecta l'informe. **No són resultats.**
