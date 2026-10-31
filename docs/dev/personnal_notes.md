This is like a journal de bord.

I will take notes about evertything I would likle to keep, that could be useful to remember.

# Oct,15 26

My 1st /ask-matt interaction

```markdown
/mattpocock-skills:ask-matt I want to start a new project (in English, be nice this is not my native language (I am Frenech)). I have been using google photos (and before that picasa web) for a long time, more than 20 years. I have many many albums shared with lots of captions on photos and comments from family. I would like to host those under my Nas, and by host I mean all albums, photos, captions, comments, ... everything. My NAS is a synology DS 923. I can export all my google photos data (photos + metadata) from google (it was about 15 GB last time I asked for this export) , that will be the starting point of this journey. Help me create and run everything needed to get the final result. And I would like to document, explain all steps so that other users can do the same
```

The full path

1. /wayfinder: answer the open questions (Takeout content, what Synology Photos supports, the import strategy).
2. /to-spec: turn the decisions into one clear plan.
3. /to-tickets: split the plan into small GitHub issues.
4. /implement on each ticket: Python code, written test-first, with tests and a review. Clear the context between tickets.
5. The documentation for other users is written during the work, in the existing MkDocs site: user guides go in docs/user/, technical details go in docs/dev/.

Some steps need you: asking Google for the export, the NAS admin settings, family accounts. For those I can use /wizard, which makes a guided script that walks you through each step.


I am starting the takeout procedure

> Google crée une copie des données de Google Photos
> Ce processus est long et peut prendre des heures, voire des jours. Vous recevrez un e-mail une fois l'exportation terminée.
> Création : 15 octobre 2026, 22:13

First 15 questions with /wayfinder

This leads to a map and 7 issues : https://github.com/castorfou/google-to-synology-photos/issues

Matt completed the research part of the map. 4 tickets.

https://github.com/jaimetur/PhotoMigrator is a good catch, maybe what I try to do already exists.
But I guess I could learn a lot by developping mine.


Where the map is now
Done: the 4 research tickets.
Waiting for you: Get a fresh Takeout Export into data/raw. Everything else waits for this export.
Then:
Inspect the real Takeout Export: I do it alone.
Which app holds the NAS Library? and How do photos from other Contributors reach the NAS Library?: decisions we make together.
Test Synology Photos metadata on the DS923: small tests on your NAS, only if Synology Photos is kept.
The four research reports are on their own research/... branches, not on main. Their temporary working copies are still in .claude/worktrees/. You can delete those folders, because the branches are pushed to GitHub. CONTEXT.md is still not committed.

!!! info "next step"

    When your export is in data/raw/, start a new session with /mattpocock-skills:wayfinder #1.

Interesting, /matt is working by creating branches with results for each issues, and they don't mean to be merged (throwaway on purpose)

> Wayfinder treats these branches as throwaway on purpose. Each one holds one research report, a source for a decision. The report is not part of the product. Each closed ticket and the map link to the report on its branch, so the branches must stay, or those links break.
> They should not go into main as they are. These reports are notes from a moment in time ("latest release 2026-09", "uncertain"…). The project rules in CLAUDE.md say the documentation in docs/ must describe the current system, without that kind of history. Also, mkdocs build --strict could complain about pages that are not in the menu.
> What is useful will reach main later, in the right form. When we write the spec with /to-spec, and then the docs, the useful facts get rewritten in docs/user/ and docs/dev/, for example "Synology Photos reads the Caption from EXIF ImageDescription". Each fact will carry a link to the research report as its source.


# Oct, 29 26

the wayfinder is now completed

the map is closed : https://github.com/castorfou/google-to-synology-photos/issues/1

I have just invoqued /to-spec

Result is in https://github.com/castorfou/google-to-synology-photos/issues/28

Next steps

