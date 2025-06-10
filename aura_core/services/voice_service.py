import os
import threading
import time
import logging
import struct  # For converting audio frames
import wave  # For saving audio to pass to whisper

import pyaudio
import pvporcupine
from dotenv import load_dotenv
import openai  # For Whisper
import numpy as np

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Configuration
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
# For built-in keywords, pvporcupine.KEYWORDS gives a list.
# We can use 'porcupine' or 'grasshopper' or 'hey siri' etc.
# Let's use 'porcupine' as a placeholder.
# You can find the .ppn files in the pvporcupine package directory or download custom ones.
# For simplicity, we'll try to use built-in keyword paths if possible.
# If you create a custom "Hey Aura.ppn", you'll set KEYWORD_FILE_PATHS to its path.
KEYWORD_NAMES = ["porcupine"]  # Example, use a keyword available in your Porcupine installation
# To find paths to built-in keywords:
# from pvporcupine import KEYWORD_PATHS
# print(KEYWORD_PATHS) # This will show available built-in keyword paths
# For now, let's assume 'porcupine.ppn' is found by the library if we just pass the keyword name.
# If not, you'll need to specify the full path to the .ppn file.
# KEYWORD_FILE_PATHS = [pvporcupine.KEYWORD_PATHS[kw] for kw in KEYWORD_NAMES]

# Whisper Configuration
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base.en")  # "tiny.en", "base.en", "small.en"
COMMAND_RECORD_DURATION_SECONDS = 7  # Max duration to record for a command
SILENCE_THRESHOLD = 500  # Adjust based on microphone sensitivity (amplitude)
SILENCE_DURATION_SECONDS = 2  # Seconds of silence to stop recording command


