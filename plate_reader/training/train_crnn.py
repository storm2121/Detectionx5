"""Train the CRNN with CTC on synthetic crops, optionally fine-tune on ``data/ocr``.

Synthetic pretraining streams fresh crops every epoch with a curriculum over augmentation
strength; mixed precision on CUDA, fp32 on CPU. The best epoch by validation exact match
(greedy decoding on a fixed synthetic validation split) is kept. When labelled real crops
exist under ``data/ocr/train`` a short fine-tuning phase follows at a lower learning rate.

Training is seeded but not bitwise reproducible on GPU (cuDNN's LSTM kernels are not
deterministic); the exported model's hash is its version, and results record it.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from ..crnn.charset import CHARSET_ID
from ..crnn.decode import constrained_beam_search, greedy, log_softmax
from ..crnn.model import CRNN, CRNNConfig, count_parameters
from ..crnn.preprocess import batch as preprocess_batch
from ..settings import PROJECT_ROOT
from ..synthetic.augment import DEFAULT, AugmentConfig
from ..synthetic.generate import GENERATOR_VERSION, make_crop
from ..synthetic.splits import SPLIT_SEEDS
from .data import Curriculum, EpochSampler, LabelledCrops, SyntheticCrops, collate

Log = Callable[[str], object]


@dataclass
class TrainConfig:
    epochs: int = 24
    epoch_size: int = 20000
    batch_size: int = 128
    lr: float = 2e-3
    weight_decay: float = 1e-4
    workers: int = 6
    #: Keep the data workers alive between epochs. A process that builds many loaders in a
    #: row (the sweep) turns this off: stale persistent workers break on Windows.
    persistent_workers: bool = True
    val_size: int = 1000
    seed: int = 0
    device: str = "auto"
    amp: bool = True
    curriculum_start: float = 0.3
    curriculum_ramp: float = 0.6
    beam_every: int = 6
    fine_tune_epochs: int = 6
    fine_tune_lr: float = 3e-4
    data_dir: Path | None = None
    checkpoint: Path = field(
        default_factory=lambda: PROJECT_ROOT / "models" / "checkpoints" / "crnn_best.pt"
    )
    model: CRNNConfig = field(default_factory=CRNNConfig)
    #: Start from these weights instead of a random initialisation (the sweep's trials).
    init_weights: Path | None = None
    #: Degradation bounds of the synthetic training crops (the sweep scales them).
    augment: AugmentConfig = field(default_factory=lambda: DEFAULT)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["data_dir"] = _relative(self.data_dir) if self.data_dir else None
        data["checkpoint"] = Path(self.checkpoint).name
        data["init_weights"] = _relative(self.init_weights) if self.init_weights else None
        data["model"] = self.model.as_dict()
        return data


def _relative(path: Path) -> str:
    """Repository-relative path for results files (no machine paths in committed JSON)."""
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def resolve_device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)


def ctc_loss(model_out: torch.Tensor, targets: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
    log_probs = model_out.float().log_softmax(-1).transpose(0, 1)  # (T, B, C) in fp32
    frames = torch.full((model_out.shape[0],), model_out.shape[1], dtype=torch.long)
    loss: torch.Tensor = nn.functional.ctc_loss(
        log_probs, targets, frames, lengths, blank=0, reduction="mean", zero_infinity=True
    )
    return loss


@torch.no_grad()
def predict_logits(
    model: CRNN, images: np.ndarray, device: torch.device, batch_size: int = 256
) -> np.ndarray:
    model.eval()
    outputs = []
    for start in range(0, len(images), batch_size):
        chunk = torch.from_numpy(images[start : start + batch_size]).to(device)
        outputs.append(model(chunk).float().cpu().numpy())
    return (
        np.concatenate(outputs)
        if outputs
        else np.zeros((0, model.config.time_steps, model.config.num_classes))
    )


def validation_split(size: int) -> tuple[np.ndarray, list[str]]:
    samples = [make_crop(SPLIT_SEEDS["val"], i) for i in range(size)]
    return preprocess_batch([s.image for s in samples]), [s.tokens for s in samples]


def exact_match(logits: np.ndarray, truths: list[str], beam: bool) -> float:
    correct = 0
    for item, truth in zip(logits, truths, strict=True):
        log_probs = log_softmax(item)
        if beam:
            hyps = constrained_beam_search(log_probs)
            prediction = hyps[0].tokens if hyps else None
        else:
            prediction = greedy(log_probs)[0]
        correct += int(prediction == truth)
    return correct / max(1, len(truths))


@dataclass
class TrainResult:
    model: CRNN
    history: list[dict[str, Any]]
    best_epoch: int
    best_val: float
    device: str
    parameters: int
    seconds: float
    fine_tuned: bool


def _loader(
    dataset: Any, sampler: Any, config: TrainConfig, shuffle: bool = False
) -> DataLoader[Any]:
    return DataLoader(
        dataset,
        batch_size=config.batch_size,
        sampler=sampler,
        shuffle=shuffle if sampler is None else False,
        num_workers=config.workers,
        collate_fn=collate,
        persistent_workers=config.workers > 0 and config.persistent_workers,
        pin_memory=torch.cuda.is_available(),
        drop_last=False,
    )


def _run_epoch(
    model: CRNN,
    loader: DataLoader[Any],
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None,
    scaler: torch.amp.GradScaler,
    device: torch.device,
    amp: bool,
) -> float:
    model.train()
    losses: list[float] = []
    for images, targets, lengths in loader:
        images = images.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=amp):
            out = model(images)
        loss = ctc_loss(out, targets, lengths)
        scaled: torch.Tensor = scaler.scale(loss)
        scaled.backward()  # type: ignore[no-untyped-call]
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        scaler.step(optimizer)
        scaler.update()
        if scheduler is not None:
            scheduler.step()
        losses.append(float(loss.detach()))
    return float(np.mean(losses)) if losses else math.nan


def train(config: TrainConfig, log: Log = print) -> TrainResult:
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    torch.backends.cudnn.benchmark = False
    device = resolve_device(config.device)
    amp = config.amp and device.type == "cuda"
    model = (
        load_weights(config.init_weights) if config.init_weights is not None else CRNN(config.model)
    ).to(device)
    params = count_parameters(model)
    log(f"CRNN with {params} parameters on {device} (amp={amp})")

    curriculum = Curriculum(config.epochs, config.curriculum_start, config.curriculum_ramp)
    dataset = SyntheticCrops(SPLIT_SEEDS["train"], config.epoch_size, curriculum, config.augment)
    sampler = EpochSampler(config.epoch_size, config.seed)
    loader = _loader(dataset, sampler, config)
    steps = config.epochs * math.ceil(config.epoch_size / config.batch_size)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=config.lr, total_steps=steps, pct_start=0.15
    )
    scaler = torch.amp.GradScaler(device.type, enabled=amp)
    val_images, val_truths = validation_split(config.val_size)

    history: list[dict[str, Any]] = []
    best_val, best_epoch = -1.0, -1
    best_state: dict[str, torch.Tensor] | None = None
    start = time.perf_counter()
    for epoch in range(config.epochs):
        sampler.set_epoch(epoch)
        tick = time.perf_counter()
        loss = _run_epoch(model, loader, optimizer, scheduler, scaler, device, amp)
        logits = predict_logits(model, val_images, device)
        val_greedy = exact_match(logits, val_truths, beam=False)
        entry: dict[str, Any] = {
            "epoch": epoch,
            "phase": "synthetic",
            "loss": round(loss, 6),
            "strength_max": round(curriculum.upper(epoch), 4),
            "lr": round(float(scheduler.get_last_lr()[0]), 8),
            "val_exact_greedy": round(val_greedy, 6),
            "seconds": round(time.perf_counter() - tick, 2),
        }
        if (epoch + 1) % config.beam_every == 0 or epoch == config.epochs - 1:
            entry["val_exact_beam"] = round(exact_match(logits, val_truths, beam=True), 6)
        history.append(entry)
        log(json.dumps(entry))
        if val_greedy > best_val:
            best_val, best_epoch = val_greedy, epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            config.checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {"config": config.model.as_dict(), "state_dict": best_state}, config.checkpoint
            )

    if best_state is not None:
        model.load_state_dict(best_state)

    fine_tuned = False
    real = (config.data_dir / "ocr" / "train" / "labels.csv") if config.data_dir else None
    if real is not None and real.exists():
        crops = LabelledCrops(real)
        if len(crops) > 0 and config.fine_tune_epochs > 0:
            fine_tuned = True
            log(f"fine-tuning on {len(crops)} labelled crops from {real.parent}")
            ft_loader = _loader(crops, None, config, shuffle=True)
            ft_optimizer = torch.optim.AdamW(
                model.parameters(), lr=config.fine_tune_lr, weight_decay=config.weight_decay
            )
            for epoch in range(config.fine_tune_epochs):
                loss = _run_epoch(model, ft_loader, ft_optimizer, None, scaler, device, amp)
                logits = predict_logits(model, val_images, device)
                entry = {
                    "epoch": config.epochs + epoch,
                    "phase": "fine_tune",
                    "loss": round(loss, 6),
                    "val_exact_greedy": round(exact_match(logits, val_truths, beam=False), 6),
                }
                history.append(entry)
                log(json.dumps(entry))

    model.eval()
    return TrainResult(
        model=model.cpu(),
        history=history,
        best_epoch=best_epoch,
        best_val=best_val,
        device=str(device),
        parameters=params,
        seconds=round(time.perf_counter() - start, 1),
        fine_tuned=fine_tuned,
    )


def save_weights(model: CRNN, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save(
        {"config": model.config.as_dict(), "state_dict": state, "charset_id": CHARSET_ID}, path
    )
    return path


def load_weights(path: Path) -> CRNN:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    model = CRNN(CRNNConfig.from_dict(payload["config"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model


def training_summary(config: TrainConfig, result: TrainResult) -> dict[str, Any]:
    return {
        "schema": "detectionx5.train_crnn/1",
        "label": "trained on synthetic data; synthetic results are not real-world accuracy",
        "generator_version": GENERATOR_VERSION,
        "train_seed": SPLIT_SEEDS["train"],
        "val_seed": SPLIT_SEEDS["val"],
        "config": config.as_dict(),
        "device": result.device,
        "parameters": result.parameters,
        "seconds": result.seconds,
        "best_epoch": result.best_epoch,
        "best_val_exact_greedy": round(result.best_val, 6),
        "fine_tuned_on_real_data": result.fine_tuned,
        "history": result.history,
    }


__all__ = [
    "TrainConfig",
    "TrainResult",
    "exact_match",
    "load_weights",
    "predict_logits",
    "resolve_device",
    "save_weights",
    "train",
    "training_summary",
    "validation_split",
]
