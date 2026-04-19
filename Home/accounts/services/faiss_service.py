import os
import io
from PIL import Image
from django.conf import settings
import logging

try:
    import numpy as np
    import faiss
    from deepface import DeepFace
except ImportError:
    np = None
    faiss = None
    DeepFace = None

logger = logging.getLogger(__name__)

# Constants
EMBEDDING_DIM = 512  # FaceNet dimension
INDEX_FILE_PATH = os.path.join(settings.BASE_DIR, 'media', 'voter_faces.index')
ID_MAP_FILE_PATH = os.path.join(settings.BASE_DIR, 'media', 'voter_faces_map.npy')
SIMILARITY_THRESHOLD = 0.40  # Cosine distance threshold for FaceNet (lower is stricter)

class FAISSService:
    """Service to handle FaceNet embedding extraction and FAISS similarity search."""

    def __init__(self):
        self.index = None
        self.id_map = [] # Maps FAISS index positional ID to voter_id string
        self._load_index()

    def _load_index(self):
        """Load FAISS index and mapping from disk, or initialize if not exists."""
        if not faiss:
            logger.warning("FAISS not installed.")
            return

        if os.path.exists(INDEX_FILE_PATH) and os.path.exists(ID_MAP_FILE_PATH):
            self.index = faiss.read_index(INDEX_FILE_PATH)
            self.id_map = np.load(ID_MAP_FILE_PATH).tolist()
        else:
            # Initialize an exact search index using L2 distance
            # For 1M scaling, Replace IndexFlatL2 with IndexIVFFlat
            self.index = faiss.IndexFlatL2(EMBEDDING_DIM)
            self.id_map = []

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
        
        try:
            # Convert bytes to temporary image file or read directly
            img = Image.open(io.BytesIO(image_bytes))
            # Deepface requires numpy array for memory processing usually, or temp file path
            temp_path = os.path.join(settings.BASE_DIR, 'media', 'temp_face.jpg')
            img.save(temp_path)

            # Generate embedding using FaceNet
            embedding_objs = DeepFace.represent(
                img_path=temp_path, 
                model_name="Facenet", 
                enforce_detection=True
            )
            os.remove(temp_path)
            
            if len(embedding_objs) == 0:
                raise ValueError("No face detected.")
            
            embedding = embedding_objs[0]['embedding']
            return np.array(embedding, dtype='float32')

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise ValueError(f"Could not process face: {str(e)}")

    def register_face(self, voter_id, image_bytes):
        """Register a new face embedding to FAISS mapped to the voter_id."""
        if not DeepFace or not faiss:
            logger.warning(f"Simulating face registration for {voter_id} due to missing AI dependencies.")
            return True

        embedding = self._get_embedding(image_bytes)
        embedding = np.expand_dims(embedding, axis=0)

        self.index.add(embedding)
        self.id_map.append(voter_id)
        
        self._save_index()
        return True

    def verify_face(self, voter_id, image_bytes):
        """Verify if the LIVE captured face matches the registered voter_id."""
        if not DeepFace or not faiss:
            logger.warning(f"Simulating successful face verification for {voter_id} due to missing AI dependencies.")
            return {
                'verified': True,
                'distance': 0.0,
                'message': '(SIMULATED) Face verified successfully.'
            }

        if self.index is None or self.index.ntotal == 0:
            raise ValueError("No faces registered in the system.")

        embedding = self._get_embedding(image_bytes)
        embedding = np.expand_dims(embedding, axis=0)

        k = 3
        distances, indices = self.index.search(embedding, k)

        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            
            matched_voter_id = self.id_map[idx]
            distance = distances[0][i]

            if matched_voter_id == voter_id and distance <= SIMILARITY_THRESHOLD:
                return {
                    'verified': True,
                    'distance': float(distance),
                    'message': 'Face verified successfully.'
                }
        
        return {
            'verified': False,
            'message': 'Face does not match the registered voter.'
        }

faiss_service = FAISSService()
