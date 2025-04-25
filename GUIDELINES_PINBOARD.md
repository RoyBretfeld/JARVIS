
# 🧭 Leitfaden & Regeln für Konsistenz mit LLM und Cursor (JARVIS)

---

## 🔹 1. Komponentenverantwortung

| Komponente         | Verantwortung                                                                 |
|--------------------|------------------------------------------------------------------------------|
| AudioProcessor     | Nur Audiofluss (Input -> Transkription), keine Interpretation                 |
| WhisperRecognizer  | Reiner Speech-to-Text, keine Logik                                            |
| LLMManager         | Kontextaufbau, Prompt-Erstellung, LLM-Kommunikation                           |
| LearningManager    | Lernen: semantische Suche, Speichern von Wissen (Embeddings, ChromaDB)        |
| GUI (MainWindow)   | Darstellung & Steuerung, keine Geschäftslogik                                 |

📌 **Jede Komponente erfüllt nur ihre Aufgabe – kein Überschneiden!**

---

## 🔹 2. Ablauf: Transkript → Kontext → LLM → Antwort → Lernen

1. Audio wird aufgenommen und transkribiert
2. Transkript → LLMManager → Prompt + Kontext (via LearningManager)
3. Prompt → LLM → Antwort
4. Transkript + Antwort → LearningManager (Embedding & Speicherung)

📌 **Kein Prompt ohne Kontext & kein Lernen ohne vollständiges Paar (Frage + Antwort).**

---

## 🔹 3. LearningManager – Regeln für zuverlässiges Speichern

- IDs strukturieren: `f"{timestamp}_{hash(query)[:8]}"`
- `search_similar`: minimum Query-Länge = 3 Tokens
- Similarity-Threshold: `>= 0.7`
- Keine irrelevanten Resultate als Kontext verwenden
- Keine Duplikate speichern (ID prüfen)

📌 **Nur echte, relevante Information wird gespeichert.**

---

## 🔹 4. Logging & Sanity Checks

- Logge nach jedem wichtigen Schritt:
  - Anzahl Einträge
  - Ähnlichkeitswert (bei `query`)
  - ID + Ausschnitt des Texts
- Prüfung der LLM-Antwort:
  - `len(answer) > 10`
  - Kein Echo oder Nonsense

📌 **Logik nur als gültig markieren, wenn alle Checks bestanden wurden.**

---

## 🔹 5. Antwortvalidierung – Schutz vor Inkonsistenzen

- Kontext darf nicht doppelt verwendet werden
- Vermeide Lernen, wenn:
  - Antwort nicht zur Frage passt
  - Antwort zu allgemein ist
  - LLM „halluziniert“ oder wiederholt sich

📌 **Lernen nur bei hoher Relevanz und neuem Input.**

---

## 🔹 6. Formatierung & Validierung

- Vor LLM oder Speicherprozessen:
  - `sanitize_text()` anwenden
  - Leerzeichen trimmen
  - Sonderzeichen und Emojis entfernen
- Prüfen, ob Text überhaupt vorhanden ist

📌 **Nur bereinigte und geprüfte Texte weitergeben.**

---

## 🔹 7. Commit-Prinzip fürs Lernen

Vor jedem Speichern:

```python
if llm_response and relevance_score > 0.7 and not flagged:
    learning_manager.upsert(...)
else:
    logger.warning("Kein gültiges Lernergebnis – nicht gespeichert.")
```

📌 **Entscheidungspunkte: Lernen nur bei Validität. Keine halben Daten akzeptieren.**

---

## 🔹 Empfehlung zum Anpinnen

- Speichere diese Datei als `GUIDELINES.md` oder `PINBOARD.md`
- Hänge sie ins Root-Repo + in den Debug/Sidebar-Modus einbauen
- Zeige die Regeln ggf. als Info-Panel in der GUI an (für Live-Checks)

---

✅ Diese Regeln helfen, dass der Assistent vorne wie hinten konsistent bleibt. Keine „KI-Schizophrenie“! 😉