> D'après `ask-matt`, tu sors de la map par le bon côté : wayfinder, puis `/to-spec`, puis `/to-tickets`, puis l'implémentation.
>
> **1. Maintenant, dans cette même session : `/mattpocock-skills:to-tickets #28`**
>
> Ce skill découpe la spec en tickets **« tracer bullet »**. Chacun traverse toutes les couches de bout en bout, est vérifiable seul, tient dans une session, et déclare les tickets qui le bloquent, sous forme de vrais liens de blocage GitHub.
>
> Lance-le **avant de vider le contexte** : la spec et toutes les décisions sont encore chargées ici. Il ne peut pas se lancer seul, c'est à toi de taper la commande.
>
> **2. Ensuite, pour chaque ticket, choisis une des deux façons :**
> - **`/clear`, puis `/mattpocock-skills:implement #<ticket>`**, en commençant par les tickets qui n'ont pas de bloqueur. Chaque ticket repart d'un contexte vide. Il passe par `/tdd` sur la seam qu'on a validée (l'import complet contre le faux Synology Photos), puis par `/code-review`.
  > - Attention : `implement` commite sur la branche courante, sans push ni PR. Crée d'abord une branche par ticket, et ouvre la PR à la fin, car tu ne fusionnes que par PR.
  > - Sinon, la commande du projet **`/fix-issue <n>`** fait tout l'enchaînement d'un coup : branche, TDD, contrôles qualité, doc et PR.
> - **`/mattpocock-skills:implement-spec #28`** : il orchestre toute la spec en une fois. Il lance des sous-agents en parallèle sur les tickets prêts, met tout sur une seule branche d'intégration, puis fait une seule revue de code. Il convient si tu préfères superviser plutôt que piloter ticket par ticket. C'est plus rapide, mais tu as moins la main sur chaque étape.
>
> Je te recommande **ticket par ticket avec `/fix-issue`**, au moins pour les 2 ou 3 premiers. Ce sont eux qui posent la structure (CLI, faux NAS, lecture du Takeout) sur laquelle tout le reste s'appuie, et ça vaut le coup de les relire de près.
>
> **3. À la fin du build : `/mattpocock-skills:retro`**, dans la même session, avant de vider le contexte. Il propose des améliorations de l'environnement de travail (contrôles automatiques, standards de code), pas du code lui-même.


Pour démarrer : /clear, puis /fix-issue 29 pour le tracer bullet. Une fois qu'il est fusionné, les tickets 30 à 33 peuvent se faire en parallèle.


Tu es dans la boucle « un `/implement` par ticket » du flux principal. #29 et #30 sont faits, il reste 8 tickets plus la spec #28. Voici leurs dépendances sur GitHub :

```text
#31 Comments & Likes ──────────────┬──► #36 Refresh Albums/texte ──┬──► #37 Refresh edits/vidéos/dates ──┐
#32 Full Takeout Export ──► #35 Idempotent/reprise ──┘              │                                     ├──► #39 Docs
#33 Dates/GPS ──► #34 Vidéos MP4 ───────────────────────────────────┘                                     │
                                          #31 + #36 ──► #38 Album Downloads ─────────────────────────────┘
```

**Trois tickets sont prêts tout de suite : #31, #32 et #33.**

**Je recommande #32 (Full Takeout Export shape) en premier.** C'est le début de la plus longue chaîne : #32 → #35 → #36 → #37 → #39. #35 corrigera aussi une limite connue, le compteur d'uploads qui compte les fichiers déjà présents. Ensuite #33 puis #34, qui mènent à #37 par l'autre branche. #31 peut passer n'importe quand avant #36.

**Pour le déroulé :**
1. **`/retro` maintenant (optionnel)**, avant d'effacer le contexte. Le #30 a eu plusieurs surprises sur l'API du NAS, par exemple l'overwrite impossible et les descriptions ignorées. On pourrait en tirer des règles pour l'environnement de travail.
2. **`/clear`**, puis **`/mattpocock-skills:implement #32`**. Chaque ticket repart d'un contexte vide : tout ce qu'il faut est dans le ticket et dans `docs/dev/`.
3. Même cycle pour la suite, toujours avec PR et fusion sur GitHub.

Une autre option est `/implement-spec #28`, qui enchaîne tous les tickets restants en parallèle sur une branche d'intégration. Je ne la conseille pas ici : le contrat contre le DS923 n'accepte pas plusieurs runs en même temps, et ta validation PR par PR serait perdue.

On lance `/retro`, ou directement #32 ?

# Oct,31 26

La PR #42 est fusionnée sur GitHub (commit `5161ec4`), avec ton commit de notes et une CI verte sur son dernier commit. La branche est supprimée et ton `main` local est à jour.

La suite recommandée est `/clear`, puis `/mattpocock-skills:implement #32`.
