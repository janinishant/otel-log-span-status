"""Render docs/demo.html to docs/demo.gif, frame by frame.

The demo is one paused GSAP timeline, so frames are captured by seeking it,
not by recording in real time: the output is deterministic.

    uv run --no-project --with playwright python docs/record_demo.py
    uv run --no-project --with playwright python docs/record_demo.py --stills 10,18,24

Needs ffmpeg on PATH and Playwright's Chromium (`playwright install chromium`).
The page loads fonts from Google Fonts and GSAP from cdnjs.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

DOCS = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1280, 720


async def capture(times: list[float], out_dir: Path) -> list[Path]:
    """Seek the timeline to each time and screenshot the stage; return the PNG paths."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.goto((DOCS / "demo.html").as_uri() + "?record")
        await page.wait_for_function("window.__demo !== undefined")
        await page.evaluate("document.fonts.ready.then(() => document.fonts.size)")
        viewport = page.locator("#viewport")
        paths = []
        for i, t in enumerate(times):
            await page.evaluate("(t) => { window.__demo.seek(t, false); }", t)
            path = out_dir / f"f{i:05d}.png"
            await viewport.screenshot(path=str(path))
            paths.append(path)
        await browser.close()
        return paths


async def duration() -> float:
    """Return the timeline length in seconds, printing its chapter labels."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.goto((DOCS / "demo.html").as_uri() + "?record")
        await page.wait_for_function("window.__demo !== undefined")
        d = await page.evaluate("window.__demo.duration()")
        labels = await page.evaluate("window.__demo.labels")
        await browser.close()
        print("labels:", labels)
        return float(d)


def encode(frames_dir: Path, fps: int, out: Path) -> None:
    """Encode the numbered PNGs into a GIF with ffmpeg, using one shared palette."""
    pattern = str(frames_dir / "f%05d.png")
    palette = frames_dir / "palette.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", pattern,
         "-vf", "palettegen=stats_mode=diff", str(palette)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", pattern, "-i", str(palette),
         "-lavfi", "paletteuse=dither=none:diff_mode=rectangle", str(out)],
        check=True,
    )


def main() -> None:
    """Render the full GIF, or only the requested stills."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--out", type=Path, default=DOCS / "demo.gif")
    ap.add_argument("--stills", help="comma-separated seconds; save PNG stills instead of a GIF")
    ap.add_argument(
        "--stills-dir", type=Path, default=Path(tempfile.gettempdir()) / "demo-stills"
    )
    args = ap.parse_args()

    if args.stills:
        args.stills_dir.mkdir(parents=True, exist_ok=True)
        times = [float(t) for t in args.stills.split(",")]
        for path in asyncio.run(capture(times, args.stills_dir)):
            print(path)
        return

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH")
    total = asyncio.run(duration())
    times = [i / args.fps for i in range(int(total * args.fps) + 1)]
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(capture(times, Path(tmp)))
        encode(Path(tmp), args.fps, args.out)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, {len(times)} frames)")


if __name__ == "__main__":
    main()
