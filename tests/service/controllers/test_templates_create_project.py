#
# Copyright 2020-2023 -Swiss Data Science Center (SDSC)
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
"""Renku service templates create project controller tests."""
import pytest
from marshmallow import ValidationError

from renku.core.util.os import normalize_to_ascii
from renku.version import is_release


def test_template_create_project_ctrl(ctrl_init, svc_client_templates_creation, mocker):
    """Test template create project controller."""
    from renku.ui.service.controllers.templates_create_project import TemplatesCreateProjectCtrl

    cache, user_data = ctrl_init
    _, _, payload, _ = svc_client_templates_creation

    ctrl = TemplatesCreateProjectCtrl(cache, user_data, payload)
    ctrl_mock = mocker.patch.object(ctrl, "new_project_push", return_value=None)
    response = ctrl.to_response()

    # Check response.
    assert {"result"} == response.json.keys()
    assert {"project_id", "url", "namespace", "name", "slug"} == response.json["result"].keys()

    # Check ctrl_mock.
    assert ctrl_mock.call_count == 1
    assert response.json["result"]["slug"] == ctrl_mock.call_args[0][0].parent.name

    # Ctrl state.
    expected_context = {
        "timestamp",
        "owner",
        "project_namespace",
        "token",
        "email",
        "project_repository",
        "url",
        "identifier",
        "parameters",
        "project_name",
        "name",
        "slug",
        "project_description",
        "new_project_url",
        "fullname",
        "project_slug",
        "git_url",
        "project_name_stripped",
        "depth",
        "branch",
        "new_project_url_with_auth",
        "url_with_auth",
    }
    assert expected_context.issubset(set(ctrl.context.keys()))

    received_metadata = ctrl.default_metadata
    expected_metadata = {
        "__template_source__",
        "__template_ref__",
        "__template_id__",
        "__namespace__",
        "__repository__",
        "__sanitized_project_name__",
        "__project_slug__",
        "__project_description__",
    }
    if is_release():
        expected_metadata.add("__renku_version__")
    assert expected_metadata == set(received_metadata.keys())
    assert payload["url"] == received_metadata["__template_source__"]
    assert payload["branch"] == received_metadata["__template_ref__"]
    assert payload["identifier"] == received_metadata["__template_id__"]
    assert payload["project_namespace"] == received_metadata["__namespace__"]
    assert payload["project_repository"] == received_metadata["__repository__"]

    assert ctrl.template_version

    project_name = normalize_to_ascii(payload["project_name"])
    assert project_name == received_metadata["__sanitized_project_name__"]
    assert f"{payload['project_namespace']}/{project_name}" == received_metadata["__project_slug__"]


@pytest.mark.parametrize(
    "project_name,expected_name",
    [
        ("Test   renku-core   /é", "test-renku-core"),
        ("Test renku-core é", "test-renku-core"),
        ("Test é renku-core ", "test-renku-core"),
        ("é Test é renku-core ", "test-renku-core"),
        ("Test/renku-core", "test-renku-core"),
        ("Test 😁", "test"),
        ("invalid wörd", "invalid-w-rd"),
        ("invalid wörd and another invalid wórd", "invalid-w-rd-and-another-invalid-w-rd"),
        ("João", "jo-o"),
        ("'My Input String", "my-input-string"),
        ("My Input String", "my-input-string"),
        (" a new project ", "a-new-project"),
        ("test!_pro-ject~", "test-pro-ject"),
        ("test!!!!_pro-ject~", "test-pro-ject"),
        ("Test:-)", "test"),
        ("-Test:-)-", "test"),
        ("test----aua", "test-aua"),
        ("test --üäüaua", "test-aua"),
        ("---- test --üäüaua ----", "test-aua"),
        ("---- test --üäü", "test"),
        ("Caffè", "caff"),
        ("my.repo", "my-repo"),
        ("my......repo", "my-repo"),
        ("my_repo", "my-repo"),
        ("my_______repo", "my-repo"),
        ("-.my___repo.", "my-repo"),
        (".my___-...repository..", "my-repository"),
        ("-.-my-repo.", "my-repo"),
    ],
)
def test_project_name_handler(project_name, expected_name, ctrl_init, svc_client_templates_creation, mocker):
    """Test template create project controller correct set of project name."""
    from renku.ui.service.controllers.templates_create_project import TemplatesCreateProjectCtrl

    cache, user_data = ctrl_init
    _, _, payload, _ = svc_client_templates_creation
    payload["project_name"] = project_name

    ctrl = TemplatesCreateProjectCtrl(cache, user_data, payload)
    mocker.patch.object(ctrl, "new_project_push", return_value=None)
    response = ctrl.to_response()

    # Check response.
    assert {"result"} == response.json.keys()
    assert {"project_id", "url", "namespace", "name", "slug"} == response.json["result"].keys()
    assert expected_name == response.json["result"]["slug"]


@pytest.mark.parametrize("project_name", ["здрасти", "---- --üäü ----", "-.-", "...", "----", "~.---", "`~~"])
def test_except_project_name_handler(project_name, ctrl_init, svc_client_templates_creation, mocker):
    """Test template create project controller exception raised."""
    from renku.ui.service.controllers.templates_create_project import TemplatesCreateProjectCtrl

    cache, user_data = ctrl_init
    _, _, payload, _ = svc_client_templates_creation
    payload["project_name"] = project_name

    with pytest.raises(ValidationError) as exc_info:
        TemplatesCreateProjectCtrl(cache, user_data, payload)

    assert "Project name contains only unsupported characters" in str(exc_info.value)


def test_template_create_project_with_custom_cli_ctrl(
    ctrl_init, svc_cache_dir, svc_client_templates_creation, mocker, monkeypatch
):
    """Test template create project controller."""
    from renku.ui.service.cache.models.project import NO_BRANCH_FOLDER

    monkeypatch.setenv("RENKU_PROJECT_DEFAULT_CLI_VERSION", "9.9.9rc9")
    from renku.ui.service.controllers.templates_create_project import TemplatesCreateProjectCtrl

    cache, user_data = ctrl_init
    _, _, payload, _ = svc_client_templates_creation

    ctrl = TemplatesCreateProjectCtrl(cache, user_data, payload)
    mocker.patch.object(ctrl, "new_project_push", return_value=None)
    response = ctrl.to_response()

    # Check response.
    assert {"result"} == response.json.keys()
    assert {"project_id", "url", "namespace", "name", "slug"} == response.json["result"].keys()

    cache_dir, _ = svc_cache_dir

    project_path = (
        cache_dir
        / user_data["user_id"]
        / response.json["result"]["namespace"]
        / response.json["result"]["slug"]
        / NO_BRANCH_FOLDER
    )

    with open(project_path / "Dockerfile") as f:
        assert "ARG RENKU_VERSION=9.9.9rc9" in f.read()
