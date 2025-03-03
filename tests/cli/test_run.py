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
"""Test ``run`` command."""

import os
from typing import cast

import pytest

from renku.domain_model.workflow.plan import Plan
from renku.infrastructure.gateway.activity_gateway import ActivityGateway
from renku.infrastructure.gateway.plan_gateway import PlanGateway
from renku.ui.cli import cli
from tests.utils import format_result_exception


def test_run_simple(runner, project):
    """Test tracking of run command."""
    cmd = ["echo", "test"]

    result = runner.invoke(cli, ["run", "--no-output"] + cmd)
    assert 0 == result.exit_code, format_result_exception(result)

    # Display tools with no outputs.
    result = runner.invoke(cli, ["graph", "export"])
    assert 0 == result.exit_code, format_result_exception(result)
    assert "test" in result.output


def test_run_many_args(project, run):
    """Test a renku run command which implicitly relies on many inputs."""
    os.mkdir("files")
    output = "output.txt"
    for i in range(103):
        os.system(f"touch files/{i}.txt")
    project.repository.add("files/")
    project.repository.commit("add many files")

    exit_code = run(args=("run", "ls", "files/"), stdout=output)
    assert 0 == exit_code


@pytest.mark.serial
@pytest.mark.shelled
def test_run_clean(runner, project, run_shell):
    """Test tracking of run command in clean repository."""
    # Run a shell command with pipe.
    output = run_shell('renku run echo "a unique string" > my_output_file')

    # Assert expected empty stdout.
    assert b"" == output[0]
    # Assert not allocated stderr.
    assert output[1] is None

    # Assert created output file.
    result = runner.invoke(cli, ["graph", "export"])
    assert "my_output_file" in result.output
    assert "a unique string" in result.output


@pytest.mark.serial
@pytest.mark.shelled
def test_run_external_command_file(runner, project, run_shell, with_injection):
    """Test tracking of run command in clean repo."""
    # Run a shell command with pipe.
    output = run_shell('renku run $(which echo) "a unique string" > my_output_file')

    # Assert expected empty stdout.
    assert b"" == output[0]
    # Assert not allocated stderr.
    assert output[1] is None

    # Assert created output file.
    result = runner.invoke(cli, ["graph", "export"])
    assert "my_output_file" in result.output
    assert "a unique string" in result.output

    with with_injection():
        plan_gateway = PlanGateway()
        plan = plan_gateway.get_all_plans()[0]
        assert plan.command
        assert plan.command.endswith("/echo")


def test_run_metadata(renku_cli, runner, project, with_injection):
    """Test run with workflow metadata."""
    exit_code, activity = renku_cli(
        "run", "--name", "run-1", "--description", "first run", "--keyword", "key1", "--keyword", "key2", "touch", "foo"
    )

    assert 0 == exit_code
    plan = activity.association.plan
    assert "run-1" == plan.name
    assert "first run" == plan.description
    assert {"key1", "key2"} == set(plan.keywords)

    with with_injection():
        plan_gateway = PlanGateway()
        plan = plan_gateway.get_by_id(plan.id)
        assert "run-1" == plan.name
        assert "first run" == plan.description
        assert 1 == len(plan.creators)
        assert "Renku Bot <renku@datascience.ch>" == plan.creators[0].full_identity
        assert {"key1", "key2"} == set(plan.keywords)

    result = runner.invoke(cli, ["graph", "export", "--format", "json-ld", "--strict"])
    assert 0 == result.exit_code, format_result_exception(result)


def test_run_with_outside_files(renku_cli, runner, project, with_injection, tmpdir):
    """Test run with files that are outside the project."""

    external_file = tmpdir.join("file_1")
    external_file.write(str(1))

    exit_code, activity = renku_cli("run", "--name", "run-1", "cp", str(external_file), "file_1")

    assert 0 == exit_code
    plan = activity.association.plan
    assert "run-1" == plan.name

    with with_injection():
        plan_gateway = PlanGateway()
        plan = cast(Plan, plan_gateway.get_by_id(plan.id))
        assert "run-1" == plan.name
        assert 1 == len(plan.parameters)
        assert 1 == len(plan.outputs)
        assert 0 == len(plan.inputs)
        assert plan.parameters[0].default_value == str(external_file)

    result = runner.invoke(cli, ["graph", "export", "--format", "json-ld", "--strict"])
    assert 0 == result.exit_code, format_result_exception(result)


@pytest.mark.parametrize(
    "command, name",
    [
        (["echo", "-n", "some value"], "echo--n-some_value-"),
        (["echo", "-n", "some long value"], "echo--n-some_long_v-"),
    ],
)
def test_generated_run_name(runner, project, command, name, with_injection):
    """Test generated run name."""
    result = runner.invoke(cli, ["run", "--no-output"] + command)

    assert 0 == result.exit_code, format_result_exception(result)
    with with_injection():
        plan_gateway = PlanGateway()
        plan = plan_gateway.get_all_plans()[0]
        assert name == plan.name[:-5]


