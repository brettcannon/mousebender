# ruff: noqa: ANN001, ANN201, ANN202, D100, D103
import argparse
import pathlib
import sys

import httpx
import packaging.metadata
import packaging.requirements
import packaging.utils
import resolvelib.resolvers
import tomllib
import trio

import mousebender.install
import mousebender.lock
import mousebender.resolve
import mousebender.simple


async def get_metadata_for_file(client, file):
    """Get the METADATA file for a wheel."""
    url = file.details["url"] + ".metadata"
    response = await client.get(url)
    raw_data = response.content
    if isinstance(file.details.get("core-metadata", True), dict):
        # XXX If core-metadata is a dict, verify the hash of the data
        pass
    metadata = packaging.metadata.Metadata.from_email(raw_data, validate=False)
    file.metadata = metadata


async def get_metadata(files):
    """Get the METADATA file for a wheel."""
    async with httpx.AsyncClient() as client:
        async with trio.open_nursery() as nursery:
            for file in files:
                nursery.start_soon(get_metadata_for_file, client, file)  # type: ignore[arg-type]


class PyPIProvider(mousebender.resolve.WheelProvider):
    """A provider for wheels from PyPI."""

    def available_files(self, name):
        """Get the available wheels for a distribution."""
        project_url = mousebender.simple.create_project_url(
            "https://pypi.org/simple", name
        )
        response = httpx.get(
            project_url,
            follow_redirects=True,
            headers={"Accept": mousebender.simple.ACCEPT_SUPPORTED},
        )

        project_details = mousebender.simple.parse_project_details(
            response.text, response.headers["Content-Type"], name
        )

        nothing_yanked = list(
            filter(lambda f: not f.get("yanked", False), project_details["files"])
        )

        wheels = list(filter(lambda f: f["filename"].endswith(".whl"), nothing_yanked))
        has_metadata = list(filter(lambda f: f.get("core-metadata", False), wheels))

        if not nothing_yanked:
            print(f"😱 {name} has **no** files available", file=sys.stderr)
        elif not wheels:
            print(f"🤬 {name} has **no** wheels", file=sys.stderr)
        elif not has_metadata:
            print(f"😨 {name} has **no** wheels w/ metadata", file=sys.stderr)
        elif len(has_metadata) < len(wheels):
            print(f"😬 {name} has *some* wheels w/o metadata", file=sys.stderr)

        return map(mousebender.resolve.WheelFile, has_metadata)

    def fetch_metadata(self, file_details):
        """Fetch the METADATA file for a wheel."""
        trio.run(get_metadata, file_details)


def lock_entry(context, dependencies):
    requirements = map(
        mousebender.resolve.Requirement,
        map(packaging.requirements.Requirement, dependencies),
    )

    tags = list(packaging.tags.sys_tags())
    if context.maximize == "compatibility":
        tags = list(reversed(tags))

    provider = PyPIProvider(tags=tags)
    reporter = resolvelib.BaseReporter()
    resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
    try:
        resolution = resolver.resolve(requirements)
    except resolvelib.ResolutionImpossible:
        print("Resolution (currently) impossible 😢")
        sys.exit(1)

    # XXX also resolve for Windows

    return mousebender.lock.generate_lock(provider, resolution)


def add_lock(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())

    dependencies = lock_file_contents["dependencies"]

    contents = list(
        map(mousebender.lock.lock_entry_dict_to_toml, lock_file_contents["lock"])
    )
    contents.append(lock_entry(context, dependencies))

    lock_file = mousebender.lock.generate_file_contents(dependencies, contents)

    with context.lock_file.open("wb") as file:
        file.write(lock_file.encode("utf-8"))

    print(lock_file)


def lock(context):
    if not (dependencies := context.requirements):
        with open("pyproject.toml", "rb") as file:
            pyproject = tomllib.load(file)
        dependencies = pyproject["project"]["dependencies"]

    lock_contents = lock_entry(context, dependencies)
    lock_file = mousebender.lock.generate_file_contents(
        context.requirements, [lock_contents]
    )

    if context.lock_file:
        with context.lock_file.open("wb") as file:
            file.write(lock_file.encode("utf-8"))

    print(lock_file)


def install(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())
    if (lock_entry := mousebender.install.strict_match(lock_file_contents)) is None:
        lock_entry = mousebender.install.compatible_match(lock_file_contents)
        if lock_entry is None:
            print("No compatible lock entry found 😢")
            sys.exit(1)

    for wheel in lock_entry["wheel"]:
        print(wheel["filename"])


def _name_from_filename(filename):
    return packaging.utils.parse_wheel_filename(filename)[0]


def graph(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())

    mermaid_lines = []
    if context.self_contained:
        mermaid_lines.append("```mermaid")
    mermaid_lines.extend(["graph LR", "  subgraph top [Top-level dependencies]"])

    for top_dep in lock_file_contents["dependencies"]:
        mermaid_lines.append(f"    {top_dep}")
    mermaid_lines.append("  end")

    for entry in lock_file_contents["lock"]:
        nodes = set()
        edges = {}  # type: ignore
        mermaid_lines.append(f"  subgraph {entry['tags'][0]}")
        for wheel in entry["wheel"]:
            name = _name_from_filename(wheel["filename"])
            if name not in nodes:
                mermaid_lines.append(f"    {name}")
                nodes.add(name)
            for dep in wheel["dependencies"]:
                if dep not in nodes:
                    mermaid_lines.append(f"    {dep}")
                    nodes.add(dep)
                edges.setdefault(name, set()).add(dep)

        for parent, children in edges.items():
            for child in children:
                mermaid_lines.append(f"    {parent} --> {child}")
        mermaid_lines.append("  end")

    if context.self_contained:
        mermaid_lines.append("```")

    print("\n".join(mermaid_lines))


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="subcommand")

    lock_args = subcommands.add_parser("lock", help="Generate a lock file")
    lock_args.add_argument("requirements", nargs="*")
    lock_args.add_argument(
        "--lock-file", type=pathlib.Path, help="Where to save the lock file"
    )

    add_lock_args = subcommands.add_parser(
        "add-lock", help="Add a lock entry to a lock file"
    )
    add_lock_args.add_argument(
        "lock_file", default=None, type=pathlib.Path, help="The lock file to add to"
    )

    for subparser in (lock_args, add_lock_args):
        subparser.add_argument(
            "--maximize",
            choices=["speed", "compatibility"],
            help="What to maximize wheel selection for (speed or compatibility)",
        )

    install_args = subcommands.add_parser(
        "install", help="Install packages from a lock file"
    )
    install_args.add_argument(
        "lock_file", type=pathlib.Path, help="The lock file to install from"
    )

    graph_args = subcommands.add_parser(
        "graph",
        help="Generate a visualization of the dependency graph in Mermaid format",
    )
    graph_args.add_argument(
        "--self-contained",
        action="store_true",
        default=False,
        help="Include the surrounding Markdown to make the graph self-contained",
    )
    graph_args.add_argument(
        "lock_file", type=pathlib.Path, help="The lock file to visualize"
    )

    context = parser.parse_args(args)
    dispatch = {"lock": lock, "add-lock": add_lock, "install": install, "graph": graph}
    dispatch[context.subcommand](context)


if __name__ == "__main__":
    main()
    # py . lock numpy mousebender hatchling requests pydantic
    # trio
