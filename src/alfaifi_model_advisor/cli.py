from __future__ import annotations

import argparse
import json
import sys

from rich.console import Console
from rich.prompt import Confirm

from . import __version__
from .catalog import CatalogService
from .hardware import HardwareInspector
from .installer import install_model, open_model_page, validate_installable
from .models import ModelCandidate
from .recommender import RecommendationEngine
from .ui import AppUI


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alfaifi",
        description="Alfaifi Model Advisor — trusted open AI model recommendations",
    )
    parser.add_argument("--offline", action="store_true", help="Use cached model data without network access")
    parser.add_argument("--json", action="store_true", help="Produce JSON when supported by the command")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("scan", help="Inspect this device")
    sub.add_parser("recommend", help="Run the interactive recommendation wizard")
    sub.add_parser("list", help="List trusted models")
    sub.add_parser("update", help="Refresh the official model catalog")
    explain = sub.add_parser("explain", help="Show details for one model")
    explain.add_argument("model")
    install = sub.add_parser("install", help="Install a model through Ollama after confirmation")
    install.add_argument("model")
    install.add_argument("--yes", action="store_true", help="Explicitly approve installation without another prompt")
    open_page = sub.add_parser("open", help="Open a model's official page")
    open_page.add_argument("model")
    sub.add_parser("about", help="Show product and copyright information")
    return parser


def _find(models: list[ModelCandidate], model_id: str) -> ModelCandidate:
    exact = next((model for model in models if model.id.lower() == model_id.lower()), None)
    if exact:
        return exact
    matches = [model for model in models if model_id.lower() in model.id.lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError("The name is ambiguous. Matches: " + ", ".join(model.id for model in matches[:8]))
    raise ValueError(f"No trusted model was found for: {model_id}")


def _scan(inspector: HardwareInspector, ui: AppUI, json_output: bool):
    hardware = inspector.scan()
    if json_output:
        print(json.dumps(hardware.to_dict(), ensure_ascii=False, indent=2))
    else:
        ui.show_hardware(hardware)
    return hardware


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    console = Console(highlight=False)
    ui = AppUI(console)
    inspector = HardwareInspector()
    catalog = CatalogService()

    try:
        if args.command == "about":
            ui.about()
            ui.footer()
            return 0

        if args.command == "scan":
            if not args.json:
                ui.header()
            _scan(inspector, ui, args.json)
            if not args.json:
                ui.footer()
            return 0

        if args.command == "update":
            ui.header()
            with ui.discovery_wait(personalized=False) as progress:
                models = catalog.load(
                    offline=args.offline,
                    force_refresh=True,
                    progress=progress,
                )
            ui.show_catalog_status(
                catalog.source_state,
                catalog.checked_at,
                catalog.last_errors,
                catalog.discovered_family_count,
                catalog.verified_family_count,
                len(models),
            )
            ui.show_model_list(models)
            ui.footer()
            return 0 if catalog.source_state in {"live", "cache"} else 2

        if args.command == "list":
            models = catalog.load(offline=args.offline)
            if args.json:
                print(json.dumps([model.to_dict() for model in models], ensure_ascii=False, indent=2))
            else:
                ui.header()
                ui.show_catalog_status(
                    catalog.source_state,
                    catalog.checked_at,
                    catalog.last_errors,
                    catalog.discovered_family_count,
                    catalog.verified_family_count,
                    len(models),
                )
                ui.show_model_list(models)
                ui.footer()
            return 0

        if args.command in {"explain", "install", "open"}:
            with console.status("[cyan]Loading the trusted model catalog...[/cyan]", spinner="dots12"):
                models = catalog.load(offline=args.offline)
            model = _find(models, args.model)
            if args.command == "explain":
                if args.json:
                    print(json.dumps(model.to_dict(), ensure_ascii=False, indent=2))
                else:
                    ui.header()
                    ui.show_model_list([model])
                    console.print(f"[bold]Official page:[/bold] [link={model.official_url}]{model.official_url}[/link]")
                    console.print(f"[bold]Publisher:[/bold] [link={model.publisher_url}]{model.publisher_url}[/link]")
                    console.print(f"[bold]Install command:[/bold] {model.install_command}")
                    ui.footer()
                return 0
            if args.command == "open":
                open_model_page(model)
                console.print("The official page was opened in your browser.")
                return 0

            validate_installable(model)
            hardware = inspector.scan()
            ui.header()
            ui.show_hardware(hardware)
            console.print(f"\nCommand to execute: [bold]{model.install_command}[/bold]")
            if model.size_gb is not None:
                console.print(f"Approximate download size: {model.size_gb} GB")
            approved = args.yes or Confirm.ask("Do you approve downloading this model?", default=False)
            if not approved:
                console.print("[yellow]Installation cancelled. No model was downloaded.[/yellow]")
                return 0
            code = install_model(model, hardware)
            console.print("[green]Installation completed.[/green]" if code == 0 else f"[red]Ollama failed with exit code {code}.[/red]")
            return code

        ui.header()
        with console.status("[cyan]Inspecting hardware...[/cyan]"):
            hardware = inspector.scan()
        ui.show_hardware(hardware)
        needs = ui.ask_needs()
        if args.offline:
            ui.section(
                3,
                "OFFLINE MODEL CACHE",
                "Using the last trusted cache or the bundled fallback without network access.",
            )
            with console.status("[cyan]Loading the trusted offline catalog...[/cyan]", spinner="dots12"):
                models = catalog.load(offline=True)
        else:
            with ui.discovery_wait() as progress:
                models = catalog.load(
                    force_refresh=True,
                    needs=needs,
                    hardware=hardware,
                    progress=progress,
                )
        ui.show_catalog_status(
            catalog.source_state,
            catalog.checked_at,
            catalog.last_errors,
            catalog.discovered_family_count,
            catalog.verified_family_count,
            len(models),
        )
        recommendations, _ = RecommendationEngine().recommend(models, hardware, needs)
        ui.show_recommendations(recommendations)
        ui.footer()
        return 0 if recommendations else 3
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by the user.[/yellow]")
        return 130
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
