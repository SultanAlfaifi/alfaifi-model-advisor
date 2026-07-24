from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Iterator

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from .models import HardwareProfile, ModelCandidate, Recommendation, UserNeeds


BRAND = "MUSTAKSHIF"
X_URL = "https://x.com/SultAlfaifi"
LINKEDIN_URL = "https://www.linkedin.com/in/alfaifi-sultan/"
GITHUB_URL = "https://github.com/SultanAlfaifi/mustakshif"

EXPERIENCE = {1: "beginner", 2: "intermediate", 3: "advanced"}
GOALS = {
    1: ("general", "General chat and everyday use"),
    2: ("writing", "Writing and summarization"),
    3: ("coding", "Programming"),
    4: ("agents", "Agents and tool use"),
    5: ("vision", "Image and interface analysis"),
    6: ("ui_design", "UI design and design-to-code"),
    7: ("documents", "Document and PDF analysis"),
    8: ("translation", "Translation"),
    9: ("reasoning", "Research and reasoning"),
}
LANGUAGE = {1: "ar", 2: "en", 3: "both"}
PRIORITY = {1: "balanced", 2: "speed", 3: "quality", 4: "memory"}
LOCALITY = {1: "local", 2: "both", 3: "cloud"}
CONTEXT = {1: "short", 2: "medium", 3: "long"}
MODE_LABELS = {
    "full_gpu": "Full GPU (expected)",
    "hybrid": "GPU + system RAM",
    "cpu": "CPU / system RAM",
    "cloud": "Cloud",
}


