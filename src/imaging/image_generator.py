import vertexai
from vertexai.preview.vision_models import ImageGenerationModel, ImageGenerationResponse
import logging
import base64

logger = logging.getLogger(__name__)

class ImageGenerator:
    """Generiert Bilder mithilfe der Google Vertex AI Imagen API."""

    def __init__(self, config):
        """Initialisiert den ImageGenerator."""
        self.config = config
        self.project_id = self.config.get("gcp.project_id")
        self.location = self.config.get("gcp.location", "us-central1") # Standard-Standort
        self.model = None
        self.is_initialized = False

        if not self.project_id:
            logger.error("Google Cloud Projekt-ID fehlt in der Konfiguration (gcp.project_id).")
            return
            
        try:
            vertexai.init(project=self.project_id, location=self.location)
            self.model = ImageGenerationModel.from_pretrained("imagegeneration@005") # Beispielmodell, ggf. anpassen
            self.is_initialized = True
            logger.info(f"ImageGenerator initialisiert für Projekt '{self.project_id}' in '{self.location}'.")
        except Exception as e:
            logger.error(f"Fehler bei der Initialisierung von Vertex AI: {e}", exc_info=True)
            self.is_initialized = False

    def generate_image(self, prompt: str, number_of_images: int = 1) -> list[str] | None:
        """
        Generiert Bilder basierend auf dem gegebenen Prompt.

        Args:
            prompt: Der Text-Prompt für die Bildgenerierung.
            number_of_images: Die Anzahl der zu generierenden Bilder (max. 8 laut API).

        Returns:
            Eine Liste von Base64-kodierten Bild-Strings (PNG) oder None bei einem Fehler.
        """
        if not self.is_initialized or not self.model:
            logger.error("ImageGenerator ist nicht initialisiert.")
            return None

        if not prompt:
            logger.warning("Leerer Prompt für Bildgenerierung erhalten.")
            return None
            
        # API erlaubt max. 8 Bilder
        num_images = max(1, min(number_of_images, 8))
        
        logger.info(f"Generiere {num_images} Bild(er) für Prompt: '{prompt[:100]}...'")
        
        try:
            response: ImageGenerationResponse = self.model.generate_images(
                prompt=prompt,
                number_of_images=num_images,
                # Weitere Parameter können hier hinzugefügt werden (z.B. negative_prompt, seed, aspect_ratio)
            )
            
            base64_images = []
            if response.images:
                for image in response.images:
                    # Die API gibt das Bild als _Image Objekt zurück, das base64-Daten enthält
                    # Zugriff auf die Bytes und dann Base64-Kodierung
                    # Annahme: image._blob enthält die PNG-Bytes
                    if hasattr(image, '_blob') and image._blob:
                        base64_images.append(base64.b64encode(image._blob).decode('utf-8'))
                    else:
                         logger.warning("Generiertes Bildobjekt enthält keine erwarteten Bilddaten (_blob).")
                
                if base64_images:
                    logger.info(f"{len(base64_images)} Bild(er) erfolgreich generiert.")
                    return base64_images
                else:
                     logger.error("Bildgenerierung lieferte keine gültigen Bilddaten.")
                     return None
            else:
                logger.error("Keine Bilder in der API-Antwort gefunden.")
                return None
                
        except Exception as e:
            logger.error(f"Fehler bei der Bildgenerierung mit Vertex AI: {e}", exc_info=True)
            return None 