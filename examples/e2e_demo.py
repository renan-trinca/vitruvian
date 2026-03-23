import sys
import logging
from pathlib import Path
from rich.console import Console

# Adjust path to find the packages
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("mini-swe-agent/src").resolve()))

from minisweagent.environments.local import LocalEnvironment
from minisweagent.models.litellm_model import LitellmModel, LitellmModelConfig

from vitruvian.agents.vitruvian_agent import VitruvianAgent
from vitruvian.modules.anti_loop import AntiLoopModule
from vitruvian.modules.proofreading.tech_stack_validator import TechStackValidatorModule
from vitruvian.modules.proofreading.mismatch_repair import MismatchRepairModule
from vitruvian.modules.embodiment.embodiment_module import EmbodimentModule
from vitruvian.run import ColorLogFormatter

from pydantic import BaseModel

console = Console()

class FakeFunction(BaseModel):
    name: str
    arguments: str

class FakeToolCall(BaseModel):
    id: str = "call_1"
    type: str = "function"
    function: FakeFunction

class FakeMessage(BaseModel):
    role: str = "assistant"
    content: str = ""
    tool_calls: list[FakeToolCall] | None = None

class FakeChoice(BaseModel):
    message: FakeMessage

class FakeResponse(BaseModel):
    choices: list[FakeChoice]
    def model_dump(self, **kwargs):
        return {"choices": [{"message": {"content": self.choices[0].message.content, "tool_calls": [{"function": {"name": self.choices[0].message.tool_calls[0].function.name, "arguments": self.choices[0].message.tool_calls[0].function.arguments}}]}}]}

class MockModel(LitellmModel):
    step_counter = 0
    def __init__(self):
        super().__init__(config_class=LitellmModelConfig, model_name="mock")
    
    def _query(self, messages, **kwargs):
        self.step_counter += 1
        if self.step_counter == 1:
            cmd = "pip install react"
            content = "Instalando react do npm com pip (erro intencional de stack)"
        else:
            cmd = "python fail_script.py"
            content = f"Tentativa {self.step_counter - 1} de rodar o fail_script.py"
            
        console.print(f"\n[bold green]--> Outputting command: {cmd}[/bold green]\n")
        
        return FakeResponse(choices=[
            FakeChoice(message=FakeMessage(
                content=content,
                tool_calls=[FakeToolCall(function=FakeFunction(name="bash", arguments=f'{{"command": "{cmd}"}}'))]
            ))
        ])

    def query(self, messages, **kwargs):
        msg = super().query(messages, **kwargs)
        console.print(f"[bold magenta]PARSED ACTIONS:[/bold magenta] {msg.get('extra', {}).get('actions')}")
        return msg

    def _calculate_cost(self, response):
        return {"cost": 0.0}

def run_demo():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorLogFormatter('%(message)s'))
    logging.getLogger('vitruvian').setLevel(logging.DEBUG)
    logging.getLogger('vitruvian').addHandler(handler)
    logging.getLogger('vitruvian').propagate = False

    project_path = Path("e2e_mock").resolve()
    project_path.mkdir(exist_ok=True)
    
    with open(project_path / "fail_script.py", "w") as f:
        f.write("assert False, 'Hardcoded Failure'")
    with open(project_path / "package.json", "w") as f:
        f.write('{"dependencies": {"node-fetch": "2.0"}}')

    anti_loop = AntiLoopModule(repetition_limit=3, max_inhibitions=5)
    tech_stack = TechStackValidatorModule(project_root=project_path)
    mismatch_repair = MismatchRepairModule(project_root=project_path)
    embodiment = EmbodimentModule(project_root=project_path)
    
    tech_stack._scan_project()

    import yaml
    from minisweagent import package_dir
    agent_config = yaml.safe_load(Path(package_dir / "config" / "default.yaml").read_text())["agent"]
    agent_config["step_limit"] = 10

    agent = VitruvianAgent(
        model=MockModel(),
        env=LocalEnvironment(),
        modules=[anti_loop, tech_stack, mismatch_repair, embodiment],
        **agent_config
    )
    
    console.print("[bold yellow]--- VITRUVIAN BIOLOGICAL TELEMETRY DEMO ---[/bold yellow]")
    try:
        agent.run("Fix the script.")
    except Exception as e:
        if "CircuitBreakerError" in str(e) or "Loop infinito" in str(e):
            console.print(f"\n[bold green]✅ Simulation successful![/bold green] Agent was correctly terminated by Circuit Breaker: {e}")
        else:
            raise e

if __name__ == "__main__":
    run_demo()
