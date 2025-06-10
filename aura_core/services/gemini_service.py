import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file in the project root
# (Adjust path if .env is located elsewhere relative to this file)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=dotenv_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class GeminiService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            logger.error(
                "GEMINI_API_KEY not found in environment variables or provided. GeminiService will not function.")
            raise ValueError("Gemini API Key not configured.")

        try:
            genai.configure(api_key=self.api_key)
            # Using gemini-1.5-flash for speed and capability balance
            self._model = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("GeminiService initialized successfully with gemini-1.5-flash-latest.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
            self._model = None
            raise ConnectionError(f"Could not configure Gemini: {e}")

    def generate_text_response(self, prompt: str, max_retries: int = 3) -> str | None:
        """
        Generates a text response from Gemini based on the provided prompt.
        """
        if not self._model:
            logger.error("Gemini model not initialized. Cannot generate response.")
            return None

        for attempt in range(max_retries):
            try:
                logger.debug(f"Sending prompt to Gemini (attempt {attempt + 1}):\n{prompt}")
                response = self._model.generate_content(prompt)

                if response and response.candidates:
                    # Accessing text directly based on common Gemini API structure
                    # It's common for the text to be in response.text or response.candidates[0].content.parts[0].text
                    # For gemini-1.5-flash, response.text should work
                    if hasattr(response, 'text') and response.text:
                        logger.info(f"Gemini raw response received: {response.text[:200]}...")  # Log snippet
                        return response.text.strip()
                    else:
                        # Fallback for more complex candidate structures if needed
                        candidate = response.candidates[0]
                        if candidate.content and candidate.content.parts:
                            text_response = "".join(
                                part.text for part in candidate.content.parts if hasattr(part, 'text'))
                            if text_response:
                                logger.info(f"Gemini structured response received: {text_response[:200]}...")
                                return text_response.strip()

                logger.warning(f"Gemini response did not contain expected text structure: {response}")
                return None  # Or handle as an error

            except Exception as e:
                logger.error(f"Error communicating with Gemini API (attempt {attempt + 1}/{max_retries}): {e}",
                             exc_info=True)
                if attempt == max_retries - 1:
                    logger.error("Max retries reached for Gemini API call.")
                    return None
                # Consider adding a small delay before retrying for transient network issues
                # import time; time.sleep(1)
        return None

    def analyze_image_with_prompt(self, image_bytes: bytes, mime_type: str, prompt: str,
                                  max_retries: int = 3) -> str | None:
        """
        Sends an image (as bytes) and a text prompt to Gemini for analysis.
        mime_type: e.g., 'image/png', 'image/jpeg'
        """
        if not self._model:
            logger.error("Gemini model not initialized. Cannot analyze image.")
            return None

        image_part = {
            "mime_type": mime_type,
            "data": image_bytes
        }

        for attempt in range(max_retries):
            try:
                logger.debug(f"Sending image and prompt to Gemini for vision analysis (attempt {attempt + 1}).")
                response = self._model.generate_content([prompt, image_part])  # Order might matter for some models

                if response and response.text:
                    logger.info(f"Gemini vision response received: {response.text[:200]}...")
                    return response.text.strip()
                elif response and response.candidates:  # Fallback if .text isn't directly available
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        text_response = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                        if text_response:
                            logger.info(f"Gemini vision structured response received: {text_response[:200]}...")
                            return text_response.strip()

                logger.warning(f"Gemini vision response did not contain expected text structure: {response}")
                return None

            except Exception as e:
                logger.error(f"Error in Gemini vision API call (attempt {attempt + 1}/{max_retries}): {e}",
                             exc_info=True)
                if attempt == max_retries - 1:
                    logger.error("Max retries reached for Gemini vision API call.")
                    return None
        return None


# Example Usage (for testing this service standalone)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    try:
        gemini_service = GeminiService()
        if gemini_service._model:  # Check if model loaded
            test_prompt = "What is the capital of France? Respond in one sentence."
            print(f"\nTesting text generation with prompt: '{test_prompt}'")
            response_text = gemini_service.generate_text_response(test_prompt)
            if response_text:
                print(f"Gemini Response: {response_text}")
            else:
                print("Failed to get a response from Gemini.")

            # To test vision, you'd need an image file
            # try:
            #     image_path = "path_to_your_test_image.png" # Replace with a real image path
            #     with open(image_path, "rb") as img_file:
            #         img_bytes = img_file.read()
            #     vision_prompt = "What is in this image?"
            #     print(f"\nTesting vision analysis with prompt: '{vision_prompt}'")
            #     vision_response = gemini_service.analyze_image_with_prompt(img_bytes, "image/png", vision_prompt)
            #     if vision_response:
            #         print(f"Gemini Vision Response: {vision_response}")
            #     else:
            #         print("Failed to get a vision response from Gemini.")
            # except FileNotFoundError:
            #     print(f"Test image not found at {image_path}. Skipping vision test.")
            # except Exception as e:
            #     print(f"Error during vision test: {e}")

    except ValueError as e:
        print(f"Configuration error: {e}")
    except ConnectionError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")