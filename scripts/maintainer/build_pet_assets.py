from __future__ import annotations

import math
import shutil
import struct
import subprocess
import wave
from collections import deque
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
VIDEO_PATH = ROOT / "奶蛙.mp4"
BUILD_DIR = ROOT / ".pet-build"
OUTPUT_DIR = ROOT / "assets" / "pet"
FRAME_RATE = 8
CANVAS_SIZE = 180
CROP_BOX = (30, 100, 690, 1050)
STATE_RANGES = {
    "idle": (0.0, 2.4),
    "listen": (2.4, 5.2),
    "target": (7.4, 10.5),
    "busy": (13.6, 14.6),
    "error": (15.0, 16.0),
}


def ensure_safe_child(path: Path, parent: Path) -> None:
    path.resolve().relative_to(parent.resolve())


def is_background_pixel(red: int, green: int, blue: int, y: int, height: int) -> bool:
    brightness = max(red, green, blue)
    darkness = min(red, green, blue)
    saturation = brightness - darkness
    average = (red + green + blue) / 3
    warmth = red - blue

    is_lower_floor = (
        y >= int(height * 0.68)
        and average >= 155
        and saturation <= 70
        and abs(red - green) <= 38
        and abs(green - blue) <= 38
    )
    if is_lower_floor:
        return True

    is_warm_body = red >= green - 4 and green >= blue + 8 and warmth >= 24
    if is_warm_body or average < 72:
        return False

    is_near_white = average >= 222 and brightness >= 235 and saturation <= 42
    is_light_gray = average >= 205 and saturation <= 28
    return is_near_white or is_light_gray or is_lower_floor


