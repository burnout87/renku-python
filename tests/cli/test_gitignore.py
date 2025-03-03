#
# Copyright 2019-2023 - Swiss Data Science Center (SDSC)
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
"""Test compliance with ``.gitignore`` file."""

from renku.ui.cli import cli
from tests.utils import format_result_exception


def test_dataset_add(tmpdir, runner, project, subdirectory):
    """Test importing data into a dataset."""
    # create a dataset
    result = runner.invoke(cli, ["dataset", "create", "testing"])
    assert 0 == result.exit_code, format_result_exception(result)
    assert "OK" in result.output

    # Using an extension from gitignore.default defined as *.spec
    ignored_file = tmpdir.join("my.spec")
    ignored_file.write("My Specification")

    # The file should be ignored and command fail
    result = runner.invoke(cli, ["dataset", "add", "--copy", "testing", ignored_file.strpath], catch_exceptions=False)

    assert 1 == result.exit_code

    project.repository.reset(hard=True)
    project.repository.clean()

    # Use the --force ;)
    result = runner.invoke(cli, ["dataset", "add", "--copy", "testing", "--force", ignored_file.strpath])
    assert 0 == result.exit_code, format_result_exception(result)
