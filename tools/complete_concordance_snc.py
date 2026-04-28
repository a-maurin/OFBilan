import csv
import os
import re
import unicodedata
from difflib import SequenceMatcher


BASE = r"c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production"

REF_PATH = os.path.join(BASE, "ref", "Plans de contrôle OSCEAN 2024.csv")
CONC_PATH = os.path.join(BASE, "ref", "concordance_snc_2023_vers_2024.csv")


STOP_WORDS = {
    "controle",
    "controles",
    "relatif",
    "relatifs",
    "relative",
    "relatives",
    "a",
    "au",
    "aux",
    "des",
    "du",
    "de",
    "la",
    "le",
    "les",
    "l",
    "sur",
    "dans",
    "action",
    "snc",
}


def normaliser_texte(s: str) -> str:
    """Normalise un libellé en supprimant accents, crochets, mentions SNC, etc."""
    if not s:
        return ""

    # Minuscules
    s = s.lower()

    # Supprimer mentions [2023], (action X.X de la SNC), (snc X.X)
    s = re.sub(r"\[\d{4}\]\s*", "", s)
    s = re.sub(r"\(action\s*[0-9.]+\s*de la snc\)", "", s)
    s = re.sub(r"\(snc\s*[0-9.]+\)", "", s)

    # Décomposer unicode et enlever les accents
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))

    # Garder lettres / chiffres / espaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)

    # Réduire espaces
    s = re.sub(r"\s+", " ", s).strip()

    # Retirer stop words
    tokens = [t for t in s.split(" ") if t and t not in STOP_WORDS]
    return " ".join(tokens)


def charger_referentiel_2024(
    path: str,
) -> tuple[
    set[tuple[str, str, str]],
    dict[tuple[str, str], set[str]],
    dict[str, list[tuple[str, str, str, str]]],
]:
    """Charge les triplets (domaine, thème, type d'action) du référentiel 2024.

    Retourne :
    - un ensemble de triplets (domaine, thème, type d'action)
    - un dict {(domaine, thème): {type_action1, type_action2, ...}}
    - un dict indexé par type_action_2024 normalisé ->
      liste de tuples (type_action_2024, domaine, thème, type_action_2024_brut)
    """
    ref_set: set[tuple[str, str, str]] = set()
    par_domaine_theme: dict[tuple[str, str], set[str]] = {}
    index_type_action: dict[str, list[tuple[str, str, str, str]]] = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            key = (
                (row.get("domaine") or "").strip(),
                (row.get("thème") or "").strip(),
                (row.get("type d'action") or "").strip(),
            )
            if any(key):
                ref_set.add(key)

                dt = key[0], key[1]
                if dt not in par_domaine_theme:
                    par_domaine_theme[dt] = set()
                if key[2]:
                    par_domaine_theme[dt].add(key[2])
                    norm = normaliser_texte(key[2])
                    index_type_action.setdefault(norm, []).append(
                        (key[2], key[0], key[1], key[2])
                    )

    return ref_set, par_domaine_theme, index_type_action


def completer_concordance(
    conc_path: str,
    ref_set: set[tuple[str, str, str]],
    ref_par_domaine_theme: dict[tuple[str, str], set[str]],
    index_type_action: dict[str, list[tuple[str, str, str, str]]],
) -> int:
    """Complète les lignes de concordance quand la correspondance ne laisse pas de doute.

    Règles :
    1. Si le triplet (domaine, thème, type_action) correspond exactement à 2024 -> on remplit.
    2. Sinon, si (domaine, thème) existe dans le référentiel 2024 et n'est associé
       qu'à un seul type d'action -> on remplit avec ce type d'action unique.
    3. Sinon, on essaie de rapprocher le type d'action ancien du type d'action 2024
       via une similarité sur les libellés normalisés. Si le meilleur match dépasse
       un seuil et est unique -> on remplit.

    Ne remplit que les lignes où domaine_2024 / theme_2024 / type_action_2024 sont vides.
    """
    with open(conc_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    modifications = 0

    for row in rows:
        # Si déjà rempli côté 2024, on laisse tel quel
        if (
            (row.get("domaine_2024") or "").strip()
            or (row.get("theme_2024") or "").strip()
            or (row.get("type_action_2024") or "").strip()
        ):
            continue

        key = (
            (row.get("domaine_ancien") or "").strip(),
            (row.get("theme_ancien") or "").strip(),
            (row.get("type_action_ancien") or "").strip(),
        )
        type_action_ancien = key[2]

        # 1) Correspondance exacte sur le triplet complet
        if key in ref_set:
            d, t, a = key
            row["domaine_2024"] = d
            row["theme_2024"] = t
            row["type_action_2024"] = a
            modifications += 1
            continue

        # 2) Correspondance unique sur (domaine, thème) uniquement
        dt = key[0], key[1]
        types_possibles = ref_par_domaine_theme.get(dt)
        if types_possibles and len(types_possibles) == 1:
            d, t = dt
            (a,) = tuple(types_possibles)
            row["domaine_2024"] = d
            row["theme_2024"] = t
            row["type_action_2024"] = a
            modifications += 1
            continue

        # 3) Similarité sur le type d'action uniquement
        norm_old = normaliser_texte(type_action_ancien)
        if not norm_old:
            continue

        # Calculer la similarité avec tous les types d'action 2024 indexés
        best_score = 0.0
        best_candidate: tuple[str, str, str, str] | None = None

        for norm_new, candidats in index_type_action.items():
            score = SequenceMatcher(None, norm_old, norm_new).ratio()
            if score > best_score:
                best_score = score
                # si plusieurs candidats pour ce norm_new, ce n'est pas "sans doute"
                best_candidate = candidats[0] if len(candidats) == 1 else None

        # Seuil de confiance : à ajuster si besoin
        if best_candidate and best_score >= 0.6:
            type_action_2024, domaine_2024, theme_2024, type_action_2024_brut = (
                best_candidate
            )
            row["domaine_2024"] = domaine_2024
            row["theme_2024"] = theme_2024
            row["type_action_2024"] = type_action_2024_brut
            modifications += 1

    if not fieldnames:
        return modifications

    with open(conc_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    return modifications


def main() -> None:
    ref_set, ref_par_domaine_theme, index_type_action = charger_referentiel_2024(
        REF_PATH
    )
    print(
        "Référentiel 2024 : "
        f"{len(ref_set)} triplets (domaine, thème, type d'action) chargés."
    )
    print(
        f"{len(ref_par_domaine_theme)} couples (domaine, thème) "
        "distincts trouvés dans le référentiel."
    )
    print(f"{len(index_type_action)} libellés de type d'action indexés.")
    modifications = completer_concordance(
        CONC_PATH, ref_set, ref_par_domaine_theme, index_type_action
    )
    print(f"{modifications} lignes de concordance complétées automatiquement.")


if __name__ == "__main__":
    main()

