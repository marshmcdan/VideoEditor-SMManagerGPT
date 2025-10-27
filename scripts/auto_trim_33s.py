"""Automatically compress the active DaVinci Resolve timeline to ~33 seconds.

This script uses the official DaVinci Resolve scripting API.  It inspects all
video tracks on the current timeline, computes the total running time, and
applies proportional speed and trimming adjustments so the resulting timeline
length is approximately 33 seconds.  Every clip is retimed by the same factor
so pacing remains consistent, but a small randomised trim is also applied to
introduce slight variation between clips.

Usage:
    * Save this script in the DaVinci Resolve scripts directory.
    * From Resolve, open the timeline to shorten and run the script via the
      Workspace ➜ Scripts menu.

The script is safe to run multiple times in a session.  Undo (Ctrl+Z / Cmd+Z)
within Resolve will revert the changes if the result isn't satisfactory.
"""

from __future__ import annotations

import random
from typing import Dict, Iterable, Tuple

try:
    import DaVinciResolveScript  # type: ignore
except ImportError:  # pragma: no cover - makes local testing friendlier
    DaVinciResolveScript = None  # type: ignore

TARGET_LENGTH_SECONDS = 33.0
MINIMUM_CLIP_DURATION_FRAMES = 12  # keep at least half a second @24 fps
TRIM_VARIATION_FRAMES = 6  # random per-clip handle trim to keep cut feeling organic


class ResolveScriptError(RuntimeError):
    """Raised when the Resolve scripting API cannot be accessed."""


def _get_resolve():
    if DaVinciResolveScript is None:
        raise ResolveScriptError(
            "DaVinciResolveScript module is not available. "
            "Run this script from within DaVinci Resolve."
        )
    return DaVinciResolveScript.scriptapp("Resolve")


def _get_frame_rate(project, timeline) -> float:
    # Try timeline setting first, fall back to project setting if needed.
    if hasattr(timeline, "GetSetting"):
        value = timeline.GetSetting("timelineFrameRate")
        if value:
            return float(value)
    if hasattr(project, "GetSetting"):
        value = project.GetSetting("timelineFrameRate")
        if value:
            return float(value)
    raise ResolveScriptError("Unable to determine timeline frame rate.")


def _get_timeline_duration_frames(timeline, frame_rate: float) -> int:
    # Resolve 18+ exposes GetEndFrame(); fall back to GetEndTimecode otherwise.
    if hasattr(timeline, "GetEndFrame"):
        end_frame = timeline.GetEndFrame()
        if isinstance(end_frame, int):
            return max(end_frame, 0)
    if hasattr(timeline, "GetDuration"):
        # Some API versions return total frames as int; others string timecode.
        duration = timeline.GetDuration()
        if isinstance(duration, int):
            return max(duration, 0)
        if isinstance(duration, str):
            return _timecode_to_frames(duration, frame_rate)
    if hasattr(timeline, "GetEndTimecode"):
        return _timecode_to_frames(timeline.GetEndTimecode(), frame_rate)
    raise ResolveScriptError("Unable to determine timeline duration.")


def _timecode_to_frames(tc: str, frame_rate: float) -> int:
    parts = tc.split(":")
    if len(parts) != 4:
        raise ResolveScriptError(f"Unexpected timecode format: {tc}")
    hours, minutes, seconds, frames = map(int, parts)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return int(total_seconds * frame_rate + frames)


def _iter_video_items(timeline) -> Iterable[Tuple[int, Dict[int, object]]]:
    track_count = timeline.GetTrackCount("video")
    for track_index in range(1, track_count + 1):
        yield track_index, timeline.GetItemsInTrack("video", track_index)