def connected_background_mask(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    def maybe_add(x: int, y: int) -> None:
        if (x, y) in visited:
            return
        red, green, blue, _alpha = pixels[x, y]
        if is_background_pixel(red, green, blue, y, height):
            visited.add((x, y))
            queue.append((x, y))

    for x in range(width):
        maybe_add(x, 0)
        maybe_add(x, height - 1)
    for y in range(height):
        maybe_add(0, y)
        maybe_add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        for next_x in (x - 1, x, x + 1):
            for next_y in (y - 1, y, y + 1):
                if next_x == x and next_y == y:
                    continue
                if 0 <= next_x < width and 0 <= next_y < height:
                    maybe_add(next_x, next_y)

    mask = Image.new("L", rgba.size, 0)
    mask_pixels = mask.load()
    for x, y in visited:
        mask_pixels[x, y] = 255
    return mask


def fill_alpha_holes(alpha: Image.Image, max_fill_y: int | None = None) -> Image.Image:
    alpha = alpha.convert("L")
    width, height = alpha.size
    pixels = alpha.load()
    visited = bytearray(width * height)
    queue: deque[int] = deque()

    def maybe_add(x: int, y: int) -> None:
        index = y * width + x
        if visited[index] or pixels[x, y] != 0:
            return
        visited[index] = 1
        queue.append(index)

    for x in range(width):
        maybe_add(x, 0)
        maybe_add(x, height - 1)
    for y in range(height):
        maybe_add(0, y)
        maybe_add(width - 1, y)

    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        if x > 0:
            maybe_add(x - 1, y)
        if x + 1 < width:
            maybe_add(x + 1, y)
        if y > 0:
            maybe_add(x, y - 1)
        if y + 1 < height:
            maybe_add(x, y + 1)

    seen_holes = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            start_index = y * width + x
            if pixels[x, y] != 0 or visited[start_index] or seen_holes[start_index]:
                continue

            hole_pixels = []
            hole_queue: deque[int] = deque([start_index])
            seen_holes[start_index] = 1
            hole_max_y = y
            while hole_queue:
                index = hole_queue.popleft()
                hole_x = index % width
                hole_y = index // width
                hole_max_y = max(hole_max_y, hole_y)
                hole_pixels.append((hole_x, hole_y))
                for next_x, next_y in (
                    (hole_x - 1, hole_y),
                    (hole_x + 1, hole_y),
                    (hole_x, hole_y - 1),
                    (hole_x, hole_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_index = next_y * width + next_x
                    if (
                        pixels[next_x, next_y] == 0
                        and not visited[next_index]
                        and not seen_holes[next_index]
                    ):
                        seen_holes[next_index] = 1
                        hole_queue.append(next_index)

            if max_fill_y is None or hole_max_y <= max_fill_y:
                for hole_x, hole_y in hole_pixels:
                    pixels[hole_x, hole_y] = 255
    return alpha


def remove_white_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = connected_background_mask(rgba)
    width, height = rgba.size
    pixels = rgba.load()
    background_pixels = background.load()
    output_pixels = []
    for y in range(height):
        for x in range(width):
            red, green, blue, _alpha = pixels[x, y]
            alpha = 0 if background_pixels[x, y] else 255
            output_pixels.append((red, green, blue, alpha))
    rgba.putdata(output_pixels)
    rgba.putalpha(fill_alpha_holes(rgba.getchannel("A"), int(height * 0.68)))
    return rgba


def finalize_colorkey_safe_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda value: 255 if value >= 128 else 0)
    alpha = fill_alpha_holes(alpha, int(rgba.height * 0.68))
    rgba.putalpha(alpha)
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha_value = pixels[x, y]
            if alpha_value == 0:
                pixels[x, y] = (255, 255, 255, 0)
    return rgba


def process_frame(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        cropped = image.crop(CROP_BOX)
        transparent = remove_white_background(cropped)
        transparent.thumbnail((CANVAS_SIZE - 8, CANVAS_SIZE - 8), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 0))
        x = (CANVAS_SIZE - transparent.width) // 2
        y = CANVAS_SIZE - transparent.height - 2
        canvas.alpha_composite(transparent, (x, y))
        canvas = finalize_colorkey_safe_alpha(canvas)
        canvas.save(destination, optimize=True)


def generate_frames() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to build pet assets")
    if not VIDEO_PATH.exists():
        raise FileNotFoundError(VIDEO_PATH)

    ensure_safe_child(BUILD_DIR, ROOT)
    ensure_safe_child(OUTPUT_DIR, ROOT)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for state, (start, end) in STATE_RANGES.items():
        raw_dir = BUILD_DIR / state
        output_dir = OUTPUT_DIR / state
        raw_dir.mkdir(parents=True)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(start),
                "-t",
                str(end - start),
                "-i",
                str(VIDEO_PATH),
                "-vf",
                f"fps={FRAME_RATE}",
                str(raw_dir / "frame_%03d.png"),
                "-y",
            ],
            check=True,
        )
        for index, source in enumerate(sorted(raw_dir.glob("frame_*.png"))):
            process_frame(source, output_dir / f"{index:03d}.png")

    shutil.rmtree(BUILD_DIR)


def write_tone(path: Path, notes: list[tuple[float, float]]) -> None:
    sample_rate = 22050
    amplitude = 0.16
    samples: list[int] = []
    for frequency, duration in notes:
        count = round(sample_rate * duration)
        for index in range(count):
            position = index / max(1, count - 1)
            envelope = math.sin(math.pi * position) ** 2
            value = amplitude * envelope * math.sin(2 * math.pi * frequency * index / sample_rate)
            samples.append(round(value * 32767))
        samples.extend([0] * round(sample_rate * 0.025))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def generate_sounds() -> None:
    sound_dir = OUTPUT_DIR / "sounds"
    sound_dir.mkdir(parents=True, exist_ok=True)
    write_tone(sound_dir / "listen.wav", [(520, 0.08), (660, 0.09)])
    write_tone(sound_dir / "target.wav", [(660, 0.07), (880, 0.11)])
    write_tone(sound_dir / "busy.wav", [(760, 0.06), (960, 0.07)])
    write_tone(sound_dir / "error.wav", [(420, 0.11), (280, 0.16)])
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and VIDEO_PATH.exists():
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "3.0",
                "-t",
                "1.8",
                "-i",
                str(VIDEO_PATH),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "22050",
                "-af",
                "afade=t=in:st=0:d=0.05,afade=t=out:st=1.5:d=0.3,volume=0.8",
                str(sound_dir / "laugh.wav"),
                "-y",
            ],
            check=True,
        )


if __name__ == "__main__":
    generate_frames()
    generate_sounds()
    print(f"Pet assets created in {OUTPUT_DIR}")
