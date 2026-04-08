from config import MODEL_WEIGHT_DIR
from sentence_transformers import SentenceTransformer
from models import embed_model

model = SentenceTransformer("BAAI/bge-m3", cache_folder= (MODEL_WEIGHT_DIR / "bge-m3").as_posix())

sentences = [
    "That is a happy person",
    "That is a happy dog",
    "That is a very happy person",
    "Today is a sunny day"
]
model.encode(sentences)