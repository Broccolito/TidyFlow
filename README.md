
# TidyBrain <img src="assets/logo.png" align="right" alt="TidyBrain Logo" width="150"/>

MCP-compliant R code execution and management agent for Claude Desktop Extension.

TidyBrain aims to empower R programming with Model Context Protocol.

## Overview

**TidyBrain** is an MCP (Model Context Protocol) server that allows Claude to generate, execute, and manage R scripts within a user-specified directory. It provides a complete workflow for statistical programming and data analysis through natural language interaction — no manual setup required.

## Features

- **Execute R code and scripts** directly from Claude  
- **Manage R script files** — create, rename, append, and write  
- **Set and manage working directories** for analysis projects  
- **Inspect R objects** and session state  
- **Read and preview output files** (CSV, TSV, RDS, text, etc.)  
- **List and manage exported results**  
- **Automatic workspace saving**  
- **Sandboxed file operations** for safety  

## Installation (No Dependencies Needed)

### Step 0. Download and set up Claude Desktop

Download [Claude Desktop](https://www.claude.com/download), and then set up and log in following instructions.

### Step 1: Download `TidyBrain.mcpb`

Simply download the latest **`TidyBrain.mcpb`** file from this repository or release page.

### Step 2: Install in Claude Desktop

1. Locate the downloaded `TidyBrain.mcpb` file  
2. Double-click the file  
3. Claude Desktop will open and prompt to install  
4. Follow the on-screen instructions  

## Configuration (Optional)

To streamline your workflow:

1. Open Claude Desktop  
2. Go to **Settings → Extensions → MCP Servers**  
3. Find **“TidyBrain”**  
4. Enable **“Allow tools to run without permission”** (Auto-approve)  
5. Restart Claude Desktop  

To make the tool more powerful:

1. Open **Settings → Capabilities → Code execution and file creation**
2. Enable this option to gain improved performance

## Usage Examples

Once installed, you can interact with `TidyBrain` using natural language.  
Here are common commands and workflows:

### Common Commands

#### Setup & Configuration

```

"Set working directory to ~/my_analysis"    # Initialize workspace
"Show current state"                        # Check configuration
"Find R executable"                         # Verify R installation

```

#### File Management

```

"Create an R file called analysis.R"        # New script with scaffold
"Write R code to load and plot data"        # Generate and save code
"Append summary statistics to my script"    # Add to existing file
"Rename script.R to final_analysis.R"       # Rename files
"List all R files"                          # View R scripts

```

#### Code Execution

```

"Run my R script"                           # Execute primary file
"Run R expression: mean(1:10)"              # Quick calculations
"Execute analysis.R with arguments"         # Run with parameters
"Show R objects in workspace"               # Inspect saved data

```

#### Data Operations

```

"Preview data.csv"                          # View CSV/TSV data
"Read results.txt"                          # Read text files
"List all output files"                     # See generated files
"Show files created today"                  # Recent outputs

```

#### Visualization & Analysis

```

"Optimize my ggplot code"                   # Improve plot styling
"Check ggplot style in my script"           # Style analysis
"Create publication-ready plot"             # High-quality output

```

## Example Workflows

### Basic Data Analysis

```

You: Create an R script for linear regression analysis
You: Load the mtcars dataset and fit a model of mpg vs weight
You: Run the script and show the model summary
You: Create diagnostic plots for the model
You: Save the plots as high-resolution PNGs

```

### Data Processing Pipeline

```

You: Set working directory to ~/data_project
You: Read my raw_data.csv file and show a preview
You: Create a script to clean missing values and outliers
You: Transform the data and save as cleaned_data.csv
You: Generate summary statistics and visualizations

```

### Publication-Quality Visualization

```

You: Create a ggplot scatter plot with trend line
You: Add confidence intervals and customize colors
You: Optimize the plot code for publication
You: Save as figure1.png with 800 DPI

```

### Exploratory Data Analysis

```

You: Load the iris dataset
You: Create a script for exploratory analysis
You: Generate summary statistics by species
You: Create box plots and correlation matrices
You: Run everything and show the results

```

## Available Tools

### Core Operations

- **set_workdir** — Set working directory for R operations  
- **get_state** — View configuration and runtime state  
- **which_r** — Locate R executable  

### File Management

- **create_r_file** — Create new R script  
- **rename_r_file** — Rename existing script  
- **write_r_code** — Write code to file (with overwrite protection)  
- **append_r_code** — Append to existing file  
- **set_primary_file** — Set default script for operations  
- **list_r_files** — List R scripts in workspace  

### Execution

- **run_r_script** — Execute R script file  
- **run_r_expression** — Evaluate R expression  
- **inspect_r_objects** — Explore workspace objects  

### Data Operations

- **list_exports** — List exported files  
- **read_export** — Read file contents (text or binary)  
- **preview_table** — Preview CSV/TSV tables  

### Analysis Tools

- **ggplot_style_check** — Optimize ggplot2 code for publication  

## Technical Details

- **Extension file:** `TidyBrain.mcpb`  
- **Protocol:** MCP (Model Context Protocol) 1.0+  
- **R Execution:** via Rscript  
- **Session Persistence:** `.tidybrain` directory for state  
- **Security:** Sandboxed file operations  

## Acknowledgments

Special thanks to **Beniamin Krupkin** and **Sara Smith** for the inspiration of this idea and their valuable contributions.

## Maintainer

**Wanjun Gu** ([wanjun.gu@ucsf.edu](mailto:wanjun.gu@ucsf.edu))

## License

MIT

