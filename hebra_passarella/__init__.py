"""Passarel·la de botiga de Hebra (s'executa a la Raspberry Pi de la botiga).

Llegeix el lector RFID UHF (Impinj R700) i els sensors de cabina per cable,
agrupa les lectures en finestres curtes i les envia a la plataforma.
Només fa servir la llibreria estàndard de Python; per als sensors fa servir
`gpiozero`, que ja ve instal·lat a Raspberry Pi OS.
"""
