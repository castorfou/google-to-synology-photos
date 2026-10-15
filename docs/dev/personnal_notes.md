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
