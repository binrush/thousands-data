#!/usr/bin/env python3
"""
CLI tool for uploading images to S3 storage.
"""

import typer
from pathlib import Path
from typing import Optional
import yaml
from PIL import Image
import boto3
from botocore.client import Config
from io import BytesIO
import sys
import os

# S3 Configuration (same as in import.py)
S3_ENDPOINT = "https://s3.timeweb.cloud"
S3_BUCKET = "302f9aa7-62c4d4d3-ccfd-4077-86c8-cca52e0da376"

app = typer.Typer(help="Upload images to S3 storage")


def resize_image(image_path: Path, target_width: int) -> BytesIO:
    """
    Resize an image to the target width while maintaining aspect ratio.
    
    Args:
        image_path: Path to the source image
        target_width: Desired width in pixels
        
    Returns:
        BytesIO object containing the resized image in JPEG format
    """
    with Image.open(image_path) as img:
        # Calculate new height to maintain aspect ratio
        aspect_ratio = img.height / img.width
        target_height = int(target_width * aspect_ratio)
        
        # Resize image
        resized_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if resized_img.mode in ("RGBA", "P"):
            resized_img = resized_img.convert("RGB")
        
        # Save to BytesIO
        output = BytesIO()
        resized_img.save(output, format="JPEG", quality=85, optimize=True)
        output.seek(0)
        
        return output


def upload_to_s3(file_obj: BytesIO, s3_key: str, bucket: str) -> None:
    """
    Upload a file object to S3.
    
    Args:
        file_obj: BytesIO object containing the file data
        s3_key: S3 key (path) for the uploaded file
        bucket: S3 bucket name
    """
    # Get credentials from environment variables
    s3_access_key = os.environ.get("S3_ACCESS_KEY")
    s3_secret_key = os.environ.get("S3_SECRET_KEY")
    
    if not s3_access_key or not s3_secret_key:
        typer.secho("✗ Error: S3_ACCESS_KEY and S3_SECRET_KEY environment variables must be set", 
                   fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    
    # Create S3 client with custom endpoint and addressing style
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=s3_access_key,
        aws_secret_access_key=s3_secret_key,
        config=Config(s3={'addressing_style': 'path'})
    )
    
    s3_client.upload_fileobj(
        file_obj,
        bucket,
        s3_key,
        ExtraArgs={'ContentType': 'image/jpeg'}
    )
    typer.echo(f"  ✓ Uploaded to s3://{bucket}/{s3_key}")


@app.command()
def upload(
    image_path: Path = typer.Option(
        ...,
        "--image-path",
        help="Path to the image file to upload",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    summit_path: Path = typer.Option(
        ...,
        "--summit-path",
        help="Path to the summit YAML file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    index: int = typer.Option(
        ...,
        "--index",
        help="Index number for the image in the YAML file",
    ),
    bucket: str = typer.Option(
        S3_BUCKET,
        "--bucket",
        help="S3 bucket name",
    ),
):
    """
    Upload an image to S3 storage.
    
    This command reads the summit YAML file, resizes the image to two versions
    (main: 1600px, preview: 75px), and uploads them to S3 using the paths
    specified in the YAML file.
    """
    try:
        # Read and parse YAML file
        typer.echo(f"📖 Reading summit file: {summit_path}")
        with open(summit_path, 'r') as f:
            summit_data = yaml.safe_load(f)
        
        # Get images list
        images = summit_data.get('images')
        if not images:
            typer.secho("✗ Error: No 'images' list found in YAML file", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        
        # Get image at specified index
        if index < 0 or index >= len(images):
            typer.secho(f"✗ Error: Index {index} out of range. Found {len(images)} images.", 
                       fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        
        image_entry = images[index]
        url = image_entry.get('url')
        preview_url = image_entry.get('preview_url')
        
        if not url or not preview_url:
            typer.secho("✗ Error: 'url' or 'preview_url' not found in image entry", 
                       fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        
        typer.echo(f"📷 Processing image at index {index}:")
        typer.echo(f"  Main URL: {url}")
        typer.echo(f"  Preview URL: {preview_url}")
        
        # Resize images
        typer.echo(f"\n🔄 Resizing image from: {image_path}")
        typer.echo(f"  Creating main version (1600px width)...")
        main_image = resize_image(image_path, 1600)
        
        typer.echo(f"  Creating preview version (75px width)...")
        preview_image = resize_image(image_path, 75)
        
        # Upload to S3
        typer.echo(f"\n☁️  Uploading to S3 bucket '{bucket}':")
        upload_to_s3(main_image, url, bucket)
        upload_to_s3(preview_image, preview_url, bucket)
        
        typer.secho("\n✓ Successfully uploaded images to S3!", fg=typer.colors.GREEN, bold=True)
        
    except FileNotFoundError as e:
        typer.secho(f"✗ Error: File not found - {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except yaml.YAMLError as e:
        typer.secho(f"✗ Error parsing YAML file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"✗ Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