def _get_clip_duration_frames(item, frame_rate: float) -> int:
    clip_rate = frame_rate
    if hasattr(item, "GetProperty"):
        props = item.GetProperty()
        if isinstance(props, dict):
            clip_rate_value = props.get("Clip Frame Rate") or props.get("FrameRate")
            try:
                if clip_rate_value:
                    clip_rate = float(clip_rate_value)
            except (TypeError, ValueError):
                clip_rate = frame_rate
    if hasattr(item, "GetDuration"):
        duration = item.GetDuration()
        if isinstance(duration, int):
            return duration
        if isinstance(duration, str):
            # Timecode string, use the item's own frame rate.
            return _timecode_to_frames(duration, clip_rate)
    # fall back to end-start
    if hasattr(item, "GetStart") and hasattr(item, "GetEnd"):
        start = item.GetStart()
        end = item.GetEnd()
        if isinstance(start, int) and isinstance(end, int):
            return max(end - start, 0)
    raise ResolveScriptError("Unable to determine clip duration.")


def _set_clip_speed(item, speed_percent: float, ripple: bool = True) -> bool:
    if hasattr(item, "SetClipSpeed"):
        return bool(item.SetClipSpeed(speed_percent, ripple, True))
    if hasattr(item, "SetSpeed"):
        return bool(item.SetSpeed(speed_percent))
    raise ResolveScriptError("Timeline item does not support speed changes.")


def _trim_clip_handles(item, trim_frames: int) -> None:
    if trim_frames <= 0:
        return
    if hasattr(item, "TrimIn"):
        item.TrimIn(trim_frames)
    if hasattr(item, "TrimOut"):
        item.TrimOut(trim_frames)


def compress_timeline_to_target(seconds: float = TARGET_LENGTH_SECONDS) -> None:
    resolve = _get_resolve()
    project_manager = resolve.GetProjectManager()
    if project_manager is None:
        raise ResolveScriptError("Unable to access Resolve project manager.")
    project = project_manager.GetCurrentProject()
    if project is None:
        raise ResolveScriptError("Open a project before running this script.")
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise ResolveScriptError("Select an active timeline before running this script.")

    frame_rate = _get_frame_rate(project, timeline)
    target_frames = int(seconds * frame_rate)
    current_frames = _get_timeline_duration_frames(timeline, frame_rate)

    if current_frames <= 0:
        raise ResolveScriptError("Timeline has no measurable duration.")
    if target_frames >= current_frames:
        print(
            f"Timeline already shorter than {seconds:.1f}s. "
            "No retiming performed."
        )
        return

    speed_multiplier = current_frames / max(target_frames, 1)
    speed_percent_multiplier = speed_multiplier * 100.0

    random.seed()

    adjusted_items = 0
    for track_index, items in _iter_video_items(timeline):
        for item in items.values():
            try:
                duration_frames = _get_clip_duration_frames(item, frame_rate)
            except ResolveScriptError as exc:
                print(f"Skipping item on V{track_index}: {exc}")
                continue

            if duration_frames <= 0:
                continue

            base_speed = 100.0
            if hasattr(item, "GetProperty"):
                props = item.GetProperty()
                if isinstance(props, dict) and "Speed" in props:
                    try:
                        base_speed = float(props["Speed"])
                    except (TypeError, ValueError):
                        pass

            new_speed = base_speed * speed_multiplier
            if not _set_clip_speed(item, new_speed):
                print(f"Unable to adjust speed for clip on V{track_index}.")
                continue

            new_duration_frames = max(int(duration_frames / speed_multiplier), MINIMUM_CLIP_DURATION_FRAMES)
            extra_trim = max(duration_frames - new_duration_frames, 0)
            random_trim = min(extra_trim // 2, TRIM_VARIATION_FRAMES)
            trim_amount = random.randint(0, random_trim) if random_trim > 0 else 0
            _trim_clip_handles(item, trim_amount)
            adjusted_items += 1

    print(
        f"Adjusted {adjusted_items} clips across all video tracks. "
        f"Applied {speed_percent_multiplier:.1f}% global speed multiplier."
    )


def main() -> None:
    try:
        compress_timeline_to_target()
    except ResolveScriptError as exc:
        print(str(exc))
    except Exception as exc:  # pragma: no cover - catch unexpected Resolve errors
        print(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
