"""Textos de la fitxa NFC en català, castellà, francès i anglès.

El contingut de la peça (nom, composició, origen...) ve del fitxer d'origen de
la marca; aquí només hi ha els textos fixos de la interfície.
"""

TEXTOS = {
    "ca": {
        "composicio": "Composició", "cura": "Cura", "origen": "D'on ve", "talles": "Talles",
        "demana": "Demana una altra talla", "demana_ajuda": "Un dependent te la porta a la cabina.",
        "cabina": "Cabina (opcional)", "envia": "Demana-la", "peticio_ok": "Fet. Ara te la portem.",
        "no_disponible": "esgotada", "teva": "la que tens",
        "per_que": "Per què no te l'emportes?", "per_que_ajuda": "Una resposta, anònima. Ens ajuda a fer roba millor.",
        "motiu_ok": "Gràcies. Ho tindrem en compte.",
        "motius": {"talla": "La talla", "tall": "El tall", "preu": "El preu", "color": "El color",
                   "qualitat": "La qualitat", "altre": "Una altra cosa"},
        "preguntes": "Preguntes", "certificats": "Certificats", "privacitat":
        "Aquesta pàgina no fa servir galetes ni guarda cap dada teva.",
        "etapes": {"cultiu": "Cultiu", "filatura": "Filatura", "teixit": "Teixit", "tintura": "Tintura",
                   "confeccio": "Confecció", "acabat": "Acabat", "fibra": "Fibra", "fusta": "Fusta", "tricotat": "Tricotat"},
        "veure_origen": "Mostra el recorregut",
    },
    "es": {
        "composicio": "Composición", "cura": "Cuidados", "origen": "De dónde viene", "talles": "Tallas",
        "demana": "Pide otra talla", "demana_ajuda": "Un dependiente te la lleva al probador.",
        "cabina": "Probador (opcional)", "envia": "Pedirla", "peticio_ok": "Hecho. Ahora te la llevamos.",
        "no_disponible": "agotada", "teva": "la que tienes",
        "per_que": "¿Por qué no te la llevas?", "per_que_ajuda": "Una respuesta, anónima. Nos ayuda a hacer mejor ropa.",
        "motiu_ok": "Gracias. Lo tendremos en cuenta.",
        "motius": {"talla": "La talla", "tall": "El corte", "preu": "El precio", "color": "El color",
                   "qualitat": "La calidad", "altre": "Otra cosa"},
        "preguntes": "Preguntas", "certificats": "Certificados", "privacitat":
        "Esta página no usa cookies ni guarda ningún dato tuyo.",
        "etapes": {"cultiu": "Cultivo", "filatura": "Hilatura", "teixit": "Tejido", "tintura": "Tintura",
                   "confeccio": "Confección", "acabat": "Acabado", "fibra": "Fibra", "fusta": "Madera", "tricotat": "Tricotado"},
        "veure_origen": "Ver el recorrido",
    },
    "fr": {
        "composicio": "Composition", "cura": "Entretien", "origen": "D'où il vient", "talles": "Tailles",
        "demana": "Demander une autre taille", "demana_ajuda": "Un vendeur vous l'apporte en cabine.",
        "cabina": "Cabine (facultatif)", "envia": "La demander", "peticio_ok": "C'est noté. On vous l'apporte.",
        "no_disponible": "épuisée", "teva": "celle que vous avez",
        "per_que": "Pourquoi ne le prenez-vous pas ?", "per_que_ajuda": "Une réponse, anonyme. Elle nous aide à faire de meilleurs vêtements.",
        "motiu_ok": "Merci. Nous en tiendrons compte.",
        "motius": {"talla": "La taille", "tall": "La coupe", "preu": "Le prix", "color": "La couleur",
                   "qualitat": "La qualité", "altre": "Autre chose"},
        "preguntes": "Questions", "certificats": "Certificats", "privacitat":
        "Cette page n'utilise pas de cookies et n'enregistre aucune donnée vous concernant.",
        "etapes": {"cultiu": "Culture", "filatura": "Filature", "teixit": "Tissage", "tintura": "Teinture",
                   "confeccio": "Confection", "acabat": "Finition", "fibra": "Fibre", "fusta": "Bois", "tricotat": "Tricotage"},
        "veure_origen": "Voir le parcours",
    },
    "en": {
        "composicio": "Composition", "cura": "Care", "origen": "Where it comes from", "talles": "Sizes",
        "demana": "Ask for another size", "demana_ajuda": "A member of staff will bring it to your fitting room.",
        "cabina": "Fitting room (optional)", "envia": "Ask for it", "peticio_ok": "Done. It's on its way.",
        "no_disponible": "sold out", "teva": "the one you have",
        "per_que": "Why aren't you taking it?", "per_que_ajuda": "One anonymous answer. It helps us make better clothes.",
        "motiu_ok": "Thank you. We'll take it into account.",
        "motius": {"talla": "The size", "tall": "The fit", "preu": "The price", "color": "The colour",
                   "qualitat": "The quality", "altre": "Something else"},
        "preguntes": "Questions", "certificats": "Certificates", "privacitat":
        "This page uses no cookies and stores no data about you.",
        "etapes": {"cultiu": "Growing", "filatura": "Spinning", "teixit": "Weaving", "tintura": "Dyeing",
                   "confeccio": "Making", "acabat": "Finishing", "fibra": "Fibre", "fusta": "Wood", "tricotat": "Knitting"},
        "veure_origen": "Show the journey",
    },
}

PAISOS = {
    "FR": {"ca": "França", "es": "Francia", "fr": "France", "en": "France"},
    "LT": {"ca": "Lituània", "es": "Lituania", "fr": "Lituanie", "en": "Lithuania"},
    "IT": {"ca": "Itàlia", "es": "Italia", "fr": "Italie", "en": "Italy"},
    "PT": {"ca": "Portugal", "es": "Portugal", "fr": "Portugal", "en": "Portugal"},
    "ES": {"ca": "Espanya", "es": "España", "fr": "Espagne", "en": "Spain"},
    "TR": {"ca": "Turquia", "es": "Turquía", "fr": "Turquie", "en": "Turkey"},
    "IN": {"ca": "Índia", "es": "India", "fr": "Inde", "en": "India"},
    "AU": {"ca": "Austràlia", "es": "Australia", "fr": "Australie", "en": "Australia"},
    "NZ": {"ca": "Nova Zelanda", "es": "Nueva Zelanda", "fr": "Nouvelle-Zélande", "en": "New Zealand"},
    "CN": {"ca": "Xina", "es": "China", "fr": "Chine", "en": "China"},
    "AT": {"ca": "Àustria", "es": "Austria", "fr": "Autriche", "en": "Austria"},
    "MA": {"ca": "Marroc", "es": "Marruecos", "fr": "Maroc", "en": "Morocco"},
}


def pais(codi: str | None, idioma: str) -> str:
    if not codi:
        return ""
    return PAISOS.get(codi, {}).get(idioma, codi)