def test_run_creator(runner, project, with_injection):
    """Test generated run name."""
    result = runner.invoke(
        cli,
        [
            "run",
            "--no-output",
            "--creator",
            "John Doe <john.doe@example.com>",
            "--creator",
            "Jane Doe <jane.doe@example.com>",
            "echo",
            "-n",
            "value",
        ],
    )

    assert 0 == result.exit_code, format_result_exception(result)
    with with_injection():
        plan_gateway = PlanGateway()
        plan = plan_gateway.get_all_plans()[0]
        assert plan
        assert 2 == len(plan.creators)
        names = [c.full_identity for c in plan.creators]
        assert "John Doe <john.doe@example.com>" in names
        assert "Jane Doe <jane.doe@example.com>" in names


def test_run_invalid_name(runner, project):
    """Test run with invalid name."""
    result = runner.invoke(cli, ["run", "--name", "invalid name", "touch", "foo"])

    assert 2 == result.exit_code
    assert not (project.path / "foo").exists()
    assert "Invalid name: 'invalid name' (Hint: 'invalid_name' is valid)." in result.output


def test_run_argument_parameters(runner, project, with_injection):
    """Test names and values of workflow/provenance arguments and parameters."""
    result = runner.invoke(
        cli,
        [
            "run",
            "--input",
            "Dockerfile",
            "--output",
            "README.md",
            "echo",
            "-n",
            "some message",
            "--template",
            "requirements.txt",
            "--delta",
            "42",
        ],
    )

    assert 0 == result.exit_code, format_result_exception(result)
    with with_injection():
        plan_gateway = PlanGateway()
        plans = plan_gateway.get_all_plans()
        assert 1 == len(plans)
        plan = plans[0]

        assert 2 == len(plan.inputs)
        plan.inputs.sort(key=lambda i: i.name)
        assert plan.inputs[0].name.startswith("input-")
        assert "template-2" == plan.inputs[1].name

        assert 1 == len(plan.outputs)
        assert plan.outputs[0].name.startswith("output-")

        assert 2 == len(plan.parameters)
        plan.parameters.sort(key=lambda i: i.name)
        assert "delta-3" == plan.parameters[0].name
        assert "n-1" == plan.parameters[1].name

        activity_gateway = ActivityGateway()
        activities = activity_gateway.get_all_activities()
        assert 1 == len(activities)
        activity = activities[0]

        assert 2 == len(activity.usages)
        activity.usages.sort(key=lambda e: e.entity.path)
        assert "Dockerfile" == activity.usages[0].entity.path
        assert "requirements.txt" == activity.usages[1].entity.path

        assert 5 == len(activity.parameters)
        parameters_values = {p.value for p in activity.parameters}
        assert {"42", "Dockerfile", "README.md", "requirements.txt", "some message"} == parameters_values

    result = runner.invoke(cli, ["graph", "export", "--format", "jsonld", "--strict"])

    assert 0 == result.exit_code, format_result_exception(result)


def test_run_non_existing_command(runner, project):
    """Test run with a non-existing command."""
    result = runner.invoke(cli, ["run", "non-existing_command"])

    assert 2 == result.exit_code, format_result_exception(result)
    assert "Cannot execute command 'non-existing_command'" in result.output


def test_run_prints_plan(runner, project):
    """Test run shows the generated plan with --verbose."""
    result = runner.invoke(cli, ["run", "--verbose", "--name", "echo-command", "--no-output", "echo", "data"])

    assert 0 == result.exit_code, format_result_exception(result)
    assert "Name: echo-command" in result.stderr
    assert "Name:" not in result.stdout


def test_run_prints_plan_when_stdout_redirected(runner, project):
    """Test run shows the generated plan in stderr if stdout is redirected to a file."""
    result = runner.invoke(cli, ["run", "--verbose", "--name", "echo-command", "echo", "data"], stdout="output")

    assert 0 == result.exit_code, format_result_exception(result)
    assert "Name: echo-command" in result.stderr
    assert "Name:" not in result.stdout
    assert "Name:" not in (project.path / "output").read_text()


def test_run_prints_plan_when_stderr_redirected(runner, project):
    """Test run shows the generated plan in stdout if stderr is redirected to a file."""
    result = runner.invoke(cli, ["run", "--verbose", "--name", "echo-command", "echo", "data"], stderr="output")

    assert 0 == result.exit_code, format_result_exception(result)
    assert "Name: echo-command" in (project.path / "output").read_text()
    assert "Name:" not in result.output
