#
# Copyright 2017-2023 - Swiss Data Science Center (SDSC)
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Test ``rerun`` command."""

import os
import subprocess
import time
from pathlib import Path

import pytest

from renku.core.plugin.provider import available_workflow_providers
from renku.infrastructure.gateway.activity_gateway import ActivityGateway
from renku.infrastructure.gateway.plan_gateway import PlanGateway
from renku.ui.cli import cli
from tests.utils import format_result_exception, write_and_commit_file


@pytest.mark.parametrize("provider", available_workflow_providers())
@pytest.mark.parametrize("skip_metadata_update", [True, False])
def test_rerun(project, with_injection, renku_cli, provider, skip_metadata_update):
    """Test rerun."""
    output = project.path / "output.txt"

    assert 0 == renku_cli("run", "python", "-S", "-c", "import random; print(random.random())", stdout=output).exit_code

    content = output.read_text().strip()

    def rerun():
        cmd = ["rerun", "-p", provider]
        if skip_metadata_update:
            cmd.append("--skip-metadata-update")
        cmd.append(output)
        assert 0 == renku_cli(*cmd).exit_code
        with with_injection():
            plans = PlanGateway().get_all_plans()
            activities = ActivityGateway().get_all_activities()
            assert len(plans) == 1
            if skip_metadata_update:
                assert len(activities) == 1
            else:
                assert len(activities) > 1
        return output.read_text().strip()

    new_content = None

    for _ in range(5):
        time.sleep(1)
        new_content = rerun()
        if content != new_content:
            break

    assert content != new_content, "Something is not random"


@pytest.mark.parametrize("provider", available_workflow_providers())
@pytest.mark.parametrize(
    "source, output",
    [
        ("input with space.txt", "output .txt"),
        ("coffee-orders-☕-by-location.csv", "😍works.txt"),
        ("test-愛", "成功"),
        ("그래프", "성공"),
        ("يحاول", "نجاح.txt"),
        ("график.txt", "успех.txt"),
        ("𒁃.c", "𒁏.txt"),
    ],
)
def test_rerun_with_special_paths(project, renku_cli, runner, provider, source, output):
    """Test rerun with unicode/whitespace filenames."""
    cwd = project.path
    source = cwd / source
    output = cwd / output

    assert 0 == renku_cli("run", "python", "-S", "-c", "import random; print(random.random())", stdout=source).exit_code
    time.sleep(1)
    assert 0 == renku_cli("run", "cat", source, stdout=output).exit_code

    content = output.read_text().strip()

    def rerun():
        assert 0 == renku_cli("rerun", "-p", provider, output).exit_code
        return output.read_text().strip()

    for _ in range(5):
        time.sleep(1)
        new_content = rerun()
        if content != new_content:
            break

    assert content != output.read_text().strip(), "The output should have changed."

    result = runner.invoke(cli, ["graph", "export", "--format", "json-ld", "--strict"])
    assert 0 == result.exit_code, format_result_exception(result)


@pytest.mark.parametrize("provider", available_workflow_providers())
@pytest.mark.parametrize("source, content", [("input1", "input1 new-input2 old"), ("input2", "input1 old-input2 new")])
def test_rerun_with_from(project, renku_cli, provider, source, content):
    """Test file recreation with specified inputs."""
    cwd = project.path
    input1 = cwd / "input1"
    input2 = cwd / "input2"
    intermediate1 = cwd / "intermediate1"
    intermediate2 = cwd / "intermediate2"
    final1 = cwd / "final1"
    final2 = cwd / "final2"
    output = cwd / "output"

    write_and_commit_file(project.repository, input1, "input1 old-")
    write_and_commit_file(project.repository, input2, "input2 old")

    assert 0 == renku_cli("run", "cp", input1, intermediate1).exit_code
    assert 0 == renku_cli("run", "cp", intermediate1, final1).exit_code
    time.sleep(1)
    assert 0 == renku_cli("run", "cp", input2, intermediate2).exit_code
    assert 0 == renku_cli("run", "cp", intermediate2, final2).exit_code
    time.sleep(1)

    assert 0 == renku_cli("run", "cat", final1, final2, stdout=output).exit_code
    time.sleep(1)

    # Update both inputs
    write_and_commit_file(project.repository, input1, "input1 new-")
    write_and_commit_file(project.repository, input2, "input2 new")

    commit_sha_before = project.repository.head.commit.hexsha

    assert 0 == renku_cli("rerun", "-p", provider, "--from", source, output).exit_code

    assert content == output.read_text()

    commit_sha_after = project.repository.head.commit.hexsha
    assert commit_sha_before != commit_sha_after


@pytest.mark.skip(reason="renku rerun not implemented with --edit-inputs yet, re-enable later")
def test_rerun_with_edited_inputs(project, run, no_lfs_warning, runner):
    """Test input modification."""
    cwd = project.path
    data = cwd / "examples"
    data.mkdir()
    first = data / "first.txt"
    second = data / "second.txt"
    third = data / "third.txt"

    run(args=["run", "echo", "hello"], stdout=first)
    run(args=["run", "cat", str(first)], stdout=second)
    run(args=["run", "echo", "1"], stdout=third)

    with first.open("r") as first_fp:
        with second.open("r") as second_fp:
            assert first_fp.read() == second_fp.read()

    # Change the initial input from "hello" to "hola".
    from click.testing import make_input_stream

    stdin = make_input_stream("hola\n", "utf-8")
    assert 0 == run(args=("rerun", "--edit-inputs", str(second)), stdin=stdin)

    with second.open("r") as second_fp:
        assert "hola\n" == second_fp.read()

    # Change the input from examples/first.txt to examples/third.txt.
    stdin = make_input_stream(str(third.name), "utf-8")
    old_dir = os.getcwd()
    try:
        # Make sure the input path is relative to the current directory.
        os.chdir(str(data))

        result = runner.invoke(
            cli, ["rerun", "--show-inputs", "--from", str(first), str(second)], catch_exceptions=False
        )
        assert 0 == result.exit_code, format_result_exception(result)
        assert result.output.startswith("https://")
        assert result.output[:-1].endswith(first.name)
        assert 0 == run(args=("rerun", "--edit-inputs", "--from", str(first), str(second)), stdin=stdin)
    finally:
        os.chdir(old_dir)

    with third.open("r") as third_fp:
        with second.open("r") as second_fp:
            assert third_fp.read() == second_fp.read()


@pytest.mark.parametrize("provider", available_workflow_providers())
def test_rerun_with_no_execution(project, runner, provider):
    """Test rerun when no workflow is executed."""
    input = os.path.join(project.path, "data", "input.txt")
    write_and_commit_file(project.repository, input, "content")

    result = runner.invoke(cli, ["rerun", "-p", provider, input], catch_exceptions=False)

    assert 1 == result.exit_code
    assert "Path 'data/input.txt' is not generated by any workflows." in result.output


@pytest.mark.parametrize("provider", available_workflow_providers())
def test_output_directory(runner, project, run, no_lfs_size_limit, provider):
    """Test detection of output directory."""
    cwd = project.path
    data = cwd / "source" / "data.txt"
    source = data.parent
    source.mkdir(parents=True)
    data.write_text("data")

    # Empty destination
    destination = cwd / "destination"
    source_wc = cwd / "destination_source.wc"
    # Non empty destination
    invalid_destination = cwd / "invalid_destination"
    invalid_destination.mkdir(parents=True)
    (invalid_destination / "non_empty").touch()

    project.repository.add(all=True)
    project.repository.commit("Created source directory", no_verify=True)

    result = runner.invoke(cli, ["run", "cp", "-LRf", source, destination], catch_exceptions=False)
    assert 0 == result.exit_code, format_result_exception(result)

    destination_source = destination / data.name
    assert destination_source.exists()

    # check that the output in subdir is added to LFS
    with (cwd / ".gitattributes").open() as f:
        git_attr = f.read()
    assert str(destination.relative_to(cwd)) + "/**" in git_attr
    assert destination_source.name in subprocess.check_output(["git", "lfs", "ls-files"]).decode()

    assert 0 == run(args=["run", "wc"], stdin=destination_source, stdout=source_wc)

    # Make sure the output directory can be recreated
    assert 0 == run(args=("rerun", "-p", provider, str(source_wc)))
    if provider != "local":
        # NOTE: For ``local`` provider, since the execution is in the current directory and the destination directory
        # exists, a copy is made instead of a rename which makes this condition to fail
        assert {data.name} == {path.name for path in destination.iterdir()}

    result = runner.invoke(cli, ["graph", "export"], catch_exceptions=False)
    destination_data = str(Path("destination") / "data.txt")
    assert destination_data in result.output

    result = runner.invoke(cli, ["run", "cp", "-r", source, invalid_destination], catch_exceptions=False)
    assert 1 == result.exit_code
    assert not (invalid_destination / data.name).exists()


def test_rerun_overridden_output(project, renku_cli, runner):
    """Test a path where final output is overridden won't be rerun."""
    a = os.path.join(project.path, "a")
    b = os.path.join(project.path, "b")
    c = os.path.join(project.path, "c")

    write_and_commit_file(project.repository, a, "content")

    assert 0 == runner.invoke(cli, ["run", "--name", "r1", "cp", a, b]).exit_code
    time.sleep(1)
    assert 0 == runner.invoke(cli, ["run", "--name", "r2", "cp", b, c]).exit_code
    time.sleep(1)
    assert 0 == renku_cli("run", "--name", "r3", "wc", a, stdout=c).exit_code

    result = runner.invoke(cli, ["rerun", "--dry-run", c])

    assert 0 == result.exit_code
    assert "r1" not in result.output
    assert "r2" not in result.output
    assert "r3" in result.output


