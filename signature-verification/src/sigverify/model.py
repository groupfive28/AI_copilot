from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np
import torch
from torch import nn

from sigverify.config import settings

# Architecture copied exactly from luizgh/sigver
# (sigver/featurelearning/models/signet.py) - the reference PyTorch
# implementation of SigNet (Hafemann et al., "Learning Features for Offline
# Handwritten Signature Verification using Deep Convolutional Neural
# Networks", https://arxiv.org/abs/1705.05787). Reimplemented here rather
# than depending on the `sigver` package itself, since that package's
# install instructions (`pip install ... --process-dependency-links`) use a
# pip flag removed years ago and its other dependencies aren't needed here -
# only the architecture and the pretrained weights are.
def _conv_bn_relu(in_channels: int, out_channels: int, kernel_size: int, stride: int = 1, pad: int = 0) -> nn.Sequential:
    return nn.Sequential(OrderedDict([
        ("conv", nn.Conv2d(in_channels, out_channels, kernel_size, stride, pad, bias=False)),
        ("bn", nn.BatchNorm2d(out_channels)),
        ("relu", nn.ReLU()),
    ]))


def _linear_bn_relu(in_features: int, out_features: int) -> nn.Sequential:
    return nn.Sequential(OrderedDict([
        ("fc", nn.Linear(in_features, out_features, bias=False)),
        ("bn", nn.BatchNorm1d(out_features)),
        ("relu", nn.ReLU()),
    ]))


class SigNet(nn.Module):
    """Produces a 2048-dim embedding for a preprocessed (150x220 grayscale)
    signature image - two embeddings' cosine distance is the similarity
    signal, same idea as InsightFace's face embeddings in
    ../face-verification/, just for signatures instead of faces."""

    def __init__(self) -> None:
        super().__init__()
        self.feature_space_size = 2048

        self.conv_layers = nn.Sequential(OrderedDict([
            ("conv1", _conv_bn_relu(1, 96, 11, stride=4)),
            ("maxpool1", nn.MaxPool2d(3, 2)),
            ("conv2", _conv_bn_relu(96, 256, 5, pad=2)),
            ("maxpool2", nn.MaxPool2d(3, 2)),
            ("conv3", _conv_bn_relu(256, 384, 3, pad=1)),
            ("conv4", _conv_bn_relu(384, 384, 3, pad=1)),
            ("conv5", _conv_bn_relu(384, 256, 3, pad=1)),
            ("maxpool3", nn.MaxPool2d(3, 2)),
        ]))

        self.fc_layers = nn.Sequential(OrderedDict([
            ("fc1", _linear_bn_relu(256 * 3 * 5, 2048)),
            ("fc2", _linear_bn_relu(self.feature_space_size, self.feature_space_size)),
        ]))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        x = self.conv_layers(inputs)
        x = x.view(x.shape[0], 256 * 3 * 5)
        x = self.fc_layers(x)
        return x


# Hosted on the paper authors' own Google Drive (linked from the sigver
# README - https://github.com/luizgh/sigver), not something we control.
# Confirmed downloadable as of this writing; if this link ever dies, the
# whole feature degrades to "signature verification not configured" (see
# pipeline.py's error handling), not a hard crash.
_SIGNET_WEIGHTS_URL = "https://drive.google.com/uc?export=download&id=1l8NFdxSvQSLb2QTv71E6bKcTgvShKPpx"

_model: SigNet | None = None


def _download_weights(dest: Path) -> None:
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    urllib.request.urlretrieve(_SIGNET_WEIGHTS_URL, tmp)
    tmp.rename(dest)


def get_model() -> SigNet:
    """Lazily loads (downloading the pretrained weights on first use if not
    already present locally, mirroring how insightface caches its model
    files outside the repo). state_dict is saved by the original authors as
    a (state_dict, classification_layer, forg_layer) tuple - the latter two
    are the writer-identification/forgery-classification heads from their
    training setup, both None in the released feature-extractor checkpoint,
    so only state_dict is used here."""
    global _model
    if _model is not None:
        return _model

    weights_path = Path(settings.model_path)
    if not weights_path.exists():
        _download_weights(weights_path)

    state_dict, _classification_layer, _forg_layer = torch.load(weights_path, map_location="cpu", weights_only=False)
    model = SigNet()
    model.load_state_dict(state_dict)
    model.eval()
    _model = model
    return model


def embed(preprocessed: np.ndarray) -> np.ndarray:
    """preprocessed: (150, 220) uint8 grayscale, already run through
    preprocess.preprocess_signature. Returns a 2048-dim float32 vector."""
    model = get_model()
    tensor = torch.from_numpy(preprocessed).float().div(255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        features = model(tensor)
    return features.squeeze(0).numpy()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
