# Incident : message privé dans un message de commit

## Contexte (résolu)

Un message de courriel professionnel avait été collé par erreur dans le message du commit
`b12d07930984e15cf3416663e4eccabc52635f1e`. Ce commit avait ensuite été retiré de `main`,
mais restait accessible par URL directe sur GitHub.

## Résolution retenue

Le dépôt GitHub `a-maurin/Bilans_production` a été **supprimé puis recréé**, puis l’historique
local propre a été repoussé (`main`). L’ancienne URL du commit orphelin renvoie désormais **404**.

## Prévention

- Ne jamais coller un e-mail ou un message Teams dans `git commit -m "..."`.
- Utiliser `git commit` sans `-m` (éditeur) ou `git commit -F message.txt`.

## Si le problème se reproduit sur un dépôt à conserver

- Réécrire l’historique (`git filter-repo`) puis `git push --force-with-lease`.
- Ou supprimer/recréer le dépôt s’il n’y a pas d’issues/PR à préserver.
- En dernier recours : demande de purge du cache à https://support.github.com/contact
  (procédure « dépôt que vous contrôlez », pas le formulaire « droits d’auteur »).