class VoiceService:
    def __init__(self, on_wake_word_detected_callback=None, on_transcription_complete_callback=None, on_listening_status_callback=None):
        if not PICOVOICE_ACCESS_KEY:
            logger.error("PICOVOICE_ACCESS_KEY not found in .env file. Voice service will not start.")
            raise ValueError("Picovoice AccessKey not configured.")

        self.on_wake_word_detected_callback = on_wake_word_detected_callback
        self.on_transcription_complete_callback = on_transcription_complete_callback
        self.on_listening_status_callback = on_listening_status_callback

        self._running = False
        self._audio_thread = None
        self._porcupine = None
        self._pyaudio_instance = None
        self._audio_stream = None

        # --- MODIFIED PORCUPINE KEYWORD LOGIC ---
        # Configuration for your custom keyword
        # Make sure the spelling of "assets" is correct here and in your filesystem
        CUSTOM_KEYWORD_NAME = "Hey cc" # The phrase you trained
        # Corrected path based on your provided path (ensure 'assets' not 'assests')
        custom_keyword_file_path = os.path.join(
            os.path.dirname(__file__),  # .../aura_core/services/
            "..",                       # .../aura_core/
            "..",                       # .../aura_project/
            "assets",                   # Corrected from 'assests' if that was a typo
            "porcupine_models",
            "Hey-cc_en_windows_v3_0_0.ppn" # Your specific .ppn file
        )

        keyword_paths_to_use = None
        keywords_to_use = None

        if os.path.exists(custom_keyword_file_path):
            logger.info(f"Custom keyword file found: {custom_keyword_file_path}")
            keyword_paths_to_use = [custom_keyword_file_path]
            # Porcupine SDK expects 'keywords' argument to be None if 'keyword_paths' is provided with custom models.
            # However, for logging and internal reference, we can use CUSTOM_KEYWORD_NAME.
            # The actual keyword name embedded in the .ppn file will be used by Porcupine.
            KEYWORD_NAMES[0] = CUSTOM_KEYWORD_NAME # Update global for logging consistency
        else:
            logger.warning(f"Custom keyword file NOT found at '{custom_keyword_file_path}'. Falling back to built-in keywords.")
            # Fallback to built-in keyword (e.g., "porcupine")
            default_keyword_name = "porcupine"
            if default_keyword_name in pvporcupine.KEYWORD_PATHS:
                keyword_paths_to_use = [pvporcupine.KEYWORD_PATHS[default_keyword_name]]
                KEYWORD_NAMES[0] = default_keyword_name
                logger.info(f"Using built-in keyword: '{default_keyword_name}' with path: {keyword_paths_to_use[0]}")
            else:
                logger.error(f"Built-in keyword '{default_keyword_name}' not found either. Porcupine might fail.")
                # Attempt to initialize with just the keyword name, Porcupine might find it
                keywords_to_use = [default_keyword_name] # This will use keyword_names arg instead of keyword_paths

        try:
            self._porcupine = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keyword_paths=keyword_paths_to_use, # This will be a list with your custom path, or built-in
                keywords=keywords_to_use          # This will be None if custom_keyword_path is used, or a list of names
            )
            # KEYWORD_NAMES[0] should now reflect what's actually being used
            log_keyword_name = KEYWORD_NAMES[0]
            log_keyword_path_info = f"with paths: {keyword_paths_to_use}" if keyword_paths_to_use else f"with names: {keywords_to_use}"
            logger.info(f"Porcupine initialized for keyword: '{log_keyword_name}' {log_keyword_path_info}")

        except pvporcupine.PorcupineError as e:
            # ... (rest of your existing Porcupine error handling)
            logger.error(f"Failed to initialize Porcupine: {e}")
            if "Οι άδειες χρήσης Porcupine έχουν εξαντληθεί." in str(e) or "Porcupine activation limit reached" in str(e): # Greek or English
                 logger.error("Porcupine activation limit reached. Please check your Picovoice Console.")
            self._porcupine = None
        except Exception as e: # Catch any other errors during create
            logger.error(f"An unexpected error occurred during Porcupine initialization: {e}", exc_info=True)
            self._porcupine = None


        # Initialize Whisper client
        try:
            import whisper
            self._whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            logger.info(f"Whisper model '{WHISPER_MODEL_SIZE}' loaded.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self._whisper_model = None

    def _process_audio(self):
        if not self._porcupine:
            logger.error("Porcupine not initialized. Audio processing cannot start.")
            if self.on_listening_status_callback:
                self.on_listening_status_callback("Error: Wake word engine failed to start.")
            return

        self._pyaudio_instance = pyaudio.PyAudio()
        try:
            self._audio_stream = self._pyaudio_instance.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length
            )
            logger.info(f"Audio stream opened. Listening for wake word '{KEYWORD_NAMES[0]}'...")
            if self.on_listening_status_callback:
                self.on_listening_status_callback(f"Listening for '{KEYWORD_NAMES[0]}'...")

            while self._running:
                pcm = self._audio_stream.read(self._porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self._porcupine.frame_length, pcm)

                keyword_index = self._porcupine.process(pcm)
                if keyword_index >= 0:  # Wake word detected
                    logger.info(f"Wake word '{KEYWORD_NAMES[keyword_index]}' detected!")
                    if self.on_wake_word_detected_callback:
                        self.on_wake_word_detected_callback()
                    if self.on_listening_status_callback:
                        self.on_listening_status_callback("Wake word detected! Listening for command...")

                    self._record_and_transcribe_command()

                    if self._running:  # Check if still running after transcription
                        logger.info(f"Resuming listening for wake word '{KEYWORD_NAMES[0]}'...")
                        if self.on_listening_status_callback:
                            self.on_listening_status_callback(f"Listening for '{KEYWORD_NAMES[0]}'...")

        except Exception as e:
            logger.error(f"Error during audio processing: {e}", exc_info=True)
            if self.on_listening_status_callback:
                self.on_listening_status_callback(f"Audio Error: {e}")
        finally:
            if self._audio_stream is not None:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            if self._pyaudio_instance is not None:
                self._pyaudio_instance.terminate()
            logger.info("Audio processing stopped.")

    def _record_and_transcribe_command(self):
        if not self._whisper_model:
            logger.error("Whisper model not loaded. Cannot transcribe.")
            if self.on_listening_status_callback:
                self.on_listening_status_callback("Error: Transcription engine not ready.")
            return

        logger.info("Recording command...")
        frames = []
        start_time = time.time()
        last_sound_time = time.time()

        # Continue using the existing stream if it's correctly configured for Whisper
        # Whisper typically expects 16kHz mono audio. Porcupine also uses 16kHz.
        sample_rate = self._porcupine.sample_rate

        for _ in range(0, int(sample_rate / self._porcupine.frame_length * COMMAND_RECORD_DURATION_SECONDS)):
            if not self._running: break  # Stop if service is stopped externally

            try:
                # Read directly from the existing stream
                audio_data_bytes = self._audio_stream.read(self._porcupine.frame_length, exception_on_overflow=False)
                frames.append(audio_data_bytes)

                # Simple silence detection (optional, Whisper handles silence well)
                # Convert bytes to numpy array for RMS calculation
                audio_data_np = np.frombuffer(audio_data_bytes, dtype=np.int16)
                if audio_data_np.size > 0:  # Check if array is not empty
                    rms = np.sqrt(np.mean(audio_data_np.astype(
                        np.float64) ** 2))  # Use float64 for mean to avoid overflow with int16 squares
                else:
                    rms = 0  # Treat empty audio as silence
                # logger.debug(f"RMS: {rms}")

                if rms > SILENCE_THRESHOLD:
                    last_sound_time = time.time()

                if (time.time() - last_sound_time > SILENCE_DURATION_SECONDS) and (
                        time.time() - start_time > 1.5):  # Min 1.5s recording
                    logger.info("Silence detected, stopping command recording.")
                    break
                if time.time() - start_time > COMMAND_RECORD_DURATION_SECONDS:
                    logger.info("Max command recording duration reached.")
                    break

            except IOError as e:
                logger.warning(f"IOError during command recording: {e}")
                break  # Stop recording on error

        if not frames:
            logger.warning("No audio frames recorded for command.")
            return

        logger.info(f"Recording finished. {len(frames)} frames captured. Transcribing...")
        if self.on_listening_status_callback:
            self.on_listening_status_callback("Processing command...")

        # Save recorded audio to a temporary WAV file to pass to Whisper
        temp_wav_path = os.path.join(os.path.dirname(__file__), "..", "..", "temp_command_audio.wav")
        wf = wave.open(temp_wav_path, 'wb')
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(self._pyaudio_instance.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()

        try:
            # Transcribe using local Whisper model
            result = self._whisper_model.transcribe(temp_wav_path,
                                                    fp16=False)  # fp16=False for CPU, True for GPU if supported
            transcribed_text = result["text"].strip()
            logger.info(f"Whisper transcription: '{transcribed_text}'")

            if self.on_transcription_complete_callback and transcribed_text:
                self.on_transcription_complete_callback(transcribed_text)
            elif not transcribed_text:
                logger.info("Whisper returned empty transcription.")
                if self.on_listening_status_callback:
                    self.on_listening_status_callback("Could not understand command.")


        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}", exc_info=True)
            if self.on_listening_status_callback:
                self.on_listening_status_callback(f"Transcription Error: {e}")
        finally:
            if os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except OSError as e:
                    logger.warning(f"Could not delete temp audio file {temp_wav_path}: {e}")

    def start_listening(self):
        if not self._porcupine:
            logger.error("Cannot start listening: Porcupine not initialized.")
            return
        if not self._whisper_model:
            logger.error("Cannot start listening: Whisper model not loaded.")
            return

        if not self._running:
            self._running = True
            self._audio_thread = threading.Thread(target=self._process_audio, daemon=True)
            self._audio_thread.start()
            logger.info("Voice service started listening.")
        else:
            logger.info("Voice service is already listening.")

    def stop_listening(self):
        if self._running:
            self._running = False
            if self._audio_thread is not None:
                logger.info("Attempting to stop voice service...")
                self._audio_thread.join(timeout=5)  # Wait for thread to finish
                if self._audio_thread.is_alive():
                    logger.warning("Audio thread did not terminate gracefully.")
            logger.info("Voice service stopped.")
        else:
            logger.info("Voice service is not running.")

    def __del__(self):
        self.stop_listening()
        if self._porcupine is not None:
            self._porcupine.delete()
            logger.info("Porcupine instance deleted.")


