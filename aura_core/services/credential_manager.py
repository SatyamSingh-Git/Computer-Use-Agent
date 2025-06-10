import logging
import json
import os
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

from config.constants import CREDENTIAL_FILE_PATH, SALT_FILE_PATH

logger = logging.getLogger(__name__)


class CredentialManager:
    def __init__(self):
        self._master_key_fernet: Fernet | None = None
        self._credentials_data: dict = {}  # In-memory cache when unlocked
        self.is_unlocked: bool = False  # Default to locked

        app_data_dir = os.path.dirname(CREDENTIAL_FILE_PATH)
        if not os.path.exists(app_data_dir):
            try:
                os.makedirs(app_data_dir, exist_ok=True)
            except OSError as e:
                logger.critical(f"CRITICAL: Failed to create directory for credentials at {app_data_dir}: {e}")
                raise  # This is a critical failure

        logger.info(f"CredentialManager initialized. Store is currently LOCKED. Path: {CREDENTIAL_FILE_PATH}")

    def _derive_key(self, master_password: str, salt: bytes) -> bytes:
        # (No changes to this method)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=480000, backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))

    def setup_master_password(self, master_password: str) -> bool:
        # (No changes to this method's core logic, but it will set is_unlocked)
        if os.path.exists(SALT_FILE_PATH) or os.path.exists(CREDENTIAL_FILE_PATH):
            logger.warning(
                "Credential store or salt already exists. Cannot re-initialize without explicit user confirmation to overwrite/delete.")
            return False

        try:
            salt = os.urandom(16)
            with open(SALT_FILE_PATH, "wb") as sf:
                sf.write(salt)

            derived_key = self._derive_key(master_password, salt)
            self._master_key_fernet = Fernet(derived_key)
            self.is_unlocked = True  # Unlocked after successful setup
            self._credentials_data = {}
            self._save_credentials_to_file()
            logger.info("Master password set and credential store initialized and UNLOCKED.")
            return True
        except Exception as e:
            logger.error(f"Error during master password setup: {e}", exc_info=True)
            if os.path.exists(SALT_FILE_PATH): os.remove(SALT_FILE_PATH)
            if os.path.exists(CREDENTIAL_FILE_PATH): os.remove(CREDENTIAL_FILE_PATH)
            self._master_key_fernet = None;
            self.is_unlocked = False
            return False

    def unlock_store(self, master_password: str) -> bool:
        if self.is_unlocked:
            logger.info("Credential store is already unlocked.")
            return True

        if not self.is_initialized():  # Check if salt file exists
            logger.warning("Cannot unlock: Credential store not initialized (no salt file). Please set up first.")
            return False

        try:
            with open(SALT_FILE_PATH, "rb") as sf:
                salt = sf.read()
            derived_key = self._derive_key(master_password, salt)
            self._master_key_fernet = Fernet(derived_key)

            if self._load_credentials_from_file():  # This will decrypt and verify key
                self.is_unlocked = True
                logger.info("Credential store UNLOCKED successfully.")
                return True
            else:
                self._master_key_fernet = None;
                self.is_unlocked = False
                logger.warning("Failed to unlock credential store (incorrect master password or corrupted data).")
                return False
        except InvalidToken:
            logger.warning("Invalid master password provided for unlocking store (InvalidToken).")
            self._master_key_fernet = None;
            self.is_unlocked = False
            return False
        except Exception as e:
            logger.error(f"Error unlocking credential store: {e}", exc_info=True)
            self._master_key_fernet = None;
            self.is_unlocked = False
            return False

    def _load_credentials_from_file(self) -> bool:
        if not self._master_key_fernet:  # This implies not unlocked
            logger.error("Cannot load credentials: Store is effectively locked (no Fernet key).")
            return False

        if not os.path.exists(CREDENTIAL_FILE_PATH):
            logger.info("Credential file does not exist. Initializing empty in-memory store.")
            self._credentials_data = {}
            return True

        try:
            with open(CREDENTIAL_FILE_PATH, "rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                self._credentials_data = {};
                return True
            decrypted_data_json = self._master_key_fernet.decrypt(encrypted_data).decode()
            self._credentials_data = json.loads(decrypted_data_json)
            logger.debug(f"Loaded and decrypted {len(self._credentials_data)} credential entries into memory.")
            return True
        except InvalidToken:
            logger.error("Failed to decrypt credentials: Invalid master password or corrupted file.")
            self._credentials_data = {};
            return False
        except Exception as e:
            logger.error(f"Error loading/decrypting credentials from file: {e}", exc_info=True)
            self._credentials_data = {};
            return False

    def _save_credentials_to_file(self) -> bool:
        if not self.is_unlocked or not self._master_key_fernet:
            logger.error("Cannot save credentials: Store is locked or Fernet key not available.")
            return False
        # (rest of save logic as before)
        try:
            credentials_json = json.dumps(self._credentials_data).encode()
            encrypted_data = self._master_key_fernet.encrypt(credentials_json)
            with open(CREDENTIAL_FILE_PATH, "wb") as f:
                f.write(encrypted_data)
            logger.debug(f"Saved {len(self._credentials_data)} credential entries to encrypted file.")
            return True
        except Exception as e:
            logger.error(f"Error saving credentials to file: {e}", exc_info=True)
            return False

    def add_or_update_credential(self, service_name: str, username: str, password: str) -> bool:
        if not self.is_unlocked:  # Crucial check
            logger.warning(f"Store is locked. Cannot add/update credential for '{service_name}'. Unlock first.")
            return False

        self._credentials_data[service_name.lower()] = {"username": username, "password": password}
        logger.info(f"Credential for '{service_name}' added/updated in memory.")
        return self._save_credentials_to_file()

    def get_credential(self, service_name: str) -> dict | None:
        if not self.is_unlocked:  # Crucial check
            logger.warning(f"Store is locked. Cannot get credential for '{service_name}'. Unlock first.")
            return None

        # Data should be in self._credentials_data if unlocked and loaded.
        cred = self._credentials_data.get(service_name.lower())
        if cred:
            logger.info(f"Retrieved credential for '{service_name}' from memory.")
            return cred
        else:
            logger.info(f"No credential found in memory for '{service_name}'.")
            return None

    def remove_credential(self, service_name: str) -> bool:
        if not self.is_unlocked:  # Crucial check
            logger.warning(f"Store is locked. Cannot remove credential for '{service_name}'. Unlock first.")
            return False
        # (rest of remove logic as before)
        service_key = service_name.lower()
        if service_key in self._credentials_data:
            del self._credentials_data[service_key]
            logger.info(f"Credential for '{service_name}' removed from memory.")
            return self._save_credentials_to_file()
        else:
            logger.info(f"No credential found for '{service_name}' to remove.")
            return False

    def list_stored_services(self) -> list[str]:
        if not self.is_unlocked:
            logger.warning("Store is locked. Cannot list services. Unlock first.")
            return []
        return list(self._credentials_data.keys())

    def lock_store(self):
        # (No changes to this method)
        self._master_key_fernet = None
        self._credentials_data = {}
        self.is_unlocked = False
        logger.info("Credential store LOCKED. In-memory credentials cleared.")

    def is_initialized(self) -> bool:
        # (No changes to this method)
        return os.path.exists(SALT_FILE_PATH)

# (Example Usage __main__ block should be updated to reflect on-demand unlocking if tested standalone)