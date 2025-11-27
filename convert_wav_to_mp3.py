"""
Convert WAV files from S3 bucket to MP3 format.

For each WAV file in the S3 bucket:
1. Download WAV file
2. Convert to MP3 using ffmpeg
3. Upload MP3 back to S3 bucket
4. Delete local WAV file
5. Keep MP3 in audio/book_name folder
"""

import subprocess
from pathlib import Path
from typing import Optional
import boto3
from tqdm.auto import tqdm


class WavToMp3Converter:
    def __init__(self, s3_bucket: str, output_bucket: Optional[str] = None):
        """
        Initialize converter.

        Args:
            s3_bucket: Source S3 bucket containing WAV files
            output_bucket: Destination S3 bucket for MP3 files (defaults to same bucket)
        """
        self.s3_bucket = s3_bucket
        self.output_bucket = output_bucket or s3_bucket
        self.s3_client = boto3.client("s3")

    def _list_wav_files(self, book_name: Optional[str] = None) -> list:
        """
        List all WAV files in the S3 bucket.

        Args:
            book_name: Optional book name to filter files

        Returns:
            List of S3 object keys ending in .wav
        """
        prefix = f"{book_name}/" if book_name else ""

        wav_files = []
        paginator = self.s3_client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                if key.lower().endswith(".wav"):
                    wav_files.append(key)

        return wav_files

    def _download_wav(self, s3_key: str, local_path: Path):
        """Download WAV file from S3."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.s3_client.download_file(self.s3_bucket, s3_key, str(local_path))

    def _convert_to_mp3(self, wav_path: Path, mp3_path: Path):
        """
        Convert WAV to MP3 using ffmpeg.

        Args:
            wav_path: Path to input WAV file
            mp3_path: Path to output MP3 file
        """
        mp3_path.parent.mkdir(parents=True, exist_ok=True)

        # Use ffmpeg to convert WAV to MP3
        # -i: input file
        # -codec:a libmp3lame: use MP3 encoder
        # -q:a 2: VBR quality (0-9, where 0 is best quality)
        # -y: overwrite output file without asking
        cmd = [
            "ffmpeg",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-y",
            str(mp3_path),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            raise Exception(f"ffmpeg failed: {result.stderr}")

    def _upload_mp3(self, mp3_path: Path, s3_key: str):
        """Upload MP3 file to S3."""
        self.s3_client.upload_file(
            str(mp3_path),
            self.output_bucket,
            s3_key,
            ExtraArgs={"ContentType": "audio/mpeg"},
        )

    def _process_single_file(self, s3_key: str):
        """
        Process a single WAV file: download, convert, upload, cleanup.

        Args:
            s3_key: S3 key of the WAV file
        """
        try:
            # Parse the S3 key to extract book name and relative path
            # Expected format: book_name/path/to/file.wav
            parts = s3_key.split("/")
            if len(parts) < 2:
                tqdm.write(f"Skipping invalid key: {s3_key}")
                return

            book_name = parts[0]
            relative_path = "/".join(parts[1:])

            # Create local paths
            audio_dir = Path("audio") / book_name
            wav_path = audio_dir / relative_path
            mp3_relative = Path(relative_path).with_suffix(".mp3")
            mp3_path = audio_dir / mp3_relative

            # S3 key for MP3
            mp3_s3_key = f"{book_name}/{mp3_relative}".replace("\\", "/")

            # Check if MP3 already exists in S3
            try:
                self.s3_client.head_object(Bucket=self.output_bucket, Key=mp3_s3_key)
                tqdm.write(f"Skipping (MP3 exists in S3): {s3_key}")
                return
            except:
                pass  # MP3 doesn't exist, proceed with conversion

            # Check if MP3 already exists locally
            if mp3_path.exists():
                tqdm.write(f"Skipping (MP3 exists locally): {s3_key}")
                return

            tqdm.write(f"Processing: {s3_key}")

            # Download WAV
            tqdm.write("  Downloading WAV...")
            self._download_wav(s3_key, wav_path)

            # Convert to MP3
            tqdm.write("  Converting to MP3...")
            self._convert_to_mp3(wav_path, mp3_path)

            # Upload MP3 to S3
            tqdm.write("  Uploading MP3 to S3...")
            self._upload_mp3(mp3_path, mp3_s3_key)
            tqdm.write(f"  Uploaded: s3://{self.output_bucket}/{mp3_s3_key}")

            # Delete local WAV file
            wav_path.unlink()
            tqdm.write(f"  Deleted local WAV: {wav_path}")

            # Keep MP3 locally
            tqdm.write(f"  Kept local MP3: {mp3_path}")

        except Exception as e:
            tqdm.write(f"Error processing {s3_key}: {e}")

    def convert_book(self, book_name: Optional[str] = None):
        """
        Convert all WAV files for a specific book or all books.

        Args:
            book_name: Optional book name to process. If None, processes all books.
        """
        wav_files = self._list_wav_files(book_name)

        if not wav_files:
            print(f"No WAV files found in bucket: {self.s3_bucket}")
            if book_name:
                print(f"  (filtered by book: {book_name})")
            return

        print(f"Found {len(wav_files)} WAV files to convert")

        for wav_file in tqdm(wav_files, desc="Converting WAV to MP3"):
            self._process_single_file(wav_file)

        print("Conversion completed!")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert WAV files from S3 to MP3 format"
    )
    parser.add_argument(
        "--book",
        type=str,
        help="Book name to process (e.g., 'sirens'). If not provided, processes all books.",
    )
    parser.add_argument(
        "--source-bucket",
        type=str,
        default="ai-generated-audio-books-eu-west-1-wav",
        help="Source S3 bucket containing WAV files",
    )
    parser.add_argument(
        "--output-bucket",
        type=str,
        help="Destination S3 bucket for MP3 files (defaults to source bucket)",
    )

    args = parser.parse_args()

    converter = WavToMp3Converter(
        s3_bucket=args.source_bucket, output_bucket=args.output_bucket
    )

    converter.convert_book(args.book)


if __name__ == "__main__":
    main()
