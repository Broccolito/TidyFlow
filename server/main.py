#!/usr/bin/env python3
"""
TidyBrain: MCP-compliant R code execution and management agent
Purpose: Generate, execute, and manage R scripts within a user-specified directory
Requirements: Python 3.8+, MCP SDK, R runtime (Rscript in PATH)
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import base64
import csv
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Configure logging to stderr for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# R script scaffold template - now minimal, getting straight to business
R_SCAFFOLD = """# ---- Packages ----
library(ggplot2)

# ---- Functions ----

# ---- Main ----

"""

# ggplot Style Guide for reference
GGPLOT_STYLE_GUIDE = """
# ggplot Style Guide - One-Time Code Optimization

## Core Principles:
1. **Assignment**: Always use = instead of <- 
2. **Theme**: Use theme_minimal() or theme_classic() with base_size=14
3. **Colors**: Muted palettes (Set2 for categorical, viridis for continuous)
4. **Dimensions**: Optimize for 5x4 inches (width x height)
5. **Typography**: Base size ≥ 14pt for readability
6. **Visibility**: Points ≥ 2.5, lines ≥ 0.8 width
7. **Export**: Always save with dpi=800

## Color Palette Guidelines:
### Categorical Data:
- Set2, Set3, Pastel1, Pastel2, Dark2 (RColorBrewer)
- Avoid default ggplot2 colors

### Continuous Data:
- viridis, magma, plasma, inferno, cividis
- Colorblind-friendly by default

### Diverging Data:
- RdBu, RdYlBu, Spectral, PuOr, BrBG
- Center at meaningful value

## Code Optimization Example:
```r
# Good practice - optimized code
library(ggplot2)

# Use = for assignments
data = read.csv("data.csv")

# Build plot with optimal settings
p = ggplot(data, aes(x=x_var, y=y_var, color=group)) +
  geom_point(size=2.5, alpha=0.8) +
  geom_line(linewidth=0.8) +
  scale_color_brewer(palette="Set2") +  # Muted categorical colors
  theme_minimal(base_size=14) +
  labs(x="Clear X Label",
       y="Clear Y Label", 
       title="Concise Title") +
  theme(plot.margin=margin(10,10,10,10))

# Save with optimal dimensions and quality
ggsave("plot.png", p, width=5, height=4, dpi=800)
```

