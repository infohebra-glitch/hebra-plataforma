"""Agrupa lectures crues en finestres per (EPC, antena).

El lector pot donar desenes de lectures per segon de cada etiqueta. Enviar-les
totes no aporta res: el núvol només necessita, per cada finestra de N segons,
quantes lectures hi ha hagut i amb quina intensitat (RSSI). Això és la
`lectura_agregada` de la plataforma.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class _Finestra:
    inici: datetime
    fi: datetime
    n: int = 0
    rssi_max: float = -999.0
    suma_rssi: float = 0.0


@dataclass
class Agregador:
    nom_lector: str                 # p. ex. "R700-1"; l'antena es diu "R700-1:<port>"
    finestra_s: float = 10.0
    prefixos_epc: tuple[str, ...] = ()   # filtre opcional (hex en majúscules)
    _obertes: dict[tuple[str, int], _Finestra] = field(default_factory=dict)

    def afegeix(self, epc_hex: str, port: int, rssi_dbm: float, ts: datetime) -> None:
        epc_hex = epc_hex.upper()
        if self.prefixos_epc and not epc_hex.startswith(self.prefixos_epc):
            return  # etiqueta d'una altra marca o d'un altre sistema
        clau = (epc_hex, port)
        f = self._obertes.get(clau)
        if f is None:
            f = self._obertes[clau] = _Finestra(inici=ts, fi=ts)
        f.fi = max(f.fi, ts)
        f.n += 1
        f.rssi_max = max(f.rssi_max, rssi_dbm)
        f.suma_rssi += rssi_dbm

    def tanca(self, ara: datetime, tot: bool = False) -> list[dict]:
        """Retorna les finestres que ja han durat `finestra_s` (o totes si `tot`)."""
        sortida = []
        for clau, f in list(self._obertes.items()):
            if tot or ara - f.inici >= timedelta(seconds=self.finestra_s):
                epc_hex, port = clau
                sortida.append({
                    "epc": epc_hex,
                    "antena": f"{self.nom_lector}:{port}",
                    "inici": f.inici.isoformat(),
                    "fi": f.fi.isoformat(),
                    "n": f.n,
                    "rssi_max": round(f.rssi_max, 1),
                    "rssi_mitja": round(f.suma_rssi / f.n, 1),
                })
                del self._obertes[clau]
        return sortida
