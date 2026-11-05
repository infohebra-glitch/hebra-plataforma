# Especificació funcional

Font: *Proposta MVP abans del pilot* (30-10-2026), secció 5 i 6, amb les decisions posteriors (etiqueta doble UHF + NFC, sense QR; «Envia'm la llista» fora fins que l'advocat ho validi).

## Els 25 insights

Estat a la plataforma: **fet** a `hebra/analitica/` excepte els marcats.

| # | Insight | Definició o fórmula | Font | Nivell | Freqüència | Decisió que permet | Qui |
|---|---|---|---|---|---|---|---|
| 1 | Proves | Proves per SKU i talla (al pilot, per categoria i talla) | Lector | Bàsic | Diari, setmanal | Què interessa de debò, no només què es ven | PROD, BOT |
| 2 | Conversió de provador | Unitats venudes atribuïdes ÷ proves | Lector + TPV | Bàsic | Setmanal | Peces amb problema de talla, tall o preu | PROD, CEO |
| 3 | Molt provat, poc venut | Proves ≥ N a la setmana (proposta N = 10) i conversió al quartil inferior de la categoria | Lector + TPV | Bàsic | Setmanal | Revisar preu, exposició o tall abans de rebaixar | PROD, BOT |
| 4 | Venut sense provar | Vendes sense prova prèvia el mateix dia ÷ vendes del SKU | Lector + TPV | Bàsic | Mensual | Quines peces són segures i on posar-les | BOT, PROD |
| 5 | Talles provades contra comprades | % de proves per talla d'un model contra % d'unitats comprades per talla | Lector + comandes | Bàsic | Mensual, temporada | Refer la corba de talles de la propera comanda | PROD |
| 6 | Conversió per talla | Insight 2 desglossat per talla | Lector + TPV | Bàsic | Setmanal | Una talla que es prova i no es ven apunta al patró | PROD |
| 7 | Demanda perduda | Peticions de talla o color sense estoc a la botiga | QR o personal + estoc | Cabina (Bàsic si el personal ho apunta) | Temps real, setmanal | Què reposar o tornar a demanar | PROD, BOT |
| 8 | Motiu de no compra | % de respostes per motiu i referència, sempre amb la taxa de resposta | NFC | Cabina | Setmanal, temporada | Per què una peça no funciona | PROD, CEO |
| 9 | Peticions de talla | Peticions des del NFC ÷ sessions de cabina | NFC | Cabina | Setmanal | Més personal a la zona o un altre estoc a la sala | BOT |
| 10 | Temps de resposta | Mediana de segons entre «demanat» i «lliurat»; % per sota de 90 s | NFC + mòbil del dependent | Cabina | Temps real, setmanal | Organitzar el personal | BOT |
| 11 | Ocupació i cicles | Sessions per hora i dia, durada mitjana, % del temps amb totes les cabines plenes | Lector | Bàsic (aprox.), Cabina | Setmanal | Torns i horaris | BOT, CEO |
| 12 | Peces per sessió | Etiquetes diferents per sessió; % de sessions amb compra | Lector + TPV | Cabina | Setmanal | Límit de peces o suggeriments | BOT |
| 13 | Peces abandonades | Etiquetes que entren i no tornen a la sala ni es venen en 30 min | Lector + TPV | Bàsic | Temps real, setmanal | Ordre i reposició a la sala | BOT |
| 14 | Estoc parat | Unitats amb 0 proves i 0 vendes en 21 dies | Lector + estoc | Bàsic | Setmanal, mensual | Traspassar a una altra botiga o al web abans de rebaixar | PROD, CEO |
| 15 | Risc de rebaixa | Cobertura d'estoc > Y setmanes i proves o conversió al quartil inferior | Lector + TPV | Bàsic | Mensual | Actuar abans de les rebaixes | CEO, PROD |
| 16 | Ús de la fitxa NFC | Tocs ÷ sessions; % per secció (origen, talla, cura, combina) i idioma | NFC | Cabina | Setmanal | Quin contingut interessa | MKT |
| 17 | Efecte de l'origen | Conversió amb origen visible − conversió de control, amb interval de confiança | Lector + NFC + TPV | Cabina | Fi de pilot, temporada | Si val la pena explicar i pagar la traçabilitat | MKT, SOST, CEO |
| 18 | Efecte de qualsevol canvi | La mateixa fórmula per a preu, exposició, «combina amb» o petició de talla | Lector + TPV | Cabina | Per prova (4-8 setmanes) | Decidir amb una prova, no amb una opinió | CEO |
| 19 | «Combina amb» mesurat | Proves de la peça suggerida ÷ suggeriments vistos; peces per tiquet amb i sense | NFC + lector + TPV | Cabina, Experiència | Mensual | Si el suggeriment fa vendre més peces | MKT, BOT |
| 20 | Venda recuperada en línia | Comandes a Shopify de la llista enviada en ≤ 14 dies ÷ llistes enviades; import | NFC (consentiment) + Shopify | Cabina | Mensual | Si el pont botiga-web recupera vendes | MKT |
| 21 | Idioma del client | % de sessions de NFC per idioma del mòbil | NFC | Cabina | Mensual | Contingut i personal per a turistes o França | MKT, BOT |
| 22 | Feedback de disseny | Insights 2 i 8 agregats per atribut: tall, teixit, color, composició | NFC + lector + fitxa | Cabina | Fi de temporada | Què repetir i què canviar a la col·lecció | PROD, CEO |
| 23 | Precisió d'estoc de la zona | Recompte manual contra lectura RFID de la zona | Lector + personal | Bàsic | Inici i final del pilot | Si val la pena un inventari RFID | CEO |
| 24 | Historial de la peça | Esdeveniments per etiqueta (entrada, proves, venda) enllaçats a l'origen | Lector + origen | Experiència | Fi de temporada | Dades per a Refashion i el futur passaport | SOST |
| 25 | Senyals de pèrdua | Etiquetes que entren i no reapareixen ni es venen; per peça, mai per persona | Lector + TPV | Bàsic | Setmanal | Prevenció de pèrdues per zona i hora | Prevenció (només Mango) |