## Automatic Optimizations:
- Replace theme_gray() → theme_minimal(base_size=14)
- Convert <- to = throughout
- Add color scales if missing (no defaults)
- Optimize dimensions to 5x4 inches
- Ensure dpi=800 for all exports
- Humanize variable names in labels
"""

class TidyBrainServer:
    def __init__(self):
        self.state_dir = None
        self.state_file = None
        self.workdir = None
        self.primary_file = "agent.R"  # Changed from .r to .R
        
    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file"""
        if not self.state_file or not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return {}
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state to JSON file with atomic write"""
        if not self.state_file:
            return
        temp_file = self.state_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            temp_file.replace(self.state_file)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            if temp_file.exists():
                temp_file.unlink()
    
    def ensure_workdir_set(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if workdir is set and valid"""
        if not self.workdir:
            return False, {"code": "NO_WORKDIR", "message": "Working directory not set. Use set_workdir first.", "hints": ["Call set_workdir with a directory path"]}
        if not self.workdir.exists():
            return False, {"code": "WORKDIR_MISSING", "message": f"Working directory {self.workdir} no longer exists", "hints": ["Recreate or set a new working directory"]}
        return True, None
    
    def is_safe_path(self, path: Path) -> bool:
        """Check if path is within workdir"""
        if not self.workdir:
            return False
        try:
            resolved = path.resolve()
            # For Python 3.8 compatibility
            try:
                return resolved.is_relative_to(self.workdir)
            except AttributeError:
                # Fallback for Python < 3.9
                try:
                    resolved.relative_to(self.workdir)
                    return True
                except ValueError:
                    return False
        except (ValueError, RuntimeError):
            return False
    
    def find_r_executable(self) -> Optional[str]:
        """Find R executable, preferring Rscript"""
        rscript = shutil.which("Rscript")
        if rscript:
            return rscript
        r_exe = shutil.which("R")
        if r_exe:
            return r_exe
        return None
    
    def run_r_command(self, args: List[str], timeout: int = 120) -> Dict[str, Any]:
        """Execute R command and capture output"""
        r_exe = self.find_r_executable()
        if not r_exe:
            return {
                "ok": False,
                "error": {
                    "code": "R_NOT_FOUND",
                    "message": "Rscript not found in PATH. Please install R or add Rscript to PATH.",
                    "hints": ["Install R from https://www.r-project.org/", "Ensure Rscript is in your system PATH"]
                }
            }
        
        start_time = time.time()
        try:
            result = subprocess.run(
                [r_exe] + args,
                capture_output=True,
                text=True,
                cwd=self.workdir,
                timeout=timeout,
                env={**os.environ, "R_LIBS_USER": str(self.workdir / "R_libs")}
            )
            elapsed = time.time() - start_time
            
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "elapsed_seconds": elapsed
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": {
                    "code": "TIMEOUT",
                    "message": f"R command timed out after {timeout} seconds",
                    "hints": ["Increase timeout_sec parameter", "Check for infinite loops in your code"]
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "EXEC_ERROR",
                    "message": f"Failed to execute R command: {str(e)}"
                }
            }
    
    def optimize_ggplot_code(self, code: str) -> Tuple[str, List[str]]:
        """Apply style guide optimizations to ggplot code"""
        optimized = code
        changes = []
        
        # Replace <- with = for assignments
        if '<-' in optimized:
            optimized = optimized.replace('<-', '=')
            changes.append("Replaced <- with = for assignments")
        
        # Replace theme_gray with theme_minimal
        if 'theme_gray()' in optimized or 'theme_grey()' in optimized:
            optimized = optimized.replace('theme_gray()', 'theme_minimal(base_size=14)')
            optimized = optimized.replace('theme_grey()', 'theme_minimal(base_size=14)')
            changes.append("Replaced default theme with theme_minimal(base_size=14)")
        
        # Check for ggsave and ensure proper dpi
        if 'ggsave(' in optimized and 'dpi=' not in optimized:
            optimized = optimized.replace('ggsave(', 'ggsave(dpi=800, ')
            changes.append("Added dpi=800 to ggsave for high quality output")
        
        # Check for default dimensions
        if 'ggsave(' in optimized and 'width=' not in optimized:
            optimized = optimized.replace('ggsave(', 'ggsave(width=5, height=4, ')
            changes.append("Added optimal dimensions (5x4 inches) to ggsave")
        
        return optimized, changes
    
    async def handle_set_workdir(self, path: str, create: bool = True) -> Dict[str, Any]:
        """Set working directory"""
        try:
            workdir = Path(path).resolve()
            
            if create:
                workdir.mkdir(parents=True, exist_ok=True)
            elif not workdir.exists():
                return {
                    "ok": False,
                    "error": {
                        "code": "DIR_NOT_FOUND",
                        "message": f"Directory {path} does not exist",
                        "hints": ["Set create=true to create the directory", "Provide an existing directory path"]
                    }
                }
            
            if not workdir.is_dir():
                return {
                    "ok": False,
                    "error": {
                        "code": "NOT_A_DIRECTORY",
                        "message": f"{path} is not a directory"
                    }
                }
            
            self.workdir = workdir
            self.state_dir = workdir / ".TidyBrain"
            self.state_dir.mkdir(exist_ok=True)
            self.state_file = self.state_dir / "state.json"
            
            # Save state
            state = self.load_state()
            state["workdir"] = str(workdir)
            state["primary_file"] = self.primary_file
            state["updated_at"] = datetime.now().isoformat()
            self.save_state(state)
            
            return {
                "ok": True,
                "data": {
                    "workdir": str(workdir),
                    "primary_file": self.primary_file,
                    "state_dir": str(self.state_dir)
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "SET_WORKDIR_ERROR",
                    "message": f"Failed to set working directory: {str(e)}"
                }
            }
    
    async def handle_get_state(self) -> Dict[str, Any]:
        """Get current state"""
        state = {
            "workdir": str(self.workdir) if self.workdir else None,
            "primary_file": self.primary_file,
            "r_executable": self.find_r_executable()
        }
        
        if self.state_file and self.state_file.exists():
            saved_state = self.load_state()
            state.update(saved_state)
        
        return {"ok": True, "data": state}
    
    async def handle_create_r_file(self, filename: str, overwrite: bool = False, scaffold: bool = True) -> Dict[str, Any]:
        """Create new R file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename = filename + '.R'
        
        file_path = self.workdir / filename
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if file_path.exists() and not overwrite:
            return {
                "ok": False,
                "error": {
                    "code": "FILE_EXISTS",
                    "message": f"File {filename} already exists",
                    "hints": ["Set overwrite=true to replace", "Use a different filename"]
                }
            }
        
        try:
            content = R_SCAFFOLD if scaffold else ""
            file_path.write_text(content)
            
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "path": str(file_path),
                    "scaffold_used": scaffold
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "CREATE_ERROR",
                    "message": f"Failed to create file: {str(e)}"
                }
            }
    
    async def handle_rename_r_file(self, old_name: str, new_name: str, overwrite: bool = False) -> Dict[str, Any]:
        """Rename R file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Ensure .R extension
        if not old_name.endswith(('.R', '.r')):
            old_name = old_name + '.R'
        if not new_name.endswith(('.R', '.r')):
            new_name = new_name + '.R'
        
        old_path = self.workdir / old_name
        new_path = self.workdir / new_name
        
        if not self.is_safe_path(old_path) or not self.is_safe_path(new_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": "File paths must be within working directory"
                }
            }
        
        if not old_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {old_name} does not exist"
                }
            }
        
        if new_path.exists() and not overwrite:
            return {
                "ok": False,
                "error": {
                    "code": "FILE_EXISTS",
                    "message": f"File {new_name} already exists",
                    "hints": ["Set overwrite=true to replace", "Use a different filename"]
                }
            }
        
        try:
            if new_path.exists():
                new_path.unlink()
            old_path.rename(new_path)
            
            # Update primary file if it was renamed
            if self.primary_file == old_name:
                self.primary_file = new_name
                state = self.load_state()
                state["primary_file"] = new_name
                self.save_state(state)
            
            return {
                "ok": True,
                "data": {
                    "old_name": old_name,
                    "new_name": new_name,
                    "primary_updated": self.primary_file == new_name
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "RENAME_ERROR",
                    "message": f"Failed to rename file: {str(e)}"
                }
            }
    
    async def handle_set_primary_file(self, filename: str) -> Dict[str, Any]:
        """Set primary R file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename = filename + '.R'
        
        file_path = self.workdir / filename
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if not file_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {filename} does not exist",
                    "hints": ["Create the file first using create_r_file"]
                }
            }
        
        self.primary_file = filename
        state = self.load_state()
        state["primary_file"] = filename
        self.save_state(state)
        
        return {
            "ok": True,
            "data": {
                "primary_file": filename
            }
        }
    
    async def handle_append_r_code(self, code: str, filename: Optional[str] = None, ensure_trailing_newline: bool = True) -> Dict[str, Any]:
        """Append code to R file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        if filename is None:
            filename = self.primary_file
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename = filename + '.R'
        
        file_path = self.workdir / filename
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if not file_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {filename} does not exist",
                    "hints": ["Create the file first using create_r_file"]
                }
            }
        
        try:
            existing_content = file_path.read_text()
            
            # Ensure existing content ends with newline
            if existing_content and not existing_content.endswith('\n'):
                existing_content += '\n'
            
            # Ensure code ends with newline if requested
            if ensure_trailing_newline and code and not code.endswith('\n'):
                code += '\n'
            
            new_content = existing_content + code
            file_path.write_text(new_content)
            
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "lines_appended": len(code.splitlines()),
                    "total_lines": len(new_content.splitlines())
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "APPEND_ERROR",
                    "message": f"Failed to append code: {str(e)}"
                }
            }
    
    async def handle_write_r_code(self, code: str, filename: Optional[str] = None, overwrite: bool = False, use_scaffold_header: bool = True) -> Dict[str, Any]:
        """Write code to R file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        if filename is None:
            filename = self.primary_file
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename = filename + '.R'
        
        file_path = self.workdir / filename
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if file_path.exists() and not overwrite:
            return {
                "ok": False,
                "error": {
                    "code": "FILE_EXISTS",
                    "message": f"File {filename} already exists",
                    "hints": ["Set overwrite=true to replace", "Use append_r_code to add to existing file"]
                }
            }
        
        try:
            # Apply scaffold if requested and code doesn't already have structure
            if use_scaffold_header and not code.strip().startswith('#'):
                content = R_SCAFFOLD + code
            else:
                content = code
            
            file_path.write_text(content)
            
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "path": str(file_path),
                    "lines_written": len(content.splitlines()),
                    "scaffold_used": use_scaffold_header
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "WRITE_ERROR",
                    "message": f"Failed to write code: {str(e)}"
                }
            }
    
    async def handle_run_r_script(self, filename: Optional[str] = None, args: Optional[List[str]] = None, timeout_sec: int = 120, save_rdata: bool = True) -> Dict[str, Any]:
        """Run R script"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        if filename is None:
            filename = self.primary_file
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename = filename + '.R'
        
        file_path = self.workdir / filename
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if not file_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {filename} does not exist",
                    "hints": ["Create and write code to the file first"]
                }
            }
        
        # Build command
        cmd_args = []
        if save_rdata:
            cmd_args.extend(["--save"])
        cmd_args.append(str(file_path))
        if args:
            cmd_args.extend(args)
        
        result = self.run_r_command(cmd_args, timeout_sec)
        
        if result.get("ok"):
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "elapsed_seconds": result.get("elapsed_seconds", 0),
                    "rdata_saved": save_rdata
                }
            }
        else:
            error_info = result.get("error", {})
            error_info["filename"] = filename
            error_info["stderr"] = result.get("stderr", "")
            return {"ok": False, "error": error_info}
    
    async def handle_run_r_expression(self, expr: str, timeout_sec: int = 60) -> Dict[str, Any]:
        """Run single R expression"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Use -e flag for expression evaluation
        result = self.run_r_command(["-e", expr], timeout_sec)
        
        if result.get("ok"):
            return {
                "ok": True,
                "data": {
                    "expression": expr,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "elapsed_seconds": result.get("elapsed_seconds", 0)
                }
            }
        else:
            error_info = result.get("error", {})
            error_info["expression"] = expr
            error_info["stderr"] = result.get("stderr", "")
            return {"ok": False, "error": error_info}
    
    async def handle_list_exports(self, glob: str = "*", sort_by: str = "mtime", descending: bool = True, limit: int = 200) -> Dict[str, Any]:
        """List files in working directory"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        try:
            files = []
            for item in self.workdir.glob(glob):
                if item.is_file():
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "extension": item.suffix
                    })
            
            # Sort files
            if sort_by == "mtime":
                files.sort(key=lambda x: x["mtime"], reverse=descending)
            elif sort_by == "size":
                files.sort(key=lambda x: x["size"], reverse=descending)
            elif sort_by == "name":
                files.sort(key=lambda x: x["name"], reverse=descending)
            
            # Apply limit
            files = files[:limit]
            
            # Format times
            for f in files:
                f["mtime_str"] = datetime.fromtimestamp(f["mtime"]).isoformat()
            
            return {
                "ok": True,
                "data": {
                    "files": files,
                    "count": len(files),
                    "workdir": str(self.workdir)
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "LIST_ERROR",
                    "message": f"Failed to list files: {str(e)}"
                }
            }
    
    async def handle_read_export(self, name: str, max_bytes: int = 50000, as_text: bool = True, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file from working directory"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        file_path = self.workdir / name
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {name} is outside working directory"
                }
            }
        
        if not file_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {name} does not exist"
                }
            }
        
        try:
            file_size = file_path.stat().st_size
            
            if as_text:
                # Read as text with size limit
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read(max_bytes)
                truncated = file_size > max_bytes
                
                return {
                    "ok": True,
                    "data": {
                        "name": name,
                        "content": content,
                        "size": file_size,
                        "truncated": truncated,
                        "encoding": encoding
                    }
                }
            else:
                # Read as binary and encode to base64
                with open(file_path, 'rb') as f:
                    content = f.read(max_bytes)
                truncated = file_size > max_bytes
                
                return {
                    "ok": True,
                    "data": {
                        "name": name,
                        "content_base64": base64.b64encode(content).decode('ascii'),
                        "size": file_size,
                        "truncated": truncated
                    }
                }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "READ_ERROR",
                    "message": f"Failed to read file: {str(e)}"
                }
            }
    
    async def handle_preview_table(self, name: str, delimiter: str = ",", max_rows: int = 50) -> Dict[str, Any]:
        """Preview CSV/TSV file as table"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        file_path = self.workdir / name
        if not self.is_safe_path(file_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {name} is outside working directory"
                }
            }
        
        if not file_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {name} does not exist"
                }
            }
        
        try:
            rows = []
            headers = None
            
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delimiter)
                
                # Read header
                try:
                    headers = next(reader)
                except StopIteration:
                    return {
                        "ok": False,
                        "error": {
                            "code": "EMPTY_FILE",
                            "message": "File is empty"
                        }
                    }
                
                # Read data rows
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    rows.append(row)
            
            return {
                "ok": True,
                "data": {
                    "name": name,
                    "headers": headers,
                    "rows": rows,
                    "row_count": len(rows),
                    "column_count": len(headers) if headers else 0,
                    "truncated": len(rows) == max_rows
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "PREVIEW_ERROR",
                    "message": f"Failed to preview table: {str(e)}"
                }
            }
    
    async def handle_ggplot_style_check(self, code: str) -> Dict[str, Any]:
        """Analyze and optimize ggplot code"""
        try:
            optimized, changes = self.optimize_ggplot_code(code)
            
            # Detect potential issues
            issues = []
            suggestions = []
            
            # Check for theme
            if 'theme_' not in code:
                issues.append("No theme specified")
                suggestions.append("Add theme_minimal(base_size=14) for clean, readable plots")
            
            # Check for color palette
            if 'ggplot(' in code and 'scale_' not in code:
                issues.append("No explicit color scale")
                suggestions.append("Add scale_color_brewer(palette='Set2') for categorical or scale_color_viridis() for continuous")
            
            # Check for labels
            if 'labs(' not in code and 'xlab(' not in code and 'ylab(' not in code:
                issues.append("No axis labels specified")
                suggestions.append("Add descriptive labels with labs(x='...', y='...', title='...')")
            
            # Check for save
            if 'ggsave(' not in code:
                suggestions.append("Remember to save with ggsave('filename.png', width=5, height=4, dpi=800)")
            
            return {
                "ok": True,
                "data": {
                    "original_code": code,
                    "optimized_code": optimized,
                    "changes_made": changes,
                    "issues_detected": issues,
                    "suggestions": suggestions,
                    "style_guide": GGPLOT_STYLE_GUIDE if len(issues) > 0 else None
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "STYLE_CHECK_ERROR",
                    "message": f"Failed to analyze code: {str(e)}"
                }
            }
    
    async def handle_inspect_r_objects(self, objects: Optional[List[str]] = None, str_max_level: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        """Inspect R objects from saved session"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Check if .RData exists
        rdata_path = self.workdir / ".RData"
        if not rdata_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "NO_RDATA",
                    "message": "No .RData file found. Run a script with save_rdata=true first.",
                    "hints": ["Run an R script with save_rdata=true", "Create objects in R and save the workspace"]
                }
            }
        
        # Build R expression to inspect objects
        if objects:
            # Inspect specific objects
            inspect_code = f"""
load('.RData')
objects_to_inspect <- c({', '.join([f'"{obj}"' for obj in objects])})
results <- list()
for(obj_name in objects_to_inspect) {{
    if(exists(obj_name)) {{
        obj <- get(obj_name)
        results[[obj_name]] <- list(
            class = class(obj),
            typeof = typeof(obj),
            length = length(obj),
            dim = dim(obj),
            names = names(obj),
            str = capture.output(str(obj, max.level={str_max_level}))
        )
    }} else {{
        results[[obj_name]] <- "Object not found"
    }}
}}
print(results)
"""
        else:
            # List all objects
            inspect_code = f"""
load('.RData')
obj_list <- ls()
if(length(obj_list) > 0) {{
    results <- list()
    for(obj_name in obj_list) {{
        obj <- get(obj_name)
        results[[obj_name]] <- list(
            class = class(obj),
            typeof = typeof(obj),
            length = length(obj),
            dim = dim(obj)
        )
    }}
    print(results)
}} else {{
    print("No objects in workspace")
}}
"""
        
        result = self.run_r_command(["-e", inspect_code], timeout_sec)
        
        if result.get("ok"):
            return {
                "ok": True,
                "data": {
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "objects_requested": objects,
                    "elapsed_seconds": result.get("elapsed_seconds", 0)
                }
            }
        else:
            error_info = result.get("error", {})
            error_info["stderr"] = result.get("stderr", "")
            return {"ok": False, "error": error_info}
    
    async def handle_which_r(self) -> Dict[str, Any]:
        """Find R executable"""
        rscript = shutil.which("Rscript")
        
        executable = None
        alternatives = []
        
        if rscript:
            executable = rscript
            alternatives.append(rscript)
        
        r_exe = shutil.which("R")
        if r_exe:
            if not executable:
                executable = r_exe
            alternatives.append(r_exe)
        
        if executable:
            return {
                "ok": True,
                "data": {
                    "executable": executable,
                    "alternatives": alternatives
                }
            }
        else:
            return {
                "ok": False,
                "error": {
                    "code": "R_NOT_FOUND",
                    "message": "R not found in PATH",
                    "hints": ["Install R from https://www.r-project.org/", "Add Rscript or R to your system PATH"]
                }
            }
    
    async def handle_list_r_files(self) -> Dict[str, Any]:
        """List all R files in working directory"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        try:
            r_files = []
            # Look for both .R and .r extensions
            for pattern in ["*.R", "*.r"]:
                for item in self.workdir.glob(pattern):
                    if item.is_file() and item.name not in r_files:
                        r_files.append(item.name)
            
            r_files.sort()
            
            return {
                "ok": True,
                "data": {
                    "files": r_files,
                    "primary_file": self.primary_file
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "LIST_ERROR",
                    "message": f"Failed to list R files: {str(e)}"
                }
            }

async def main():
    """Main entry point"""
    logger.info("Starting TidyBrain MCP server...")
    
    # Create server instance
    server = Server("TidyBrain")
    TidyBrain = TidyBrainServer()
    
    # Register list_tools handler
    @server.list_tools()
    async def list_tools():
        logger.debug("Listing tools...")
        return [
            Tool(name="set_workdir", description="Set the working directory for all R operations", 
                 inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "create": {"type": "boolean", "default": True}}, "required": ["path"]}),
            Tool(name="get_state", description="Get current TidyBrain state and configuration", 
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="create_r_file", description="Create a new R script file", 
                 inputSchema={"type": "object", "properties": {"filename": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}, "scaffold": {"type": "boolean", "default": True}}, "required": ["filename"]}),
            Tool(name="rename_r_file", description="Rename an R script file", 
                 inputSchema={"type": "object", "properties": {"old_name": {"type": "string"}, "new_name": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, "required": ["old_name", "new_name"]}),
            Tool(name="set_primary_file", description="Set the primary R script file", 
                 inputSchema={"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}),
            Tool(name="append_r_code", description="Append R code to an existing script file", 
                 inputSchema={"type": "object", "properties": {"code": {"type": "string"}, "filename": {"type": "string"}, "ensure_trailing_newline": {"type": "boolean", "default": True}}, "required": ["code"]}),
            Tool(name="write_r_code", description="Write R code to a script file", 
                 inputSchema={"type": "object", "properties": {"code": {"type": "string"}, "filename": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}, "use_scaffold_header": {"type": "boolean", "default": True}}, "required": ["code"]}),
            Tool(name="run_r_script", description="Execute an R script file", 
                 inputSchema={"type": "object", "properties": {"filename": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "timeout_sec": {"type": "integer", "default": 120}, "save_rdata": {"type": "boolean", "default": True}}}),
            Tool(name="run_r_expression", description="Execute a single R expression", 
                 inputSchema={"type": "object", "properties": {"expr": {"type": "string"}, "timeout_sec": {"type": "integer", "default": 60}}, "required": ["expr"]}),
            Tool(name="list_exports", description="List files in the working directory", 
                 inputSchema={"type": "object", "properties": {"glob": {"type": "string", "default": "*"}, "sort_by": {"type": "string", "default": "mtime"}, "descending": {"type": "boolean", "default": True}, "limit": {"type": "integer", "default": 200}}}),
            Tool(name="read_export", description="Read a file from the working directory", 
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "max_bytes": {"type": "integer", "default": 50000}, "as_text": {"type": "boolean", "default": True}, "encoding": {"type": "string", "default": "utf-8"}}, "required": ["name"]}),
            Tool(name="preview_table", description="Preview a CSV/TSV file as a table", 
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "delimiter": {"type": "string", "default": ","}, "max_rows": {"type": "integer", "default": 50}}, "required": ["name"]}),
            Tool(name="ggplot_style_check", description="Analyze and optimize ggplot code for publication-quality styling", 
                 inputSchema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}),
            Tool(name="inspect_r_objects", description="Inspect R objects from the last saved session", 
                 inputSchema={"type": "object", "properties": {"objects": {"type": "array", "items": {"type": "string"}}, "str_max_level": {"type": "integer", "default": 1}, "timeout_sec": {"type": "integer", "default": 60}}}),
            Tool(name="which_r", description="Find R executable in PATH", 
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="list_r_files", description="List all R script files in the working directory", 
                 inputSchema={"type": "object", "properties": {}})
        ]
    
    # Register call_tool handler
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        logger.debug(f"Calling tool: {name} with arguments: {arguments}")
        try:
            if name == "set_workdir":
                result = await TidyBrain.handle_set_workdir(**arguments)
            elif name == "get_state":
                result = await TidyBrain.handle_get_state()
            elif name == "create_r_file":
                result = await TidyBrain.handle_create_r_file(**arguments)
            elif name == "rename_r_file":
                result = await TidyBrain.handle_rename_r_file(**arguments)
            elif name == "set_primary_file":
                result = await TidyBrain.handle_set_primary_file(**arguments)
            elif name == "append_r_code":
                result = await TidyBrain.handle_append_r_code(**arguments)
            elif name == "write_r_code":
                result = await TidyBrain.handle_write_r_code(**arguments)
            elif name == "run_r_script":
                result = await TidyBrain.handle_run_r_script(**arguments)
            elif name == "run_r_expression":
                result = await TidyBrain.handle_run_r_expression(**arguments)
            elif name == "list_exports":
                result = await TidyBrain.handle_list_exports(**arguments)
            elif name == "read_export":
                result = await TidyBrain.handle_read_export(**arguments)
            elif name == "preview_table":
                result = await TidyBrain.handle_preview_table(**arguments)
            elif name == "ggplot_style_check":
                result = await TidyBrain.handle_ggplot_style_check(**arguments)
            elif name == "inspect_r_objects":
                result = await TidyBrain.handle_inspect_r_objects(**arguments)
            elif name == "which_r":
                result = await TidyBrain.handle_which_r()
            elif name == "list_r_files":
                result = await TidyBrain.handle_list_r_files()
            else:
                result = {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {name}"}}
            
            logger.debug(f"Tool {name} result: {result}")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            logger.error(f"Error in tool {name}: {str(e)}")
            logger.error(traceback.format_exc())
            error_result = {
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Internal error: {str(e)}"
                }
            }
            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    # Run server with initialization_options parameter
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server running...")
            initialization_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, initialization_options)
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

