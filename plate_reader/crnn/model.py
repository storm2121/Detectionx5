"""The CRNN: residual CNN, height-collapsing pooling, two-layer BiLSTM, linear CTC head.

Sized for the plate problem rather than for general text: a 32 x 160 grey input, four
residual stages that halve the width twice (40 time steps, ample for at most ten symbols
with CTC repeats) and collapse the height, then a bidirectional LSTM that lets each step
see the whole plate, which is what disambiguates a digit-shaped letter between two bars.
The forward pass returns raw logits ``(batch, time, classes)``; temperature, softmax and
decoding live outside the graph (ADR 0003) so every runtime shares them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import torch
from torch import nn

from .charset import NUM_CLASSES
from .preprocess import INPUT_HEIGHT, INPUT_WIDTH


@dataclass(frozen=True)
class CRNNConfig:
    height: int = INPUT_HEIGHT
    width: int = INPUT_WIDTH
    channels: tuple[int, ...] = (32, 64, 128, 160)
    lstm_hidden: int = 128
    lstm_layers: int = 2
    dropout: float = 0.1
    num_classes: int = NUM_CLASSES
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["channels"] = list(self.channels)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CRNNConfig:
        values = dict(data)
        values["channels"] = tuple(values["channels"])
        return cls(**values)

    @property
    def time_steps(self) -> int:
        return self.width // 4


class ResidualBlock(nn.Module):
    def __init__(self, cin: int, cout: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False),
            nn.BatchNorm2d(cout),
        )
        self.skip: nn.Module = (
            nn.Identity()
            if cin == cout
            else nn.Sequential(nn.Conv2d(cin, cout, 1, bias=False), nn.BatchNorm2d(cout))
        )
        self.act = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.act(self.body(x) + self.skip(x))
        return out


class CRNN(nn.Module):
    def __init__(self, config: CRNNConfig | None = None) -> None:
        super().__init__()
        self.config = config or CRNNConfig()
        c = self.config.channels
        self.stem = nn.Sequential(
            nn.Conv2d(1, c[0], 3, padding=1, bias=False),
            nn.BatchNorm2d(c[0]),
            nn.ReLU(inplace=True),
        )
        # Pooling halves width twice (to T = W / 4) and height four times (32 -> 2).
        self.stages = nn.Sequential(
            ResidualBlock(c[0], c[0]),
            nn.MaxPool2d((2, 2)),
            ResidualBlock(c[0], c[1]),
            nn.MaxPool2d((2, 2)),
            ResidualBlock(c[1], c[2]),
            nn.MaxPool2d((2, 1)),
            ResidualBlock(c[2], c[3]),
            nn.MaxPool2d((2, 1)),
        )
        self.dropout = nn.Dropout(self.config.dropout)
        self.lstm = nn.LSTM(
            c[3],
            self.config.lstm_hidden,
            num_layers=self.config.lstm_layers,
            bidirectional=True,
            batch_first=True,
            dropout=self.config.dropout if self.config.lstm_layers > 1 else 0.0,
        )
        self.head = nn.Linear(2 * self.config.lstm_hidden, self.config.num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.stages(self.stem(x))
        # Height-collapsing pooling: average what is left of the height axis.
        sequence = features.mean(dim=2).transpose(1, 2)
        hidden, _ = self.lstm(self.dropout(sequence))
        logits: torch.Tensor = self.head(self.dropout(hidden))
        return logits


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


__all__ = ["CRNN", "CRNNConfig", "ResidualBlock", "count_parameters"]
