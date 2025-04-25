import pickle
import os
import logging
from river import compose, feature_extraction, naive_bayes
from typing import Optional

# Configure logging for this module
logger = logging.getLogger(__name__)

class RiverLearningManager:
    """
    Manages online text classification learning using the River library.

    This class implements a pipeline using BagOfWords and Multinomial Naive Bayes
    to classify text incrementally and persists the model periodically.
    """

    def __init__(self, model_path="data/learning/river_model.pkl", save_interval=10):
        """
        Initializes the manager, loads an existing model, or creates a new pipeline.

        Args:
            model_path (str): Path to save/load the pickled model.
            save_interval (int): Save the model every N learn calls.
        """
        self.model_path = model_path
        self.save_interval = save_interval
        self.learn_count = 0
        self.model: Optional[compose.Pipeline] = None

        self.load_model()  # Try loading existing model first

        if self.model is None:
            logger.info("No existing River model found or load failed. Building a new pipeline.")
            self.model = self._build_pipeline()
        else:
            logger.info(f"Successfully loaded River model from {self.model_path}")

    def _build_pipeline(self) -> compose.Pipeline:
        """Builds the River pipeline for text classification."""
        return compose.Pipeline(
            ('bow', feature_extraction.BagOfWords(lowercase=True)),
            ('nb', naive_bayes.MultinomialNB())
        )

    def learn(self, text: str, label: str):
        """
        Updates the online model with a new text sample and its label.

        Args:
            text (str): The input text.
            label (str): The correct label for the text.
        """
        if self.model is None:
            logger.error("River model is not initialized. Cannot learn.")
            return

        try:
            self.model.learn_one(text, label)
            self.learn_count += 1
            logger.debug(f"River learned: '{text[:50]}...' -> {label}. Learn count: {self.learn_count}")

            # Save model periodically
            if self.learn_count % self.save_interval == 0:
                logger.info(f"Reached save interval ({self.save_interval}). Saving River model.")
                self.save_model()
        except Exception as e:
            logger.error(f"Error during River learning for text '{text[:50]}...': {e}", exc_info=True)

    def predict(self, text: str) -> Optional[str]:
        """
        Predicts the label for a given text using the online model.

        Args:
            text (str): The input text to classify.

        Returns:
            Optional[str]: The predicted label, or None if prediction fails.
        """
        if self.model is None:
            logger.error("River model is not initialized. Cannot predict.")
            return None
        try:
            prediction = self.model.predict_one(text)
            logger.debug(f"River predicted: '{text[:50]}...' -> {prediction}")
            return prediction
        except Exception as e:
            # Might happen if the model encounters unseen words etc.
            logger.warning(f"Error during River prediction for text '{text[:50]}...': {e}", exc_info=True)
            return None

    def save_model(self):
        """Saves the current River model pipeline to a pickle file."""
        if self.model is None:
            logger.warning("Attempted to save a non-existent River model.")
            return
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"River model successfully saved to {self.model_path}")
        except (IOError, pickle.PicklingError, Exception) as e:
            logger.error(f"Error saving River model to {self.model_path}: {e}", exc_info=True)

    def load_model(self):
        """Loads the River model pipeline from a pickle file if it exists."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                # Optionally reset learn count if needed, but saving interval works on new learns
                logger.info(f"River model loaded successfully from {self.model_path}")
            except (FileNotFoundError, pickle.UnpicklingError, EOFError, Exception) as e:
                logger.error(f"Error loading River model from {self.model_path}: {e}", exc_info=True)
                self.model = None # Ensure model is None if loading fails
        else:
            logger.info(f"River model file not found at {self.model_path}. A new model will be built.")
            self.model = None

# Example Usage (can be removed or kept for testing)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) # Enable debug logging for testing
    
    # Create or load the manager
    # Use a forward slash for the path, which works on both Windows and Linux
    river_manager = RiverLearningManager(model_path="data/learning/river_model.pkl")

    # Sample data
    samples = [
        ("Wie ist das Wetter heute?", "Frage"),
        ("Spiele Musik von den Beatles", "Befehl"),
        ("Hallo wie gehts?", "Smalltalk"),
        ("Was ist die Hauptstadt von Frankreich?", "Frage"),
        ("Schalte das Licht im Wohnzimmer ein", "Befehl"),
        ("Erzähl mir einen Witz", "Befehl"), # Could also be 'Frage' depending on nuance
        ("Schöner Tag heute", "Smalltalk"),
        ("Wer bist du?", "Frage"),
        ("Stopp die Musik", "Befehl"),
        ("Danke, das war hilfreich", "Smalltalk"),
        ("Erinnere mich daran, Mama anzurufen", "Befehl"), # 11th item, should trigger save
        ("Was gibt es Neues?", "Frage")
    ]

    # Learn from samples
    print("--- Learning --- ")
    for text, label in samples:
        river_manager.learn(text, label)

    # Predict new samples
    print("\n--- Predicting --- ")
    test_texts = [
        "Wie spät ist es?",
        "Mach lauter",
        "Alles klar bei dir?",
        "Setze Timer auf 5 Minuten"
    ]
    for text in test_texts:
        prediction = river_manager.predict(text)
        print(f"'{text}' -> Predicted: {prediction}")

    # Test loading again (optional)
    print("\n--- Reloading and Predicting --- ")
    river_manager_reloaded = RiverLearningManager(model_path="data/learning/river_model.pkl")
    for text in test_texts:
        prediction = river_manager_reloaded.predict(text)
        print(f"'{text}' -> Predicted (reloaded): {prediction}") 