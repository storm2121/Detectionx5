"""Export the CRNN to ONNX (opset 17, dynamic batch) and write its metadata.

The TorchScript-based exporter is used because it emits the native ONNX ``LSTM`` operator
at opset 17; the dynamo exporter in this torch version only targets opset 18 and above.
The graph outputs raw logits, so temperature and decoding stay identical across runtimes.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Final

import torch

from ..crnn.model import CRNN
from ..crnn.runtime import CRNNMetadata, file_version, metadata_path_for

OPSET: Final = 17
INPUT_NAME: Final = "image"
OUTPUT_NAME: Final = "logits"


def export_onnx(model: CRNN, path: Path) -> Path:
    model = model.cpu().eval()
    cfg = model.config
    dummy = torch.zeros(2, 1, cfg.height, cfg.width)
    path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        torch.onnx.export(
            model,
            (dummy,),
            str(path),
            dynamo=False,
            opset_version=OPSET,
            input_names=[INPUT_NAME],
            output_names=[OUTPUT_NAME],
            dynamic_axes={INPUT_NAME: {0: "batch"}, OUTPUT_NAME: {0: "batch"}},
            do_constant_folding=True,
        )
    return path


def write_metadata(onnx_path: Path, metadata: CRNNMetadata | None = None) -> CRNNMetadata:
    """(Re)write the metadata JSON; the version is always the hash of the ONNX bytes."""
    meta_path = metadata_path_for(onnx_path)
    if metadata is None:
        metadata = CRNNMetadata.load(meta_path) if meta_path.exists() else CRNNMetadata(version="")
    metadata.version = file_version(onnx_path)
    metadata.save(meta_path)
    return metadata


__all__ = ["INPUT_NAME", "OPSET", "OUTPUT_NAME", "export_onnx", "write_metadata"]
