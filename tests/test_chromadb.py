import chromadb
import os
import numpy as np

# --- Konfiguration ---
DB_PATH = "./data/chroma_test_db"  # Speicherort für die Test-DB
COLLECTION_NAME = "my_test_collection"
EMBEDDING_DIM = 3 # Nur für dieses Beispiel eine kleine Dimension

# --- Hilfsfunktion für Dummy-Vektoren ---
def get_dummy_vector(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """ Erzeugt einen einfachen, reproduzierbaren Vektor basierend auf dem Text. """
    # Einfacher Hash-basierter Ansatz für Demo-Zwecke
    seed = hash(text) % (2**32)
    rng = np.random.RandomState(seed)
    vector = rng.rand(dim).astype(float).tolist()
    # Normalisieren (optional, aber oft gut für Kosinus-Ähnlichkeit)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = (np.array(vector) / norm).tolist()
    return vector

# --- Haupt-Testlogik ---
print("Starte ChromaDB Test...")

# 1. Stelle sicher, dass das DB-Verzeichnis existiert
os.makedirs(DB_PATH, exist_ok=True)
print(f"Verwende DB-Pfad: {os.path.abspath(DB_PATH)}")

try:
    # 2. Initialisiere den persistenten Client
    #    PersistentClient speichert Daten auf der Festplatte im angegebenen Pfad.
    client = chromadb.PersistentClient(path=DB_PATH)
    print("ChromaDB Client initialisiert.")

    # 3. Erstelle oder lade eine Collection
    #    get_or_create_collection gibt die Collection zurück, falls sie existiert,
    #    oder erstellt sie neu.
    print(f"Erstelle/Lade Collection: {COLLECTION_NAME}")
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    print("Collection erhalten.")

    # 4. Bereite Beispieldaten vor
    print("Bereite Beispieldaten vor...")
    documents = [
        "Das ist der erste Satz.",
        "Hier kommt ein zweiter Satz zum Testen.",
        "Ein dritter Satz mit anderen Worten.",
        "Äpfel und Birnen sind Früchte.",
        "Das Wetter ist heute schön.",
    ]
    embeddings = [get_dummy_vector(doc) for doc in documents]
    metadatas = [{"source": f"doc_{i+1}"} for i in range(len(documents))]
    ids = [f"id_{i+1}" for i in range(len(documents))]

    print(f" - Dokumente: {documents}")
    # print(f" - Embeddings (Beispiel): {embeddings[0]}...") # Zu lang für Konsolenausgabe
    print(f" - Metadaten: {metadatas}")
    print(f" - IDs: {ids}")

    # 5. Füge Daten zur Collection hinzu
    print("Füge Daten zur Collection hinzu...")
    # Verwende add() - upsert() würde Einträge mit gleicher ID aktualisieren
    collection.add(
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print(f"{collection.count()} Einträge hinzugefügt/aktualisiert.")

    # 6. Bereite eine Test-Abfrage vor
    print("\nFühre eine Test-Abfrage durch...")
    query_text = "Ein Satz über Obst"
    query_embedding = get_dummy_vector(query_text)
    print(f" - Suche nach Ähnlichkeit zu: '{query_text}'")
    # print(f" - Query Embedding: {query_embedding}")

    # 7. Führe die Abfrage durch
    #    Suche nach den 2 ähnlichsten Einträgen
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
        # Optional: Filter hinzufügen: where={"source": "doc_4"}
    )

    # 8. Gib die Ergebnisse aus
    print("\n--- Abfrageergebnisse ---")
    if results and results.get('ids') and results['ids'][0]:
        print(f" - Gefundene IDs: {results['ids'][0]}")
        print(f" - Ähnlichste Dokumente: {results['documents'][0]}")
        print(f" - Zugehörige Metadaten: {results['metadatas'][0]}")
        print(f" - Distanzen: {results['distances'][0]} (Kleinere Distanz = ähnlicher)")
    else:
        print("Keine Ergebnisse gefunden.")

    # 9. Test: Client neu laden und Daten prüfen (Persistenz)
    print("\nPrüfe Persistenz...")
    client_reloaded = chromadb.PersistentClient(path=DB_PATH)
    collection_reloaded = client_reloaded.get_collection(name=COLLECTION_NAME)
    count = collection_reloaded.count()
    print(f"Anzahl Einträge nach Neuladen: {count}")
    if count == len(documents):
        print("Persistenztest erfolgreich!")
    else:
        print("FEHLER: Persistenztest fehlgeschlagen!")

    # Optional: Collection leeren/löschen für sauberen Zustand nach Test
    # print("\nLösche Test-Collection...")
    # client.delete_collection(name=COLLECTION_NAME)
    # print("Test-Collection gelöscht.")


except Exception as e:
    print(f"\n--- FEHLER im Testskript ---")
    import traceback
    traceback.print_exc()

print("\nChromaDB Test beendet.") 