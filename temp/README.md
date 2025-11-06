# Temporary Scripts Directory

This directory contains temporary, testing, and one-off utility scripts that are not part of the core application.

## Categories

### Test Scripts

- `test_*.py` - Various test scripts for Flask app, video slicing, similarity, etc.

### Database Setup Scripts

- `create_schema_*.py` - Scripts to create database schemas for video embeddings
- `regenerate_*.py` - Scripts to regenerate embeddings
- `query_*.py` - Scripts to query video embeddings
- `store_*.py` - Scripts to store video embeddings
- `retrieve_*.py` - Scripts to retrieve existing embeddings

### One-off Utility Scripts

- `generate_readme_*.py` - Scripts to generate PDF versions of README
- `compress_*.py` - Video compression utilities
- `delete_*.py` - Scripts to delete specific items from the database

### Backup & Old Versions

- `localhost_flask.py` - Old version of Flask app
- `working_flask.py` - Previous working version of Flask app
- `INTEGRATION_GUIDE.py` - Integration guide script

## Usage

These scripts are for development, testing, and maintenance purposes. They should not be imported or used by the main application code in the `src/` directory.

## Note

If you need to run any of these scripts, make sure to:

1. Set up your `.env` file with proper credentials
2. Be in the project root directory
3. Have the virtual environment activated (if using one)
4. Be cautious with cleanup and delete scripts as they may modify the database

## Core Application

The core application code is located in the `src/` directory:

- `src/localhost_only_flask.py` - Main Flask application
- `src/search_unified_flask_safe.py` - Unified search for photos and video segments
- `src/video_upload_handler.py` - Video upload and slicing handler
- `src/video_slicer.py` - Video slicing utilities
- `src/video_thumbnail_generator.py` - Video thumbnail generation
- `src/generate_chunk_embeddings.py` - Generate embeddings for video chunks
