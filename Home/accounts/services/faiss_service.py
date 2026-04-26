import os
import io
import uuid
import logging
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import numpy as np
    import faiss
    from deepface import DeepFace
    MOCK_MODE = False
except ImportError as e:
    logger.warning(f"AI dependencies missing ({e}). Running in MOCK_MODE.")
    np = None
    faiss = None
    DeepFace = None
    MOCK_MODE = True

logger = logging.getLogger(__name__)

# Constants
EMBEDDING_DIM = 128  # FaceNet outputs 128-dimensional embeddings
INDEX_FILE_PATH = os.path.join(settings.BASE_DIR, 'media', 'voter_faces.index')
ID_MAP_FILE_PATH = os.path.join(settings.BASE_DIR, 'media', 'voter_faces_map.npy')
# L2 distance threshold for normalized FaceNet embeddings.
# Lower = stricter. 0.60 is strict enough to reject different people
# while being lenient enough for the same person under varied lighting.
SIMILARITY_THRESHOLD = 0.60


class FAISSService:
    """Service to handle FaceNet embedding extraction and FAISS similarity search."""

    def __init__(self):
        self.index = None
        self.id_map = []  # Maps FAISS index positional ID to voter_id string
        self._load_index()

    def _load_index(self):
        """Load FAISS index and mapping from disk, or initialize if not exists."""
        if not faiss:
            logger.warning("FAISS not installed.")
            return

        if os.path.exists(INDEX_FILE_PATH) and os.path.exists(ID_MAP_FILE_PATH):
            self.index = faiss.read_index(INDEX_FILE_PATH)
            self.id_map = np.load(ID_MAP_FILE_PATH).tolist()
            logger.info(f"FAISS index loaded with {self.index.ntotal} faces.")
        else:
            self.index = faiss.IndexFlatL2(EMBEDDING_DIM)
            self.id_map = []
            logger.info("FAISS index initialized (empty).")

    def has_face(self, voter_id):
        """Check if a specific voter_id has a registered face."""
        if MOCK_MODE:
            return True
        self._load_index()
        return voter_id in self.id_map

    def _save_index(self):
        """Persist FAISS index and ID map to disk."""
        if self.index:
            os.makedirs(os.path.dirname(INDEX_FILE_PATH), exist_ok=True)
            faiss.write_index(self.index, INDEX_FILE_PATH)
            np.save(ID_MAP_FILE_PATH, np.array(self.id_map))

    def _get_embedding(self, image_bytes):
        """Extract a facial embedding from an image using DeepFace."""
        if not DeepFace:
            raise RuntimeError("DeepFace not installed.")

        # Save to a unique temp file to avoid race conditions
        temp_path = os.path.join(settings.BASE_DIR, 'media', f'temp_face_{uuid.uuid4().hex[:8]}.jpg')
        try:
            img = Image.open(io.BytesIO(image_bytes))
            # Convert to RGB in case of RGBA or other modes
            if img.mode != 'RGB':
                img = img.convert('RGB')
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            img.save(temp_path, 'JPEG', quality=95)

            # Generate embedding using FaceNet
            # enforce_detection=False to avoid crashes with webcam images
            # We still check if a face was found via the response
            embedding_objs = DeepFace.represent(
                img_path=temp_path,
                model_name="Facenet",
                enforce_detection=False,
                detector_backend="opencv"
            )

            if len(embedding_objs) == 0:
                raise ValueError("No face detected in the image.")

            # Check face confidence — reject if DeepFace found no real face
            face_confidence = embedding_objs[0].get('face_confidence', 0)
            if face_confidence < 0.50:
                raise ValueError("No clear face detected. Please ensure your face is visible and well-lit.")

            embedding = np.array(embedding_objs[0]['embedding'], dtype='float32')
            # L2 normalize for cosine-like distance via FAISS L2 index
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding

        except ValueError:
            raise  # Re-raise our own ValueErrors
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise ValueError(f"Could not process face: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def register_face(self, voter_id, image_bytes):
        """Register a new face embedding to FAISS mapped to the voter_id."""
        if MOCK_MODE:
            logger.info(f"[MOCK] Face registered for {voter_id}")
            if not hasattr(self, 'mock_id_map'):
                self.mock_id_map = set()
            self.mock_id_map.add(voter_id)
            return True

        if not DeepFace or not faiss:
            raise ValueError("System error: AI dependencies are missing. Registration unavailable.")

        # Reload index from disk to get latest state
        self._load_index()

        # Remove any existing embeddings for this voter_id (re-registration)
        if voter_id in self.id_map:
            logger.info(f"Re-registering face for {voter_id}, removing old embedding.")
            new_index = faiss.IndexFlatL2(EMBEDDING_DIM)
            new_id_map = []
            for i, vid in enumerate(self.id_map):
                if vid != voter_id:
                    vec = self.index.reconstruct(i)
                    new_index.add(np.expand_dims(vec, axis=0))
                    new_id_map.append(vid)
            self.index = new_index
            self.id_map = new_id_map

        embedding = self._get_embedding(image_bytes)
        embedding = np.expand_dims(embedding, axis=0)

        self.index.add(embedding)
        self.id_map.append(voter_id)

        self._save_index()
        logger.info(f"Face registered for {voter_id}. Total faces in index: {self.index.ntotal}")
        return True

    def verify_face(self, voter_id, image_bytes):
        """Verify if the LIVE captured face matches the registered voter_id."""
        if MOCK_MODE:
            logger.info(f"[MOCK] Face verified for {voter_id}")
            return {
                'verified': True,
                'distance': 0.1,
                'message': 'Face verified successfully (MOCK).'
            }

        if not DeepFace or not faiss:
            raise ValueError("System error: AI dependencies are missing. Verification unavailable.")

        # Reload index from disk to get latest state
        self._load_index()

        if self.index is None or self.index.ntotal == 0:
            raise ValueError("No faces registered in the system. Please register your face first.")

        if voter_id not in self.id_map:
            raise ValueError("Your face is not registered. Please register your Face ID first.")

        embedding = self._get_embedding(image_bytes)
        embedding = np.expand_dims(embedding, axis=0)

        # Search for the nearest face in the index
        k = min(3, self.index.ntotal)
        distances, indices = self.index.search(embedding, k)

        best_match_distance = float('inf')
        best_match_voter = None

        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            matched_voter_id = self.id_map[idx]
            distance = float(distances[0][i])

            if matched_voter_id == voter_id and distance < best_match_distance:
                best_match_distance = distance
                best_match_voter = matched_voter_id

        logger.info(f"Face verify for {voter_id}: best_distance={best_match_distance:.4f}, threshold={SIMILARITY_THRESHOLD}")

        if best_match_voter == voter_id and best_match_distance <= SIMILARITY_THRESHOLD:
            return {
                'verified': True,
                'distance': best_match_distance,
                'message': 'Face verified successfully.'
            }

        return {
            'verified': False,
            'distance': best_match_distance if best_match_voter else None,
            'message': 'Face does not match. This is not the registered voter.'
        }


faiss_service = FAISSService()
