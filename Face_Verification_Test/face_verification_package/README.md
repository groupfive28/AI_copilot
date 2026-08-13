# Face Verification Module

This module evaluates whether photographs detected in uploaded document images
are consistent with one person.

It uses the InsightFace `buffalo_l` pretrained model to:

1. Detect faces.
2. Try the original image and 90/180/270 degree rotations.
3. Select the orientation with the strongest face-detection evidence.
4. Select the largest detected face as the primary/document-holder face.
5. Generate a 512-dimensional face embedding.
6. Compare document embeddings using cosine similarity.
7. Group documents into identity clusters using the project's experimental
   similarity threshold.
8. Flag documents that are inconsistent with the dominant identity group.

## Important scope

This module does **not** determine whether a document itself is genuine or
fake. It determines whether the faces found across the submitted document
images are consistent with one identity.

It currently accepts image files: JPG, JPEG, PNG and WEBP.

PDF rendering, OCR, document authenticity checks, database verification and
the wider onboarding workflow should be handled by their respective modules.

## Usage

```python
from face_verification import verify_documents

result = verify_documents("path/to/uploaded_documents")

print(result["status"])
print(result["suspicious_documents"])
```

Example statuses:

- `FACE_CONSISTENT`
- `REVIEW_REQUIRED`
- `INSUFFICIENT_EVIDENCE`

The current experimental threshold is `0.20`. It was selected from the
project's current test data and should not be treated as a universal
production biometric threshold.

## Model

The module uses InsightFace `buffalo_l` with CPU execution. InsightFace may
download/cache the required model files when `FaceAnalysis` is initialized.

For production deployment, confirm the group's dependency versions and model
distribution/cache strategy.
