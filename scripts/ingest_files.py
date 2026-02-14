#!/usr/bin/env python3
import argparse
from app.tools.files_local import FileIngester

def main():
    parser = argparse.ArgumentParser(description="Ingest files for Q&A")
    parser.add_argument("directory", help="Directory to ingest")
    args = parser.parse_args()
    
    ingester = FileIngester()
    ingester.ingest_directory(args.directory)
    print(f"Ingested files from {args.directory}")

if __name__ == "__main__":
    main()
