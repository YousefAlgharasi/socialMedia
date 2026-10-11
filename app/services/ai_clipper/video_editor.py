import subprocess
import os
from pathlib import Path
from typing import List, Optional
import imageio_ffmpeg

class VideoEditor:
    """
    Automated video cutting, vertical re-framing (9:16), and clip stitching.
    Uses embedded FFmpeg binary for zero external configuration.
    """

    def __init__(self):
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def cut_clip(self, input_video: str, output_clip: str, start_sec: float, end_sec: float) -> bool:
        """
        Extracts a sub-clip between start_sec and end_sec.
        """
        duration = end_sec - start_sec
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-ss", str(start_sec),
            "-i", input_video,
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            output_clip
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode == 0

    def convert_to_vertical_9_16(self, input_video: str, output_video: str, style: str = "blur_background") -> bool:
        """
        Converts a standard horizontal video (16:9) to vertical format (9:16, 1080x1920) for Shorts/Reels/TikTok.
        Styles:
        - 'blur_background': Blurred background scaled to fill 1080x1920 with crisp original in the center.
        - 'crop_center': Crops 9:16 window directly out of the center.
        """
        if style == "blur_background":
            filter_complex = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                "boxblur=20:5[bg];"
                "[0:v]scale=1080:-1[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
            )
        else: # crop_center
            filter_complex = "[0:v]crop=ih*9/16:ih,scale=1080:1920[v]"

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-b:v", "4500k",
            output_video
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode == 0

    def combine_clips(self, clip_paths: List[str], output_video: str) -> bool:
        """
        Combines/concatenates multiple video clips sequentially into a single video reel.
        """
        if not clip_paths:
            return False

        # Create temporary file list for ffmpeg concat
        concat_txt = Path(output_video).parent / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in clip_paths:
                clean_path = p.replace("\\", "/")
                f.write(f"file '{clean_path}'\n")

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            output_video
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if concat_txt.exists():
            concat_txt.unlink()

        return proc.returncode == 0

video_editor = VideoEditor()
