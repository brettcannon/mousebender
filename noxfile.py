import nox

python_versions = ["3.7", "3.8", "3.9", "3.10", "3.11"]


def run_tests(session, extras=[]):
    session.install("-e", ".[test]")
    session.run("pytest", *extras)


@nox.session(python=python_versions)
def test(session):
    run_tests(session)


@nox.session(python=python_versions)
def coverage(session):
    run_tests(session, ["--cov"])


@nox.session
def type_check(session):
    session.install("-e", ".")
    session.install("mypy")
    session.run("mypy", "mousebender")