def test_rerun_overridden_outputs_partially(project, renku_cli, runner):
    """Test a path where one of the final output is overridden won't be rerun."""
    a = os.path.join(project.path, "a")
    b = os.path.join(project.path, "b")
    c = os.path.join(project.path, "c")
    d = os.path.join(project.path, "d")

    write_and_commit_file(project.repository, a, "content")

    assert 0 == runner.invoke(cli, ["run", "--name", "r1", "cp", a, b]).exit_code
    time.sleep(1)
    assert 0 == renku_cli("run", "--name", "r2", "tee", c, d, stdin=b).exit_code
    time.sleep(1)
    assert 0 == renku_cli("run", "--name", "r3", "wc", a, stdout=c).exit_code

    result = runner.invoke(cli, ["rerun", "--dry-run", c])

    assert 0 == result.exit_code
    assert "r1" not in result.output
    assert "r2" not in result.output
    assert "r3" in result.output

    # Rerunning d will rerun r1 and r2
    result = runner.invoke(cli, ["rerun", "--dry-run", d])

    assert 0 == result.exit_code
    assert "r1" in result.output
    assert "r2" in result.output
    assert "r3" not in result.output

    result = runner.invoke(cli, ["graph", "export", "--format", "json-ld", "--strict"])
    assert 0 == result.exit_code, format_result_exception(result)


