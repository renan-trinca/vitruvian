import logging
import os
from pathlib import Path

import typer
import yaml

from minisweagent import package_dir
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models.litellm_model import LitellmModel

from vitruvian.agents.vitruvian_agent import VitruvianAgent
from vitruvian.modules.anti_loop import AntiLoopModule
from vitruvian.modules.proofreading.tech_stack_validator import TechStackValidatorModule
from vitruvian.modules.proofreading.mismatch_repair import MismatchRepairModule
from vitruvian.modules.embodiment.embodiment_module import EmbodimentModule

app = typer.Typer()

class ColorLogFormatter(logging.Formatter):
    """Custom formatter to highlight biological interventions in terminal."""
    def format(self, record):
        msg = super().format(record)
        # ANSI Colors
        YELLOW = "\033[93m"
        CYAN = "\033[96m"
        RED = "\033[91m"
        GREEN = "\033[92m"
        RESET = "\033[0m"

        if "INIBIÇÃO" in msg or "Lib desconhecida" in msg or "Anti-pattern" in msg or "MismatchRepair" in msg:
            return f"{YELLOW}🛡️ [VITRUVIAN INTERVENTION]{RESET} {msg}"
        if "Embodiment" in msg or "SchemaBuidler" in msg:
            return f"{CYAN}🧠 [VITRUVIAN CONTEXT]{RESET} {msg}"
        if record.levelno >= logging.WARNING:
            return f"{RED}{msg}{RESET}"
        if record.levelno == logging.INFO:
            return f"{GREEN}{msg}{RESET}"
        return msg

@app.command()
def main(
    task: str = typer.Option(..., "-t", "--task", help="Task/problem statement", show_default=False, prompt=True),
    model_name: str = typer.Option(
        os.getenv("VITRUVIAN_MODEL_NAME", os.getenv("MSWEA_MODEL_NAME", "claude-3-5-sonnet-20241022")),
        "-m",
        "--model",
        help="Model name (defaults to VITRUVIAN_MODEL_NAME env var)",
    ),
    project_root: str = typer.Option(
        ".",
        "-d",
        "--dir",
        help="Project directory to scan and modify (default: current dir)"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
) -> VitruvianAgent:
    
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(ColorLogFormatter('%(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=log_level, handlers=[handler], force=True)

    project_path = Path(project_root).resolve()
    typer.secho(f"🚀 Vitruvian Agent initializing on {project_path} with {model_name}", fg=typer.colors.GREEN, bold=True)

    agent = VitruvianAgent.create_with_biology(project_path, model_name)
    
    typer.secho(f"\n--- ASSIGNMENT ---", fg=typer.colors.YELLOW, bold=True)
    typer.echo(task)
    typer.secho(f"------------------\n", fg=typer.colors.YELLOW, bold=True)

    try:
        agent.run(task)
    except Exception as e:
        typer.secho(f"\n❌ Execution ended with error: {e}", fg=typer.colors.RED, bold=True)
        if debug:
            import traceback
            traceback.print_exc()
            
    return agent

if __name__ == "__main__":
    app()
