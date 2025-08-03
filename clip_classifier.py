# clip_classifier.py

import torch
import clip
import cv2
from PIL import Image
import numpy as np
from loguru import logger


class ClipImageClassifier:
    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)

        # Default categories (can be customized)
        self.house_categories = [
            "a photo of a house",
            "a photo of a kitchen",
            "a living room interior",
            "a bathroom interior",
            "a bedroom",
            "a floorplan",
            "a building exterior",
            "an office",
            "abstract art",
        ]
        self.logo = [
            "a logo",
        ]
        self.person_categories = [
            "a person",
            "headshot",

        ]

        self.categories = self.house_categories + self.logo + self.person_categories
        self.text_tokens = clip.tokenize(self.categories).to(self.device)

    def classify(self, roi: np.ndarray) -> tuple[str, float]:
        """
        Classifies a single image ROI using CLIP and returns best label and score.
        """
        if roi.size == 0:
            return "invalid", 0.0

        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        roi_pil = Image.fromarray(roi_rgb)
        roi_tensor = self.preprocess(roi_pil).unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(roi_tensor)
            text_features = self.model.encode_text(self.text_tokens)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)

            similarity = image_features @ text_features.T
            best_idx = similarity.argmax().item()
            best_label = self.categories[best_idx]
            score = similarity[0, best_idx].item()

        return best_label, score

    def is_house_related(self, label: str) -> bool:
        return label in self.house_categories

    def is_logo_related(self, label: str) -> bool:
        return label in self.logo

    def is_person_related(self, label: str) -> bool:
        return label in self.person_categories
