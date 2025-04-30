'''Modul zur Klassifizierung des Nutzer-Intents.'''

class IntentClassifier:
    '''Klassifiziert den Intent einer Nutzereingabe.'''

    def __init__(self):
        '''Initialisiert den IntentClassifier mit Schlüsselwörtern für jeden Intent.'''
        self.intent_keywords = {
            "code": ["code", "programmieren", "api", "funktion", "klasse", "script", "fehler", "debug", "python", "javascript", "java", "c++", "html", "css", "sql", "datenbank", "automatisieren", "algorithmus", "framework", "bibliothek"],
            "tech_support": ["problem", "hilfe", "fehler", "installieren", "konfigurieren", "netzwerk", "hardware", "software", "treiber", "absturz", "langsam", "einstellung", "router", "drucker", "computer", "laptop", "server", "system", "update"],
            "knowledge": ["was ist", "wer ist", "erkläre", "definition", "bedeutung", "wissen", "fakten", "geschichte", "wie funktioniert", "unterschied", "vergleich"],
            # "chat" ist der Standard-Intent, falls keine anderen Schlüsselwörter passen
        }

    def classify_intent(self, user_input: str) -> str:
        '''Bestimmt den Intent der Nutzereingabe basierend auf Schlüsselwörtern.

        Args:
            user_input: Die Eingabe des Nutzers.

        Returns:
            Der erkannte Intent ("code", "tech_support", "knowledge", "chat").
        '''
        user_input_lower = user_input.lower()

        for intent, keywords in self.intent_keywords.items():
            if any(keyword in user_input_lower for keyword in keywords):
                return intent

        # Wenn keine spezifischen Schlüsselwörter gefunden werden, ist es Smalltalk/Chat
        return "chat" 