Fora d'aquesta versió:
- **19 «Combina amb» mesurat**: fora del MVP segons la Proposta (2.2). La fitxa ja mostra «combina amb» si el fitxer d'origen el porta, però no es mesura.
- **20 Venda recuperada en línia**: depèn d'«Envia'm la llista», en suspens per protecció de dades.

## Els 7 informes

A. Alertes en temps real (web del dependent) · B. Resum diari · C. Setmanal d'una pàgina · D. Mensual d'accions · E. Fi de temporada · F. Final del pilot · G. Pilot de Mango. Detall dels blocs a `docs/API.md` (Informes).

## Què hi guanya el client (palanques)

| Palanca | Insights | Fórmula | Exemple il·lustratiu |
|---|---|---|---|
| Menys rebaixes | 3, 14, 15 | Unitats detectades a temps × PVP × (descompte evitat − descompte final) | 40 u × 80 € × (40 % − 10 %) = 960 € per temporada |
| Menys talles esgotades | 7 | Peticions sense estoc × % reposat a temps × % que compra × marge per peça | 60 × 50 % × 40 % × 40 € = 480 € al mes |
| Millor recompra | 5, 6 | Unitats sobrants evitades per talla × cost unitari × % que s'hauria liquidat | 30 u × 25 € × 60 % = 450 € per comanda |
| Més conversió | 2, 17, 18 | Punts de conversió guanyats × proves al mes × marge per peça | 2 punts × 1.600 × 40 € = 1.280 € al mes |
| Disseny | 8, 22 | Unitats no produïdes d'un tall que no funciona × cost | Difícil de posar en euros |
| Compliment a França | 24 | Hores estalviades a la declaració Refashion × cost per hora | Preparem dades, no fem la declaració |

Tots els valors en euros són **estimacions** amb els paràmetres que posa la marca (marge per peça, quota...). No són resultats.

## Peces del sistema

| Part | Qui l'usa | On |
|---|---|---|
| Fitxa NFC | Client final, al mòbil | `/p/{token}` (servidor, sense galetes ni seguiment) |
| Web del dependent | Dependent i encarregada | `/app/dependent` (mòbil, alertes en directe) |
| Tauler de la marca | CEO, producte, màrqueting, sostenibilitat | `/app/` |
| Informes imprimibles | Tots | `/app/informes/...` (es poden desar en PDF des del navegador) |
| API del tauler | El tauler | `/api/v2/...` (contracte a `docs/API.md`) |
| API de la passarel·la | Raspberry Pi | `/api/v1/lots` |
| Passarel·la | Raspberry Pi a la botiga | `hebra_passarella/` |
