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
        # TODO If core-metadata is a dict, verify the hash of the data
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


def system_details():
    """Get the details of the current environment."""
    return packaging.markers.default_environment(), packaging.tags.sys_tags()


def pure_python_details(version):
    """Calculate the details for a specific Python version."""
    version_str = f"{version[0]}.{version[1]}"
    markers = {
        "python_version": version_str,
        "python_full_version": f"{version_str}.0",
    }
    # https://github.com/pypa/packaging/issues/781 to get rid of the `filter()`
    # call.
    tags = filter(
        lambda tag: tag.platform != "_",
        packaging.tags.compatible_tags(version, platforms=["_"]),
    )

    return markers, tags


def cpython_windows_details(version):
    version_str = f"{version[0]}.{version[1]}"
    markers = {
        "implementation_name": "cpython",
        "implementation_version": f"{version_str}.0",
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_release": "10",
        "platform_system": "Windows",
        "python_full_version": f"{version_str}.0",
        "platform_python_implementation": "CPython",
        "python_version": version_str,
        "sys_platform": "win32",
    }

    tags = [
        *packaging.tags.cpython_tags(
            version, [f"cp{version[0]}{version[1]}", "abi3"], ["win_amd64"]
        ),
        *packaging.tags.compatible_tags(
            version, f"cp{version[0]}{version[1]}", platforms=["win_amd64"]
        ),
    ]

    return markers, tags


def generate_lock_entry(dependencies, markers, tags):
    requirements = map(
        mousebender.resolve.Requirement,
        map(packaging.requirements.Requirement, dependencies),
    )
    provider = PyPIProvider(markers=markers, tags=tags)
    reporter = resolvelib.BaseReporter()
    resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
    try:
        resolution = resolver.resolve(requirements)
    except resolvelib.ResolutionImpossible:
        print("Resolution (currently) impossible 😢")
        sys.exit(1)

    return mousebender.lock.generate_lock(provider, resolution)


def update_lock(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())

    lock_entries = []
    for entry in lock_file_contents["lock"]:
        print("Updating", entry["tags"][0], "...")
        tags = map(lambda t: packaging.tags.Tag(*t.split("-")), entry["tags"])
        lock_entries.append(
            generate_lock_entry(
                lock_file_contents["dependencies"], entry["markers"], tags
            )
        )

    new_lock_file = mousebender.lock.generate_file_contents(
        lock_file_contents["dependencies"], lock_entries
    )
    with context.lock_file.open("wb") as file:
        file.write(new_lock_file.encode("utf-8"))


def lock_entry(context, dependencies):
    tags = list(packaging.tags.sys_tags())
    if context.maximize == "compatibility":
        tags = list(reversed(tags))

    if context.platform == "system":
        markers, tags = system_details()
    elif context.platform.startswith("python"):
        markers, tags = pure_python_details(
            tuple(map(int, context.platform.removeprefix("python").split(".", 1)))
        )
    elif context.platform.startswith("cpython") and context.platform.endswith(
        "windows-x64"
    ):
        version = context.platform.removeprefix("cpython").removesuffix("-windows-x64")
        markers, tags = cpython_windows_details(tuple(map(int, version.split(".", 1))))
    else:
        raise ValueError(f"Unknown platform: {context.platform}")

    return generate_lock_entry(dependencies, markers, tags)


def add_lock_entry(context):
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
        print(wheel["name"], "@", wheel.get("filename") or wheel["origin"])


def graph(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())

    mermaid_lines = []
    if context.self_contained:
        mermaid_lines.append("```mermaid")
    mermaid_lines.extend(["graph LR", "  subgraph top [Top-level dependencies]"])

    for top_dep in lock_file_contents["dependencies"]:
        requirement = packaging.requirements.Requirement(top_dep)
        line = f"    {requirement.name}"
        if requirement.name != top_dep:
            line += f"[{top_dep}]"
        mermaid_lines.append(line)
    mermaid_lines.append("  end")

    for entry in lock_file_contents["lock"]:
        nodes = set()
        edges = {}  # type: ignore
        mermaid_lines.append(f"  subgraph {entry['tags'][0]}")
        for wheel in entry["wheel"]:
            name = wheel["name"]
            if name not in nodes:
                mermaid_lines.append(f"    {name}")
                nodes.add(name)
            for dep in wheel["dependencies"]:
                if dep not in nodes:
                    mermaid_lines.append(f"    {dep}")
                    nodes.add(dep)
                edges.setdefault(name, set()).add(dep)

        for parent, children in edges.items():
            for child in sorted(children):
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
        "add-lock-entry", help="Add a lock entry to a lock file"
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
        subparser.add_argument(
            "--platform",
            choices=[
                "system",
                "cpython3.8-windows-x64",
                "cpython3.9-windows-x64",
                "cpython3.10-windows-x64",
                "cpython3.11-windows-x64",
                "cpython3.12-windows-x64",
                "python3.8",
                "python3.9",
                "python3.10",
                "python3.11",
                "python3.12",
            ],
            default="system",
            help="The platform to lock for",
        )
        # XXX x64 manylinux 2_17 (aka 2014)
        # {
        #     "implementation_name": "cpython",
        #     "implementation_version": "3.12.2",
        #     "os_name": "posix",
        #     "platform_machine": "x86_64",
        #     "platform_release": "6.7.4-200.fc39.x86_64",
        #     "platform_system": "Linux",
        #     "platform_version": "#1 SMP PREEMPT_DYNAMIC Mon Feb  5 22:21:14 UTC 2024",
        #     "python_full_version": "3.12.2",
        #     "platform_python_implementation": "CPython",
        #     "python_version": "3.12",
        #     "sys_platform": "linux",
        # }

    update_lock_args = subcommands.add_parser(
        "update-lock", help="Update the a lock file"
    )
    update_lock_args.add_argument(
        "lock_file", type=pathlib.Path, help="The lock file to update"
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
    dispatch = {
        "lock": lock,
        "add-lock-entry": add_lock_entry,
        "update-lock": update_lock,
        "install": install,
        "graph": graph,
    }
    dispatch[context.subcommand](context)


if __name__ == "__main__":
    main()
    # py . lock numpy mousebender hatchling requests pydantic
    # trio
