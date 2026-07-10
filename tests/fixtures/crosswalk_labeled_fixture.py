"""Labeled fixture of known cross-source players (Phase 2 precision gate).

LEFT mimics ASA identities; RIGHT mimics FBref spellings of (mostly) the same people.
`TRUE_MATCH` maps right_id -> the correct left player_id, or None when the right
player has no left counterpart (negatives include sibling traps and same-first-name
different players). All are real, well-known MLS-era players; birth years are real.
"""

import pandas as pd

LEFT = pd.DataFrame([
    # player_id, player_name, birth_year, seasons active
    ("asa01", "Carles Gil", 1992, {2019, 2020, 2021, 2022}),
    ("asa02", "Hany Mukhtar", 1995, {2020, 2021, 2022}),
    ("asa03", "Lucas Zelarayan", 1992, {2020, 2021, 2022}),
    ("asa04", "Darwin Quintero", 1987, {2018, 2019, 2020}),
    ("asa05", "Cristian Espinoza", 1995, {2019, 2020, 2021, 2022}),
    ("asa06", "Walker Zimmerman", 1993, {2018, 2019, 2020, 2021, 2022}),
    ("asa07", "Djordje Mihailovic", 1998, {2018, 2019, 2020, 2021, 2022}),
    ("asa08", "Carlos Vela", 1989, {2018, 2019, 2020, 2021, 2022}),
    ("asa09", "Josef Martinez", 1993, {2018, 2019, 2020, 2021, 2022}),
    ("asa10", "Diego Rossi", 1998, {2018, 2019, 2020, 2021}),
    ("asa11", "Raul Ruidiaz", 1990, {2018, 2019, 2020, 2021, 2022}),
    ("asa12", "Nicolas Lodeiro", 1989, {2018, 2019, 2020, 2021, 2022}),
    ("asa13", "Alejandro Pozuelo", 1991, {2019, 2020, 2021, 2022}),
    ("asa14", "Diego Chara", 1986, {2018, 2019, 2020, 2021, 2022}),
    ("asa15", "Yimmi Chara", 1991, {2020, 2021, 2022}),
    ("asa16", "Cristian Roldan", 1995, {2018, 2019, 2020, 2021, 2022}),
    ("asa17", "Alex Roldan", 1996, {2018, 2019, 2020, 2021, 2022}),
    ("asa18", "Jonathan dos Santos", 1990, {2018, 2019, 2020, 2021}),
    ("asa19", "Sebastian Blanco", 1988, {2018, 2019, 2020, 2021, 2022}),
    ("asa20", "Sean Johnson", 1989, {2018, 2019, 2020, 2021, 2022}),
    ("asa21", "Jesus Medina", 1997, {2018, 2019, 2020, 2021}),
    ("asa22", "Kai Wagner", 1997, {2019, 2020, 2021, 2022}),
    ("asa23", "Luiz Fernando", 1996, {2019, 2020, 2021}),
    ("asa24", "Memo Rodriguez", 1995, {2018, 2019, 2020, 2021}),
], columns=["player_id", "player_name", "birth_year", "seasons"])

RIGHT = pd.DataFrame([
    # right_id, player_name (FBref-style spelling), birth_year, seasons
    ("fb01", "Carles Gil", 1992, {2019, 2020, 2021, 2022}),
    ("fb02", "Hany Mukhtar", 1995, {2020, 2021, 2022}),
    ("fb03", "Lucas Zelarayán", 1992, {2020, 2021, 2022}),          # accent
    ("fb04", "Darwin Quintero", 1987, {2018, 2019, 2020}),
    ("fb05", "Cristian Espinoza", 1995, {2019, 2020, 2021, 2022}),
    ("fb06", "Walker Zimmerman", 1993, {2018, 2019, 2020, 2021, 2022}),
    ("fb07", "Đorđe Mihailović", 1998, {2018, 2019, 2020, 2021, 2022}),  # diacritics
    ("fb08", "Carlos Vela", 1989, {2018, 2019, 2020, 2021, 2022}),
    ("fb09", "Josef Martínez", 1993, {2018, 2019, 2020, 2021, 2022}),    # accent
    ("fb10", "Diego Rossi", 1998, {2018, 2019, 2020, 2021}),
    ("fb11", "Raúl Ruidíaz", 1990, {2018, 2019, 2020, 2021, 2022}),      # accents
    ("fb12", "Nicolás Lodeiro", 1989, {2018, 2019, 2020, 2021, 2022}),
    ("fb13", "Alejandro Pozuelo", 1991, {2019, 2020, 2021, 2022}),
    ("fb14", "Diego Chará", 1986, {2018, 2019, 2020, 2021, 2022}),       # brother trap
    ("fb15", "Yimmi Chará", 1991, {2020, 2021, 2022}),                   # brother trap
    ("fb16", "Cristian Roldán", 1995, {2018, 2019, 2020, 2021, 2022}),   # brother trap
    ("fb17", "Álex Roldán", 1996, {2018, 2019, 2020, 2021, 2022}),       # brother trap
    ("fb18", "Giovani dos Santos", 1989, {2018, 2019}),                  # brother, NOT in LEFT
    ("fb19", "Sebastián Driussi", 1996, {2021, 2022}),                   # shares first name only
    ("fb20", "Sean Davis", 1993, {2018, 2019, 2020, 2021}),              # shares first name only
    ("fb21", "Jesús Ferreira", 2000, {2018, 2019, 2020, 2021, 2022}),    # shares first name only
    ("fb22", "Kai Wagner", 1997, {2019, 2020, 2021, 2022}),
    ("fb23", "Luiz Fernando Jr.", 1996, {2019, 2020, 2021}),             # suffix
    ("fb24", "Memo Rodríguez", 1995, {2018, 2019, 2020, 2021}),          # accent
], columns=["right_id", "player_name", "birth_year", "seasons"])

TRUE_MATCH = {
    "fb01": "asa01", "fb02": "asa02", "fb03": "asa03", "fb04": "asa04",
    "fb05": "asa05", "fb06": "asa06", "fb07": "asa07", "fb08": "asa08",
    "fb09": "asa09", "fb10": "asa10", "fb11": "asa11", "fb12": "asa12",
    "fb13": "asa13", "fb14": "asa14", "fb15": "asa15", "fb16": "asa16",
    "fb17": "asa17",
    "fb18": None,   # Giovani dos Santos never in LEFT; must not bind to Jonathan
    "fb19": None,   # Driussi not in LEFT; must not bind to Blanco
    "fb20": None,   # Sean Davis not in LEFT; must not bind to Sean Johnson
    "fb21": None,   # Jesús Ferreira not in LEFT; must not bind to Jesús Medina
    "fb22": "asa22", "fb23": "asa23", "fb24": "asa24",
}