class AppUI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(highlight=False)

    def header(self) -> None:
        title = Text()
        title.append("  MUSTAKSHIF  ", style="bold white on #2563eb")
        subtitle = Text("Explore the models. Discover the right fit.", style="bold white")
        trust_line = Text("PRIVATE  •  EXPLAINABLE  •  OFFICIAL SOURCES  •  NO AUTO-DOWNLOADS", style="dim cyan")
        body = Text.assemble(
            title,
            "\n\n",
            subtitle,
            "\n",
            trust_line,
            "\n\n",
            Text("Created by Sultan Alfaifi", style="dim"),
        )
        self.console.print(
            Panel(body, border_style="#38bdf8", box=box.DOUBLE, padding=(1, 3))
        )

    def section(self, number: int, title: str, subtitle: str) -> None:
        heading = Text()
        heading.append(f" {number:02d} ", style="bold white on #2563eb")
        heading.append(f"  {title}", style="bold bright_cyan")
        self.console.print()
        self.console.print(heading)
        self.console.print(f"[dim]{subtitle}[/dim]")

    @contextmanager
    def discovery_wait(self, *, personalized: bool = True) -> Iterator[Callable[[str], None]]:
        self.section(
            3,
            "LIVE MODEL DISCOVERY",
            (
                "Searching the official catalog only after your answers are known."
                if personalized
                else "Refreshing model details from the official Ollama library."
            ),
        )
        self.console.print(
            Panel(
                "[bold]Mustakshif is exploring Ollama...[/bold]\n"
                "Every official family is scanned, relevant variants are verified, and nothing is downloaded.",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        with self.console.status(
            "[bold cyan]Preparing the model explorer...[/bold cyan]",
            spinner="dots12",
            spinner_style="bright_cyan",
        ) as status:
            yield lambda message: status.update(f"[bold cyan]{message}[/bold cyan]")

    def footer(self) -> None:
        links = Text()
        links.append("Sultan Alfaifi\n", style="bold white")
        links.append("X:        ", style="dim")
        links.append(X_URL, style=f"link {X_URL} cyan underline")
        links.append("\nLinkedIn: ", style="dim")
        links.append(LINKEDIN_URL, style=f"link {LINKEDIN_URL} blue underline")
        links.append("\nGitHub:   ", style="dim")
        links.append(GITHUB_URL, style=f"link {GITHUB_URL} bright_blue underline")
        links.append("\n\nTip: use Ctrl+Click in Windows Terminal. The full URLs remain copyable everywhere.", style="dim")
        links.append("\nCopyright © 2026 Sultan Alfaifi · Apache-2.0", style="dim")
        self.console.print(
            Panel(links, title="PROJECT LINKS", border_style="dim blue", box=box.ROUNDED, padding=(1, 2))
        )

    def show_hardware(self, hardware: HardwareProfile) -> None:
        self.section(1, "DEVICE PROFILE", "A private hardware snapshot used only on this computer.")
        table = Table(box=box.ROUNDED, border_style="blue", show_header=False, padding=(0, 1))
        table.add_column("Item", style="bold cyan")
        table.add_column("Value")
        table.add_row("Operating system", hardware.os_name)
        table.add_row("Processor", hardware.cpu)
        table.add_row("CPU cores", f"{hardware.physical_cores} physical / {hardware.logical_cores} logical")
        table.add_row("System memory", f"{hardware.ram_gb} GB — {hardware.free_ram_gb} GB currently available")
        if hardware.best_gpu:
            free = f" — {hardware.best_gpu.free_vram_gb} GB currently free" if hardware.best_gpu.free_vram_gb is not None else ""
            table.add_row("GPU", f"{hardware.best_gpu.name} — {hardware.best_gpu.vram_gb} GB VRAM{free}")
        else:
            table.add_row("GPU", "No discrete GPU with reliable dedicated-memory data was detected")
        table.add_row("Model storage", f"{hardware.free_disk_gb} GB free at {hardware.model_path}")
        ollama = (hardware.ollama.version or "Installed") if hardware.ollama.installed else "Not installed"
        ollama_style = "[green]READY[/green]" if hardware.ollama.installed else "[yellow]NOT INSTALLED[/yellow]"
        table.add_row("Ollama", f"{ollama_style}  {ollama}")
        self.console.print(table)

    def _choice(self, title: str, choices: dict[int, str], default: int = 1) -> int:
        self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        for number, label in choices.items():
            self.console.print(f"  [bold blue]{number}[/bold blue]. {label}")
        while True:
            value = IntPrompt.ask("Selection", default=default)
            if value in choices:
                return value
            self.console.print("[red]Choose a number shown in the list.[/red]")

    def ask_needs(self) -> UserNeeds:
        self.section(2, "YOUR IDEAL MODEL", "A short interview turns preferences into measurable filters.")
        experience_choice = self._choice(
            "What is your experience level?",
            {1: "Beginner", 2: "Intermediate", 3: "Advanced"},
        )

        self.console.print("\n[bold cyan]What will you use the model for? Enter one or more numbers separated by commas.[/bold cyan]")
        for number, (_, label) in GOALS.items():
            self.console.print(f"  [bold blue]{number}[/bold blue]. {label}")
        while True:
            raw = Prompt.ask("Goals", default="1")
            try:
                values = sorted({int(item.strip()) for item in raw.split(",") if item.strip()})
            except ValueError:
                values = []
            if values and all(value in GOALS for value in values):
                goals = [GOALS[value][0] for value in values]
                break
            self.console.print("[red]Example: enter 3,4 for programming and agents.[/red]")

        language_choice = self._choice(
            "Which language will you use most?",
            {1: "Arabic", 2: "English", 3: "Arabic and English"},
            default=3,
        )
        priority_choice = self._choice(
            "What matters most?",
            {1: "Balanced quality and speed", 2: "Maximum speed", 3: "Maximum quality", 4: "Lowest memory use"},
        )
        locality_choice = self._choice(
            "Where should the model run?",
            {1: "Local only", 2: "Show both local and cloud options", 3: "Cloud is acceptable"},
        )
        context_choice = self._choice(
            "How large are your conversations and files?",
            {1: "Short — regular chat", 2: "Medium — files and projects", 3: "Long — repositories and large document sets"},
            default=2,
        )

        vision_by_goal = any(goal in goals for goal in ("vision", "ui_design"))
        tools_by_goal = "agents" in goals
        needs_vision = vision_by_goal or Confirm.ask("Do you need the model to understand images?", default=False)
        needs_tools = tools_by_goal or Confirm.ask("Do you need tool calling?", default=False)
        permissive = Confirm.ask("Restrict results to Apache, MIT, or BSD-style licenses?", default=False)

        return UserNeeds(
            experience=EXPERIENCE[experience_choice],
            goals=goals,
            language=LANGUAGE[language_choice],
            priority=PRIORITY[priority_choice],
            locality=LOCALITY[locality_choice],
            needs_vision=needs_vision,
            needs_tools=needs_tools,
            context_size=CONTEXT[context_choice],
            permissive_license_only=permissive,
        )

    def show_catalog_status(
        self,
        state: str,
        checked_at: str | None,
        errors: list[str],
        discovered_families: int = 0,
        verified_families: int = 0,
        candidate_count: int = 0,
    ) -> None:
        label = {
            "live": "live official sources",
            "index": "automatic daily catalog index",
            "cache": "local cache",
            "bundled": "trusted catalog bundled with the app",
            "seed": "trusted fallback catalog",
        }.get(state, state)
        checked_label = checked_at
        if checked_at:
            try:
                checked_label = datetime.fromisoformat(checked_at).astimezone().strftime("%Y-%m-%d %H:%M %Z")
            except ValueError:
                pass
        message = f"Model data: {label}" + (f" — checked {checked_label}" if checked_label else "")
        self.console.print(f"[dim]{message}[/dim]")
        if discovered_families:
            self.console.print(
                f"[dim]Scanned {discovered_families} official families; "
                f"verified {verified_families} runnable families; "
                f"compared {candidate_count} runnable variants.[/dim]"
            )
        if errors:
            self.console.print(f"[yellow]{len(errors)} source(s) could not be refreshed; trusted cached data was used instead.[/yellow]")

    def show_recommendations(self, recommendations: list[Recommendation]) -> None:
        self.section(4, "YOUR SHORTLIST", "Ranked for fit, usefulness, trust, and practical runtime behavior.")
        if not recommendations:
            self.console.print(Panel("No model satisfies every selected requirement. Try allowing cloud models or relaxing image and tool requirements.", border_style="red"))
            return

        category_labels = {
            "best_overall": "BEST OVERALL",
            "best_quality": "HIGHEST QUALITY",
            "fastest": "FASTEST",
            "lightest": "LIGHTEST",
            "most_popular": "MOST POPULAR",
        }
        for index, item in enumerate(recommendations):
            model = item.model
            lines = Text()
            lines.append(f"{model.display_name}\n", style="bold bright_cyan")
            lines.append(f"Score: {item.score}/100   Confidence: {item.confidence}\n")
            if item.score_breakdown:
                parts = " · ".join(
                    f"{name.title()} {value:.1f}"
                    for name, value in item.score_breakdown.items()
                )
                lines.append(f"{parts}\n", style="dim")
            lines.append(f"Execution: {MODE_LABELS[item.hardware_mode]}   Starting context: {item.recommended_context_k}K\n")
            if model.size_gb is not None:
                lines.append(f"Download: {model.size_gb} GB")
                if item.estimated_memory_gb is not None:
                    lines.append(f"   Estimated runtime memory: {item.estimated_memory_gb} GB")
                lines.append("\n")
            lines.append(f"License: {model.license_name}\n")
            for reason in item.reasons:
                lines.append(f"• {reason}\n", style="green")
            for warning in item.warnings:
                lines.append(f"Warning: {warning}\n", style="yellow")
            lines.append("Official page: ")
            lines.append(model.official_url, style=f"link {model.official_url} blue underline")
            if model.install_command:
                lines.append(f"\nCopy to install: {model.install_command}", style="bold")
            title = category_labels.get(item.category, f"CHOICE {index + 1}")
            self.console.print(Panel(lines, title=title, border_style="bright_blue" if index == 0 else "blue"))

    def show_model_list(self, models: list[ModelCandidate]) -> None:
        table = Table(title=f"Trusted models ({len(models)})", box=box.SIMPLE_HEAVY, border_style="blue")
        table.add_column("Model", style="cyan")
        table.add_column("Publisher")
        table.add_column("Runtime")
        table.add_column("Size", justify="right")
        table.add_column("Context", justify="right")
        table.add_column("Source")
        for model in models:
            table.add_row(
                model.id,
                model.publisher,
                "Local" if model.runtime == "local" else "Cloud",
                f"{model.size_gb} GB" if model.size_gb is not None else "—",
                f"{model.context_k}K",
                model.source_state,
            )
        self.console.print(table)

    def about(self) -> None:
        body = Text()
        body.append("Mustakshif\n", style="bold bright_cyan")
        body.append("A local-first tool for matching trusted open AI models to hardware and user goals.\n\n")
        body.append("Created by Sultan Alfaifi\n", style="bold")
        body.append(X_URL + "\n", style=f"link {X_URL} cyan underline")
        body.append(LINKEDIN_URL, style=f"link {LINKEDIN_URL} blue underline")
        self.console.print(Panel(body, border_style="bright_blue", padding=(1, 3)))
