# Manim Animation Generator

AI-powered Manim animation generator using LangGraph and MCP (FastMCP). This project allows users to create mathematical animations by simply describing what they want in natural language.

## Features

- 🤖 **AI-Powered Code Generation**: Uses OpenAI GPT-4.1 to generate Manim code from natural language descriptions
- 🔄 **Automatic Error Fixing**: LangGraph automatically detects and fixes errors in generated code
- 🎬 **Beautiful Animations**: Generates high-quality mathematical animations using Manim
- 🎨 **Simple UI**: Clean Streamlit interface for easy interaction
- 🏗️ **Modular Architecture**: Follows SOLID principles for maintainability

## Architecture

- **LangGraph**: Orchestrates the workflow (query refinement → code generation → execution → error fixing)
- **FastMCP**: MCP server for executing Manim code
- **Streamlit**: Simple web UI for user interaction
- **OpenAI**: LLM for code generation and refinement

## Setup

### Prerequisites

- Python 3.11+
- OpenAI API key (or Azure OpenAI credentials)
- Manim installed (will be installed via dependencies)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd manim_animation_generator
```

2. Install dependencies using `uv`:
```bash
uv sync
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Edit `.env` and configure one provider:

   Option A (OpenAI):
```
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

   Option B (Azure OpenAI):
```
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Running the Application

1. Start the Streamlit app using `uv run`:
```bash
uv run streamlit run app/streamlit_app.py
```

   Alternatively, if you have activated the virtual environment:
```bash
streamlit run app/streamlit_app.py
```

2. Open your browser to the URL shown in the terminal (usually `http://localhost:8501`)

3. Enter a description of the animation you want (e.g., "Create an animation showing how a neural network works")

4. Click "Generate Animation" and wait for the result!

## Project Structure

```
manim_animation_generator/
├── app/
│   └── streamlit_app.py          # Streamlit UI
├── core/
│   ├── config.py                 # Configuration management
│   ├── models.py                 # Pydantic models
│   ├── llm/
│   │   └── openai_client.py     # OpenAI client wrapper
│   ├── manim_client/
│   │   ├── interfaces.py         # IManimExecutor interface
│   │   └── mcp_client.py         # MCP client implementation
│   └── graph/
│       ├── state.py              # LangGraph state
│       ├── nodes.py              # Graph nodes
│       └── builder.py            # Graph builder
├── mcp_servers/
│   └── manim_server/
│       └── main.py               # FastMCP server
├── .env.example                  # Environment variables template
├── pyproject.toml                # Project dependencies
└── README.md                     # This file
```

## Usage Example

1. Enter prompt: "Create an animation of how a neural network works"
2. LangGraph refines the query
3. OpenAI generates Manim Python code
4. MCP server executes the code
5. Video is displayed in the UI

## Configuration

Edit `.env` to customize:
- `OPENAI_MODEL`: Model name (OpenAI) or optional override for Azure deployment
- `OPENAI_BASE_URL`: Optional custom OpenAI-compatible base URL
- `AZURE_OPENAI_ENDPOINT`: Azure endpoint (required for Azure mode)
- `AZURE_OPENAI_DEPLOYMENT`: Azure deployment name (required for Azure mode)
- `MANIM_OUTPUT_DIR`: Directory for generated videos (default: videos)
- `MANIM_DEFAULT_QUALITY`: Animation quality - low/medium/high (default: medium)
- `MAX_RETRIES`: Maximum retry attempts for error fixing (default: 3)


