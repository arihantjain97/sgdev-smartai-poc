#!/usr/bin/env python3
"""
Script to recursively collect all files from a directory and output them
in a structured text format with tree hierarchy and file contents.
"""

import os
import argparse
from pathlib import Path


def generate_tree(directory):
    """Generate a tree-like structure of the directory."""
    tree_lines = []
    
    def build_tree(path, prefix="", is_last=True):
        path = Path(path)
        if path.is_file():
            tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{path.name}")
        elif path.is_dir():
            tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{path.name}/")
            
            try:
                children = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                for i, child in enumerate(children):
                    is_last_child = i == len(children) - 1
                    child_prefix = prefix + ("    " if is_last else "│   ")
                    build_tree(child, child_prefix, is_last_child)
            except PermissionError:
                tree_lines.append(f"{prefix}    [Permission Denied]")
    
    build_tree(directory)
    return tree_lines


def collect_files(directory, output_file):
    """
    Recursively collect all files from directory and write to output file.
    
    Args:
        directory (str): Source directory to collect files from
        output_file (str): Output file path
    """
    source_dir = Path(directory).resolve()
    output_path = Path(output_file).resolve()
    
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory '{directory}' does not exist")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get all files recursively
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = Path(root) / file
            all_files.append(file_path)
    
    # Sort files for consistent ordering
    all_files.sort(key=lambda x: str(x).lower())
    
    print(f"Found {len(all_files)} files in '{source_dir}'")
    print(f"Writing to '{output_path}'")
    
    with open(output_path, 'w', encoding='utf-8') as outfile:
        # Write tree hierarchy
        outfile.write("Directory Structure:\n")
        outfile.write("=" * 50 + "\n")
        tree_lines = generate_tree(source_dir)
        for line in tree_lines:
            outfile.write(line + "\n")
        outfile.write("\n")
        
        # Write file contents
        for file_path in all_files:
            try:
                # Calculate relative path from source directory
                rel_path = file_path.relative_to(source_dir)
                
                # Write file header
                outfile.write(f"File: {rel_path}\n")
                outfile.write(f"[{file_path.name}: start]\n")
                
                # Read and write file content
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                        outfile.write(content)
                        
                        # Ensure content ends with newline if it doesn't already
                        if content and not content.endswith('\n'):
                            outfile.write('\n')
                            
                except UnicodeDecodeError:
                    # Handle binary files
                    outfile.write(f"[Binary file - {file_path.stat().st_size} bytes]\n")
                except Exception as e:
                    outfile.write(f"[Error reading file: {str(e)}]\n")
                
                # Write file footer
                outfile.write(f"[{file_path.name}: end]\n")
                outfile.write("\n")
                
            except Exception as e:
                outfile.write(f"Error processing {file_path}: {str(e)}\n")
                outfile.write(f"[{file_path.name}: end]\n")
                outfile.write("\n")
    
    print(f"Successfully wrote {len(all_files)} files to '{output_path}'")


def main():
    parser = argparse.ArgumentParser(
        description="Recursively collect all files from a directory and output them in a structured format"
    )
    parser.add_argument(
        "source_dir", 
        help="Source directory to collect files from (directory A)"
    )
    parser.add_argument(
        "output_file", 
        help="Output file path"
    )
    
    args = parser.parse_args()
    
    try:
        collect_files(args.source_dir, args.output_file)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
