"""Greedy IoU tracking of plate detections across sampled video frames.

Plates move little between frames sampled a fraction of a second apart, so matching each
frame's detections to the open tracks by intersection over union (best pairs first) is
enough; a track that is not matched for ``max_misses`` sampled frames is closed. Each track
then becomes one multi-view read, fused across its crops.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from plate_reader.detector import Detection, iou


@dataclass
class Track:
    id: int
    observations: list[tuple[int, Detection]] = field(default_factory=list)
    misses: int = 0
    closed: bool = False

    @property
    def last(self) -> Detection:
        return self.observations[-1][1]

    @property
    def frames(self) -> list[int]:
        return [frame for frame, _ in self.observations]


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_misses: int = 2) -> None:
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self.tracks: list[Track] = []

    @property
    def open_tracks(self) -> list[Track]:
        return [t for t in self.tracks if not t.closed]

    def update(self, frame: int, detections: list[Detection]) -> None:
        candidates = self.open_tracks
        pairs = sorted(
            (
                (iou(track.last.box, det.box), t_index, d_index)
                for t_index, track in enumerate(candidates)
                for d_index, det in enumerate(detections)
            ),
            reverse=True,
        )
        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        for overlap, t_index, d_index in pairs:
            if overlap < self.iou_threshold:
                break
            if t_index in used_tracks or d_index in used_dets:
                continue
            candidates[t_index].observations.append((frame, detections[d_index]))
            candidates[t_index].misses = 0
            used_tracks.add(t_index)
            used_dets.add(d_index)
        for t_index, track in enumerate(candidates):
            if t_index not in used_tracks:
                track.misses += 1
                if track.misses > self.max_misses:
                    track.closed = True
        for d_index, det in enumerate(detections):
            if d_index not in used_dets:
                self.tracks.append(Track(id=len(self.tracks), observations=[(frame, det)]))

    def finish(self) -> list[Track]:
        for track in self.tracks:
            track.closed = True
        return list(self.tracks)


__all__ = ["IoUTracker", "Track"]
