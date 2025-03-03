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
"""Test ``gc`` command."""

from renku.core.constant import CACHE, RENKU_HOME, RENKU_TMP
from renku.ui.cli import cli
from tests.utils import format_result_exception


def test_gc(runner, project):
    """Test clean caches and temporary files."""
    # NOTE: Mock caches
    tmp = project.path / RENKU_HOME / RENKU_TMP
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "temp-file").touch()
    cache = project.path / RENKU_HOME / CACHE
    cache.mkdir(parents=True, exist_ok=True)
    (tmp / "cache").touch()

    (project.path / "tracked").write_text("tracked file")
    project.repository.add("tracked")

    (project.path / "untracked").write_text("untracked file")

    commit_sha_before = project.repository.head.commit.hexsha

    result = runner.invoke(cli, ["gc"])

    commit_sha_after = project.repository.head.commit.hexsha

    assert 0 == result.exit_code, format_result_exception(result)
    assert not tmp.exists()
    assert not cache.exists()
    assert "tracked" in [f.a_path for f in project.repository.staged_changes]
    assert "untracked" in project.repository.untracked_files
    assert commit_sha_after == commit_sha_before
