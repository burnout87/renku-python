#
# Copyright 2018-2023- Swiss Data Science Center (SDSC)
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
"""Test Git ranges used by various commands."""

from renku.ui.cli import cli
from tests.utils import format_result_exception


def test_limit_log(runner, project, run, subdirectory):
    """Test naming of CWL tools and workflows."""
    cwd = project.path
    data = cwd / "data.txt"
    output = cwd / "output.txt"

    assert 0 == run(args=("run", "echo", "unique input string"), stdout=data)
    assert data.exists()

    assert 0 == run(args=("run", "wc", "-c"), stdin=data, stdout=output)
    assert output.exists()

    cmd = ["graph", "export", "--revision", "HEAD^.."]
    result = runner.invoke(cli, cmd)
    assert 0 == result.exit_code, format_result_exception(result)
    assert "unique input string" not in result.output
    assert output.name in result.output

    cmd = ["graph", "export", "--revision", "HEAD^"]
    result = runner.invoke(cli, cmd)
    assert 0 == result.exit_code, format_result_exception(result)
    assert "unique input string" in result.output
    assert output.name not in result.output