def test_rerun_multiple_paths_common_output(project, renku_cli, runner):
    """Test when multiple paths generate the same output only the most recent path will be rerun."""
    a = os.path.join(project.path, "a")
    b = os.path.join(project.path, "b")
    c = os.path.join(project.path, "c")
    d = os.path.join(project.path, "d")

    write_and_commit_file(project.repository, a, "content")

    assert 0 == runner.invoke(cli, ["run", "--name", "r1", "cp", a, b]).exit_code
    time.sleep(1)
    assert 0 == runner.invoke(cli, ["run", "--name", "r2", "cp", b, d]).exit_code
    time.sleep(1)
    assert 0 == runner.invoke(cli, ["run", "--name", "r3", "cp", a, c]).exit_code
    time.sleep(1)
    assert 0 == renku_cli("run", "--name", "r4", "wc", c, stdout=d).exit_code

    result = runner.invoke(cli, ["rerun", "--dry-run", d])

    assert 0 == result.exit_code
    assert "r1" not in result.output
    assert "r2" not in result.output
    assert "r3" in result.output
    assert "r4" in result.output


def test_rerun_output_in_subdirectory(runner, project):
    """Test re-run when an output is in a sub-directory."""
    output = project.path / "sub-dir" / "output"
    write_and_commit_file(project.repository, output, "")

    result = runner.invoke(cli, ["run", "bash", "-c", 'touch "$0" ; echo data > "$0"', output])

    assert 0 == result.exit_code, format_result_exception(result)

    write_and_commit_file(project.repository, output, "")

    result = runner.invoke(cli, ["rerun", output])

    assert 0 == result.exit_code, format_result_exception(result)
    assert "data" in output.read_text()