# Example Usage (for testing this service standalone)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s")

    if not PICOVOICE_ACCESS_KEY:
        print("PICOVOICE_ACCESS_KEY not set in .env. Please set it and try again.")
        exit()


    def handle_wake_word():
        print("==> WAKE WORD DETECTED! Speak your command. <==")


    def handle_transcription(text):
        print(f"==> Transcribed Command: '{text}' <==")
        if "stop listening" in text.lower():
            global keep_running
            keep_running = False  # Signal main loop to exit


    def handle_status(status_msg):
        print(f"==> Status: {status_msg} <==")


    keep_running = True
    try:
        voice_service = VoiceService(
            on_wake_word_detected_callback=handle_wake_word,
            on_transcription_complete_callback=handle_transcription,
            on_listening_status_callback=handle_status
        )
        voice_service.start_listening()

        print("Voice service example running. Say 'Porcupine' (or your configured wake word) then your command.")
        print("Say 'stop listening' as a command to exit this example.")
        while keep_running:
            time.sleep(0.1)

    except ValueError as e:  # Catches PICOVOICE_ACCESS_KEY not found
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logger.exception("Unhandled exception in example usage.")
    finally:
        if 'voice_service' in locals() and voice_service:
            voice_service.stop_listening()
        print("Example finished.")