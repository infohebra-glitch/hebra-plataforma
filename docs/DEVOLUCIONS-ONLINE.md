# Provador i online: motius de no compra contra motius de devolució (v0.9)

Idea de la Marta Mateu (Mango StartUp Studio, 27-11-2026): connectar el que diu el client al provador
quan no s'emporta una peça amb el que diu el client online quan la torna, per veure si els motius són
els mateixos.

## Què és viable i com ho fem

| Pregunta | Resposta |
|---|---|
| Es pot unir la persona del provador amb el client online? | **No, i no cal.** El provador no sap qui és ningú (no hi ha cap identificador de persona) i unir-los demanaria consentiment i dades personals. La comparació es fa **per peça (model), talla i període**, sempre amb totals. |
| Quines dades calen de la marca? | Un CSV de devolucions online: `data, gtin, quantitat, motiu`, i opcionalment `comentari` i `comanda`. Ho exporten Shopify, qualsevol ERP o un full de càlcul. |
| RGPD | Només es desen data, GTIN, unitats i el motiu. Columnes com correu, nom, adreça, telèfon o DNI s'ignoren i l'importador avisa. El comentari lliure es llegeix per deduir-ne el motiu i es llença. La comanda es desa com una empremta SHA-256 amb sal, només per no duplicar línies. Una instal·lació per marca: les dades no surten de la seva base de dades. |
| Cada botiga en línia té codis diferents | Hebra els tradueix sola (paraules clau en català, castellà, anglès i francès) a les categories del provador. La marca pot corregir qualsevol traducció a «Provador i online» i tot es recalcula. |
| Motius que al provador no existeixen | «No era com a la foto», «defecte», «enviament» i «canvi d'opinió» es compten a part (només online). «Només mirava» del provador no entra a la comparació. |
| Talla | Online es distingeix «massa petita» de «massa gran». Al provador, el sentit surt de les peticions de talla de la fitxa (demanar una de més gran vol dir que la provada anava petita). |

## Què hi ha a la plataforma

- **Connexions i dades → Devolucions online**: pujada del CSV (marca o admin), sense duplicats si es torna a pujar, i botó per esborrar-les totes.
- **Provador i online** (tauler): coincidència global, gràfic provador contra online, motius només online, taula peça a peça (primer les que menys coincideixen, amb una frase de lectura), devolucions per talla, traducció de motius editable i el text de privacitat.
- **Fitxa de la peça** (tauler): bloc «Al provador i online» amb el gràfic i la lectura del model.
- **Informes** mensual, temporada, pilot i Mango: gràfic «Per què no se l'emporten (provador) i per què la tornen (online)» amb lectura, només quan hi ha devolucions al període.
- **Lot de prova**: porta devolucions inventades i s'esborren amb ell.

**Coincidència** = Σ min(% provador, % online) sobre les categories comparables. 100 % = el mateix
repartiment de motius; 0 % = res en comú. Només amb 5 respostes o més a cada costat. Una peça amb
menys del 50 % es marca com a «no coincideix».

## Què queda per fer (pla)

- Connexió automàtica amb les devolucions de Shopify (API `returns`) o l'ERP de la marca, en lloc del CSV.
- Taxa de devolució per peça: cal també el fitxer de vendes online (unitats venudes) per dividir.
- Desfasament: ara es compara per data de devolució; es podria comparar per data de compra quan el fitxer la porti.
- Validar les paraules clau amb codis reals de 2-3 marques i amb l'advocat el text de privacitat.
