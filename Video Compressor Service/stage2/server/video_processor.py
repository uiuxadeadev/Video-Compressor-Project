# video_processor.py

import os
import subprocess
import json
import logging
from typing import Dict, Any, Tuple, Optional
from common.logging_config import LogConfig
import shutil

class VideoProcessor:
    """Video processing service using FFmpeg"""
    
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.logger = LogConfig.get_component_logger("VideoProcessor")
        self._verify_ffmpeg()

    def _verify_ffmpeg(self):
        """Verify FFmpeg installation"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError("FFmpeg is not installed or accessible")

    def analyze_video(self, input_path: str) -> Dict[str, Any]:
        """
        Analyze video characteristics using FFprobe
        
        Args:
            input_path: Path to input video file
            
        Returns:
            Dict containing video information
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            video_stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
            
            return {
                'bitrate': int(info['format'].get('bit_rate', 0)),
                'duration': float(info['format'].get('duration', 0)),
                'format': info['format'].get('format_name', ''),
                'size': int(info['format'].get('size', 0)),
                'video': {
                    'codec': video_stream.get('codec_name', ''),
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                    'bitrate': int(video_stream.get('bit_rate', 0))
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing video: {e}")
            raise

    def _get_optimal_compression_params(self, video_info: Dict[str, Any]) -> Dict[str, str]:
        """
        Determine optimal compression parameters based on video characteristics
        
        Args:
            video_info: Video analysis information
            
        Returns:
            Dict containing FFmpeg parameters
        """
        video = video_info['video']
        pixels = video['width'] * video['height']
        input_bitrate = video['bitrate']

        # Select CRF (Constant Rate Factor) based on resolution and current bitrate
        if pixels <= 1280 * 720:  # 720p or lower
            crf = 23 if input_bitrate > 2_000_000 else 26
        elif pixels <= 1920 * 1080:  # 1080p
            crf = 22 if input_bitrate > 4_000_000 else 24
        else:  # 4K or higher
            crf = 20 if input_bitrate > 8_000_000 else 22

        # Select encoder preset based on resolution
        if pixels > 1920 * 1080:
            preset = 'slower'  # Higher quality for 4K
        else:
            preset = 'medium'  # Balanced for 1080p and below

        return {
            'crf': str(crf),
            'preset': preset
        }

    def compress_video(self, input_path: str, output_path: str) -> bool:
        """
        Compress video with optimal quality
        
        Args:
            input_path: Input video file path
            output_path: Output video file path
            
        Returns:
            bool: Success status
        """
        
        # Ensure the output path has .mp4 extension
        output_path = output_path if output_path.endswith('.mp4') else output_path + '.mp4'
    
        try:
            info = self.analyze_video(input_path)
            params = self._get_optimal_compression_params(info)
            
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                '-crf', params['crf'],
                '-preset', params['preset'],
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                output_path
            ]
            
            self.logger.info(f"Compressing video with parameters: {params}")
            subprocess.run(cmd, check=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Error compressing video: {e}")
            return False

    def change_resolution(self, input_path: str, output_path: str, width: int, height: int) -> bool:
        """
        Change video resolution
        
        Args:
            input_path: Input video file path
            output_path: Output video file path
            width: Target width
            height: Target height
            
        Returns:
            bool: Success status
        """
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264',
                '-crf', '23',
                '-c:a', 'copy',
                output_path
            ]
            
            self.logger.info(f"Changing resolution to {width}x{height}")
            subprocess.run(cmd, check=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Error changing resolution: {e}")
            return False

    def change_aspect_ratio(self, input_path: str, output_path: str, aspect_ratio: str) -> bool:
        """
        Change video aspect ratio
        
        Args:
            input_path: Input video file path
            output_path: Output video file path
            aspect_ratio: Target aspect ratio (e.g., "16:9")
            
        Returns:
            bool: Success status
        """
        try:
            # Parse aspect ratio
            width_ratio, height_ratio = map(int, aspect_ratio.split(':'))
            
            cmd = [
                'ffmpeg', '-i', input_path,
                '-vf', f'setdar={width_ratio}/{height_ratio}',
                '-c:v', 'libx264',
                '-crf', '23',
                '-c:a', 'copy',
                output_path
            ]
            
            self.logger.info(f"Changing aspect ratio to {aspect_ratio}")
            subprocess.run(cmd, check=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Error changing aspect ratio: {e}")
            return False

    def extract_audio(self, input_path: str, output_path: str) -> bool:
        """
        Extract audio from video to MP3
        
        Args:
            input_path: Input video file path
            output_path: Output audio file path
            
        Returns:
            bool: Success status
        """
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-vn',
                '-acodec', 'libmp3lame',
                '-q:a', '2',
                output_path
            ]
            
            self.logger.info("Extracting audio to MP3")
            subprocess.run(cmd, check=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Error extracting audio: {e}")
            return False

    def create_gif(self, input_path: str, output_path: str, start_time: float, duration: float) -> bool:
        """
        Create GIF from video segment
        
        Args:
            input_path: Input video file path
            output_path: Output GIF file path
            start_time: Start time in seconds
            duration: Duration in seconds
            
        Returns:
            bool: Success status
        """
        try:
            # Generate palette for better quality
            palette_path = os.path.join(self.work_dir, 'palette.png')
            
            # Generate palette
            palette_cmd = [
                'ffmpeg', '-ss', str(start_time),
                '-t', str(duration),
                '-i', input_path,
                '-vf', 'fps=10,scale=320:-1:flags=lanczos,palettegen',
                palette_path
            ]
            
            # Create GIF using palette
            gif_cmd = [
                'ffmpeg', '-ss', str(start_time),
                '-t', str(duration),
                '-i', input_path,
                '-i', palette_path,
                '-filter_complex', 'fps=10,scale=320:-1:flags=lanczos[x];[x][1:v]paletteuse',
                output_path
            ]
            
            self.logger.info(f"Creating GIF from {start_time}s to {start_time + duration}s")
            subprocess.run(palette_cmd, check=True)
            subprocess.run(gif_cmd, check=True)
            
            # Clean up palette
            os.remove(palette_path)
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating GIF: {e}")
            if os.path.exists(palette_path):
                os.remove(palette_path)
            return False

    def create_webm(self, input_path: str, output_path: str, start_time: float, duration: float) -> bool:
        """
        Create WebM from video segment
        
        Args:
            input_path: Input video file path
            output_path: Output WebM file path
            start_time: Start time in seconds
            duration: Duration in seconds
            
        Returns:
            bool: Success status
        """
        try:
            cmd = [
                'ffmpeg', '-ss', str(start_time),
                '-t', str(duration),
                '-i', input_path,
                '-c:v', 'libvpx-vp9',
                '-crf', '30',
                '-b:v', '0',
                '-c:a', 'libopus',
                output_path
            ]
            
            self.logger.info(f"Creating WebM from {start_time}s to {start_time + duration}s")
            subprocess.run(cmd, check=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating WebM: {e}")
            return False