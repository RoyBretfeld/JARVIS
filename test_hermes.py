from data.models.hermes.hermes_runner import query_hermes

antwort = query_hermes("Hermes, was kannst du?")
print("------ RAW OUTPUT ------")
print(repr(antwort))
print("------ Klartext --------")
print(antwort)
