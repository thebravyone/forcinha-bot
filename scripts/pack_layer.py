import os
import shutil

from rich import print
from rich.console import Console


def main():
    console = Console()
    print("\n")
    console.rule("[bold]AWS Lambda Layer Packager[/]")

    print(
        "\n:light_bulb: Before attempting to zip a layer, make sure you have run `sam build`.\n"
    )
    layer_name = console.input(
        "[bold cyan]>[/] Enter the name of the [bold red]layer[/] to zip: "
    )
    if layer_name == "":
        console.print("[bold red]\u2717[/] Aborted.")
        return

    with console.status(f"Zipping [bold red]{layer_name}[/]..."):
        try:
            aws_sam_build_subfolders = os.listdir(".aws-sam/build/")
        except FileNotFoundError:
            print(
                "[bold red]\u2717[/] [bold].aws-sam/build/[/] folder not found. Run `sam build` first."
            )
            return

        for sub_folder in aws_sam_build_subfolders:
            if layer_name == sub_folder:
                output_path = f".zip/{layer_name}"
                layer_path = f".aws-sam/build/{layer_name}"

                shutil.make_archive(output_path, format="zip", root_dir=layer_path)
                console.print(
                    f"[bold green]\u2713[/] Zipped [bold red]{layer_name}[/] layer at [bold]{output_path}.zip[/]"
                )
                return

    console.print(
        f"[bold red]\u2717[/] Layer [bold red]{layer_name}[/] not found in .aws-sam/build/ folder."
    )


if __name__ == "__main__":
    main()
    pass
