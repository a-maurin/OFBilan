# Code legacy / obsolète

Ce dossier regroupe les **anciens scripts** conservés à titre d'archive.

Les bilans utilisent désormais :

- le **moteur thématique unifié** `scripts/bilan_thematique/bilan_thematique_engine.py` ;
- le **bilan global** `scripts/bilan_global/analyse_global.py` ;
- les wrappers récents (`scripts/run_bilan.py`, `bilans/cli.py`).

Les anciens scripts dédiés (`bilan_agrainage`, `bilan_chasse`, `bilan_procedures`, anciens générateurs de cartes, etc.)
peuvent être déplacés ici lorsqu'ils ne sont plus utilisés, afin de clarifier ce qui est maintenu.

## Regle de maintenance

- `legacy/` est en lecture/consultation : pas de nouvelles fonctionnalites metier ici ;
- les corrections et evolutions se font uniquement dans les moteurs actifs (`scripts/` et `bilans/`) ;
- en cas de besoin de comparaison, utiliser des scripts de controle (ex. `tools/compare_legacy_vs_new.py`) plutot que reactiver des anciens flux.