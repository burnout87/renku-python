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
"""Test plugins for the ``run`` command."""

from renku.core.plugin import pluginmanager as pluginmanager
from renku.ui.cli import cli
from tests.utils import format_result_exception


def test_renku_pre_run_hook(monkeypatch, dummy_pre_run_plugin_hook, runner, project):
    """Tests that the renku run plugin hook on ``CmdLineTool`` is called."""
    pm = pluginmanager.get_plugin_manager()
    pm.register(dummy_pre_run_plugin_hook)

    with monkeypatch.context() as m:
        m.setattr(pluginmanager, "get_plugin_manager", lambda: pm)
        cmd = ["echo", "test"]

        result = runner.invoke(cli, ["run", "--no-output"] + cmd)

        assert 0 == result.exit_code, format_result_exception(result)
        assert 1 == dummy_pre_run_plugin_hook.called


def test_renku_activity_hook(monkeypatch, dummy_activity_plugin_hook, runner, project):
    """Tests that the renku run plugin hook on ``Activity`` is called."""
    pm = pluginmanager.get_plugin_manager()
    pm.register(dummy_activity_plugin_hook)

    with monkeypatch.context() as m:
        m.setattr(pluginmanager, "get_plugin_manager", lambda: pm)
        cmd = ["echo", "test"]
        result = runner.invoke(cli, ["run", "--no-output"] + cmd)
        assert 0 == result.exit_code, format_result_exception(result)

        # check for dummy plugin
        result = runner.invoke(cli, ["graph", "export", "--format", "json-ld"])
        assert "Dummy Activity Hook" in result.output
        assert "dummy Activity hook body" in result.output


def test_renku_plan_hook(monkeypatch, dummy_plan_plugin_hook, runner, project):
    """Tests that the renku run plugin hook on ``Activity`` is called."""
    pm = pluginmanager.get_plugin_manager()
    pm.register(dummy_plan_plugin_hook)

    with monkeypatch.context() as m:
        m.setattr(pluginmanager, "get_plugin_manager", lambda: pm)
        cmd = ["echo", "test"]
        result = runner.invoke(cli, ["run", "--no-output"] + cmd)
        assert 0 == result.exit_code, format_result_exception(result)

        # check for dummy plugin
        result = runner.invoke(cli, ["graph", "export", "--format", "json-ld"])
        assert "Dummy Plan Hook" in result.output
        assert "dummy Plan hook body" in result.output
