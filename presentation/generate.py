"""CLI script to generate a MoodMeshi presentation slide deck."""

import argparse
import asyncio
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a MoodMeshi presentation using Claude AI"
    )
    parser.add_argument(
        "--with-demo",
        action="store_true",
        help="Run a demo orchestrator call and include results in slides",
    )
    parser.add_argument(
        "--mood",
        type=str,
        default="今日は疲れました",
        help="Mood text to use for the demo (requires --with-demo)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="presentation/output/slides.html",
        help="Output path for the HTML presentation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    demo_result = None
    if args.with_demo:
        print(f"Running demo with mood: '{args.mood}'")
        from app.agents.orchestrator import run_orchestrator
        proposal = asyncio.run(run_orchestrator(args.mood))
        demo_result = proposal.model_dump()
        print(f"Demo completed: {len(proposal.proposals)} proposals generated")

    print("Generating presentation...")
    from presentation.agent import generate_presentation
    result_path = generate_presentation(demo_result, str(output_path))
    print(f"Presentation saved to: {result_path}")


if __name__ == "__main__":
    main()
