# Purge du commit orphelin contenant un message privé

## Contexte

Le commit `b12d07930984e15cf3416663e4eccabc52635f1e` a été retiré de la branche `main`
(message corrigé en `704c8cb`), mais GitHub conserve encore l’objet accessible par URL directe :

https://github.com/a-maurin/Bilans_production/commit/b12d07930984e15cf3416663e4eccabc52635f1e

Un simple `git push --force` ne supprime pas ce cache côté GitHub.

## Actions à faire sur GitHub (obligatoire)

1. Ouvrir : https://support.github.com/contact
2. Choisir **« Remove sensitive data cached in my repository »** (ou équivalent sécurité).
3. Indiquer :
   - Dépôt : `a-maurin/Bilans_production`
   - SHA à purger : `b12d07930984e15cf3416663e4eccabc52635f1e`
   - Nature : message de commit contenant une correspondance professionnelle privée (nom d’un collègue).
4. En attendant la purge, envisager de passer le dépôt en **privé** (Settings → Danger zone / Change visibility).

## Nettoyage local (déjà recommandé)

```powershell
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Prévention

- Ne jamais coller un e-mail ou un message Teams dans `git commit -m "..."`.
- Utiliser `git commit` sans `-m` (éditeur) ou `git commit -F message.txt`.
