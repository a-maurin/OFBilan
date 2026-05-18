# Distribution hors Git

## Kit `ref/` pour un autre poste

Les référentiels sous `ref/programme/` ne sont pas sur GitHub (confidentialité). Pour préparer un envoi :

```powershell
python scripts/pack_ref_distribution.py
```

Cela crée `distribution/Bilans_ref_<date>/` contenant :

- `ref/` — à copier-coller à la racine du dépôt cloné ;
- `LISEZMOI_REF.md` — guide d’installation et rôle de chaque fichier.

Transmettre le dossier par le canal interne habituel (partage réseau, clé USB, etc.), puis zipper si besoin.

Documentation de référence versionnée : `GUIDE_REF_INSTALLATION.md`.
